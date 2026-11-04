"""Linux-runnable core regression tests; these do not simulate Windows UI support."""
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

TEMP=tempfile.TemporaryDirectory(prefix='hermes-macos-test-')
BASE=Path(TEMP.name)
os.environ['LOCALAPPDATA']=str(BASE)
os.environ['HERMES_TOOL_TOKEN']='test-only-token'
sys.path.insert(0,str(Path(__file__).parent/'source'))
import mac_platform
mac_platform.BASE=BASE
mac_platform.DATA_DIR=BASE/"data"
mac_platform.CONFIG_DIR=BASE/"config"
mac_platform.xdg_user_directory=lambda name: BASE/name
mac_platform.PROJECT_ROOT=BASE/'project'
mac_platform.PROJECT_ROOT.mkdir()
for name in ('DESKTOP','DOCUMENTS','DOWNLOAD','PICTURES','MUSIC','VIDEOS'): (BASE/name).mkdir()
import platform_support
from fastapi.testclient import TestClient
import app, computer_control, persistent_workflow, backup_manager

class PortTests(unittest.TestCase):
    def setUp(self):
        self.client=TestClient(app.app)
        self.headers={'Authorization':'Bearer test-only-token'}

    def test_authentication(self):
        r=self.client.get('/computer/applications')
        self.assertEqual(r.status_code,401)

    def test_unicode_multiline_file(self):
        target=BASE/'DOCUMENTS/hello.txt'
        r=self.client.post('/computer/files/write',headers=self.headers,json={'path':str(target),'content':'Hello\nनमस्ते\nThird line'})
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(target.read_text(encoding='utf-8'),'Hello\nनमस्ते\nThird line')
        r=self.client.post('/computer/files/write',headers=self.headers,json={'path':str(target),'content':'overwrite'})
        self.assertNotEqual(r.status_code,200)

    def test_writable_boundary(self):
        r=self.client.post('/computer/files/write',headers=self.headers,json={'path':str(BASE/'outside.txt'),'content':'no'})
        self.assertEqual(r.status_code,403,r.text)
        self.assertFalse((BASE/'outside.txt').exists())

    def test_writable_roots_resolve_directory_aliases(self):
        alias=BASE/'documents-alias'
        alias.symlink_to(BASE/'DOCUMENTS', target_is_directory=True)
        original=mac_platform.xdg_user_directory
        try:
            mac_platform.xdg_user_directory=lambda name: alias
            self.assertEqual(mac_platform.writable_roots()[0],(BASE/'DOCUMENTS').resolve())
        finally:
            mac_platform.xdg_user_directory=original
            alias.unlink()

    def test_terminal_requires_consent(self):
        r=self.client.post('/computer/terminal/run',headers=self.headers,json={'program':'python','cwd':str(BASE/'DOCUMENTS')})
        self.assertEqual(r.status_code,403,r.text)

    def test_document_creation_and_collision(self):
        result=persistent_workflow.persistent_document_workflow('sample.txt','Line one\nLine two')
        self.assertTrue(result['success'],result)
        self.assertFalse(persistent_workflow.persistent_document_workflow('sample.txt','bad')['success'])

    def test_backup(self):
        result=backup_manager.create_backup()
        archive=Path(result['path'])
        self.assertTrue(archive.is_file(),result)
        with zipfile.ZipFile(archive) as package:
            self.assertIn('data/agent.db',package.namelist())

    def test_clipboard_confirmation(self):
        r=self.client.post('/graphical/clipboard/read',headers=self.headers,json={})
        self.assertEqual(r.status_code,400,r.text)

    def test_tool_schemas(self):
        import sync_openwebui_tool
        specs=sync_openwebui_tool.generated_specs()
        self.assertGreaterEqual(len(specs),122)
        self.assertEqual(len({s['name'] for s in specs}),len(specs))
        self.assertIn('get_personal_command_center',{s['name'] for s in specs})

    def test_v8_agent_command_center(self):
        r=self.client.get('/agent/command-center',headers=self.headers)
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(r.json()['safety_mode'],'normal')

if __name__=='__main__':
    unittest.main(verbosity=2)
