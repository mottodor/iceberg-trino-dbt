"""The project cannot pass with a missing slice, criterion or competency."""
import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import verify_project_completion as target
from run_acceptance import AcceptanceError


class CompletionTests(unittest.TestCase):
    def reports(self):
        return {name:{'outcome':'PASS','error':None,'ac_results':{f'AC-{n:03}':'PASS' for n in numbers}} for name,(_,numbers) in target.REPORTS.items()}

    def test_all_slices_and_exact_criterion_sets_required(self):
        reports=self.reports()
        self.assertEqual(len(target.aggregate_summaries(reports)),44)
        variants=[]
        missing=copy.deepcopy(reports);del missing['maintenance'];variants.append(missing)
        missing=copy.deepcopy(reports);del missing['incremental']['ac_results']['AC-044'];variants.append(missing)
        failed=copy.deepcopy(reports);failed['maintenance']['ac_results']['AC-037']='FAIL';variants.append(failed)
        pending=copy.deepcopy(reports);pending['incremental']['outcome']='CHECKPOINT';variants.append(pending)
        cleanup=copy.deepcopy(reports);cleanup['incremental']['error']='cleanup failed';variants.append(cleanup)
        for value in variants:
            with self.subTest(value=value.keys()),self.assertRaises(AcceptanceError):target.aggregate_summaries(value)

    def test_exactly_fourteen_closed_competencies_required(self):
        idea='## Приобретаемые компетенции\n'+''.join(f'- Goal {i}\n' for i in range(1,15))+'### scope\n'
        rows=[f'| {i} | Competency {i} | Exercise | Evidence | Подтверждено |' for i in range(1,15)]
        matrix='\n'.join(rows)
        self.assertEqual(len(target.competency_rows(idea,matrix)),14)
        for value in ('\n'.join(rows[:-1]),matrix.replace('Подтверждено','Открыто',1),matrix+'\n'+rows[0]):
            with self.assertRaises(AcceptanceError):target.competency_rows(idea,value)
