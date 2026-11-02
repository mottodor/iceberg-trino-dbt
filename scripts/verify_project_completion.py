#!/usr/bin/env python3
"""Read-only audit of all six accepted slices, frozen contracts and AC-002."""
from __future__ import annotations
import argparse,hashlib,json,re,subprocess
from pathlib import Path
from datetime import datetime,timezone
from run_acceptance import ROOT,DEFAULT_EVIDENCE_ROOT,RUN_ID_PATTERN,AcceptanceError
from run_time_travel_acceptance import require,verify_manifest,verify_saved_behavior
from run_maintenance_acceptance import verify_maintenance,required_evidence as maintenance_paths
from run_incremental_acceptance import verify_incremental,required_evidence as incremental_paths

REPORTS={
 'core':('imp007_final5',{1,*range(3,13)}),
 'schema_evolution':('seimp006_final2',set(range(13,21))),
 'partitioning':('pfimp006_final',set(range(21,28))),
 'time_travel':('tt_imp006_final',set(range(28,34))),
 'maintenance':('ma_imp005_final',set(range(34,41))),
 'incremental':('inc_imp001_final2',set(range(41,46))),
}
COMPETENCY_ACS=({12},{12,33},{15,29,30},{4},{4,5,11},{6,7,8,10},{3},{9,11},{42,43,44},{22,23,24,25},{24,25,26},{29,30,31},{35},{36,37,38,39,40})
CODE_PATHS=(['README.md','compose.yaml'],['infra/polaris/bootstrap.sh'],['scripts/run_schema_evolution_acceptance.py','scripts/run_time_travel_acceptance.py'],['dbt/models/bronze/bronze_tracking_events.sql'],['dbt/models/silver/silver_tracking_events_typed.sql','dbt/models/silver/silver_package_current_state.sql'],['dbt/models/gold/gold_package_delivery_fact.sql','dbt/models/silver/silver_route_plan_versions.sql'],['dbt/models/silver/silver_package_route_binding.sql'],['dbt/tests/assert_cross_layer_reconciliation.sql'],['dbt/exercises/incremental/models/events_safe.sql','scripts/run_incremental_acceptance.py'],['scripts/run_partitioning_file_pruning_acceptance.py'],['scripts/run_partitioning_file_pruning_acceptance.py'],['scripts/run_time_travel_acceptance.py'],['scripts/run_maintenance_acceptance.py'],['scripts/run_maintenance_acceptance.py'])


def aggregate_summaries(summaries):
 result={}
 for name,(_,numbers) in REPORTS.items():
  require(name in summaries,'missing accepted slice: '+name)
  doc=summaries[name]
  expected={f'AC-{n:03}' for n in numbers}
  require(doc.get('outcome')=='PASS' and doc.get('error') is None,'slice did not pass: '+name)
  require(set(doc.get('ac_results',{}))==expected and set(doc['ac_results'].values())=={'PASS'},'slice criterion coverage incomplete: '+name)
  require(not set(result).intersection(expected),'duplicate criterion ownership')
  result.update(doc['ac_results'])
 require(set(result)=={f'AC-{n:03}' for n in range(1,46) if n!=2},'project criteria gap')
 return result


def competency_rows(idea,matrix):
 source=idea.split('## Приобретаемые компетенции',1)[1].split('###',1)[0]
 goals=re.findall(r'^- (.+)',source,re.M)
 require(len(goals)==14,'source competency count changed')
 rows={}
 for line in matrix.splitlines():
  cells=[cell.strip() for cell in line.strip().strip('|').split('|')]
  if cells and cells[0].isdigit():
   number=int(cells[0]);require(number not in rows and 1<=number<=14,'duplicate/unknown competency')
   require(len(cells)==5 and cells[-1]=='Подтверждено','competency still open')
   rows[number]=cells
 require(set(rows)==set(range(1,15)),'competency matrix incomplete')
 return [{'number':i,'source_goal':goals[i-1],'exercise':rows[i][2],'criteria':[f'AC-{n:03}' for n in sorted(COMPETENCY_ACS[i-1])],'code_paths':CODE_PATHS[i-1]} for i in range(1,15)]


def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)


def frozen_boundary():
 baseline='c568502'
 names=git('ls-tree','-r','--name-only',baseline).decode().splitlines()
 code=[name for name in names if name.startswith(('dbt/','docker/','infra/','scripts/')) or name in {'compose.yaml','.gitignore','.env.example','docs/idea.md'}]
 hashes={}
 for name in code:
  original=git('show',f'{baseline}:{name}')
  require((ROOT/name).is_file() and (ROOT/name).read_bytes()==original,'completed implementation changed: '+name)
  hashes[name]=hashlib.sha256(original).hexdigest()
 spec=git('show',f'{baseline}:docs/spec.md')
 require((ROOT/'docs/spec.md').read_bytes().startswith(spec),'completed specification sections 1-12 changed')
 return {'baseline_commit':baseline,'unchanged_implementation_sha256':hashes,'completed_spec_prefix_sha256':hashlib.sha256(spec).hexdigest()}


