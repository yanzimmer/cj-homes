import os
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch


class AuthRecoveryApiTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.backend_dir = os.path.dirname(os.path.abspath(__file__))
        if cls.backend_dir not in sys.path:
            sys.path.insert(0, cls.backend_dir)

        import common

        cls.common = common
        cls.original_db_name = common.DB_NAME
        common.DB_NAME = os.path.join(cls.temp_dir.name, "api-test.db")

        init_scripts_dir = os.path.join(cls.backend_dir, "init-scripts")
        if init_scripts_dir not in sys.path:
            sys.path.insert(0, init_scripts_dir)
        from init_hotel_db import ensure_tables

        ensure_tables()

        from app import app
        from forgot_password import sha256

        cls.app = app
        cls.app.config.update(TESTING=True)
        conn = sqlite3.connect(common.DB_NAME)
        conn.execute(
            "INSERT INTO admins (username, password_hash, full_name) VALUES (?, ?, ?)",
            ("admin", sha256("old-password"), "管理员"),
        )
        conn.commit()
        conn.close()

    @classmethod
    def tearDownClass(cls):
        cls.common.DB_NAME = cls.original_db_name
        cls.temp_dir.cleanup()

    def test_authenticator_setup_login_recovery_lock_and_disable(self):
        from app import _clean_log_value
        from totp_service import totp_code

        self.assertEqual(
            {"totp_code": "***", "code": "***", "password": "***"},
            _clean_log_value(
                {"totp_code": "123456", "code": "ABC123-DEF456", "password": "secret"}
            ),
        )
        self.assertEqual(
            "94287082",
            totp_code(
                "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ",
                for_time=59,
                digits=8,
            ),
        )

        client = self.app.test_client()
        login_response = client.post(
            "/api/login",
            json={"username": "admin", "password": "old-password"},
        )
        self.assertEqual(200, login_response.status_code)
        token = login_response.get_json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        setup_response = client.post(
            "/api/totp/setup",
            headers=headers,
            json={"current_password": "old-password"},
        )
        self.assertEqual(200, setup_response.status_code)
        setup_payload = setup_response.get_json()
        secret = setup_payload["secret"]
        self.assertTrue(setup_payload["otpauth_uri"].startswith("otpauth://totp/"))

        enable_response = client.post(
            "/api/totp/enable",
            headers=headers,
            json={
                "current_password": "old-password",
                "code": totp_code(secret),
            },
        )
        self.assertEqual(200, enable_response.status_code)
        recovery_codes = enable_response.get_json()["recovery_codes"]
        self.assertEqual(10, len(recovery_codes))

        conn = sqlite3.connect(self.common.DB_NAME)
        stored_secret, stored_recovery_codes = conn.execute(
            "SELECT totp_secret, totp_recovery_codes FROM admins WHERE username = 'admin'"
        ).fetchone()
        conn.close()
        self.assertEqual(secret, stored_secret)
        self.assertTrue(all(code not in stored_recovery_codes for code in recovery_codes))

        required_response = client.post(
            "/api/login",
            json={"username": "admin", "password": "old-password"},
        )
        self.assertEqual(401, required_response.status_code)
        self.assertEqual("AUTH_TOTP_REQUIRED", required_response.get_json()["code"])

        for attempt in range(5):
            invalid_response = client.post(
                "/api/login",
                json={
                    "username": "admin",
                    "password": "old-password",
                    "totp_code": "000000",
                },
            )
            expected_status = 429 if attempt == 4 else 401
            self.assertEqual(expected_status, invalid_response.status_code)
        self.assertEqual("AUTH_TOTP_LOCKED", invalid_response.get_json()["code"])

        locked_response = client.post(
            "/api/login",
            json={
                "username": "admin",
                "password": "old-password",
                "totp_code": totp_code(secret),
            },
        )
        self.assertEqual(429, locked_response.status_code)

        conn = sqlite3.connect(self.common.DB_NAME)
        conn.execute(
            "UPDATE admins SET totp_failed_attempts = 0, totp_locked_until = NULL WHERE username = 'admin'"
        )
        conn.commit()
        conn.close()

        totp_login_response = client.post(
            "/api/login",
            json={
                "username": "admin",
                "password": "old-password",
                "totp_code": totp_code(secret),
            },
        )
        self.assertEqual(200, totp_login_response.status_code)

        recovery_login_response = client.post(
            "/api/login",
            json={
                "username": "admin",
                "password": "old-password",
                "totp_code": recovery_codes[0],
            },
        )
        self.assertEqual(200, recovery_login_response.status_code)
        self.assertTrue(recovery_login_response.get_json()["recovery_code_used"])
        self.assertEqual(9, recovery_login_response.get_json()["recovery_codes_remaining"])

        reused_recovery_response = client.post(
            "/api/login",
            json={
                "username": "admin",
                "password": "old-password",
                "totp_code": recovery_codes[0],
            },
        )
        self.assertEqual(401, reused_recovery_response.status_code)
        self.assertEqual("AUTH_TOTP_INVALID", reused_recovery_response.get_json()["code"])

        disable_response = client.post(
            "/api/totp/disable",
            headers=headers,
            json={
                "current_password": "old-password",
                "code": totp_code(secret),
            },
        )
        self.assertEqual(200, disable_response.status_code)

        password_only_response = client.post(
            "/api/login",
            json={"username": "admin", "password": "old-password"},
        )
        self.assertEqual(200, password_only_response.status_code)
        password_only_headers = {
            "Authorization": f"Bearer {password_only_response.get_json()['token']}"
        }
        self.assertEqual(200, client.post("/api/logout", headers=headers).status_code)
        self.assertEqual(200, client.post("/api/logout", headers=password_only_headers).status_code)

    def test_setting_recovery_then_resetting_password_revokes_session(self):
        client = self.app.test_client()
        login_response = client.post(
            "/api/login",
            json={"username": "admin", "password": "old-password"},
        )
        self.assertEqual(200, login_response.status_code)
        token = login_response.get_json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        status_response = client.get("/api/recovery-settings", headers=headers)
        self.assertEqual(200, status_response.status_code)
        self.assertFalse(status_response.get_json()["configured"])

        settings_response = client.put(
            "/api/recovery-settings",
            headers=headers,
            json={
                "current_password": "old-password",
                "security_answer": "safe-answer",
            },
        )
        self.assertEqual(200, settings_response.status_code)
        self.assertTrue(settings_response.get_json()["configured"])

        reset_response = client.post(
            "/api/forgot-password",
            json={
                "username": "admin",
                "answer": "safe-answer",
                "new_password": "new-password",
            },
        )
        self.assertEqual(200, reset_response.status_code)
        self.assertEqual(1, reset_response.get_json()["revoked_sessions"])

        verification_response = client.get("/api/verify-token", headers=headers)
        self.assertEqual(401, verification_response.status_code)
        self.assertEqual("AUTH_SESSION_REVOKED", verification_response.get_json()["code"])

        new_login_response = client.post(
            "/api/login",
            json={"username": "admin", "password": "new-password"},
        )
        self.assertEqual(200, new_login_response.status_code)

    def test_procurement_management_routes_require_authentication(self):
        requests = [
            ("get", "/api/procurements", None),
            ("post", "/api/procurements", {}),
            ("post", "/api/procurements/ai-draft", {}),
            ("post", "/api/repair-records/ai-draft", {}),
            ("put", "/api/procurements/1", {}),
            ("post", "/api/procurements/1/image", None),
            ("put", "/api/procurements/1/images", {}),
            ("delete", "/api/procurements/1", None),
        ]
        client = self.app.test_client()
        for method, path, payload in requests:
            kwargs = {"json": payload} if payload is not None else {}
            response = getattr(client, method)(path, **kwargs)
            self.assertEqual(401, response.status_code, f"{method.upper()} {path}")
            self.assertEqual("AUTH_TOKEN_MISSING", response.get_json()["code"])

    def test_public_procurement_ai_requires_an_active_business_token(self):
        client = self.app.test_client()
        missing_response = client.post(
            "/api/public-entry/procurement/not-a-token/ai-draft",
            json={"text": "灯泡 2 个"},
        )
        self.assertEqual(404, missing_response.status_code)

        conn = sqlite3.connect(self.common.DB_NAME)
        conn.execute(
            """
            INSERT INTO public_entry_links (business_type, token, status)
            VALUES ('procurement', 'disabled-token', 'disabled')
            """
        )
        conn.commit()
        conn.close()
        disabled_response = client.post(
            "/api/public-entry/procurement/disabled-token/ai-draft",
            json={"text": "灯泡 2 个"},
        )
        self.assertEqual(400, disabled_response.status_code)
        self.assertEqual("填写链接已失效", disabled_response.get_json()["error"])

        conn = sqlite3.connect(self.common.DB_NAME)
        conn.execute("DELETE FROM public_entry_links WHERE token = 'disabled-token'")
        conn.commit()
        conn.close()

    def test_public_procurement_multi_item_submission_syncs_inventory_once(self):
        conn = sqlite3.connect(self.common.DB_NAME)
        conn.execute(
            """
            INSERT INTO public_entry_links (business_type, token, status)
            VALUES ('procurement', 'procurement-multi-token', 'active')
            """
        )
        conn.commit()
        conn.close()

        payload = {
            "procurement_date": "2026-07-30",
            "purchase_channel": "线上",
            "payment_person": "测试付款人",
            "total_amount": 36,
            "remarks": "公开多物品采购测试",
            "images": ["/static/uploads/public_entries/procurement/test.png"],
            "items": [
                {
                    "item_name": "公开测试灯泡",
                    "specification": "12W",
                    "quantity": 2,
                    "unit_price": 8,
                    "unit": "个",
                },
                {
                    "item_name": "公开测试开关",
                    "specification": "单开",
                    "quantity": 4,
                    "unit_price": 5,
                    "unit": "个",
                },
            ],
        }
        client = self.app.test_client()
        create_response = client.post(
            "/api/public-entry/procurement/procurement-multi-token/submit",
            json=payload,
            headers={"Idempotency-Key": "procurement-multi-once"},
        )
        self.assertEqual(200, create_response.status_code)

        retry_response = client.post(
            "/api/public-entry/procurement/procurement-multi-token/submit",
            json=payload,
            headers={"Idempotency-Key": "procurement-multi-once"},
        )
        self.assertEqual(200, retry_response.status_code)
        self.assertTrue(retry_response.get_json()["duplicate"])
        self.assertEqual(create_response.get_json()["id"], retry_response.get_json()["id"])

        conn = sqlite3.connect(self.common.DB_NAME)
        records = conn.execute(
            """
            SELECT item_name, quantity, payment_person, purchase_channel,
                   purchase_batch_no, procurement_images, warehouse_item_id
            FROM procurements
            WHERE remarks = '公开多物品采购测试'
            ORDER BY item_name
            """
        ).fetchall()
        stock = dict(
            conn.execute(
                """
                SELECT item_name, quantity
                FROM warehouse_items
                WHERE item_name IN ('公开测试灯泡', '公开测试开关')
                """
            ).fetchall()
        )
        submission_count = conn.execute(
            "SELECT COUNT(*) FROM public_entry_submissions WHERE idempotency_key = 'procurement-multi-once'"
        ).fetchone()[0]
        conn.close()

        self.assertEqual(2, len(records))
        self.assertEqual({"公开测试开关", "公开测试灯泡"}, {row[0] for row in records})
        self.assertTrue(all(row[2] == "测试付款人" for row in records))
        self.assertTrue(all(row[3] == "线上" for row in records))
        self.assertEqual(1, len({row[4] for row in records}))
        self.assertTrue(all("test.png" in row[5] for row in records))
        self.assertTrue(all(row[6] for row in records))
        self.assertEqual(2, stock["公开测试灯泡"])
        self.assertEqual(4, stock["公开测试开关"])
        self.assertEqual(1, submission_count)

    def test_public_repair_ai_requires_an_active_business_token(self):
        client = self.app.test_client()
        missing_response = client.post(
            "/api/public-entry/repair/not-a-token/ai-draft",
            json={"text": "A栋走廊灯坏了"},
        )
        self.assertEqual(404, missing_response.status_code)

        conn = sqlite3.connect(self.common.DB_NAME)
        conn.execute(
            """
            INSERT INTO public_entry_links (business_type, token, status)
            VALUES ('repair', 'repair-ai-token', 'disabled')
            """
        )
        conn.commit()
        conn.close()

        disabled_response = client.post(
            "/api/public-entry/repair/repair-ai-token/ai-draft",
            json={"text": "A栋走廊灯坏了"},
        )
        self.assertEqual(400, disabled_response.status_code)
        self.assertEqual("填写链接已失效", disabled_response.get_json()["error"])

        conn = sqlite3.connect(self.common.DB_NAME)
        conn.execute(
            "UPDATE public_entry_links SET status = 'active' WHERE token = 'repair-ai-token'"
        )
        conn.commit()
        conn.close()
        with patch(
            "public_entry_links_api._generate_repair_ai_draft",
            return_value={"draft": {"description": "走廊灯损坏"}, "model": "test-model"},
        ):
            active_response = client.post(
                "/api/public-entry/repair/repair-ai-token/ai-draft",
                json={"text": "A栋走廊灯坏了"},
            )
        self.assertEqual(200, active_response.status_code)
        self.assertEqual("走廊灯损坏", active_response.get_json()["draft"]["description"])

        conn = sqlite3.connect(self.common.DB_NAME)
        conn.execute("DELETE FROM public_entry_links WHERE token = 'repair-ai-token'")
        conn.commit()
        conn.close()

    def test_public_repair_inventory_is_deducted_and_restored_on_delete(self):
        conn = sqlite3.connect(self.common.DB_NAME)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO public_entry_links (business_type, token, status)
            VALUES ('repair', 'repair-inventory-token', 'active')
            """
        )
        cursor.execute(
            """
            INSERT INTO warehouse_items (item_name, specification, quantity, unit, location)
            VALUES ('测试灯泡', '10W', 10, '个', '测试仓库')
            """
        )
        warehouse_item_id = cursor.lastrowid
        conn.commit()
        conn.close()

        client = self.app.test_client()
        payload = {
            "scope_type": "公共区域",
            "repair_type": "电器维修",
            "description": "更换公共区域灯泡",
            "report_by": "测试人员",
            "inventory_usages": [
                {"warehouse_item_id": warehouse_item_id, "quantity": 2},
            ],
        }

        form_response = client.get("/api/public-entry/repair/repair-inventory-token")
        self.assertEqual(200, form_response.status_code)
        self.assertNotIn("room_options", form_response.get_json())
        self.assertNotIn("tenant_names", form_response.get_json())

        missing_key_response = client.post(
            "/api/public-entry/repair/repair-inventory-token/submit",
            json=payload,
        )
        self.assertEqual(400, missing_key_response.status_code)
        self.assertIn("Idempotency-Key", missing_key_response.get_json()["error"])

        with patch(
            "public_entry_links_api._insert_submission_log",
            side_effect=sqlite3.OperationalError("submission log failed"),
        ):
            failed_log_response = client.post(
                "/api/public-entry/repair/repair-inventory-token/submit",
                json={**payload, "description": "日志失败时必须回滚"},
                headers={"Idempotency-Key": "repair-log-failure"},
            )
        self.assertEqual(500, failed_log_response.status_code)
        conn = sqlite3.connect(self.common.DB_NAME)
        quantity_after_log_failure = conn.execute(
            "SELECT quantity FROM warehouse_items WHERE id = ?",
            (warehouse_item_id,),
        ).fetchone()[0]
        rolled_back_records = conn.execute(
            "SELECT COUNT(*) FROM repair_records WHERE description = '日志失败时必须回滚'"
        ).fetchone()[0]
        conn.close()
        self.assertEqual(10, quantity_after_log_failure)
        self.assertEqual(0, rolled_back_records)

        create_response = client.post(
            "/api/public-entry/repair/repair-inventory-token/submit",
            json=payload,
            headers={"Idempotency-Key": "repair-create-once"},
        )
        self.assertEqual(200, create_response.status_code)
        repair_id = create_response.get_json()["id"]

        retry_response = client.post(
            "/api/public-entry/repair/repair-inventory-token/submit",
            json=payload,
            headers={"Idempotency-Key": "repair-create-once"},
        )
        self.assertEqual(200, retry_response.status_code)
        self.assertTrue(retry_response.get_json()["duplicate"])
        self.assertEqual(repair_id, retry_response.get_json()["id"])

        conn = sqlite3.connect(self.common.DB_NAME)
        quantity = conn.execute(
            "SELECT quantity FROM warehouse_items WHERE id = ?",
            (warehouse_item_id,),
        ).fetchone()[0]
        submission_count = conn.execute(
            "SELECT COUNT(*) FROM public_entry_submissions WHERE idempotency_key = 'repair-create-once'"
        ).fetchone()[0]
        conn.close()
        self.assertEqual(8, quantity)
        self.assertEqual(1, submission_count)

        insufficient_response = client.post(
            "/api/public-entry/repair/repair-inventory-token/submit",
            json={
                **payload,
                "description": "库存不足时不应创建",
                "inventory_usages": [
                    {"warehouse_item_id": warehouse_item_id, "quantity": 9},
                ],
            },
            headers={"Idempotency-Key": "repair-insufficient-stock"},
        )
        self.assertEqual(400, insufficient_response.status_code)
        self.assertIn("库存不足", insufficient_response.get_json()["error"])

        conn = sqlite3.connect(self.common.DB_NAME)
        quantity = conn.execute(
            "SELECT quantity FROM warehouse_items WHERE id = ?",
            (warehouse_item_id,),
        ).fetchone()[0]
        failed_records = conn.execute(
            "SELECT COUNT(*) FROM repair_records WHERE description = '库存不足时不应创建'"
        ).fetchone()[0]
        conn.close()
        self.assertEqual(8, quantity)
        self.assertEqual(0, failed_records)

        login_response = client.post(
            "/api/login",
            json={"username": "admin", "password": "old-password"},
        )
        self.assertEqual(200, login_response.status_code)
        token = login_response.get_json()["token"]
        delete_response = client.delete(
            f"/api/repair-records/{repair_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(200, delete_response.status_code)

        logout_response = client.post(
            "/api/logout",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(200, logout_response.status_code)

        conn = sqlite3.connect(self.common.DB_NAME)
        restored_quantity = conn.execute(
            "SELECT quantity FROM warehouse_items WHERE id = ?",
            (warehouse_item_id,),
        ).fetchone()[0]
        conn.close()
        self.assertEqual(10, restored_quantity)


if __name__ == "__main__":
    unittest.main()
