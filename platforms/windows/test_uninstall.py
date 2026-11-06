"""Ownership and uninstall decision tests; never invoke real package managers."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parent/'source'))
import windows_dependencies as d
import windows_runtime as runtime
import windows_setup

class OwnershipTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.state=Path(self.temp.name)
        self.patcher=patch.object(d,'STATE',self.state); self.patcher.start(); self.addCleanup(self.patcher.stop)
        self.package='Git.Git'
        self.entry=[{'hive':'machine','view':256,'key':'Git_is1','name':'Git version 2.50','version':'2.50','location':'C:\\Git'}]

    def receipt(self):
        (self.state/(self.package+'.json')).write_text(json.dumps({'package':self.package,'owned':True,'entries':self.entry}))

    def test_preexisting_install_never_claimed(self):
        with patch.object(d,'inventory',return_value=self.entry),patch.object(d.subprocess,'run') as run:
            d.install(self.package); run.assert_not_called()
        self.assertFalse(list(self.state.iterdir()))

    def test_winget_failure_is_not_absence(self):
        with patch.object(d,'inventory',return_value=[]),patch.object(d.shutil,'which',return_value='winget'),patch.object(d.subprocess,'run',return_value=subprocess.CompletedProcess([],1)) as run:
            with self.assertRaises(RuntimeError): d.install(self.package)
            self.assertEqual(run.call_count,3)
        self.assertFalse(list(self.state.iterdir()))

    def test_fresh_install_recorded(self):
        with patch.object(d,'inventory',side_effect=[[],self.entry]),patch.object(d.shutil,'which',return_value='winget'),patch.object(d.subprocess,'run',side_effect=[subprocess.CompletedProcess([],0x8A150014),subprocess.CompletedProcess([],0)]):
            d.install(self.package)
        self.assertTrue(d.eligible(d.load_receipt(self.package),self.entry))

    def test_success_without_registry_receipt_is_nonfatal(self):
        results=[subprocess.CompletedProcess([],d.NOT_FOUND),subprocess.CompletedProcess([],0),
                 subprocess.CompletedProcess([],0)]
        with patch.object(d,'inventory',return_value=[]),patch.object(d.shutil,'which',return_value='winget'),patch.object(d.subprocess,'run',side_effect=results):
            d.install(self.package)
        receipt=json.loads((self.state/(self.package+'.json')).read_text())
        self.assertFalse(receipt['owned'])
        self.assertIsNone(d.load_receipt(self.package))

    def test_unverifiable_inventory_never_claims_ownership(self):
        results=[subprocess.CompletedProcess([],d.NOT_FOUND),subprocess.CompletedProcess([],0),
                 subprocess.CompletedProcess([],0)]
        with patch.object(d,'inventory',side_effect=OSError('registry unavailable')),patch.object(d.shutil,'which',return_value='winget'),patch.object(d.subprocess,'run',side_effect=results):
            d.install(self.package)
        self.assertFalse(json.loads((self.state/(self.package+'.json')).read_text())['owned'])

    def test_success_that_cannot_be_detected_is_fatal(self):
        results=[subprocess.CompletedProcess([],d.NOT_FOUND),subprocess.CompletedProcess([],0),
                 subprocess.CompletedProcess([],d.NOT_FOUND)]
        with patch.object(d,'inventory',return_value=[]),patch.object(d.shutil,'which',return_value='winget'),patch.object(d.subprocess,'run',side_effect=results):
            with self.assertRaises(RuntimeError): d.install(self.package)

    def test_failed_install_not_owned(self):
        results=[subprocess.CompletedProcess([],d.NOT_FOUND)]+[subprocess.CompletedProcess([],1)]*3
        with patch.object(d,'inventory',return_value=[]),patch.object(d.shutil,'which',return_value='winget'),patch.object(d.subprocess,'run',side_effect=results):
            with self.assertRaises(subprocess.CalledProcessError): d.install(self.package)
        self.assertIsNone(d.load_receipt(self.package))

    def test_no_receipt_means_no_removal(self):
        with patch.object(d.subprocess,'run') as run:
            d.remove(self.package); run.assert_not_called()

    def test_changed_version_kept(self):
        self.receipt(); changed=[dict(self.entry[0],version='3.0')]
        with patch.object(d,'inventory',return_value=changed),patch.object(d.subprocess,'run') as run:
            d.remove(self.package); run.assert_not_called()

    def test_owned_unchanged_removed_and_verified(self):
        self.receipt()
        with patch.object(d,'inventory',side_effect=[self.entry,[]]),patch.object(d.shutil,'which',return_value='winget'),patch.object(d.subprocess,'run') as run:
            d.remove(self.package)
            self.assertIn('uninstall',run.call_args.args[0])
        self.assertIsNone(d.load_receipt(self.package))

    def test_failed_removal_retains_receipt(self):
        self.receipt()
        with patch.object(d,'inventory',return_value=self.entry),patch.object(d.shutil,'which',return_value='winget'),patch.object(d.subprocess,'run',side_effect=subprocess.CalledProcessError(1,[])):
            with self.assertRaises(subprocess.CalledProcessError): d.remove(self.package)
        self.assertIsNotNone(d.load_receipt(self.package))

    def test_unknown_package_rejected(self):
        with self.assertRaises(ValueError): d.remove('arbitrary-command')

    def test_optional_tool_failure_does_not_abort_core_setup(self):
        with patch.object(d,'install',side_effect=[None,RuntimeError('network unavailable'),None]):
            failures=runtime.install_desktop_dependencies()
        self.assertEqual(failures,{'OpenJS.NodeJS.LTS':'network unavailable'})

    def test_all_optional_tools_can_be_repaired_on_rerun(self):
        with patch.object(d,'install',side_effect=RuntimeError('winget unavailable')):
            first=runtime.install_desktop_dependencies()
        with patch.object(d,'install',return_value=None):
            second=runtime.install_desktop_dependencies()
        self.assertEqual(set(first),{'Git.Git','OpenJS.NodeJS.LTS','Microsoft.VisualStudioCode'})
        self.assertEqual(second,{})

    def test_repair_report_is_created_then_cleared(self):
        with patch.object(runtime,'DATA_DIR',self.state):
            runtime.record_optional_failures({'Git.Git':'temporary failure'})
            report=self.state/'optional-dependencies.json'
            self.assertTrue(report.is_file())
            runtime.record_optional_failures({})
            self.assertFalse(report.exists())

    def test_install_finishes_in_fresh_python_process(self):
        with patch.object(runtime,'install_dependencies') as dependencies, \
             patch.object(runtime.subprocess,'run') as run, \
             patch.object(runtime,'environment',return_value={'HERMES_ROOT':'test'}) as environment:
            runtime.install()
        dependencies.assert_called_once_with()
        environment.assert_called_once_with()
        argv=run.call_args.args[0]
        self.assertEqual(argv[0],str(runtime.PYTHON))
        self.assertEqual(Path(argv[1]).resolve(),Path(runtime.__file__).resolve())
        self.assertEqual(argv[2],'finish-install')
        self.assertTrue(run.call_args.kwargs['check'])

    def test_setup_startup_uses_fresh_python_process(self):
        setup=object.__new__(windows_setup.WindowsSetup)
        setup.command=unittest.mock.Mock()
        setup.startup()
        argv, callback=setup.command.call_args.args
        self.assertEqual(argv,[str(runtime.PYTHON),str(runtime.PROJECT_ROOT/'windows_runtime.py'),'startup'])
        self.assertTrue(callable(callback))

if __name__=='__main__': unittest.main(verbosity=2)
