import os
import sqlite3
import tempfile
import unittest

import common
from tenant_stays_service import (
    checkout_current_stay,
    create_tenant_stay,
    ensure_tenant_stays_schema,
)


class TenantStaysMigrationTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_name = common.DB_NAME
        common.DB_NAME = os.path.join(self.temp_dir.name, "hotel.db")
        self._create_legacy_database()

    def tearDown(self):
        common.DB_NAME = self.original_db_name
        self.temp_dir.cleanup()

    def _create_legacy_database(self):
        conn = sqlite3.connect(common.DB_NAME)
        conn.executescript(
            """
            PRAGMA foreign_keys = ON;
            CREATE TABLE rooms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                building TEXT,
                room_no TEXT UNIQUE NOT NULL,
                price REAL,
                price_unit TEXT DEFAULT '月',
                deposit REAL DEFAULT 0,
                status TEXT DEFAULT '空闲'
            );
            CREATE TABLE tenants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                id_card TEXT UNIQUE,
                phone TEXT,
                check_in_date TEXT,
                check_out_date TEXT,
                room_id INTEGER,
                remarks TEXT,
                status TEXT DEFAULT '在住',
                FOREIGN KEY (room_id) REFERENCES rooms(id)
            );
            CREATE TABLE contracts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER,
                room_id INTEGER,
                start_date TEXT,
                end_date TEXT
            );
            CREATE TABLE tenant_moves (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER,
                old_room_id INTEGER,
                new_room_id INTEGER,
                move_date TEXT,
                remarks TEXT
            );
            CREATE TABLE self_checkin_submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                room_id INTEGER,
                approved_tenant_id INTEGER
            );
            CREATE TABLE rent_ledger_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER NOT NULL,
                room_id INTEGER,
                building TEXT DEFAULT '',
                room_no TEXT DEFAULT '',
                tenant_name TEXT DEFAULT '',
                lease_start TEXT DEFAULT '',
                lease_end TEXT DEFAULT '',
                rent_amount REAL NOT NULL DEFAULT 0,
                rent_unit TEXT DEFAULT '月',
                period_index INTEGER NOT NULL DEFAULT 1,
                period_label TEXT NOT NULL,
                period_start TEXT NOT NULL,
                period_end TEXT NOT NULL,
                due_amount REAL NOT NULL DEFAULT 0,
                actual_amount REAL NOT NULL DEFAULT 0,
                allocated_amount REAL NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT '未交',
                payment_date TEXT DEFAULT '',
                payment_person TEXT DEFAULT '',
                payment_method TEXT DEFAULT '',
                remarks TEXT DEFAULT '',
                payment_images TEXT DEFAULT '[]',
                created_at TEXT DEFAULT '',
                updated_at TEXT DEFAULT '',
                UNIQUE (tenant_id, period_start)
            );
            INSERT INTO rooms (id, building, room_no, price, price_unit, deposit)
            VALUES (1, 'A', 'A101', 1000, '月', 1000),
                   (2, 'B', 'B202', 1200, '月', 1200);
            INSERT INTO tenants (
                id, name, id_card, phone, check_in_date, check_out_date,
                room_id, remarks, status
            ) VALUES (1, '测试租户', '520000199001010011', '13800000000',
                      '2026-01-01', '2026-06-30', 1, '首次入住', '已退租');
            INSERT INTO contracts (id, tenant_id, room_id, start_date, end_date)
            VALUES (1, 1, 1, '2026-01-01', '2026-06-30');
            INSERT INTO rent_ledger_entries (
                tenant_id, room_id, building, room_no, tenant_name,
                lease_start, lease_end, rent_amount, rent_unit, period_index,
                period_label, period_start, period_end, due_amount, actual_amount,
                allocated_amount, status, payment_date
            ) VALUES (
                1, 1, 'A', 'A101', '测试租户', '2026-01-01', '2026-06-30',
                1000, '月', 1, '第1期', '2026-01-01', '2026-01-31',
                1000, 1000, 1000, '已交', '2026-01-01'
            );
            """
        )
        conn.commit()
        conn.close()

    def test_migration_backfills_stays_and_preserves_ledger(self):
        backup_path = ensure_tenant_stays_schema()
        self.assertTrue(backup_path)
        self.assertTrue(os.path.exists(backup_path))

        conn = sqlite3.connect(common.DB_NAME)
        stay = conn.execute(
            "SELECT tenant_id, room_id, status, actual_check_out_date FROM tenant_stays"
        ).fetchone()
        self.assertEqual((1, 1, "已退租", "2026-06-30"), stay)
        ledger = conn.execute(
            "SELECT stay_id, actual_amount, allocated_amount FROM rent_ledger_entries"
        ).fetchone()
        self.assertEqual(1, ledger[0])
        self.assertEqual(1000, ledger[1])
        self.assertEqual(1000, ledger[2])
        self.assertEqual(1, conn.execute("SELECT stay_id FROM contracts WHERE id = 1").fetchone()[0])

        table_sql = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'rent_ledger_entries'"
        ).fetchone()[0]
        self.assertIn("UNIQUE (stay_id, period_start)", table_sql)
        conn.close()

        ensure_tenant_stays_schema()
        conn = sqlite3.connect(common.DB_NAME)
        self.assertEqual(1, conn.execute("SELECT COUNT(*) FROM tenant_stays").fetchone()[0])
        self.assertEqual(1, conn.execute("SELECT COUNT(*) FROM rent_ledger_entries").fetchone()[0])
        conn.close()

    def test_returning_tenant_gets_new_stay_without_overwriting_history(self):
        ensure_tenant_stays_schema()
        conn = common.connect()
        stay_id = create_tenant_stay(
            conn,
            tenant_id=1,
            room_id=2,
            check_in_date="2026-09-01",
            planned_check_out_date="2027-08-31",
            remarks="再次入住",
        )
        conn.commit()

        stays = conn.execute(
            "SELECT id, room_id, check_in_date, status FROM tenant_stays WHERE tenant_id = 1 ORDER BY id"
        ).fetchall()
        self.assertEqual(2, len(stays))
        self.assertEqual((1, 1, "2026-01-01", "已退租"), tuple(stays[0]))
        self.assertEqual((stay_id, 2, "2026-09-01", "在住"), tuple(stays[1]))
        tenant = conn.execute(
            "SELECT room_id, check_in_date, check_out_date, status FROM tenants WHERE id = 1"
        ).fetchone()
        self.assertEqual((2, "2026-09-01", "2027-08-31", "在住"), tuple(tenant))

        with self.assertRaisesRegex(ValueError, "已有一条在住记录"):
            create_tenant_stay(conn, 1, 1, "2027-01-01", "2027-12-31")

        checkout = checkout_current_stay(conn, 1, "2027-03-15")
        self.assertEqual(stay_id, checkout[0])
        third_stay_id = create_tenant_stay(conn, 1, 1, "2027-06-01", "2028-05-31")
        self.assertGreater(third_stay_id, stay_id)
        conn.commit()
        self.assertEqual(3, conn.execute("SELECT COUNT(*) FROM tenant_stays WHERE tenant_id = 1").fetchone()[0])
        self.assertEqual(1, conn.execute("SELECT COUNT(*) FROM tenant_stays WHERE tenant_id = 1 AND status = '在住'").fetchone()[0])
        conn.close()


if __name__ == "__main__":
    unittest.main()
