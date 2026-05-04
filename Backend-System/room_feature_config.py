import json
import os

from common import BASE_DIR


ROOM_FEATURE_OPTIONS_FILE = os.path.join(BASE_DIR, "config", "room_feature_options.json")
DEFAULT_ROOM_FEATURE_OPTIONS = [
    "冰箱",
    "抽油烟机",
    "热水器",
    "床",
]


def _normalize_options(values):
    normalized = []
    for value in values or []:
        text = str(value or "").strip()
        if text and text not in normalized:
            normalized.append(text)
    return normalized


def ensure_room_feature_options_file():
    os.makedirs(os.path.dirname(ROOM_FEATURE_OPTIONS_FILE), exist_ok=True)
    if os.path.exists(ROOM_FEATURE_OPTIONS_FILE):
        return
    with open(ROOM_FEATURE_OPTIONS_FILE, "w", encoding="utf-8") as f:
        json.dump({"options": DEFAULT_ROOM_FEATURE_OPTIONS}, f, ensure_ascii=False, indent=2)


def get_room_feature_options():
    ensure_room_feature_options_file()
    try:
        with open(ROOM_FEATURE_OPTIONS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        options = _normalize_options((data or {}).get("options") or [])
        if options:
            return options
    except Exception:
        pass
    return list(DEFAULT_ROOM_FEATURE_OPTIONS)


def save_room_feature_options(options):
    ensure_room_feature_options_file()
    normalized = _normalize_options(options)
    with open(ROOM_FEATURE_OPTIONS_FILE, "w", encoding="utf-8") as f:
        json.dump({"options": normalized}, f, ensure_ascii=False, indent=2)
    return normalized
