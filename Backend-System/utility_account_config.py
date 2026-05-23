import json
import os

from common import BASE_DIR, connect


UTILITY_ACCOUNT_OPTIONS_FILE = os.path.join(BASE_DIR, "config", "utility_account_options.json")
DEFAULT_UTILITY_ACCOUNT_OPTIONS = {
    "electricity": [],
    "water": [],
}


def _normalize_options(values):
    normalized = []
    for value in values or []:
        text = str(value or "").strip()
        if text and text not in normalized:
            normalized.append(text)
    return normalized


def _normalize_payload(data):
    payload = data if isinstance(data, dict) else {}
    return {
        "electricity": _normalize_options(payload.get("electricity") or []),
        "water": _normalize_options(payload.get("water") or []),
    }


def ensure_utility_account_options_file():
    os.makedirs(os.path.dirname(UTILITY_ACCOUNT_OPTIONS_FILE), exist_ok=True)
    if os.path.exists(UTILITY_ACCOUNT_OPTIONS_FILE):
        return
    with open(UTILITY_ACCOUNT_OPTIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(DEFAULT_UTILITY_ACCOUNT_OPTIONS, f, ensure_ascii=False, indent=2)


def get_utility_account_options():
    ensure_utility_account_options_file()
    try:
        with open(UTILITY_ACCOUNT_OPTIONS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        normalized = _normalize_payload(data)
        if normalized["electricity"] or normalized["water"]:
            return normalized
    except Exception:
        pass

    conn = connect()
    cursor = conn.cursor()
    try:
      cursor.execute(
          """
          SELECT utility_type, subject
          FROM utility_bills
          WHERE COALESCE(TRIM(subject), '') <> ''
          ORDER BY utility_type, subject COLLATE NOCASE
          """
      )
      discovered = {
          "electricity": [],
          "water": [],
      }
      for utility_type, subject in cursor.fetchall():
          key = str(utility_type or "").strip()
          text = str(subject or "").strip()
          if key in discovered and text and text not in discovered[key]:
              discovered[key].append(text)
      return discovered
    except Exception:
      return dict(DEFAULT_UTILITY_ACCOUNT_OPTIONS)
    finally:
      conn.close()


def save_utility_account_options(options):
    ensure_utility_account_options_file()
    normalized = _normalize_payload(options)
    with open(UTILITY_ACCOUNT_OPTIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(normalized, f, ensure_ascii=False, indent=2)
    return normalized
