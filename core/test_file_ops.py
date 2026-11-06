import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import file_ops


class FileOperationTests(unittest.TestCase):
    def test_actual_read_is_bounded_even_when_stat_is_stale(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'large.txt'
            path.write_bytes(b'a' * 20)
            with patch.object(file_ops, 'MAX_READ_BYTES', 10), patch.object(Path, 'stat') as stat:
                stat.return_value.st_size = 0
                with patch.object(Path, 'is_file', return_value=True):
                    with self.assertRaises(SystemExit), contextlib.redirect_stdout(io.StringIO()) as output:
                        file_ops.read_file(path)
                    self.assertEqual(output.getvalue(), '')

    def test_create_never_overwrites_file_created_after_check(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'existing.txt'
            path.write_text('keep')
            with patch.object(Path, 'exists', return_value=False), self.assertRaises(FileExistsError):
                file_ops.write_file(path, 'replace', False, True)
            self.assertEqual(path.read_text(), 'keep')

    def test_overwrite_flag_never_overwrites_file_created_after_check(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'existing.txt'
            path.write_text('keep')
            with patch.object(Path, 'exists', return_value=False), self.assertRaises(FileExistsError):
                file_ops.write_file(path, 'replace', True, True)
            self.assertEqual(path.read_text(), 'keep')

    def test_cli_delete_preserves_symlink_target(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'target.txt'
            target.write_text('keep')
            link = Path(folder) / 'link.txt'
            try:
                link.symlink_to(target)
            except OSError:
                self.skipTest('Symlink creation unavailable')
            with patch('sys.argv', ['file_ops', 'delete', str(link)]), patch('builtins.input', return_value='DELETE'), contextlib.redirect_stdout(io.StringIO()):
                file_ops.main()
            self.assertFalse(link.is_symlink())
            self.assertEqual(target.read_text(), 'keep')
