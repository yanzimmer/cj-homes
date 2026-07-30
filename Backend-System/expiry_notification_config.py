#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import json
import logging
import uuid
from copy import deepcopy
from datetime import datetime
from urllib.parse import urlsplit

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
except Exception:
    pass

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('expiry_notification')

# 配置文件路径（迁移至 config 目录）
CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'config', 'notification_config.json')
BARK_ENDPOINTS_FILE = os.path.join(os.path.dirname(__file__), 'config', 'bark_endpoints.json')
MASKED_VALUE = "********"
NOTIFICATION_SCENES = {"lease_expiry", "rent_reminder"}

DEFAULT_CONFIG = {
    "enabled": True,
    "lease_advance_days": 7,
    "rent_advance_days": 7,
    "advance_days": 7,
    "reminder_count": 1,
    "tenant_notification_methods": ["email"],
    "landlord_notification_methods": ["email"],
    "tenant_notification_scenes": ["lease_expiry"],
    "landlord_notification_scenes": ["lease_expiry"],
    "smtp_config": {
        "server": "",
        "port": 587,
        "username": "",
        "password": "",
        "use_tls": True,
    },
    "sms_config": {
        "secret_id": "",
        "secret_key": "",
        "app_id": "",
        "sign_name": "",
        "tenant_template_id": "",
        "landlord_template_id": "",
        "tenant_template_text": "",
        "landlord_template_text": "",
    },
    "bark_config": {
        "enabled": True,
        "auto_send_enabled": True,
        "send_time": "09:00",
        "lease_expiry_enabled": True,
        "rent_reminder_enabled": True,
        "title": "从江房屋登记系统",
        "group": "房屋提醒",
        "sound": "",
        "icon": "",
        "endpoints": [],
    },
    "tenant_email_config": {
        "sender": "",
        "subject": "",
        "template": "",
        "recipients": [],
    },
    "landlord_email_config": {
        "sender": "",
        "subject": "",
        "template": "",
        "recipients": [],
    },
    "landlords": [],
    "last_updated": "",
}

ENV_FIELD_MAP = {
    ("smtp_config", "server"): ("SMTP_SERVER", str),
    ("smtp_config", "port"): ("SMTP_PORT", int),
    ("smtp_config", "username"): ("SMTP_USERNAME", str),
    ("smtp_config", "password"): ("SMTP_PASSWORD", str),
    ("smtp_config", "use_tls"): ("SMTP_USE_TLS", "bool"),
    ("sms_config", "secret_id"): ("TENCENT_SMS_SECRET_ID", str),
    ("sms_config", "secret_key"): ("TENCENT_SMS_SECRET_KEY", str),
    ("sms_config", "app_id"): ("TENCENT_SMS_APP_ID", str),
    ("sms_config", "sign_name"): ("TENCENT_SMS_SIGN_NAME", str),
    ("sms_config", "tenant_template_id"): ("TENCENT_SMS_TENANT_TEMPLATE_ID", str),
    ("sms_config", "landlord_template_id"): ("TENCENT_SMS_LANDLORD_TEMPLATE_ID", str),
}

SENSITIVE_FIELDS = {
    ("smtp_config", "password"),
    ("sms_config", "secret_id"),
    ("sms_config", "secret_key"),
}

# 默认配置已迁移至 init-scripts/init_notification_config.py

def ensure_config_file():
    """检查配置文件是否存在（不再自动写入默认配置）。"""
    if not os.path.exists(CONFIG_FILE):
        logger.error(f"配置文件不存在: {CONFIG_FILE}，请先运行初始化脚本生成默认配置")
        return False
    return True


def _coerce_env_value(value, caster):
    if caster == "bool":
        return str(value).strip().lower() in {"1", "true", "yes", "on"}
    if caster is int:
        try:
            return int(value)
        except Exception:
            return value
    return str(value)


def _read_config_raw():
    if not os.path.exists(CONFIG_FILE):
        return {}
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"读取配置文件失败: {str(e)}")
        return {}


