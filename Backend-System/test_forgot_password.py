import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

import forgot_password as recovery


class ForgotPasswordTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test.db")
        self.connect_patch = patch.object(
            recovery,
            "connect",
            side_effect=lambda: sqlite3.connect(self.db_path),
        )
        self.connect_patch.start()
        recovery.ensure_schema()
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO admins (username, password_hash, full_name) VALUES (?, ?, ?)",
            ("admin", recovery.sha256("old-password"), "管理员"),
        )
        conn.commit()
        conn.close()

    def tearDown(self):
        self.connect_patch.stop()
        self.temp_dir.cleanup()

    def test_recovery_locks_after_five_failures_and_recovers_after_timeout(self):
        recovery.set_recovery_info("admin", security_answer="safe-answer")

        for remaining in (4, 3, 2, 1):
            ok, message = recovery.verify_and_reset_password("admin", "wrong", "new-password")
            self.assertFalse(ok)
            self.assertIn(f"还可尝试 {remaining} 次", message)

        ok, message = recovery.verify_and_reset_password("admin", "wrong", "new-password")
        self.assertFalse(ok)
        self.assertIn("连续验证失败 5 次", message)

        ok, message = recovery.verify_and_reset_password("admin", "safe-answer", "new-password")
        self.assertFalse(ok)
        self.assertIn("后重试", message)

        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "UPDATE admins SET recovery_locked_until = ? WHERE username = 'admin'",
            ((datetime.now() - timedelta(seconds=1)).strftime("%Y-%m-%d %H:%M:%S"),),
        )
        conn.commit()
        conn.close()

        ok, message = recovery.verify_and_reset_password("admin", "safe-answer", "new-password")
        self.assertTrue(ok)
        self.assertEqual("密码重置成功", message)

    def test_migration_invalidates_the_legacy_default_answer(self):
        legacy_db = os.path.join(self.temp_dir.name, "legacy.db")
        conn = sqlite3.connect(legacy_db)
        conn.execute(
            """
            CREATE TABLE admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                security_answer_hash TEXT
            )
            """
        )
        conn.execute(
            "INSERT INTO admins (username, password_hash, security_answer_hash) VALUES (?, ?, ?)",
            ("admin", "password-hash", recovery.LEGACY_DEFAULT_ANSWER_HASH),
        )
        conn.commit()
        conn.close()

        with patch.object(recovery, "connect", side_effect=lambda: sqlite3.connect(legacy_db)):
            recovery.ensure_schema()

        conn = sqlite3.connect(legacy_db)
        answer_hash = conn.execute(
            "SELECT security_answer_hash FROM admins WHERE username = 'admin'"
        ).fetchone()[0]
        conn.close()
        self.assertIsNone(answer_hash)


if __name__ == "__main__":
    unittest.main()
