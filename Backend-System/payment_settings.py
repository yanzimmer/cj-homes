import json
import os
from datetime import datetime

BASE_DIR = os.path.dirname(__file__)
CONFIG_FILE = os.path.join(BASE_DIR, "config", "payment_settings.json")

DEFAULT_SETTINGS = {
    "enabled": False,
    "notify_base_url": "",
    "wechat_enabled": False,
    "wechat_mode": "native",
    "wechat_appid": "",
    "wechat_mchid": "",
    "wechat_api_v3_key": "",
    "wechat_private_key_pem": "",
    "wechat_serial_no": "",
    "wechat_platform_public_key_pem": "",
    "alipay_enabled": False,
    "alipay_mode": "precreate",
    "alipay_app_id": "",
    "alipay_gateway": "https://openapi.alipay.com/gateway.do",
    "alipay_merchant_private_key_pem": "",
    "alipay_public_key_pem": "",
    "updated_at": "",
}


def _clean_text(value):
    return str(value or "").strip()


def _normalize_bool(value):
    return bool(value)


def _normalize_optional_url(value):
    text = _clean_text(value).rstrip("/")
    if not text:
        return ""
    if not (text.startswith("http://") or text.startswith("https://")):
        text = f"https://{text}"
    return text.rstrip("/")


def _normalize_wechat_mode(value):
    text = _clean_text(value).lower()
    return text if text in {"native"} else "native"


def _normalize_alipay_mode(value):
    text = _clean_text(value).lower()
    return text if text in {"precreate"} else "precreate"


def _normalize_gateway(value):
    text = _normalize_optional_url(value)
    return text or DEFAULT_SETTINGS["alipay_gateway"]


def _normalize_settings(data):
    merged = dict(DEFAULT_SETTINGS)
    if isinstance(data, dict):
        merged.update(data)
    merged["enabled"] = _normalize_bool(merged.get("enabled"))
    merged["notify_base_url"] = _normalize_optional_url(merged.get("notify_base_url"))
    merged["wechat_enabled"] = _normalize_bool(merged.get("wechat_enabled"))
    merged["wechat_mode"] = _normalize_wechat_mode(merged.get("wechat_mode"))
    merged["wechat_appid"] = _clean_text(merged.get("wechat_appid"))
    merged["wechat_mchid"] = _clean_text(merged.get("wechat_mchid"))
    merged["wechat_api_v3_key"] = _clean_text(merged.get("wechat_api_v3_key"))
    merged["wechat_private_key_pem"] = str(merged.get("wechat_private_key_pem") or "").strip()
    merged["wechat_serial_no"] = _clean_text(merged.get("wechat_serial_no"))
    merged["wechat_platform_public_key_pem"] = str(merged.get("wechat_platform_public_key_pem") or "").strip()
    merged["alipay_enabled"] = _normalize_bool(merged.get("alipay_enabled"))
    merged["alipay_mode"] = _normalize_alipay_mode(merged.get("alipay_mode"))
    merged["alipay_app_id"] = _clean_text(merged.get("alipay_app_id"))
    merged["alipay_gateway"] = _normalize_gateway(merged.get("alipay_gateway"))
    merged["alipay_merchant_private_key_pem"] = str(merged.get("alipay_merchant_private_key_pem") or "").strip()
    merged["alipay_public_key_pem"] = str(merged.get("alipay_public_key_pem") or "").strip()
    merged["updated_at"] = _clean_text(merged.get("updated_at"))
    return merged


def load_payment_settings():
    data = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    data.update(loaded)
        except Exception:
            data = {}
    return _normalize_settings(data)


def save_payment_settings(data):
    current = load_payment_settings()
    if isinstance(data, dict):
        current.update(data)
    current = _normalize_settings(current)
    current["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(current, f, ensure_ascii=False, indent=2)
    return current


def build_payment_status(settings=None):
    current = settings or load_payment_settings()
    notify_base_url = _clean_text(current.get("notify_base_url"))
    wechat_configured = all(
        [
            _clean_text(current.get("wechat_appid")),
            _clean_text(current.get("wechat_mchid")),
            _clean_text(current.get("wechat_api_v3_key")),
            str(current.get("wechat_private_key_pem") or "").strip(),
            _clean_text(current.get("wechat_serial_no")),
            str(current.get("wechat_platform_public_key_pem") or "").strip(),
            notify_base_url,
        ]
    )
    alipay_configured = all(
        [
            _clean_text(current.get("alipay_app_id")),
            _normalize_gateway(current.get("alipay_gateway")),
            str(current.get("alipay_merchant_private_key_pem") or "").strip(),
            str(current.get("alipay_public_key_pem") or "").strip(),
            notify_base_url,
        ]
    )
    return {
        "enabled": bool(current.get("enabled")),
        "notify_base_url": notify_base_url,
        "wechat": {
            "enabled": bool(current.get("enabled")) and bool(current.get("wechat_enabled")),
            "configured": wechat_configured,
            "mode": current.get("wechat_mode") or "native",
            "reason": "" if wechat_configured else "请完善微信支付商户参数和回调地址",
        },
        "alipay": {
            "enabled": bool(current.get("enabled")) and bool(current.get("alipay_enabled")),
            "configured": alipay_configured,
            "mode": current.get("alipay_mode") or "precreate",
            "reason": "" if alipay_configured else "请完善支付宝商户参数和回调地址",
        },
        "updated_at": current.get("updated_at", ""),
    }


def serialize_payment_settings(settings=None):
    current = settings or load_payment_settings()
    status = build_payment_status(current)
    payload = dict(current)
    payload.update(status)
    return payload

