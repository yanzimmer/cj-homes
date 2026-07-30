import json
import os
import tempfile
import unittest
from copy import deepcopy
from unittest.mock import patch

import expiry_notification_config as notify_config
import notify_api


class _FakeBarkResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self, size=-1):
        return b'{"code":200,"message":"success"}'


class BarkNotificationTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_config_file = notify_config.CONFIG_FILE
        self.original_endpoints_file = notify_config.BARK_ENDPOINTS_FILE
        notify_config.CONFIG_FILE = os.path.join(self.temp_dir.name, "notification_config.json")
        notify_config.BARK_ENDPOINTS_FILE = os.path.join(self.temp_dir.name, "bark_endpoints.json")
        with open(notify_config.CONFIG_FILE, "w", encoding="utf-8") as file:
            json.dump(deepcopy(notify_config.DEFAULT_CONFIG), file, ensure_ascii=False)

    def tearDown(self):
        notify_config.CONFIG_FILE = self.original_config_file
        notify_config.BARK_ENDPOINTS_FILE = self.original_endpoints_file
        self.temp_dir.cleanup()

    def test_endpoints_are_saved_outside_main_config(self):
        config = deepcopy(notify_config.DEFAULT_CONFIG)
        config["bark_config"]["endpoints"] = [
            {
                "remark": "房东手机",
                "bark_url": "https://bark.example/device-key/",
                "enabled": True,
            }
        ]

        valid, message = notify_config.validate_config(config)
        self.assertTrue(valid, message)
        success, saved = notify_config.update_config(config)
        self.assertTrue(success)
        self.assertEqual("https://bark.example/device-key", saved["bark_config"]["endpoints"][0]["bark_url"])

        with open(notify_config.CONFIG_FILE, "r", encoding="utf-8") as file:
            main_config = json.load(file)
        self.assertEqual([], main_config["bark_config"]["endpoints"])
        self.assertNotIn("device-key", json.dumps(main_config))
        self.assertEqual(0o600, os.stat(notify_config.BARK_ENDPOINTS_FILE).st_mode & 0o777)

    def test_duplicate_and_invalid_urls_are_rejected(self):
        config = deepcopy(notify_config.DEFAULT_CONFIG)
        config["bark_config"]["endpoints"] = [
            {"bark_url": "not-a-url", "enabled": True},
        ]
        valid, message = notify_config.validate_config(config)
        self.assertFalse(valid)
        self.assertIn("HTTP", message)

        config["bark_config"]["endpoints"] = [
            {"bark_url": "https://bark.example/key", "enabled": True},
            {"bark_url": "https://bark.example/key/", "enabled": True},
        ]
        valid, message = notify_config.validate_config(config)
        self.assertFalse(valid)
        self.assertIn("不能重复", message)

    @patch("notify_api.urlopen", return_value=_FakeBarkResponse())
    def test_send_encodes_content_and_returns_no_device_url(self, mocked_urlopen):
        bark_config = {
            "enabled": True,
            "title": "房租提醒",
            "group": "房屋提醒",
            "sound": "",
            "icon": "",
            "endpoints": [
                {
                    "id": "phone-1",
                    "remark": "房东手机",
                    "bark_url": "https://bark.example/device-key",
                    "enabled": True,
                }
            ],
        }
        result = notify_api.send_bark_notification(
            "房租提醒",
            "A-201 本月房租待收",
            bark_config=bark_config,
            force=True,
        )

        self.assertTrue(result["success"])
        self.assertNotIn("bark_url", result["results"][0])
        request_url = mocked_urlopen.call_args.args[0].full_url
        self.assertIn("%E6%88%BF%E7%A7%9F%E6%8F%90%E9%86%92", request_url)
        self.assertIn("group=%E6%88%BF%E5%B1%8B%E6%8F%90%E9%86%92", request_url)


if __name__ == "__main__":
    unittest.main()
