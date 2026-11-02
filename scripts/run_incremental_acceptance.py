#!/usr/bin/env python3
"""Exercise real dbt incremental source/target predicates in an isolated schema."""
from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from learning_exercise import LearningExercise, verify_snapshot
from run_acceptance import CATALOG, ROOT, DEFAULT_EVIDENCE_ROOT, AcceptanceError
from run_time_travel_acceptance import require

CUTOFF = '2024-12-29 00:00:00 UTC'
NARROW = '2025-01-03 00:00:00 UTC'
BASE = [
    ['E0','2024-12-01T00:00:00Z','2024-12-01T00:00:00Z',5],
    *[[f'E{i}',f'2025-01-0{i}T00:00:00Z',f'2025-01-0{i}T00:00:00Z',i*10] for i in range(1,5)],
]
LATE = [['E5','2025-01-01T12:00:00Z','2025-01-05T10:00:00Z',50], ['E6','2025-01-05T10:01:00Z','2025-01-05T10:01:00Z',60]]
MODELS = {'events_safe','events_full','events_narrow_source','events_narrow_target'}
STATES = ('initial','after_incremental','replay','full_refresh','after_refresh','final')


def normalize(rows):
    result=[]
    for row in rows:
        require(isinstance(row,list) and len(row)==4 and type(row[0]) is str and type(row[3]) is int,'incremental row type mismatch')
        times=[]
        for value in row[1:3]:
            require(type(value) is str,'timestamp/SQL NULL mismatch')
            instant=datetime.fromisoformat(value.replace('Z','+00:00'))
            require(instant.tzinfo is not None,'timestamp timezone missing')
            times.append(instant.astimezone(timezone.utc).isoformat(timespec='microseconds'))
        result.append([row[0],*times,row[3]])
    return result


def expected_rows(initial=False):
    return normalize([row.copy() for row in BASE + ([] if initial else LATE)])


def assert_rows(rows, *, initial=False):
    require(normalize(rows)==expected_rows(initial),'incremental rows/grain/late-event oracle mismatch')


def assert_counterexamples(source_rows,target_rows):
    expected=expected_rows()
    source=normalize(source_rows);target=normalize(target_rows)
    require(source==[row for row in expected if row[0]!='E5'],'narrow source did not isolate missing late event E5')
    wanted=sorted(expected+[expected[1],expected[2]],key=lambda row:row[0])
    require(target==wanted and len(target)==9 and len({row[0] for row in target})==7,'narrow target did not duplicate E1/E2')


def validate_predicates(merge,source):
    clean=lambda value:re.sub(r'\s+',' ',value.replace('"','').lower())
    merge,source=clean(merge),clean(source)
    require('merge into' in merge and 'when matched then update' in merge and 'when not matched then insert' in merge,'actual dbt MERGE missing')
    require('dbt_internal_source.event_id = dbt_internal_dest.event_id' in merge,'MERGE unique key missing')
    require("dbt_internal_dest.received_at >= timestamp '"+CUTOFF.lower()+"'" in merge,'safe target predicate missing')
    require("received_at >= timestamp '"+CUTOFF.lower()+"'" in source and 'canonical_rank = 1' in source,'safe incoming predicate/dedup missing')


def required_evidence():
    paths={'safe/comparison.json','counterexamples/comparison.json','idempotence/comparison.json','predicates/comparison.json','runtime/end_to_end.json','sql/actual_merge.sql','sql/actual_source.sql','sql/bad_source.sql','sql/bad_target_merge.sql','plans/source_io.csv','plans/target_io.csv','plans/source_analyze.txt','plans/target_analyze.txt','counterexamples/source.json','counterexamples/target.json','safe/full_reference.json'}
    for name in STATES:
        for file in ('bundle.json','metadata.json','catalog_metadata.json','columns.csv','snapshots.csv','history.csv','files.csv','sha256.txt','rows.csv','rows.json'):
            paths.add(f'states/{name}/{file}')
    for step in ('initial','incremental','counterexamples','replay','full_refresh','after_refresh'):
        paths.add(f'dbt/{step}/target/run_results.json')
    return paths


def verify_incremental(root):
    read=lambda name:json.loads((root/name).read_text())
    states={name:verify_snapshot(root,name) for name in STATES}
    for name,state in states.items():assert_rows(state['rows'],initial=name=='initial')
    reference=read('safe/full_reference.json');assert_rows(reference)
    for name in STATES[1:]:require(normalize(states[name]['rows'])==normalize(reference),'saved incremental/full-rebuild mismatch')
    assert_counterexamples(read('counterexamples/source.json'),read('counterexamples/target.json'))
    validate_predicates((root/'sql/actual_merge.sql').read_text(),(root/'sql/actual_source.sql').read_text())
    for step in ('initial','incremental','counterexamples','replay','full_refresh','after_refresh'):
        results=read(f'dbt/{step}/target/run_results.json')['results']
        wanted=MODELS if step=='initial' else ({'events_narrow_source','events_narrow_target'} if step=='counterexamples' else ({'events_safe','events_full'} if step in {'incremental','replay'} else {'events_safe'}))
        models=[row for row in results if row['unique_id'].startswith('model.')]
        require({row['unique_id'].split('.')[-1] for row in models}==wanted and len(models)==len(wanted),'saved model selection mismatch')
        require(all(row['status'] in {'success','pass'} for row in results),'saved dbt failure/skip')
        if step not in {'initial','counterexamples'}:
            require(len([row for row in results if row['unique_id'].startswith('test.')])==3*len(wanted),'saved dbt tests missing')
    counts=read('predicates/comparison.json')
    require(counts['eligible_source_ids']==6 and counts['eligible_target_rows']==6 and counts['total_ids']==7,'saved predicate selection mismatch')


