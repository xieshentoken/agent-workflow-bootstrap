"""Tests only the bundled helpers, not an agent or production runtime."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parent.parent

def load(name):
    spec=importlib.util.spec_from_file_location(name, ROOT/'scripts'/(name+'.py'))
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

scaffold=load('scaffold')
checker=load('check_workspace')

class HelperTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.parent=Path(self.tmp.name).resolve()
        self.work=self.parent/'workspace'
    def tearDown(self):
        self.tmp.cleanup()
    def create(self):
        scaffold.scaffold(str(self.work),True)
    def patch(self,rel,edit):
        p=self.work/rel; value=json.loads(p.read_text()); edit(value)
        p.write_text(json.dumps(value),encoding='utf-8')
    def result(self):
        return checker.check_workspace(str(self.work))
    def test_preview_does_not_write(self):
        result=scaffold.scaffold(str(self.work))
        self.assertFalse(self.work.exists()); self.assertFalse(result['created'])
    def test_apply_is_unapproved_template(self):
        self.create(); result=self.result()
        self.assertEqual(result['status'],'PASS')
        self.assertTrue(any('not approved' in w for w in result['warnings']))
    def test_existing_target_refused(self):
        self.create(); p=self.work/'user.txt'; p.write_text('keep')
        with self.assertRaises(ValueError): scaffold.scaffold(str(self.work),True)
        self.assertEqual(p.read_text(),'keep')
    def test_relative_target_refused(self):
        with self.assertRaises(ValueError): scaffold.scaffold('workspace')
    def test_missing_parent_refused(self):
        with self.assertRaises(ValueError): scaffold.scaffold(str(self.parent/'missing'/'work'))
    def test_symlink_parent_refused(self):
        link=self.parent/'linked'; link.symlink_to(self.parent,target_is_directory=True)
        with self.assertRaises(ValueError): scaffold.scaffold(str(link/'workspace'))
    def test_simulate_cannot_external_write(self):
        self.create(); self.patch('control/policy.json',lambda x:x.update(external_actions_enabled=True))
        self.assertEqual(self.result()['status'],'FAIL')
    def test_done_without_evidence_fails(self):
        self.create(); self.patch('tasks/T-DEMO-001/state.json',lambda x:x.update(state='DONE'))
        self.assertEqual(self.result()['status'],'FAIL')
    def test_blocked_requires_resume_information(self):
        self.create(); self.patch('tasks/T-DEMO-001/state.json',lambda x:x.update(state='BLOCKED'))
        self.assertEqual(self.result()['status'],'FAIL')
    def test_verified_requires_evidence(self):
        self.create(); self.patch('control/capabilities.json',lambda x:x['capabilities'][0].update(status='VERIFIED'))
        self.assertEqual(self.result()['status'],'FAIL')
    def test_unknown_cannot_blind_retry(self):
        self.create(); self.patch('tasks/T-DEMO-001/state.json',lambda x:x.update(external_operations=[{'status':'UNKNOWN','retry_planned':True}]))
        self.assertEqual(self.result()['status'],'FAIL')
    def test_path_escape_refused(self):
        self.create(); self.patch('control/policy.json',lambda x:x.update(approval_status='APPROVED',approval_ref='../private.txt'))
        self.assertEqual(self.result()['status'],'FAIL')
    def test_symbolic_reference_refused(self):
        self.create(); external=self.parent/'external.txt'; external.write_text('not to read')
        (self.work/'external-link.txt').symlink_to(external)
        self.patch('control/policy.json',lambda x:x.update(approval_status='APPROVED',approval_ref='external-link.txt'))
        self.assertEqual(self.result()['status'],'FAIL')
    def test_duplicate_json_keys_fail(self):
        self.create(); (self.work/'control/policy.json').write_text('{"schema_version":1,"schema_version":2}')
        self.assertEqual(self.result()['status'],'FAIL')
    def test_complete_build_requires_gates(self):
        self.create(); self.patch('BUILD_STATE.json',lambda x:x.update(stage='S6',stage_status='COMPLETE'))
        self.assertEqual(self.result()['status'],'FAIL')
    def test_consistent_done_and_changed_version(self):
        self.create(); d=self.work/'tasks/T-DEMO-001'; (d/'outputs').mkdir(); (d/'evidence').mkdir()
        out=d/'outputs/result.md'; out.write_text('fixture only')
        (d/'evidence/review.md').write_text('fixture, not human verification')
        (d/'evidence/delivery.md').write_text('fixture, not external receipt')
        prefix='tasks/T-DEMO-001/'
        self.patch(prefix+'state.json',lambda x:x.update(
            state='DONE',artifact=prefix+'outputs/result.md',artifact_sha256=hashlib.sha256(out.read_bytes()).hexdigest(),
            review={'verdict':'PASS','kind':'SELF_CHECK','evidence_ref':prefix+'evidence/review.md'},
            delivery_ref=prefix+'evidence/delivery.md'))
        self.assertEqual(self.result()['status'],'PASS')
        out.write_text('changed')
        self.assertEqual(self.result()['status'],'FAIL')

if __name__=='__main__': unittest.main()