def _normalize_bark_endpoint(endpoint, index=0):
    if not isinstance(endpoint, dict):
        raise ValueError(f"bark_config.endpoints[{index}] 必须是对象")

    bark_url = str(endpoint.get("bark_url") or "").strip().rstrip("/")
    if not bark_url:
        raise ValueError(f"bark_config.endpoints[{index}].bark_url 不能为空")
    if len(bark_url) > 2048:
        raise ValueError(f"bark_config.endpoints[{index}].bark_url 过长")

    parsed = urlsplit(bark_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"bark_config.endpoints[{index}].bark_url 必须是有效的 HTTP 或 HTTPS 地址")
    if parsed.query or parsed.fragment:
        raise ValueError(f"bark_config.endpoints[{index}].bark_url 不能包含查询参数或片段")

    endpoint_id = str(endpoint.get("id") or "").strip() or uuid.uuid4().hex
    remark = str(endpoint.get("remark") or "").strip()
    if len(endpoint_id) > 64:
        raise ValueError(f"bark_config.endpoints[{index}].id 过长")
    if len(remark) > 80:
        raise ValueError(f"bark_config.endpoints[{index}].remark 不能超过 80 个字符")

    return {
        "id": endpoint_id,
        "remark": remark,
        "bark_url": bark_url,
        "enabled": bool(endpoint.get("enabled", True)),
    }


def normalize_bark_endpoints(endpoints):
    if not isinstance(endpoints, list):
        raise ValueError("bark_config.endpoints 必须是列表")
    normalized = [_normalize_bark_endpoint(item, index) for index, item in enumerate(endpoints)]
    urls = [item["bark_url"] for item in normalized]
    if len(urls) != len(set(urls)):
        raise ValueError("Bark 推送地址不能重复")
    return normalized


def _read_bark_endpoints():
    if not os.path.exists(BARK_ENDPOINTS_FILE):
        return []
    try:
        with open(BARK_ENDPOINTS_FILE, "r", encoding="utf-8") as file:
            payload = json.load(file)
        return normalize_bark_endpoints(payload.get("endpoints", []))
    except Exception as error:
        logger.error("读取 Bark 私密配置失败: %s", error)
        return []


def _write_bark_endpoints(endpoints):
    normalized = normalize_bark_endpoints(endpoints)
    os.makedirs(os.path.dirname(BARK_ENDPOINTS_FILE), exist_ok=True)
    temp_path = f"{BARK_ENDPOINTS_FILE}.tmp"
    with open(temp_path, "w", encoding="utf-8") as file:
        json.dump({"endpoints": normalized}, file, ensure_ascii=False, indent=2)
    os.chmod(temp_path, 0o600)
    os.replace(temp_path, BARK_ENDPOINTS_FILE)
    return normalized


def _attach_bark_endpoints(config):
    merged = deepcopy(config) if isinstance(config, dict) else {}
    bark_config = merged.setdefault("bark_config", {})
    bark_config["endpoints"] = _read_bark_endpoints()
    return merged


def _deep_merge_dict(base, override):
    result = deepcopy(base) if isinstance(base, dict) else {}
    if not isinstance(override, dict):
        return result
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge_dict(result[key], value)
        else:
            result[key] = value
    return result


def _normalize_config_shape(config):
    raw_config = config if isinstance(config, dict) else {}
    merged = _deep_merge_dict(DEFAULT_CONFIG, raw_config)

    legacy_advance_days = merged.get("advance_days")
    try:
        legacy_days = int(legacy_advance_days)
    except Exception:
        legacy_days = 7

    if "lease_advance_days" not in raw_config:
        merged["lease_advance_days"] = legacy_days
    if "rent_advance_days" not in raw_config:
        merged["rent_advance_days"] = legacy_days
    merged["advance_days"] = merged["lease_advance_days"]

    if "notification_methods" in merged:
        merged.setdefault("tenant_notification_methods", merged.get("notification_methods") or [])
        merged.setdefault("landlord_notification_methods", merged.get("notification_methods") or [])

    tenant_scenes = [
        item for item in (merged.get("tenant_notification_scenes", []) or [])
        if item in NOTIFICATION_SCENES
    ]
    landlord_scenes = [
        item for item in (merged.get("landlord_notification_scenes", []) or [])
        if item in NOTIFICATION_SCENES
    ]

    if "tenant_notification_scenes" in raw_config:
        merged["tenant_notification_scenes"] = tenant_scenes
    else:
        merged["tenant_notification_scenes"] = tenant_scenes or ["lease_expiry"]

    if "landlord_notification_scenes" in raw_config:
        merged["landlord_notification_scenes"] = landlord_scenes
    else:
        merged["landlord_notification_scenes"] = landlord_scenes or ["lease_expiry"]
    return merged


