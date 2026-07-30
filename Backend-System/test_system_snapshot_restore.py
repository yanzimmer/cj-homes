import json
import os
import sqlite3
import tempfile
import unittest
import zipfile
from unittest.mock import patch

import common
import system_api


class SystemSnapshotRestoreTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_name = common.DB_NAME
        common.DB_NAME = os.path.join(self.temp_dir.name, 'snapshot-test.db')

    def tearDown(self):
        common.DB_NAME = self.original_db_name
        self.temp_dir.cleanup()

    def _create_valid_stay_database(self):
        conn = sqlite3.connect(common.DB_NAME)
        conn.executescript(
            """
            PRAGMA foreign_keys = ON;
            CREATE TABLE rooms (id INTEGER PRIMARY KEY);
            CREATE TABLE tenants (id INTEGER PRIMARY KEY, name TEXT);
            CREATE TABLE tenant_stays (
                id INTEGER PRIMARY KEY,
                tenant_id INTEGER NOT NULL,
                room_id INTEGER,
                status TEXT,
                FOREIGN KEY (tenant_id) REFERENCES tenants(id),
                FOREIGN KEY (room_id) REFERENCES rooms(id)
            );
            CREATE TABLE contracts (id INTEGER PRIMARY KEY, tenant_id INTEGER, stay_id INTEGER);
            CREATE TABLE tenant_moves (id INTEGER PRIMARY KEY, tenant_id INTEGER, stay_id INTEGER);
            CREATE TABLE rent_ledger_entries (id INTEGER PRIMARY KEY, tenant_id INTEGER, stay_id INTEGER);
            CREATE TABLE self_checkin_submissions (
                id INTEGER PRIMARY KEY,
                approved_tenant_id INTEGER,
                approved_stay_id INTEGER
            );
            INSERT INTO rooms VALUES (1);
            INSERT INTO tenants VALUES (1, '测试租户');
            INSERT INTO tenant_stays VALUES (10, 1, 1, '在住');
            INSERT INTO contracts VALUES (20, 1, 10);
            INSERT INTO tenant_moves VALUES (30, 1, 10);
            INSERT INTO rent_ledger_entries VALUES (40, 1, 10);
            INSERT INTO self_checkin_submissions VALUES (50, 1, 10);
            """
        )
        conn.commit()
        conn.close()

    def test_legacy_snapshot_without_app_version_is_allowed(self):
        system_api._validate_snapshot_version({'metadata': {'version': '1.0'}})

    def test_newer_snapshot_is_rejected(self):
        with patch.object(system_api, 'get_app_version', return_value='1.3.1'):
            with self.assertRaisesRegex(ValueError, '不支持降级恢复'):
                system_api._validate_snapshot_version({'metadata': {'app_version': '1.4.0'}})

    def test_current_or_older_snapshot_is_allowed(self):
        with patch.object(system_api, 'get_app_version', return_value='1.3.1'):
            system_api._validate_snapshot_version({'metadata': {'app_version': '1.3.1'}})
            system_api._validate_snapshot_version({'metadata': {'app_version': '1.2.0'}})

    def test_newer_snapshot_format_is_rejected(self):
        with self.assertRaisesRegex(ValueError, '更高的格式版本'):
            system_api._validate_snapshot_version(
                {'metadata': {'snapshot_format_version': system_api.SNAPSHOT_FORMAT_VERSION + 1}}
            )

    def test_snapshot_dump_contains_real_app_and_format_versions(self):
        conn = sqlite3.connect(common.DB_NAME)
        conn.execute('CREATE TABLE sample (id INTEGER PRIMARY KEY, value TEXT)')
        conn.execute("INSERT INTO sample VALUES (1, 'ok')")
        conn.commit()
        conn.close()

        with patch.object(system_api, 'get_app_version', return_value='1.3.1'):
            dumped = system_api._dump_db_to_dict()

        self.assertEqual('1.3.1', dumped['metadata']['app_version'])
        self.assertEqual(system_api.SNAPSHOT_FORMAT_VERSION, dumped['metadata']['snapshot_format_version'])
        self.assertEqual([{'id': 1, 'value': 'ok'}], dumped['tables']['sample'])

    def test_restore_validation_accepts_complete_stay_links(self):
        self._create_valid_stay_database()
        source_data = {
            'tables': {
                'rooms': [{}],
                'tenants': [{}],
                'contracts': [{}],
                'tenant_moves': [{}],
                'rent_ledger_entries': [{}],
                'self_checkin_submissions': [{}],
            }
        }
        system_api._validate_restored_database(source_data)

    def test_restore_validation_rejects_missing_stay_link(self):
        self._create_valid_stay_database()
        conn = sqlite3.connect(common.DB_NAME)
        conn.execute('UPDATE rent_ledger_entries SET stay_id = NULL WHERE id = 40')
        conn.commit()
        conn.close()

        with self.assertRaisesRegex(RuntimeError, '收租台账未正确关联入住记录'):
            system_api._validate_restored_database({'tables': {}})

    def test_prepare_staging_rejects_future_snapshot(self):
        zip_path = os.path.join(self.temp_dir.name, 'future.zip')
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(
                'database.json',
                json.dumps({'metadata': {'app_version': '9.0.0'}, 'tables': {}}),
            )

        with patch.object(system_api, 'get_app_version', return_value='1.3.1'):
            with self.assertRaisesRegex(ValueError, '不支持降级恢复'):
                system_api._prepare_import_staging(zip_path)

    def test_validation_failure_restores_pre_import_database_and_files(self):
        conn = sqlite3.connect(common.DB_NAME)
        conn.execute('CREATE TABLE state (id INTEGER PRIMARY KEY, value TEXT)')
        conn.execute("INSERT INTO state VALUES (1, '恢复前')")
        conn.commit()
        conn.close()

        current_config = os.path.join(self.temp_dir.name, 'current-config')
        current_uploads = os.path.join(self.temp_dir.name, 'current-uploads')
        staged_config = os.path.join(self.temp_dir.name, 'staged-config')
        staged_uploads = os.path.join(self.temp_dir.name, 'staged-uploads')
        staged_env = os.path.join(self.temp_dir.name, 'staged-env')
        for directory in (current_config, current_uploads, staged_config, staged_uploads, staged_env):
            os.makedirs(directory, exist_ok=True)
        with open(os.path.join(current_config, 'value.txt'), 'w', encoding='utf-8') as f:
            f.write('恢复前配置')
        with open(os.path.join(current_uploads, 'value.txt'), 'w', encoding='utf-8') as f:
            f.write('恢复前文件')
        with open(os.path.join(staged_config, 'value.txt'), 'w', encoding='utf-8') as f:
            f.write('快照配置')
        with open(os.path.join(staged_uploads, 'value.txt'), 'w', encoding='utf-8') as f:
            f.write('快照文件')

        staging = {
            'db_data': {
                'tables': {'state': [{'id': 1, 'value': '快照状态'}]},
                'schemas': {'state': 'CREATE TABLE state (id INTEGER PRIMARY KEY, value TEXT)'},
                'table_order': ['state'],
            },
            'config_dir': staged_config,
            'uploads_dir': staged_uploads,
            'env_dir': staged_env,
            'env_manifest': [],
        }

        with patch.object(system_api, 'CONFIG_DIR', current_config), \
             patch.object(system_api, 'UPLOADS_DIR', current_uploads), \
             patch.object(system_api, '_snapshot_env_files', return_value=[]), \
             patch.object(system_api, '_restore_env_files_from_staging'), \
             patch.object(system_api, '_run_post_restore_schema_migrations'), \
             patch.object(system_api, '_validate_restored_database', side_effect=RuntimeError('校验失败')):
            with self.assertRaisesRegex(RuntimeError, '校验失败'):
                system_api._apply_staged_import(staging)

        conn = sqlite3.connect(common.DB_NAME)
        self.assertEqual('恢复前', conn.execute('SELECT value FROM state WHERE id = 1').fetchone()[0])
        conn.close()
        with open(os.path.join(current_config, 'value.txt'), encoding='utf-8') as f:
            self.assertEqual('恢复前配置', f.read())
        with open(os.path.join(current_uploads, 'value.txt'), encoding='utf-8') as f:
            self.assertEqual('恢复前文件', f.read())


if __name__ == '__main__':
    unittest.main()
