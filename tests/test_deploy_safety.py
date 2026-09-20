"""Offline regression tests; no credentials, hosting calls or package installs."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '.agents' / 'skills' / 'ispmanager-hosting' / 'scripts'))
import deploy_static_file as deploy


class FakePanel:
    def __init__(self):
        self.content = b'old live content'
        self.present = True
        self.created = []
        self.writes = []
        self.fail_write = False
        self.fail_restore = False
        self.fail_read = False

    def exists(self, target):
        return self.present

    def create_file(self, target):
        self.created.append(target)
        self.present = True

    def read_file(self, target):
        if self.fail_read:
            raise deploy.DeployError('read failed')
        return self.content

    def write_file(self, target, content):
        self.writes.append(content)
        self.content = content[:3]
        if self.fail_write and len(self.writes) == 1:
            raise deploy.DeployError('write failed')
        if self.fail_restore and len(self.writes) > 1:
            raise deploy.DeployError('restore failed')
        self.content = content


class DeploySafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.backups = Path(self.temp.name)
        self.panel = FakePanel()
        self.target = 'www/fastup.by/robots.txt'

    def run_deploy(self):
        return deploy.replace_file(self.panel, self.target, b'new content', self.backups)

    def test_success_keeps_actual_live_backup(self):
        receipt = self.run_deploy()
        self.assertEqual(self.panel.content, b'new content')
        self.assertEqual(Path(receipt['backup']).read_bytes(), b'old live content')

    def test_unreadable_original_never_writes(self):
        self.panel.fail_read = True
        with self.assertRaises(deploy.DeployError):
            self.run_deploy()
        self.assertEqual(self.panel.writes, [])

    def test_failed_backup_never_writes(self):
        with patch.object(deploy, 'save_backup', side_effect=OSError('disk full')):
            with self.assertRaises(deploy.DeployError):
                self.run_deploy()
        self.assertEqual(self.panel.writes, [])

    def test_partial_write_is_restored_and_still_fails(self):
        self.panel.fail_write = True
        with self.assertRaisesRegex(deploy.DeployError, 'restored original'):
            self.run_deploy()
        self.assertEqual(self.panel.content, b'old live content')

    def test_failed_restore_reports_recovery_file(self):
        self.panel.fail_write = self.panel.fail_restore = True
        with self.assertRaisesRegex(deploy.DeployError, 'MANUAL RESTORATION REQUIRED'):
            self.run_deploy()
        self.assertEqual(next(self.backups.glob('*/original.bin')).read_bytes(), b'old live content')

    def test_readback_mismatch_rolls_back(self):
        original_write = self.panel.write_file
        def corrupt(target, content):
            original_write(target, content)
            if len(self.panel.writes) == 1:
                self.panel.content = b'corrupt'
        self.panel.write_file = corrupt
        with self.assertRaisesRegex(deploy.DeployError, 'restored original'):
            self.run_deploy()
        self.assertEqual(self.panel.content, b'old live content')

    def test_concurrent_change_aborts_without_overwrite(self):
        original_read = self.panel.read_file
        calls = []
        def changed(target):
            calls.append(target)
            return original_read(target) if len(calls) == 1 else b'other deploy'
        self.panel.read_file = changed
        with self.assertRaisesRegex(deploy.DeployError, 'modified concurrently'):
            self.run_deploy()
        self.assertEqual(self.panel.writes, [])

    def test_noop_writes_nothing(self):
        self.panel.content = b'new content'
        self.run_deploy()
        self.assertEqual(self.panel.writes, [])

    def test_missing_file_is_created_not_refused(self):
        """Регрессия: чтение оригинала как обязательный шаг делало заливку нового файла невозможной."""
        self.panel.present = False
        receipt = deploy.replace_file(self.panel, self.target, b'new content', self.backups)
        self.assertTrue(receipt['created'])
        self.assertEqual(self.panel.created, [self.target])
        self.assertEqual(self.panel.content, b'new content')

    def test_created_file_is_read_back(self):
        self.panel.present = False
        original_write = self.panel.write_file
        def corrupt(target, content):
            original_write(target, content)
            self.panel.content = b'corrupt'
        self.panel.write_file = corrupt
        with self.assertRaisesRegex(deploy.DeployError, 'hash verification failed'):
            deploy.replace_file(self.panel, self.target, b'new content', self.backups)

    def test_no_backup_writes_without_reading(self):
        """--no-backup — путь для файлов, которые панель не отдаёт (FileMaxEditSize)."""
        self.panel.fail_read = True
        receipt = deploy.replace_file(self.panel, self.target, b'new content', self.backups, backup=False)
        self.assertTrue(receipt['unverified'])
        self.assertEqual(self.panel.writes, [b'new content'])
        self.assertEqual(list(self.backups.glob('*/original.bin')), [])

    def test_rejects_non_utf8_payload(self):
        with self.assertRaises(deploy.DeployError):
            deploy.replace_file(self.panel, self.target, b'\xff\xfe binary', self.backups)
        self.assertEqual(self.panel.writes, [])

    def test_crlf_is_normalised_before_upload(self):
        """Регрессия: панель пишет LF, а рабочая копия на Windows — CRLF.

        Без нормализации сверка после записи не сходилась ни на одном файле темы,
        и каждая выкатка откатывалась как испорченная.
        """
        source = Path(self.temp.name) / 'header.php'
        source.write_bytes(b'<?php\r\necho 1;\r\n')
        self.assertEqual(deploy.validate_local_file(source, 'header.php'), b'<?php\necho 1;\n')

    def test_ftp_exists_compares_basenames(self):
        """Регрессия: NLST у ProFTPD отдаёт полные пути, а не имена.

        Сравнение «имя в списке» тихо давало False на существующем файле, и перезапись
        уходила по ветке создания — без бэкапа и без сверки с текущей версией.
        """
        transfer = deploy.Transfer.__new__(deploy.Transfer)
        transfer._root_items = {'www'}

        class FakeFTP:
            def nlst(self, path):
                return [f'{path}/header.php', f'{path}/footer.php']

        transfer.ftp = FakeFTP()
        target = 'www/fastup.by/wp-content/themes/fastup-v2/header.php'
        self.assertTrue(transfer.exists(target))
        self.assertFalse(transfer.exists(target.replace('header', 'missing')))

    def test_rejects_unsafe_paths(self):
        for path in ('../x', '/www/x', 'www/a/../b', 'www/a\\b', 'www/a, b'):
            with self.subTest(path=path), self.assertRaises(deploy.DeployError):
                deploy.validate_remote_path(path)

    def test_panel_list_dir_detects_ispmanager_parent_fallback(self):
        """Регрессия: если каталога нет, ISPmanager возвращает листинг родителя.
        Без сверки plid exists('missing/index.html') давал True, если index.html был в родителе."""
        panel = deploy.Panel.__new__(deploy.Panel)
        panel.call = lambda func, params: {
            'doc': {
                'plid': {'$': 'www/fastup.by/tz'},
                'elem': [{'name': {'$': 'index.html'}}]
            }
        }
        with self.assertRaisesRegex(deploy.DeployError, 'Remote directory does not exist'):
            panel.list_dir('www/fastup.by/tz/missing')

    def test_panel_list_dir_returns_names_when_plid_matches(self):
        panel = deploy.Panel.__new__(deploy.Panel)
        panel.call = lambda func, params: {
            'doc': {
                'plid': {'$': 'www/fastup.by/tz'},
                'elem': [{'name': {'$': 'index.html'}}, {'name': {'$': 'test.php'}}]
            }
        }
        self.assertEqual(panel.list_dir('www/fastup.by/tz'), ['index.html', 'test.php'])

    def test_transfer_create_file_ensures_dirs(self):
        transfer = deploy.Transfer.__new__(deploy.Transfer)
        transfer._root_items = {'www'}
        mkd_calls = []

        class FakeFTP:
            def nlst(self, path):
                if path == 'www/fastup.by/tz':
                    return []
                return []

            def mkd(self, path):
                mkd_calls.append(path)

        transfer.ftp = FakeFTP()
        transfer.create_file('www/fastup.by/tz/newclient/index.html')
        self.assertIn('www/fastup.by/tz/newclient', mkd_calls)


if __name__ == '__main__':
    unittest.main()