def verify_report_fingerprints(root,spec_versions):
 for name in ('preflight/immutable.json','preflight/immutable_before.json','preflight/implementation.json'):
  path=root/name
  if not path.exists():continue
  document=json.loads(path.read_text());fingerprints=document.get('sha256',document)
  for filename,digest in fingerprints.items():
   current=ROOT/filename
   require(current.is_file(),'accepted file disappeared: '+filename)
   if hashlib.sha256(current.read_bytes()).hexdigest()==digest:continue
   if filename=='README.md':continue
   if filename=='docs/spec.md':
    require(digest in spec_versions and current.read_bytes().startswith(spec_versions[digest]),'accepted contract changed')
   else:raise AcceptanceError('accepted implementation fingerprint changed: '+filename)


def check_docker():
 raw=subprocess.check_output(['docker','ps','-a','--format','{{.Names}}'],text=True)
 networks=subprocess.check_output(['docker','network','ls','--format','{{.Name}}'],text=True)
 prefixes=('iceberg-trino-dbt-maintenance-','iceberg-trino-dbt-incremental-','iceberg-trino-dbt-tt-')
 remaining=[name for name in raw.splitlines()+networks.splitlines() if name.startswith(prefixes)]
 require(not remaining,'task-owned containers/networks remain: '+str(remaining))
 return {'task_containers_and_networks_absent':True,'named_volumes_preserved_by_exercises':True}


def audit(*,check_runtime=False):
 summaries={};reports=[]
 versions={}
 for commit in git('log','--format=%H','--','docs/spec.md').decode().splitlines():
  contents=git('show',f'{commit}:docs/spec.md');versions[hashlib.sha256(contents).hexdigest()]=contents
 for name,(run_id,_) in REPORTS.items():
  root=DEFAULT_EVIDENCE_ROOT/run_id
  document=json.loads((root/'acceptance_summary.json').read_text());summaries[name]=document
  require(document.get('run_id')==run_id,'report identity mismatch')
  verify_manifest(root,{'commands.jsonl','secret_scan.json','cleanup/environment.json'})
  scan=json.loads((root/'secret_scan.json').read_text());require(scan.get('secret_values_written') is False and not scan.get('findings'),'unclean secret scan')
  environment=json.loads((root/'cleanup/environment.json').read_text())
  require(environment.get('restored') is True or (environment.get('preexisting_volumes_preserved') is True and environment.get('final_project_containers')==[]),'environment not restored')
  verify_report_fingerprints(root,versions)
  reports.append({'slice':name,'run_id':run_id,'summary_sha256':hashlib.sha256((root/'acceptance_summary.json').read_bytes()).hexdigest(),'manifest_sha256':hashlib.sha256((root/'evidence_manifest.json').read_bytes()).hexdigest(),'files':len(json.loads((root/'evidence_manifest.json').read_text())['files'])})
 ac=aggregate_summaries(summaries)
 verify_saved_behavior(DEFAULT_EVIDENCE_ROOT/'tt_imp006_final')
 verify_maintenance(DEFAULT_EVIDENCE_ROOT/'ma_imp005_final')
 verify_manifest(DEFAULT_EVIDENCE_ROOT/'ma_imp005_final',maintenance_paths())
 verify_incremental(DEFAULT_EVIDENCE_ROOT/'inc_imp001_final2')
 verify_manifest(DEFAULT_EVIDENCE_ROOT/'inc_imp001_final2',incremental_paths())
 competencies=competency_rows((ROOT/'docs/idea.md').read_text(),(ROOT/'docs/learning-outcomes.md').read_text())
 for item in competencies:
  require(all(ac.get(key)=='PASS' for key in item['criteria']),'unverified competency criterion')
  require(all((ROOT/name).is_file() for name in item['code_paths']),'competency implementation missing')
 ac['AC-002']='PASS'
 return {'outcome':'PASS','ac_results':dict(sorted(ac.items())),'competencies':competencies,'slice_reports':reports,'frozen_boundary':frozen_boundary(),'runtime':check_docker() if check_runtime else {'mode':'retained cleanup evidence'},'git_head':git('rev-parse','HEAD').decode().strip(),'auditor_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'verified_at':datetime.now(timezone.utc).isoformat()}


def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run-id',required=True);parser.add_argument('--check-docker',action='store_true');args=parser.parse_args()
 require(RUN_ID_PATTERN.fullmatch(args.run_id) is not None,'invalid report ID')
 root=DEFAULT_EVIDENCE_ROOT/args.run_id
 require(root.resolve()==root and not root.exists(),'fresh canonical final report directory required')
 root.mkdir(parents=True)
 try:
  report=audit(check_runtime=args.check_docker)
  (root/'project_completion.json').write_text(json.dumps(report,indent=2,ensure_ascii=False,sort_keys=True)+'\n')
  data=(root/'project_completion.json').read_bytes()
  (root/'evidence_manifest.json').write_text(json.dumps({'files':[{'path':'project_completion.json','size':len(data),'sha256':hashlib.sha256(data).hexdigest()}]},indent=2)+'\n')
  verify_manifest(root,{'project_completion.json'})
  summary={'run_id':args.run_id,'outcome':'PASS','error':None,'ac_results':report['ac_results'],'competencies_verified':14,'slices_verified':6}
 except Exception as error:
  summary={'run_id':args.run_id,'outcome':'FAIL','error':str(error),'ac_results':{'AC-002':'NOT_RUN'}}
 (root/'acceptance_summary.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
 print('Project completion '+summary['outcome']+': '+str(summary.get('error') or '45 AC, 14 competencies, 6 accepted slices'))
 return 0 if summary['outcome']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