def _has_explicit_config_value(config, section, field):
    if not isinstance(config, dict):
        return False
    section_value = config.get(section)
    if not isinstance(section_value, dict):
        return False
    return field in section_value


def _apply_env_overrides(config, include_secrets=False):
    raw_config = config if isinstance(config, dict) else {}
    merged = _normalize_config_shape(raw_config)
    for (section, field), (env_name, caster) in ENV_FIELD_MAP.items():
        if _has_explicit_config_value(raw_config, section, field):
            continue
        raw = os.getenv(env_name)
        if raw is None or raw == "":
            continue
        merged.setdefault(section, {})
        merged[section][field] = _coerce_env_value(raw, caster)

    if not include_secrets:
        for section, field in SENSITIVE_FIELDS:
            value = merged.get(section, {}).get(field)
            if value:
                merged[section][field] = MASKED_VALUE
    return merged


def get_runtime_config():
    """获取运行时配置，包含从环境变量注入的真实密钥。仅后端内部使用。"""
    return _attach_bark_endpoints(_apply_env_overrides(_read_config_raw(), include_secrets=True))


def _strip_masked_values(value):
    if isinstance(value, dict):
        cleaned = {}
        for key, item in value.items():
            if item == MASKED_VALUE:
                continue
            cleaned[key] = _strip_masked_values(item)
        return cleaned
    if isinstance(value, list):
        return [_strip_masked_values(item) for item in value]
    return value


def get_config():
    """获取当前配置，敏感字段仅返回脱敏占位符。"""
    return _attach_bark_endpoints(_apply_env_overrides(_read_config_raw(), include_secrets=False))

