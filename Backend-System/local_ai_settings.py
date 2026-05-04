import json
import os
from datetime import datetime

BASE_DIR = os.path.dirname(__file__)
CONFIG_FILE = os.path.join(BASE_DIR, "config", "ai_settings.json")
ALLOWED_PROCUREMENT_MODELS = ["qwen3.5:4b", "qwen3.5:2b", "qwen3.5:0.8b"]
DEFAULT_SETTINGS = {
    "enabled": True,
    "procurement_model": os.getenv("PROCUREMENT_AI_MODEL", "qwen3.5:4b"),
    "updated_at": "",
}


def _normalize_model(value):
    text = str(value or "").strip()
    return text if text in ALLOWED_PROCUREMENT_MODELS else "qwen3.5:4b"


def load_ai_settings():
    data = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    data.update(loaded)
        except Exception:
            data = {}

    merged = dict(DEFAULT_SETTINGS)
    merged.update(data)
    merged["enabled"] = bool(merged.get("enabled", True))
    merged["procurement_model"] = _normalize_model(merged.get("procurement_model"))
    return merged


def save_ai_settings(data):
    current = load_ai_settings()
    if isinstance(data, dict) and "enabled" in data:
        current["enabled"] = bool(data.get("enabled"))
    if isinstance(data, dict) and "procurement_model" in data:
        current["procurement_model"] = _normalize_model(data.get("procurement_model"))
    current["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(current, f, ensure_ascii=False, indent=2)
    return current
