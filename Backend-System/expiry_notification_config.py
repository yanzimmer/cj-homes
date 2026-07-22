#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import json
import logging
from copy import deepcopy
from datetime import datetime

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
    return _apply_env_overrides(_read_config_raw(), include_secrets=True)


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
    return _apply_env_overrides(_read_config_raw(), include_secrets=False)

def update_config(new_config):
    """更新配置"""
    ensure_config_file()
    try:
        # 读取当前配置
        current_config = _normalize_config_shape(_read_config_raw())
        new_config = _strip_masked_values(new_config)
        
        # 更新配置
        for key, value in new_config.items():
            if isinstance(value, dict) and isinstance(current_config.get(key), dict):
                for sub_key, sub_value in value.items():
                    current_config[key][sub_key] = sub_value
            else:
                current_config[key] = value

        current_config = _normalize_config_shape(current_config)

        # 更新最后修改时间
        current_config["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 写入文件
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(current_config, f, ensure_ascii=False, indent=4)
        
        logger.info("配置已更新")
        return True, current_config
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