def update_config(new_config):
    """更新配置"""
    ensure_config_file()
    try:
        # 读取当前配置
        current_config = _normalize_config_shape(_read_config_raw())
        new_config = _strip_masked_values(new_config)
        bark_payload = new_config.get("bark_config") if isinstance(new_config.get("bark_config"), dict) else None
        bark_endpoints_provided = bark_payload is not None and "endpoints" in bark_payload
        bark_endpoints = bark_payload.get("endpoints", []) if bark_endpoints_provided else None
        
        # 更新配置
        for key, value in new_config.items():
            if isinstance(value, dict) and isinstance(current_config.get(key), dict):
                for sub_key, sub_value in value.items():
                    current_config[key][sub_key] = sub_value
            else:
                current_config[key] = value

        current_config = _normalize_config_shape(current_config)
        current_config.setdefault("bark_config", {})["endpoints"] = []

        if bark_endpoints_provided:
            _write_bark_endpoints(bark_endpoints)

        # 更新最后修改时间
        current_config["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 写入文件
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(current_config, f, ensure_ascii=False, indent=4)
        
        logger.info("配置已更新")
        return True, get_config()
    except Exception as e:
        logger.error(f"更新配置失败: {str(e)}")
        return False, str(e)

def validate_config(config):
    """验证配置是否有效（支持部分字段更新，缺失字段从现有文件补全）。"""
    # 兼容旧字段名
    if "notification_methods" in config:
        config.setdefault("tenant_notification_methods", config["notification_methods"])
        config.setdefault("landlord_notification_methods", config["notification_methods"])

    current = get_runtime_config()
    config = _strip_masked_values(config)

    # 构建合并视图（不写盘，仅用于校验）
    merged = _normalize_config_shape(_deep_merge_dict(current, config))

    required_fields = [
        "enabled",
        "lease_advance_days",
        "rent_advance_days",
        "reminder_count",
        "tenant_notification_methods",
        "landlord_notification_methods",
        "tenant_notification_scenes",
        "landlord_notification_scenes",
    ]
    missing = [f for f in required_fields if f not in merged]
    if missing:
        return False, f"缺少必填字段: {', '.join(missing)}"

    # 类型校验
    if not isinstance(merged["enabled"], bool):
        return False, "enabled 字段必须是布尔类型"
    if not isinstance(merged["lease_advance_days"], int) or merged["lease_advance_days"] < 0:
        return False, "lease_advance_days 字段必须是非负整数"
    if not isinstance(merged["rent_advance_days"], int) or merged["rent_advance_days"] < 0:
        return False, "rent_advance_days 字段必须是非负整数"
    if not isinstance(merged["reminder_count"], int) or merged["reminder_count"] < 0:
        return False, "reminder_count 字段必须是非负整数"
    if not isinstance(merged["tenant_notification_methods"], list):
        return False, "tenant_notification_methods 字段必须是列表"
    if not isinstance(merged["landlord_notification_methods"], list):
        return False, "landlord_notification_methods 字段必须是列表"
    if not isinstance(merged["tenant_notification_scenes"], list):
        return False, "tenant_notification_scenes 字段必须是列表"
    if not isinstance(merged["landlord_notification_scenes"], list):
        return False, "landlord_notification_scenes 字段必须是列表"
    if any(item not in NOTIFICATION_SCENES for item in merged["tenant_notification_scenes"]):
        return False, "tenant_notification_scenes 包含不支持的提醒场景"
    if any(item not in NOTIFICATION_SCENES for item in merged["landlord_notification_scenes"]):
        return False, "landlord_notification_scenes 包含不支持的提醒场景"

    # SMTP 配置
    if "smtp_config" not in merged or not isinstance(merged["smtp_config"], dict):
        return False, "缺少或不合法的 smtp_config"
    smtp = merged["smtp_config"]
    for field in ["server", "port", "username", "password", "use_tls"]:
        if field not in smtp:
            return False, f"smtp_config.{field} 字段缺失"
    if not isinstance(smtp["port"], int) or smtp["port"] <= 0:
        return False, "smtp_config.port 必须是正整数"
    if not isinstance(smtp["use_tls"], bool):
        return False, "smtp_config.use_tls 必须是布尔类型"

    # 短信配置（可选，若提供需字段完整）
    if "sms_config" in merged:
        sms_config = merged["sms_config"]
        if not isinstance(sms_config, dict):
            return False, "sms_config 字段必须是字典类型"
        for field in [
            "secret_id",
            "secret_key",
            "app_id",
            "sign_name",
            "tenant_template_id",
            "landlord_template_id",
        ]:
            if field not in sms_config:
                return False, f"sms_config.{field} 字段缺失"

    bark_config = merged.get("bark_config")
    if not isinstance(bark_config, dict):
        return False, "bark_config 字段必须是对象"
    if not isinstance(bark_config.get("enabled"), bool):
        return False, "bark_config.enabled 字段必须是布尔类型"
    for field in ["auto_send_enabled", "lease_expiry_enabled", "rent_reminder_enabled"]:
        if not isinstance(bark_config.get(field), bool):
            return False, f"bark_config.{field} 字段必须是布尔类型"
    try:
        datetime.strptime(bark_config.get("send_time", ""), "%H:%M")
    except (TypeError, ValueError):
        return False, "bark_config.send_time 必须是 HH:MM 格式"
    for field in ["title", "group", "sound", "icon"]:
        if not isinstance(bark_config.get(field), str):
            return False, f"bark_config.{field} 字段必须是字符串"
    try:
        normalize_bark_endpoints(bark_config.get("endpoints", []))
    except ValueError as error:
        return False, str(error)

    # 邮件配置
    for cfg_key in ["tenant_email_config", "landlord_email_config"]:
        if cfg_key not in merged or not isinstance(merged[cfg_key], dict):
            return False, f"缺少或不合法的 {cfg_key}"
        email_cfg = merged[cfg_key]
        for f in ["sender", "subject", "template"]:
            if f not in email_cfg:
                return False, f"{cfg_key}.{f} 字段缺失"
        if "recipients" in email_cfg and not isinstance(email_cfg["recipients"], list):
            return False, f"{cfg_key}.recipients 必须是列表类型"

    # 房东信息（可选，若提供需字段完整）
    if "landlords" in merged:
        if not isinstance(merged["landlords"], list):
            return False, "landlords 字段必须是列表类型"
        for i, landlord in enumerate(merged["landlords"]):
            if not isinstance(landlord, dict):
                return False, f"landlords[{i}] 必须是字典类型"
            for field in ["name", "phone", "email"]:
                if field not in landlord:
                    return False, f"landlords[{i}].{field} 字段缺失"

    return True, "配置有效"

# 初始化配置文件
ensure_config_file()

if __name__ == "__main__":
    # 测试配置功能
    print("当前配置:", get_config())