class IncrementalRun(LearningExercise):
    exercise='incremental'
    table_name='events_safe'
    ac_numbers=tuple(range(41,46))

    def rows_query(self,table=None):
        return f"SELECT json_format(CAST(ARRAY[CAST(event_id AS JSON), CAST(to_iso8601(event_at) AS JSON), CAST(to_iso8601(received_at) AS JSON), CAST(amount_units AS JSON)] AS JSON)) AS row_json FROM {self.relation(table or 'events_safe')} ORDER BY event_id"

    def read_table(self,name,table):
        return self.rows(name,self.rows_query(table))

    def capture_state(self,name):
        return self.snapshot(name,self.rows_query())

    def load_batch(self,batch,name):
        path=ROOT/'dbt/exercises/incremental/fixtures/events.csv'
        with path.open() as handle:rows=list(csv.DictReader(handle))
        actual=[[int(row['batch_number']),row['event_id'],row['event_at'],row['received_at'],int(row['amount_units'])] for row in rows]
        expected=[[1,*row] for row in BASE]+[[2,*row] for row in LATE]+[[2,*BASE[1]]]
        require(actual==expected,'incremental fixture contract changed')
        values=[]
        for number,event,event_at,received,amount in actual:
            if number==batch:
                values.append(f"('{event}',from_iso8601_timestamp('{event_at}'),from_iso8601_timestamp('{received}'),BIGINT '{amount}',INTEGER '{number}')")
        require(bool(values),'empty fixture batch')
        self.sql(f'input/{name}',f"INSERT INTO {self.relation('events_input')} VALUES "+', '.join(values))

    def dbt_step(self,name,args,models):
        base=f'dbt/{name}'
        self.dbt(self.schema,['--debug',*args,'--project-dir','exercises/incremental','--profiles-dir','/usr/app/dbt'],base,f'{base}/dbt.log')
        results=json.loads((self.evidence_dir/base/'target/run_results.json').read_text())['results']
        executed=[row for row in results if row['unique_id'].startswith('model.')]
        require(len(executed)==len(models) and {row['unique_id'].split('.')[-1] for row in executed}==set(models),'dbt selected wrong exercise models')
        require(all(row['status'] in {'success','pass'} for row in results),'dbt exercise failed/skipped nodes')
        if args[0]=='build':require(len(results)==len(models)*4,'dbt exercise tests missing')

    def copy_sql(self,step,model,folder,name):
        path=self.evidence_dir/f'dbt/{step}/target/{folder}/incremental_exercise/models/{model}.sql'
        require(path.is_file(),'actual executed/compiled model SQL missing')
        value=path.read_text();self.write_text(f'sql/{name}.sql',value)
        return value

    def stage_initial(self):
        self.current_ac='AC-042'
        self.create_schema(self.schema,'input/schema')
        self.sql('input/create',f"CREATE TABLE {self.relation('events_input')} (event_id VARCHAR,event_at TIMESTAMP(6) WITH TIME ZONE,received_at TIMESTAMP(6) WITH TIME ZONE,amount_units BIGINT,batch_number INTEGER) WITH (format='PARQUET',format_version=2)")
        self.load_batch(1,'batch_1')
        self.dbt_step('initial',['run'],MODELS)
        for model in MODELS:assert_rows(self.read_table(f'initial/{model}',model),initial=True)
        state=self.capture_state('initial')
        require([row[:2] for row in state['columns'][1:]]==[['event_id','varchar'],['event_at','timestamp(6) with time zone'],['received_at','timestamp(6) with time zone'],['amount_units','bigint']],'incremental table types mismatch')

    def stage_incremental(self):
        self.load_batch(2,'batch_2')
        self.dbt_step('incremental',['build','--select','events_safe','events_full'],{'events_safe','events_full'})
        safe=self.read_table('safe/rows','events_safe');full=self.read_table('safe/full_reference','events_full')
        assert_rows(safe);assert_rows(full)
        require(normalize(safe)==normalize(full),'incremental/full-rebuild rows differ')
        merge=self.copy_sql('incremental','events_safe','run','actual_merge')
        source=self.copy_sql('incremental','events_safe','compiled','actual_source')
        validate_predicates(merge,source)
        self.capture_state('after_incremental')
        self.write_json('safe/comparison.json',{'rows':7,'late_event_E5_present':True,'old_E0_preserved':True,'independent_full_rebuild_matches':True})

    def stage_counterexamples(self):
        self.current_ac='AC-043'
        self.dbt_step('counterexamples',['run','--select','events_narrow_source','events_narrow_target'],{'events_narrow_source','events_narrow_target'})
        source=self.read_table('counterexamples/source','events_narrow_source');target=self.read_table('counterexamples/target','events_narrow_target')
        assert_counterexamples(source,target)
        self.copy_sql('counterexamples','events_narrow_source','compiled','bad_source')
        self.copy_sql('counterexamples','events_narrow_target','run','bad_target_merge')
        self.write_json('counterexamples/comparison.json',{'narrow_source_rows':6,'missing_id':'E5','narrow_target_rows':9,'distinct_ids':7,'duplicate_ids':['E1','E2']})
        self.ac_results['AC-043']='PASS'

    def stage_idempotence(self):
        self.current_ac='AC-042'
        self.load_batch(2,'batch_2_replay')
        self.dbt_step('replay',['build','--select','events_safe','events_full'],{'events_safe','events_full'})
        for model in ('events_safe','events_full'):assert_rows(self.read_table(f'replay/{model}',model))
        self.capture_state('replay')
        self.dbt_step('full_refresh',['build','--full-refresh','--select','events_safe'],{'events_safe'})
        self.capture_state('full_refresh')
        self.dbt_step('after_refresh',['build','--select','events_safe'],{'events_safe'})
        self.capture_state('after_refresh')
        assert_rows(self.read_table('idempotence/final','events_safe'))
        self.write_json('idempotence/comparison.json',{'replay_rows':7,'full_refresh_rows':7,'after_refresh_incremental_rows':7,'unique_ids':7})
        self.ac_results['AC-042']='PASS'

    def stage_plans(self):
        self.current_ac='AC-044'
        for label,table in (('source','events_input'),('target','events_safe')):
            query=f"SELECT event_id FROM {self.relation(table)} WHERE received_at >= TIMESTAMP '{CUTOFF}'"
            raw=self.query_csv(f'plans/{label}_io.csv',f'EXPLAIN (TYPE IO) {query}')
            require(len(raw)==2,'missing IO plan')
            plan=json.loads(raw[1][0])
            require('received_at' in json.dumps(plan),'IO predicate evidence missing')
            self.write_json(f'plans/{label}_io.json',plan)
            self.capture(['docker','compose','exec','-T','trino','trino','--execute','EXPLAIN ANALYZE '+query],f'plans/{label}_analyze.txt')
        counts=self.query_csv('predicates/eligible.csv',f"SELECT (SELECT count(DISTINCT event_id) FROM {self.relation('events_input')} WHERE received_at >= TIMESTAMP '{CUTOFF}') AS source_ids,(SELECT count(*) FROM {self.table} WHERE received_at >= TIMESTAMP '{CUTOFF}') AS target_rows,(SELECT count(*) FROM {self.table}) AS all_ids")
        require(counts[1:]==[['6','6','7']],'predicate candidate counts mismatch')
        self.write_json('predicates/comparison.json',{'cutoff':CUTOFF,'lookback_days':7,'processing_at':'2025-01-05 12:00:00 UTC','cutoff_rule':'processing-day start minus seven days','eligible_source_ids':6,'eligible_target_rows':6,'total_ids':7,'physical_reduction_required':False})
        self.ac_results['AC-044']='PASS'

    def stage_final(self):
        self.capture_state('final')
        assert_rows(self.read_table('final/safe','events_safe'))
        tables=self.query_csv('runtime/catalog_tables.csv',f"SELECT table_name FROM {CATALOG}.information_schema.tables WHERE table_schema='{self.schema}' ORDER BY table_name")
        require({row[0] for row in tables[1:]}==MODELS|{'events_input'} and len(tables)==6,'incremental registrations mismatch')
        self.write_json('runtime/end_to_end.json',{'table_count':5,'final_safe_rows':7,'raw_rows_expected':11,'actual_dbt_merge':True})

    def workflow(self):
        for stage in (self.stage_initial,self.stage_incremental,self.stage_counterexamples,self.stage_idempotence,self.stage_plans,self.stage_final):
            print('Incremental: '+stage.__name__,flush=True);stage()

    def verify_behavior(self,root):verify_incremental(root)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run-id',required=True);args=parser.parse_args()
    try:
        run=IncrementalRun(args.run_id,DEFAULT_EVIDENCE_ROOT/args.run_id)
        run.run(run.workflow,required=required_evidence())
    except (AcceptanceError,OSError) as error:
        print('Incremental failed: '+str(error));return 1
    print('Incremental acceptance PASS: AC-041–AC-045');return 0


if __name__=='__main__':raise SystemExit(main())
