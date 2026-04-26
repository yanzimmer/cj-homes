# 该文件负责管理阿里云 OCR 配置、识别次数限制与使用统计。
import json
import os
from typing import Dict

from common import BASE_DIR, connect


OCR_SETTINGS_FILE = os.path.join(BASE_DIR, "config", "ocr_settings.json")
OCR_SETTINGS_DEFAULTS = {
    "access_key_id": "",
    "access_key_secret": "",
    "endpoint": "ocr-api.cn-hangzhou.aliyuncs.com",
    "max_recognitions": 0,
    "updated_at": "",
}


def ensure_ocr_settings_file():
    os.makedirs(os.path.dirname(OCR_SETTINGS_FILE), exist_ok=True)
    if os.path.exists(OCR_SETTINGS_FILE):
        return
    with open(OCR_SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(OCR_SETTINGS_DEFAULTS, f, ensure_ascii=False, indent=2)


def ensure_ocr_usage_schema():
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS ocr_recognition_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT,
            token TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        )
        """
    )
    conn.commit()
    conn.close()


def _clean_text(value):
    return str(value or "").strip()


def _safe_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default


def load_ocr_settings() -> Dict:
    ensure_ocr_settings_file()
    try:
        with open(OCR_SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        merged = dict(OCR_SETTINGS_DEFAULTS)
        if isinstance(data, dict):
            merged.update(data)
        merged["access_key_id"] = _clean_text(merged.get("access_key_id"))
        merged["access_key_secret"] = _clean_text(merged.get("access_key_secret"))
        merged["endpoint"] = _clean_text(merged.get("endpoint")) or OCR_SETTINGS_DEFAULTS["endpoint"]
        merged["max_recognitions"] = max(0, _safe_int(merged.get("max_recognitions"), 0))
        return merged
    except Exception:
        return dict(OCR_SETTINGS_DEFAULTS)


def save_ocr_settings(data) -> Dict:
    ensure_ocr_settings_file()
    payload = dict(OCR_SETTINGS_DEFAULTS)
    payload.update(data or {})
    payload["access_key_id"] = _clean_text(payload.get("access_key_id"))
    payload["access_key_secret"] = _clean_text(payload.get("access_key_secret"))
    payload["endpoint"] = _clean_text(payload.get("endpoint")) or OCR_SETTINGS_DEFAULTS["endpoint"]
    payload["max_recognitions"] = max(0, _safe_int(payload.get("max_recognitions"), 0))
    from datetime import datetime
    payload["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(OCR_SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return payload


def get_ocr_runtime_config() -> Dict:
    settings = load_ocr_settings()
    access_key_id = settings["access_key_id"] or _clean_text(os.getenv("ALIBABA_CLOUD_ACCESS_KEY_ID"))
    access_key_secret = settings["access_key_secret"] or _clean_text(os.getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET"))
    endpoint = settings["endpoint"] or _clean_text(os.getenv("ALIYUN_OCR_ENDPOINT")) or OCR_SETTINGS_DEFAULTS["endpoint"]
    return {
        "access_key_id": access_key_id,
        "access_key_secret": access_key_secret,
        "endpoint": endpoint,
        "max_recognitions": settings["max_recognitions"],
    }


def get_ocr_usage_count() -> int:
    ensure_ocr_usage_schema()
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM ocr_recognition_usage")
    count = int(cur.fetchone()[0] or 0)
    conn.close()
    return count


def build_ocr_status() -> Dict:
    runtime = get_ocr_runtime_config()
    used_count = get_ocr_usage_count()
    max_recognitions = max(0, _safe_int(runtime.get("max_recognitions"), 0))
    configured = bool(runtime["access_key_id"] and runtime["access_key_secret"])
    remaining_count = None if max_recognitions <= 0 else max(0, max_recognitions - used_count)
    enabled = configured and (max_recognitions <= 0 or used_count < max_recognitions)
    reason = ""
    if not configured:
        reason = "管理员未配置阿里云 OCR"
    elif max_recognitions > 0 and used_count >= max_recognitions:
        reason = "身份证识别次数已达上限"
    return {
        "configured": configured,
        "enabled": enabled,
        "used_count": used_count,
        "max_recognitions": max_recognitions,
        "remaining_count": remaining_count,
        "reason": reason,
    }


def record_ocr_usage(source="", token=""):
    ensure_ocr_usage_schema()
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO ocr_recognition_usage (source, token) VALUES (?, ?)",
        (_clean_text(source), _clean_text(token)),
    )
    conn.commit()
    conn.close()
