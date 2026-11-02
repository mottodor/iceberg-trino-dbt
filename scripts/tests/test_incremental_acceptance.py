"""Independent incremental oracles and predicate counterexample regressions."""
import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import run_incremental_acceptance as target
from run_acceptance import AcceptanceError


class IncrementalTests(unittest.TestCase):
    def test_initial_and_late_event_oracle(self):
        target.assert_rows(target.expected_rows(initial=True),initial=True)
        target.assert_rows(target.expected_rows())
        self.assertEqual(len(target.expected_rows()),7)
        self.assertEqual(sum(row[3] for row in target.expected_rows()),215)
        self.assertEqual(target.expected_rows()[5][0],'E5')

    def test_grain_null_timestamp_and_amount_mutations_rejected(self):
        rows=target.expected_rows()
        variants=[rows[:-1],rows+[rows[1]],[rows[0],rows[0],*rows[2:]]]
        for column,value in [(1,None),(1,'2025-01-01T00:00:00.000001Z'),(2,'2025-01-05T10:00:00'),(3,True),(3,10.0),(3,999)]:
            changed=copy.deepcopy(rows);changed[1][column]=value;variants.append(changed)
        for value in variants:
            with self.subTest(value=value),self.assertRaises(AcceptanceError):target.assert_rows(value)

    def test_predicate_counterexamples_are_specific_not_arbitrary_failures(self):
        rows=target.expected_rows()
        source=[row for row in rows if row[0]!='E5']
        destination=sorted(rows+[rows[1],rows[2]],key=lambda row:row[0])
        target.assert_counterexamples(source,destination)
        for wrong_source,wrong_target in [(rows,destination),(source,rows),(rows[:-1],destination),(source,destination[:-1])]:
            with self.assertRaises(AcceptanceError):target.assert_counterexamples(wrong_source,wrong_target)

    def test_actual_merge_and_source_predicate_must_both_be_present(self):
        merge="merge into target as DBT_INTERNAL_DEST using source as DBT_INTERNAL_SOURCE on DBT_INTERNAL_SOURCE.event_id = DBT_INTERNAL_DEST.event_id and DBT_INTERNAL_DEST.received_at >= TIMESTAMP '"+target.CUTOFF+"' when matched then update set amount_units=1 when not matched then insert values (1)"
        source="select * from ranked where canonical_rank = 1 and received_at >= TIMESTAMP '"+target.CUTOFF+"'"
        target.validate_predicates(merge,source)
        for left,right in [(merge.replace('DBT_INTERNAL_DEST.received_at','DBT_INTERNAL_DEST.event_at'),source),(merge,source.replace('received_at >=','event_at >=')),(merge.replace('event_id =','other_id ='),source),('select 1',source)]:
            with self.assertRaises(AcceptanceError):target.validate_predicates(left,right)
