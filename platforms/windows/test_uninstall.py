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
            self.assertEqual(run.call_count,1)
        self.assertFalse(list(self.state.iterdir()))

    def test_fresh_install_recorded(self):
        with patch.object(d,'inventory',side_effect=[[],self.entry]),patch.object(d.shutil,'which',return_value='winget'),patch.object(d.subprocess,'run',side_effect=[subprocess.CompletedProcess([],0x8A150014),subprocess.CompletedProcess([],0)]):
            d.install(self.package)
        self.assertTrue(d.eligible(d.load_receipt(self.package),self.entry))

    def test_failed_install_not_owned(self):
        with patch.object(d,'inventory',return_value=[]),patch.object(d.shutil,'which',return_value='winget'),patch.object(d.subprocess,'run',side_effect=[subprocess.CompletedProcess([],0x8A150014),subprocess.CalledProcessError(1,[]) ]):
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

if __name__=='__main__': unittest.main(verbosity=2)
