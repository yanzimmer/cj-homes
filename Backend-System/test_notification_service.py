import os
import sqlite3
import tempfile
import unittest
from copy import deepcopy
from datetime import datetime
from unittest.mock import patch

import expiry_notification_config as notify_config
import notification_service


class AutomaticBarkNotificationTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = os.path.join(self.temp_dir.name, "hotel.db")
        conn = sqlite3.connect(self.database_path)
        conn.executescript(
            """
            CREATE TABLE rooms (
                id INTEGER PRIMARY KEY,
                building TEXT,
                room_no TEXT,
                price REAL,
                price_unit TEXT
            );
            CREATE TABLE tenants (
                id INTEGER PRIMARY KEY,
                name TEXT,
                phone TEXT
            );
            CREATE TABLE tenant_stays (
                id INTEGER PRIMARY KEY,
                tenant_id INTEGER,
                room_id INTEGER,
                planned_check_out_date TEXT,
                rent_amount REAL,
                rent_unit TEXT,
                status TEXT
            );
            CREATE TABLE rent_ledger_entries (
                id INTEGER PRIMARY KEY,
                tenant_id INTEGER,
                stay_id INTEGER,
                room_id INTEGER,
                building TEXT,
                room_no TEXT,
                tenant_name TEXT,
                period_start TEXT,
                period_end TEXT,
                due_amount REAL,
                actual_amount REAL,
                allocated_amount REAL,
                status TEXT
            );
            INSERT INTO rooms VALUES (1, 'A栋', '101', 2000, '月');
            INSERT INTO tenants VALUES (1, '测试租户', '13800000000');
            INSERT INTO tenant_stays VALUES (1, 1, 1, '2026-08-05', 2000, '月', '在住');
            INSERT INTO rent_ledger_entries VALUES (
                1, 1, 1, 1, 'A栋', '101', '测试租户',
                '2026-08-01', '2026-08-31', 2000, 0, 0, '未交'
            );
            """
        )
        conn.commit()
        conn.close()

        self.config = deepcopy(notify_config.DEFAULT_CONFIG)
        self.config["reminder_count"] = 2
        self.config["lease_advance_days"] = 7
        self.config["rent_advance_days"] = 7
        self.config["bark_config"].update(
            {
                "enabled": True,
                "auto_send_enabled": True,
                "send_time": "09:00",
                "lease_expiry_enabled": True,
                "rent_reminder_enabled": True,
                "endpoints": [
                    {
                        "id": "phone-1",
                        "remark": "房东手机",
                        "bark_url": "https://bark.example/device-key",
                        "enabled": True,
                    }
                ],
            }
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def _connect(self):
        return sqlite3.connect(self.database_path)

    @patch("notification_service._rebuild_rent_ledger_year", return_value=0)
    @patch("notify_api.send_bark_notification")
    def test_daily_deduplication_and_repeat_limit(self, mocked_send, mocked_rebuild):
        mocked_send.return_value = {
            "success": True,
            "success_count": 1,
            "failure_count": 0,
            "results": [{"success": True}],
        }
        with patch("notification_service.connect", side_effect=self._connect), patch(
            "notification_service.notify_config.get_runtime_config", return_value=self.config
        ):
            first = notification_service.run_due_bark_notifications(datetime(2026, 7, 30, 9, 30))
            conn = self._connect()
            conn.execute("UPDATE rent_ledger_entries SET id = 99 WHERE id = 1")
            conn.commit()
            conn.close()
            same_day = notification_service.run_due_bark_notifications(datetime(2026, 7, 30, 15, 0))
            second_day = notification_service.run_due_bark_notifications(datetime(2026, 7, 31, 9, 30))
            after_limit = notification_service.run_due_bark_notifications(datetime(2026, 8, 1, 9, 30))

        self.assertEqual(2, first["sent"])
        self.assertEqual(2, first["claimed_events"])
        self.assertEqual(0, same_day["sent"])
        self.assertEqual(2, second_day["sent"])
        self.assertEqual(0, after_limit["sent"])
        self.assertEqual(4, mocked_send.call_count)

        titles = [call.args[0] for call in mocked_send.call_args_list]
        contents = [call.args[1] for call in mocked_send.call_args_list]
        self.assertTrue(any("租期到期提醒" in title for title in titles))
        self.assertTrue(any("待收房租提醒" in title for title in titles))
        self.assertTrue(any("A栋 101" in content for content in contents))

    @patch("notification_service._rebuild_rent_ledger_year", return_value=0)
    @patch("notify_api.send_bark_notification")
    def test_worker_waits_until_configured_time(self, mocked_send, mocked_rebuild):
        with patch("notification_service.connect", side_effect=self._connect), patch(
            "notification_service.notify_config.get_runtime_config", return_value=self.config
        ):
            result = notification_service.run_due_bark_notifications(datetime(2026, 7, 30, 8, 59))

        self.assertEqual("skipped", result["status"])
        self.assertIn("发送时间", result["reason"])
        mocked_send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
