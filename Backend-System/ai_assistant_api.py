# 该文件负责处理多业务 AI 助手的对话补全、工具调用和语音转文字接口。
import copy
import json
import mimetypes
import os
import uuid
from datetime import date, datetime
from urllib import error as urllib_error
from urllib import request as urllib_request

from flask import Blueprint, jsonify, request

from auth_api import token_required
from common import BASE_DIR, connect


ai_bp = Blueprint("ai_assistant", __name__, url_prefix="/api/ai")

DEFAULT_PROVIDER = os.getenv("AI_PROVIDER", "openai").strip().lower()
AI_SETTINGS_FILE = os.path.join(BASE_DIR, "config", "ai_settings.json")

AI_SETTINGS_DEFAULTS = {
    "provider": DEFAULT_PROVIDER or "openai",
    "base_url": "",
    "chat_completions_url": "",
    "responses_url": "",
    "model": "",
    "api_key": "",
    "transcription_mode": "inherit",
    "transcription_provider": "",
    "transcription_url": "",
    "transcription_model": "",
    "transcription_api_key": "",
    "updated_at": "",
}

ASSISTANT_CONFIGS = {
    "tenant": {
        "label": "租户录入",
        "tool_name": "submit_tenant_info",
        "tool_description": "当且仅当租户录入所需必填信息已经齐全时，调用此函数返回结构化表单数据。",
        "required": [
            "building",
            "room_no",
            "name",
            "gender",
            "id_card",
            "phone",
            "emergency_contact",
            "emergency_phone",
            "check_in_date",
            "check_out_date",
        ],
        "field_labels": {
            "building": "楼栋",
            "room_no": "房间号",
            "name": "姓名",
            "gender": "性别",
            "nation": "民族",
            "birth_date": "出生日期",
            "id_card": "身份证号",
            "address": "住址",
            "phone": "联系电话",
            "emergency_contact": "紧急联系人",
            "emergency_phone": "紧急联系电话",
            "check_in_date": "入住日期",
            "check_out_date": "退房日期",
            "status": "状态",
            "notes": "备注",
        },
        "defaults": {"status": "在住"},
        "context_help": "系统可选房间列表会通过 context.available_rooms 传入，你应优先用它来规范化楼栋和房间号。如果图片中包含身份证正反面，请优先提取姓名、性别、民族、出生日期、身份证号、住址等关键信息。",
        "completion_reply": "我已经帮你整理好了租户信息，你可以直接去租户页面检查并继续保存。",
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "building": {"type": "string", "description": "楼栋，例如 A栋。"},
                "room_no": {"type": "string", "description": "房间号，例如 301 或 A301。"},
                "name": {"type": "string", "description": "租户姓名。"},
                "gender": {"type": "string", "enum": ["男", "女"], "description": "租户性别。"},
                "nation": {"type": "string", "description": "民族。"},
                "birth_date": {"type": "string", "description": "出生日期，格式 YYYY-MM-DD。"},
                "id_card": {"type": "string", "description": "身份证号。"},
                "address": {"type": "string", "description": "住址。"},
                "phone": {"type": "string", "description": "联系电话。"},
                "emergency_contact": {"type": "string", "description": "紧急联系人姓名。"},
                "emergency_phone": {"type": "string", "description": "紧急联系人电话。"},
                "check_in_date": {"type": "string", "description": "入住日期，格式 YYYY-MM-DD。"},
                "check_out_date": {"type": "string", "description": "退房日期，格式 YYYY-MM-DD。"},
                "status": {"type": "string", "enum": ["在住", "已退租"], "description": "租户状态。"},
                "notes": {"type": "string", "description": "备注。"},
            },
        },
    },
    "room": {
        "label": "房间录入",
        "tool_name": "submit_room_info",
        "tool_description": "当房间录入所需信息已经齐全时，调用此函数返回结构化房间表单数据。",
        "required": ["building", "room_no", "room_type", "price"],
        "field_labels": {
            "building": "楼栋",
            "room_no": "房间号",
            "room_type": "房间类型",
            "price": "价格",
            "deposit": "押金",
            "status": "状态",
            "description": "描述",
        },
        "defaults": {"status": "空闲"},
        "context_help": "你只需收集房间新增所需的字段。楼层会由前端根据房间号自动推断。",
        "completion_reply": "房间信息已经整理好了，你可以直接去房间页面继续确认保存。",
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "building": {"type": "string", "description": "楼栋字母或楼栋名称，例如 A栋。"},
                "room_no": {"type": "string", "description": "房间号数字部分，例如 301。"},
                "room_type": {"type": "string", "description": "房间类型，例如 单间、套间。"},
                "price": {"type": "number", "description": "月租价格。"},
                "deposit": {"type": "number", "description": "押金金额。"},
                "status": {"type": "string", "enum": ["空闲", "已入住"], "description": "房间状态。通常新增默认为空闲。"},
                "description": {"type": "string", "description": "房间描述。"},
            },
        },
    },
    "repair": {
        "label": "维修录入",
        "tool_name": "submit_repair_info",
        "tool_description": "当维修记录录入所需信息已经齐全时，调用此函数返回结构化维修表单数据。",
        "required": ["building", "room_no", "repair_type", "description", "report_by"],
        "field_labels": {
            "building": "楼栋",
            "room_no": "房间号",
            "repair_type": "维修类型",
            "description": "问题描述",
            "report_by": "报修人",
            "report_date": "报修日期",
            "status": "状态",
            "repair_date": "维修日期",
            "repair_cost": "维修费用",
            "repair_person": "维修人员",
            "remarks": "备注",
        },
        "defaults": {"status": "待处理"},
        "context_help": "如果用户没有单独提供报修日期，默认使用今天。系统可选房间列表会通过 context.available_rooms 传入。",
        "completion_reply": "维修记录信息已经整理好了，你可以去维修记录页面继续确认保存。",
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "building": {"type": "string", "description": "楼栋，例如 A栋。"},
                "room_no": {"type": "string", "description": "房间号，例如 301。"},
                "repair_type": {"type": "string", "description": "维修类型，例如 水电维修、家具维修、电器维修、其他。"},
                "description": {"type": "string", "description": "问题描述。"},
                "report_by": {"type": "string", "description": "报修人姓名。"},
                "report_date": {"type": "string", "description": "报修日期，格式 YYYY-MM-DD。"},
                "status": {"type": "string", "enum": ["待处理", "处理中", "已完成"], "description": "状态。"},
                "repair_date": {"type": "string", "description": "维修日期，格式 YYYY-MM-DD。"},
                "repair_cost": {"type": "number", "description": "维修费用。"},
                "repair_person": {"type": "string", "description": "维修人员。"},
                "remarks": {"type": "string", "description": "备注。"},
            },
        },
    },
    "procurement": {
        "label": "采购录入",
        "tool_name": "submit_procurement_info",
        "tool_description": "当采购记录录入所需信息已经齐全时，调用此函数返回结构化采购表单数据。",
        "required": ["procurement_date", "item_name", "quantity", "unit_price", "unit", "total_amount"],
        "field_labels": {
            "procurement_date": "采购日期",
            "item_name": "采购项目",
            "specification": "规格",
            "quantity": "数量",
            "unit_price": "单价",
            "unit": "单位",
            "total_amount": "总金额",
            "remarks": "备注",
        },
        "defaults": {},
        "context_help": "如果用户提供了数量和单价但没有总金额，你可以帮用户计算 total_amount = quantity * unit_price。",
        "completion_reply": "采购信息已经整理好了，你可以去采购页面继续确认保存。",
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "procurement_date": {"type": "string", "description": "采购日期，格式 YYYY-MM-DD。"},
                "item_name": {"type": "string", "description": "采购项目名称。"},
                "specification": {"type": "string", "description": "规格型号。"},
                "quantity": {"type": "number", "description": "数量。"},
                "unit_price": {"type": "number", "description": "单价。"},
                "unit": {"type": "string", "description": "单位，例如 个、箱、米。"},
                "total_amount": {"type": "number", "description": "总金额。"},
                "remarks": {"type": "string", "description": "备注。"},
            },
        },
    },
    "warehouse": {
        "label": "库存物资录入",
        "tool_name": "submit_warehouse_item_info",
        "tool_description": "当库存物资录入所需信息已经齐全时，调用此函数返回结构化库存表单数据。",
        "required": ["item_name", "quantity"],
        "field_labels": {
            "item_name": "物资名称",
            "category": "分类",
            "quantity": "库存数量",
            "unit": "单位",
            "location": "存放位置",
            "remarks": "备注",
        },
        "defaults": {},
        "context_help": "如果用户只提供了最基本的物资名称和库存数量，也可以调用工具；其余字段可选。",
        "completion_reply": "库存物资信息已经整理好了，你可以去库存页面继续确认保存。",
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "item_name": {"type": "string", "description": "物资名称。"},
                "category": {"type": "string", "description": "分类。"},
                "quantity": {"type": "number", "description": "库存数量。"},
                "unit": {"type": "string", "description": "单位。"},
                "location": {"type": "string", "description": "存放位置。"},
                "remarks": {"type": "string", "description": "备注。"},
            },
        },
    },
    "move": {
        "label": "搬迁录入",
        "tool_name": "submit_move_info",
        "tool_description": "当搬迁记录所需关键信息已经齐全时，调用此函数返回结构化搬迁表单数据。",
        "required": ["move_type", "to_room", "reason"],
        "field_labels": {
            "move_type": "搬迁方式",
            "tenant_name": "租户姓名",
            "from_room": "原房间",
            "from_room_whole": "整间搬迁原房间",
            "to_room": "新房间",
            "reason": "搬迁原因",
        },
        "defaults": {"move_type": 1},
        "context_help": "如果是选择租户搬迁，优先收集 tenant_name；如果是整间搬迁，优先收集 from_room_whole。搬迁方式中 1 表示选择租户搬迁，2 表示整间搬迁。",
        "completion_reply": "搬迁信息已经整理好了，你可以去搬迁页面继续确认提交。",
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "move_type": {"type": "integer", "enum": [1, 2], "description": "搬迁方式：1=选择租户搬迁，2=整间搬迁。"},
                "tenant_name": {"type": "string", "description": "租户姓名，选择租户搬迁时使用。"},
                "from_room": {"type": "string", "description": "原房间，选择租户搬迁时可辅助匹配。"},
                "from_room_whole": {"type": "string", "description": "原房间，整间搬迁时使用。"},
                "to_room": {"type": "string", "description": "新房间。"},
                "reason": {"type": "string", "description": "搬迁原因。"},
            },
        },
    },
    "contract_template": {
        "label": "合同模板录入",
        "tool_name": "submit_contract_template_info",
        "tool_description": "当合同模板的基础信息已经齐全时，调用此函数返回结构化合同模板草稿。",
        "required": ["name", "content_html"],
        "field_labels": {
            "name": "合同名称",
            "description": "合同说明",
            "content_html": "合同内容",
            "default_landlord": "默认甲方",
        },
        "defaults": {},
        "context_help": "合同模板是富文本内容。如果用户只说“生成一个标准租房合同模板”，你应直接产出可保存的中文 HTML 内容。内容应包含甲乙双方、房屋信息、租赁期限、租金与押金、违约责任等常见条款，并使用 {{name}}、{{room_no}}、{{start_date}}、{{end_date}}、{{rent}}、{{deposit}}、{{landlord}} 等占位符。",
        "completion_reply": "合同模板草稿已经整理好了，你可以去合同模板页面继续检查和保存。",
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "name": {"type": "string", "description": "合同名称。"},
                "description": {"type": "string", "description": "合同说明。"},
                "content_html": {"type": "string", "description": "HTML 格式的合同内容。"},
                "default_landlord": {"type": "string", "description": "默认甲方/房东名称。"},
            },
        },
    },
}


def _provider_defaults(provider_name):
    provider = (provider_name or "openai").strip().lower()
    if provider in {"doubao", "volcengine", "ark"}:
        return {
            "base_url": "https://ark.cn-beijing.volces.com/api/v3",
            "model": "doubao-seed-2-0-pro-260215",
            "api_key": (os.getenv("AI_API_KEY") or os.getenv("ARK_API_KEY") or os.getenv("VOLCENGINE_API_KEY") or os.getenv("OPENAI_API_KEY") or "").strip(),
            "responses_url": "https://ark.cn-beijing.volces.com/api/v3/responses",
            "transcription_url": "",
            "transcription_model": "",
            "transcription_api_key": (os.getenv("AI_TRANSCRIPTION_API_KEY") or os.getenv("ARK_API_KEY") or os.getenv("VOLCENGINE_API_KEY") or "").strip(),
        }
    if provider == "deepseek":
        return {
            "base_url": "https://api.deepseek.com/v1",
            "model": "deepseek-chat",
            "api_key": (os.getenv("AI_API_KEY") or os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY") or "").strip(),
            "responses_url": "",
            "transcription_url": "",
            "transcription_model": "",
            "transcription_api_key": (os.getenv("AI_TRANSCRIPTION_API_KEY") or os.getenv("OPENAI_API_KEY") or "").strip(),
        }
    if provider in {"qwen", "dashscope", "bailian"}:
        return {
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "model": "qwen-plus",
            "api_key": (os.getenv("AI_API_KEY") or os.getenv("DASHSCOPE_API_KEY") or os.getenv("BAILIAN_API_KEY") or os.getenv("OPENAI_API_KEY") or "").strip(),
            "responses_url": "",
            "transcription_url": "",
            "transcription_model": "",
            "transcription_api_key": (os.getenv("AI_TRANSCRIPTION_API_KEY") or os.getenv("DASHSCOPE_API_KEY") or os.getenv("BAILIAN_API_KEY") or "").strip(),
        }
    return {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "api_key": (os.getenv("AI_API_KEY") or os.getenv("OPENAI_API_KEY") or "").strip(),
        "responses_url": "https://api.openai.com/v1/responses",
        "transcription_url": "https://api.openai.com/v1/audio/transcriptions",
        "transcription_model": "gpt-4o-transcribe",
        "transcription_api_key": (os.getenv("AI_TRANSCRIPTION_API_KEY") or os.getenv("AI_API_KEY") or os.getenv("OPENAI_API_KEY") or "").strip(),
    }


def _ensure_ai_settings_file():
    os.makedirs(os.path.dirname(AI_SETTINGS_FILE), exist_ok=True)
    if os.path.exists(AI_SETTINGS_FILE):
        return
    with open(AI_SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(AI_SETTINGS_DEFAULTS, f, ensure_ascii=False, indent=2)


def _ensure_ai_history_tables():
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assistant_type TEXT NOT NULL,
            title TEXT,
            current_form_json TEXT DEFAULT '{}',
            missing_fields_json TEXT DEFAULT '[]',
            completed INTEGER DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_session_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (session_id) REFERENCES ai_sessions(id) ON DELETE CASCADE
        )
        """
    )
    conn.commit()
    conn.close()


def _build_session_title(assistant_type, messages):
    label = _get_assistant_config(assistant_type)["label"]
    first_user = ""
    for item in messages or []:
        if item.get("role") == "user":
            first_user = _clean_text(item.get("content"))
            break
    if not first_user:
        return label
    text = first_user.replace("\n", " ").strip()
    return text[:40] + ("..." if len(text) > 40 else "")


def _create_ai_session(assistant_type, messages, current_form):
    _ensure_ai_history_tables()
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO ai_sessions (assistant_type, title, current_form_json, missing_fields_json, completed)
        VALUES (?, ?, ?, '[]', 0)
        """,
        (
            assistant_type,
            _build_session_title(assistant_type, messages),
            json.dumps(current_form or {}, ensure_ascii=False),
        ),
    )
    session_id = cur.lastrowid
    conn.commit()
    conn.close()
    return session_id


def _append_ai_session_message(session_id, role, content):
    text = _clean_text(content)
    if not text:
        return
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO ai_session_messages (session_id, role, content)
        VALUES (?, ?, ?)
        """,
        (session_id, role, text),
    )
    cur.execute(
        "UPDATE ai_sessions SET updated_at = datetime('now') WHERE id = ?",
        (session_id,),
    )
    conn.commit()
    conn.close()


def _update_ai_session_state(session_id, current_form, missing_fields, completed):
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE ai_sessions
        SET current_form_json = ?, missing_fields_json = ?, completed = ?, updated_at = datetime('now')
        WHERE id = ?
        """,
        (
            json.dumps(current_form or {}, ensure_ascii=False),
            json.dumps(missing_fields or [], ensure_ascii=False),
            1 if completed else 0,
            session_id,
        ),
    )
    conn.commit()
    conn.close()


def _list_ai_sessions(limit=30):
    _ensure_ai_history_tables()
    conn = connect()
    conn.row_factory = __import__("sqlite3").Row
    cur = conn.cursor()
    cur.execute(
        """
        SELECT s.id, s.assistant_type, s.title, s.completed, s.created_at, s.updated_at,
               (
                 SELECT m.content
                 FROM ai_session_messages m
                 WHERE m.session_id = s.id
                 ORDER BY m.id DESC
                 LIMIT 1
               ) AS last_message
        FROM ai_sessions s
        ORDER BY s.updated_at DESC, s.id DESC
        LIMIT ?
        """,
        (limit,),
    )
    rows = cur.fetchall()
    conn.close()
    return [
        {
            "id": row["id"],
            "assistant_type": row["assistant_type"],
            "title": row["title"] or _get_assistant_config(row["assistant_type"])["label"],
            "completed": bool(row["completed"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "last_message": _clean_text(row["last_message"]),
        }
        for row in rows
    ]


def _get_ai_session_detail(session_id):
    _ensure_ai_history_tables()
    conn = connect()
    conn.row_factory = __import__("sqlite3").Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM ai_sessions WHERE id = ?", (session_id,))
    session_row = cur.fetchone()
    if not session_row:
        conn.close()
        return None
    cur.execute(
        """
        SELECT id, role, content, created_at
        FROM ai_session_messages
        WHERE session_id = ?
        ORDER BY id ASC
        """,
        (session_id,),
    )
    message_rows = cur.fetchall()
    conn.close()
    return {
        "id": session_row["id"],
        "assistant_type": session_row["assistant_type"],
        "title": session_row["title"] or _get_assistant_config(session_row["assistant_type"])["label"],
        "completed": bool(session_row["completed"]),
        "created_at": session_row["created_at"],
        "updated_at": session_row["updated_at"],
        "current_form": json.loads(session_row["current_form_json"] or "{}"),
        "missing_required_fields": json.loads(session_row["missing_fields_json"] or "[]"),
        "messages": [
            {
                "id": row["id"],
                "role": row["role"],
                "content": row["content"],
                "created_at": row["created_at"],
            }
            for row in message_rows
        ],
    }


def _delete_ai_session(session_id):
    _ensure_ai_history_tables()
    conn = connect()
    cur = conn.cursor()
    cur.execute("DELETE FROM ai_session_messages WHERE session_id = ?", (session_id,))
    cur.execute("DELETE FROM ai_sessions WHERE id = ?", (session_id,))
    deleted = cur.rowcount
    conn.commit()
    conn.close()
    return deleted > 0


def _load_ai_settings():
    _ensure_ai_settings_file()
    try:
        with open(AI_SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        merged = dict(AI_SETTINGS_DEFAULTS)
        if isinstance(data, dict):
            merged.update(data)
        return merged
    except Exception:
        return dict(AI_SETTINGS_DEFAULTS)


def _save_ai_settings(data):
    _ensure_ai_settings_file()
    payload = dict(AI_SETTINGS_DEFAULTS)
    payload.update(data or {})
    payload["provider"] = _clean_text(payload.get("provider")) or DEFAULT_PROVIDER or "openai"
    payload["base_url"] = _clean_text(payload.get("base_url"))
    payload["chat_completions_url"] = _clean_text(payload.get("chat_completions_url"))
    payload["responses_url"] = _clean_text(payload.get("responses_url"))
    payload["model"] = _clean_text(payload.get("model"))
    payload["api_key"] = _clean_text(payload.get("api_key"))
    payload["transcription_mode"] = _clean_text(payload.get("transcription_mode")) or "inherit"
    payload["transcription_provider"] = _clean_text(payload.get("transcription_provider"))
    payload["transcription_url"] = _clean_text(payload.get("transcription_url"))
    payload["transcription_model"] = _clean_text(payload.get("transcription_model"))
    payload["transcription_api_key"] = _clean_text(payload.get("transcription_api_key"))
    payload["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(AI_SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return payload


def _resolve_provider_name(name, fallback):
    value = _clean_text(name or fallback).lower()
    return value or "openai"


def _get_chat_runtime_config():
    settings = _load_ai_settings()
    provider = _resolve_provider_name(settings.get("provider"), DEFAULT_PROVIDER)
    defaults = _provider_defaults(provider)
    base_url = (_clean_text(settings.get("base_url")) or os.getenv("AI_BASE_URL") or defaults["base_url"]).strip().rstrip("/")
    chat_url = _clean_text(settings.get("chat_completions_url")) or os.getenv("AI_CHAT_COMPLETIONS_URL") or f"{base_url}/chat/completions"
    responses_url = _clean_text(settings.get("responses_url")) or defaults.get("responses_url") or f"{base_url}/responses"
    model = _clean_text(settings.get("model")) or os.getenv("AI_MODEL") or defaults["model"]
    api_key = _clean_text(settings.get("api_key")) or defaults["api_key"]
    return {
        "provider": provider,
        "chat_url": chat_url.strip(),
        "responses_url": responses_url.strip(),
        "model": model.strip(),
        "api_key": api_key,
    }


def _get_transcription_runtime_config():
    settings = _load_ai_settings()
    mode = _clean_text(settings.get("transcription_mode")) or "inherit"
    provider = _resolve_provider_name(
        settings.get("transcription_provider"),
        settings.get("provider") if mode == "inherit" else DEFAULT_PROVIDER,
    )
    defaults = _provider_defaults(provider)
    url = _clean_text(settings.get("transcription_url"))
    model = _clean_text(settings.get("transcription_model"))
    api_key = _clean_text(settings.get("transcription_api_key"))
    if mode == "inherit":
        url = url or defaults["transcription_url"]
        model = model or defaults["transcription_model"]
        api_key = api_key or _clean_text(settings.get("api_key")) or defaults["transcription_api_key"]
    else:
        url = url or defaults["transcription_url"]
        model = model or defaults["transcription_model"]
        api_key = api_key or defaults["transcription_api_key"]
    return {
        "provider": provider,
        "mode": mode,
        "url": url.strip(),
        "model": model.strip(),
        "api_key": api_key,
    }


def _build_headers(content_type, api_key):
    if not api_key:
        raise RuntimeError("服务端未配置可用的 AI API Key")
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": content_type,
    }


def _post_json(url, payload, api_key):
    req = urllib_request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=_build_headers("application/json", api_key),
        method="POST",
    )
    try:
        with urllib_request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib_error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        lower_detail = detail.lower()
        if "unknown variant `image_url`" in detail or '"unknown variant \\"image_url\\""' in detail or "expected `text`" in detail or "expected \\\"text\\\"" in lower_detail:
            raise RuntimeError("当前厂商/模型不支持图片多模态输入，请在 AI 设置 中切换到支持图片识别的视觉模型。") from exc
        raise RuntimeError(detail or f"AI 请求失败: HTTP {exc.code}") from exc
    except urllib_error.URLError as exc:
        raise RuntimeError(f"AI 网络请求失败: {exc}") from exc


def _extract_responses_output_text(data):
    direct = _clean_text(data.get("output_text"))
    if direct:
        return direct
    texts = []
    for item in data.get("output") or []:
        for content in item.get("content") or []:
            text = _clean_text(content.get("text"))
            if text:
                texts.append(text)
    return "\n".join(texts).strip()


def _encode_multipart_form(fields, files):
    boundary = f"----CodexBoundary{uuid.uuid4().hex}"
    chunks = []
    for name, value in fields.items():
        chunks.extend(
            [
                f"--{boundary}\r\n".encode("utf-8"),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"),
                str(value).encode("utf-8"),
                b"\r\n",
            ]
        )
    for file_item in files:
        chunks.extend(
            [
                f"--{boundary}\r\n".encode("utf-8"),
                (
                    f'Content-Disposition: form-data; name="{file_item["field_name"]}"; filename="{file_item["filename"]}"\r\n'
                    f'Content-Type: {file_item["content_type"]}\r\n\r\n'
                ).encode("utf-8"),
                file_item["content"],
                b"\r\n",
            ]
        )
    chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def _post_multipart(url, fields, files, api_key):
    body, content_type = _encode_multipart_form(fields, files)
    req = urllib_request.Request(
        url,
        data=body,
        headers=_build_headers(content_type, api_key),
        method="POST",
    )
    try:
        with urllib_request.urlopen(req, timeout=90) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib_error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(detail or f"AI 请求失败: HTTP {exc.code}") from exc
    except urllib_error.URLError as exc:
        raise RuntimeError(f"AI 网络请求失败: {exc}") from exc


def _clean_text(value):
    return str(value or "").strip()


def _detect_vision_support(provider, model):
    p = _clean_text(provider).lower()
    m = _clean_text(model).lower()
    if not m:
        return False, "当前未配置模型，暂时无法使用图片识别。"

    if p == "openai":
        if m.startswith("gpt-4o") or m.startswith("gpt-4.1") or m.startswith("gpt-5"):
            return True, ""
        return False, "当前 OpenAI 模型看起来不是视觉模型，请改用支持图片输入的模型。"

    if p in {"qwen", "dashscope", "bailian"}:
        if any(token in m for token in ["vl", "vision", "omni"]):
            return True, ""
        return False, "当前千问模型更像纯文本模型，请改用 Qwen-VL / Vision / Omni 系列后再上传图片。"

    if p == "deepseek":
        if any(token in m for token in ["vl", "vision"]):
            return True, ""
        return False, "当前 DeepSeek 模型更像纯文本模型，请改用支持视觉的模型后再上传图片。"

    if any(token in m for token in ["vl", "vision", "omni", "4o"]):
        return True, ""
    return False, "当前自定义模型是否支持图片输入无法确认，请先切换到明确支持视觉的模型。"


def _has_value(value):
    if value is None:
        return False
    if isinstance(value, str):
        return _clean_text(value) != ""
    return True


def _normalize_messages(raw_messages):
    messages = []
    for item in (raw_messages or [])[-20:]:
        role = _clean_text(item.get("role"))
        content = _clean_text(item.get("content"))
        if role not in {"user", "assistant"} or not content:
            continue
        messages.append({"role": role, "content": content})
    return messages


def _normalize_input_images(raw_images):
    images = []
    for item in (raw_images or [])[:4]:
        if not isinstance(item, dict):
            continue
        data_url = _clean_text(item.get("data_url"))
        name = _clean_text(item.get("name")) or "image"
        if not data_url.startswith("data:image/"):
            continue
        images.append({"name": name, "data_url": data_url})
    return images


def _normalize_context(raw_context):
    context = dict(raw_context or {})
    available_rooms = []
    for item in context.get("available_rooms") or []:
        available_rooms.append(
            {
                "building": _clean_text(item.get("building")),
                "room_no": _clean_text(item.get("room_no")),
                "status": _clean_text(item.get("status")),
                "room_type": _clean_text(item.get("room_type")),
                "price": item.get("price"),
            }
        )
    if available_rooms:
        context["available_rooms"] = available_rooms[:200]
    return context


def _normalize_current_form(form_data):
    result = {}
    for key, value in dict(form_data or {}).items():
        if isinstance(value, str):
            result[key] = _clean_text(value)
        else:
            result[key] = value
    return result


def _get_assistant_config(assistant_type):
    cfg = ASSISTANT_CONFIGS.get((assistant_type or "").strip().lower())
    if not cfg:
        raise KeyError("unsupported assistant type")
    return cfg


def _get_tool_schema(assistant_type):
    cfg = _get_assistant_config(assistant_type)
    schema = {
        "type": "function",
        "function": {
            "name": cfg["tool_name"],
            "description": cfg["tool_description"],
            "strict": True,
            "parameters": copy.deepcopy(cfg["parameters"]),
        },
    }
    schema["function"]["parameters"]["required"] = list(cfg["required"])
    if DEFAULT_PROVIDER != "openai":
        schema["function"].pop("strict", None)
    return schema


def _merge_form_patch(current_form, patch, assistant_type):
    cfg = _get_assistant_config(assistant_type)
    merged = dict(cfg.get("defaults") or {})
    merged.update(current_form or {})
    for key, value in (patch or {}).items():
        if _has_value(value):
            merged[key] = value
    return merged


def _get_missing_required_fields(form_data, assistant_type):
    cfg = _get_assistant_config(assistant_type)
    missing = [field for field in cfg["required"] if not _has_value(form_data.get(field))]
    if assistant_type == "move":
        move_type = int(form_data.get("move_type") or 1)
        if move_type == 1 and not _has_value(form_data.get("tenant_name")):
            missing.append("tenant_name")
        if move_type == 2 and not _has_value(form_data.get("from_room_whole")):
            missing.append("from_room_whole")
    return missing


def _field_label(field_name, assistant_type):
    return _get_assistant_config(assistant_type)["field_labels"].get(field_name, field_name)


def _fallback_question(current_form, assistant_type):
    missing = _get_missing_required_fields(current_form, assistant_type)
    if not missing:
        return "信息已经基本齐全，我已经帮你整理好了。"
    return f"还缺少{_field_label(missing[0], assistant_type)}，请补充一下。"


def _build_assistant_system_prompt(assistant_type, current_form, context):
    cfg = _get_assistant_config(assistant_type)
    today = date.today().isoformat()
    image_hint = ""
    if (context or {}).get("image_count", 0) > 0:
        image_hint = "用户本轮还上传了图片。你必须结合图片内容一起判断和提取信息，不能忽略图片。"
    return (
        f"你是一个{cfg['label']}助理。你的唯一目标是收集足够的信息来调用 {cfg['tool_name']} 函数。"
        "如果用户提供的信息缺失了必填项，你必须以自然、礼貌、简洁的中文向用户提问，引导他们补充缺失的信息。"
        "每次只问一个最重要的问题。不要做多余的寒暄，不要解释工具机制。"
        f"今天的日期是 {today}。所有日期都必须输出为 YYYY-MM-DD。"
        "如果用户给的是相对日期或模糊日期，例如“明年6月”“下个月底”，请结合今天日期推断为最合理的具体日期；"
        "当只给到月份而没有具体日时，默认使用该月最后一天。"
        f"{cfg['context_help']}"
        f"{image_hint}"
        "只有当必填字段足够时才调用工具。"
        f"当前表单已有值如下：{json.dumps(current_form, ensure_ascii=False)}。"
        f"上下文信息如下：{json.dumps(context or {}, ensure_ascii=False)}。"
        f"必填字段为：{', '.join(cfg['required'])}。"
    )


def _build_chat_messages(system_prompt, messages, input_images):
    chat_messages = [{"role": "system", "content": system_prompt}]
    image_payload = [
        {
            "type": "image_url",
            "image_url": {"url": item["data_url"]},
        }
        for item in (input_images or [])
    ]

    for index, item in enumerate(messages):
        is_last = index == len(messages) - 1
        if is_last and item["role"] == "user" and image_payload:
            text_content = item["content"] or "请结合我上传的图片提取并整理信息。"
            chat_messages.append(
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": text_content},
                        *image_payload,
                    ],
                }
            )
        else:
            chat_messages.append(item)
    return chat_messages


def _build_image_extraction_prompt(assistant_type, current_form, context):
    cfg = _get_assistant_config(assistant_type)
    fields = list(cfg.get("field_labels", {}).keys())
    return (
        f"你是一个{cfg['label']}信息抽取助手。"
        "请仅根据用户上传的图片提取尽可能多的结构化字段。"
        "如果某个字段无法从图片中确定，就不要输出该字段。"
        "必须只返回 JSON 对象，不要输出任何解释。"
        "日期统一输出为 YYYY-MM-DD。"
        f"可提取字段集合：{json.dumps(fields, ensure_ascii=False)}。"
        f"当前表单已有值：{json.dumps(current_form, ensure_ascii=False)}。"
        f"上下文信息：{json.dumps(context or {}, ensure_ascii=False)}。"
    )


def _extract_fields_from_images(runtime, assistant_type, current_form, context, input_images):
    if runtime["provider"] not in {"doubao", "volcengine", "ark"}:
        return {}

    prompt = _build_image_extraction_prompt(assistant_type, current_form, context)
    payload = {
        "model": runtime["model"],
        "input": [
            {
                "role": "user",
                "content": [
                    *[
                        {
                            "type": "input_image",
                            "image_url": item["data_url"],
                        }
                        for item in input_images
                    ],
                    {
                        "type": "input_text",
                        "text": prompt,
                    },
                ],
            }
        ],
    }
    response = _post_json(runtime["responses_url"], payload, runtime["api_key"])
    output_text = _extract_responses_output_text(response)
    if not output_text:
        return {}
    try:
        data = json.loads(output_text)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def _post_process_form(assistant_type, merged_form):
    cfg = _get_assistant_config(assistant_type)
    result = dict(cfg.get("defaults") or {})
    result.update(merged_form or {})

    if assistant_type == "repair":
        if not _has_value(result.get("report_date")):
            result["report_date"] = date.today().isoformat()
        if not _has_value(result.get("status")):
            result["status"] = "待处理"

    if assistant_type == "procurement":
        quantity = result.get("quantity")
        unit_price = result.get("unit_price")
        total_amount = result.get("total_amount")
        if _has_value(quantity) and _has_value(unit_price) and not _has_value(total_amount):
            try:
                result["total_amount"] = round(float(quantity) * float(unit_price), 2)
            except Exception:
                pass

    return result


def _validate_ai_settings_payload(data):
    if not isinstance(data, dict):
        return False, "配置格式不正确"
    provider = _clean_text(data.get("provider")).lower()
    if provider not in {"openai", "deepseek", "qwen", "dashscope", "bailian", "doubao", "volcengine", "ark", "custom"}:
        return False, "不支持的 AI 厂商"
    transcription_mode = _clean_text(data.get("transcription_mode")) or "inherit"
    if transcription_mode not in {"inherit", "separate"}:
        return False, "不支持的语音配置模式"
    return True, ""


def _build_test_chat_payload(model):
    return {
        "model": model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": "你是一个连接测试助手。"},
            {"role": "user", "content": "请只回复：ok"},
        ],
    }


@ai_bp.route("/settings", methods=["GET"])
@token_required
def api_get_ai_settings(current_user):
    return jsonify(_load_ai_settings())


@ai_bp.route("/settings", methods=["PUT"])
@token_required
def api_update_ai_settings(current_user):
    data = request.json or {}
    valid, message = _validate_ai_settings_payload(data)
    if not valid:
        return jsonify({"error": message}), 400
    saved = _save_ai_settings(data)
    return jsonify(saved)


@ai_bp.route("/settings/test-chat", methods=["POST"])
@token_required
def api_test_ai_chat(current_user):
    runtime = _get_chat_runtime_config()
    try:
        response = _post_json(runtime["chat_url"], _build_test_chat_payload(runtime["model"]), runtime["api_key"])
    except RuntimeError as exc:
        return jsonify({"success": False, "error": str(exc)}), 502
    message = (((response.get("choices") or [{}])[0]).get("message") or {}).get("content", "")
    return jsonify(
        {
            "success": True,
            "provider": runtime["provider"],
            "model": runtime["model"],
            "reply": _clean_text(message) or "连接成功",
        }
    )


@ai_bp.route("/settings/test-transcription", methods=["POST"])
@token_required
def api_test_ai_transcription(current_user):
    runtime = _get_transcription_runtime_config()
    if not runtime["url"] or not runtime["model"] or not runtime["api_key"]:
        return jsonify(
            {
                "success": False,
                "error": "语音转写配置不完整，请检查转写 URL、模型和 API Key。",
            }
        ), 400
    return jsonify(
        {
            "success": True,
            "provider": runtime["provider"],
            "mode": runtime["mode"],
            "url": runtime["url"],
            "model": runtime["model"],
            "message": "语音转写配置看起来完整，可继续在 AI 助手页实际录音验证。",
        }
    )


@ai_bp.route("/sessions", methods=["GET"])
@token_required
def api_list_ai_sessions(current_user):
    return jsonify({"sessions": _list_ai_sessions()})


@ai_bp.route("/sessions/<int:session_id>", methods=["GET"])
@token_required
def api_get_ai_session(current_user, session_id):
    session = _get_ai_session_detail(session_id)
    if not session:
        return jsonify({"error": "会话不存在"}), 404
    return jsonify({"session": session})


@ai_bp.route("/sessions/<int:session_id>", methods=["DELETE"])
@token_required
def api_delete_ai_session(current_user, session_id):
    ok = _delete_ai_session(session_id)
    if not ok:
        return jsonify({"error": "会话不存在"}), 404
    return jsonify({"message": "会话已删除"})


@ai_bp.route("/assistant/chat", methods=["POST"])
@token_required
def api_assistant_chat(current_user):
    data = request.json or {}
    assistant_type = _clean_text(data.get("assistant_type")).lower()
    if assistant_type not in ASSISTANT_CONFIGS:
        return jsonify({"error": "不支持的 assistant_type"}), 400
    session_id = data.get("session_id")

    messages = _normalize_messages(data.get("messages") or [])
    input_images = _normalize_input_images(data.get("input_images") or [])
    current_form = _normalize_current_form(data.get("current_form") or {})
    context = _normalize_context(data.get("context") or {})
    if not messages and not input_images:
        return jsonify({"error": "缺少对话内容"}), 400
    if not messages and input_images:
        messages = [{"role": "user", "content": "请结合我上传的图片提取并整理信息。"}]

    if session_id is not None:
        try:
            session_id = int(session_id)
        except Exception:
            return jsonify({"error": "session_id 格式不正确"}), 400
        if not _get_ai_session_detail(session_id):
            return jsonify({"error": "会话不存在"}), 404
    else:
        session_id = _create_ai_session(assistant_type, messages, current_form)

    context["image_count"] = len(input_images)
    if input_images:
        context["image_names"] = [item["name"] for item in input_images]

    runtime = _get_chat_runtime_config()
    if input_images:
        vision_supported, vision_message = _detect_vision_support(runtime["provider"], runtime["model"])
        if not vision_supported:
            return jsonify({"error": vision_message}), 400
        try:
            extracted_patch = _extract_fields_from_images(runtime, assistant_type, current_form, context, input_images)
        except RuntimeError as exc:
            return jsonify({"error": str(exc)}), 502
        if extracted_patch:
            current_form = _post_process_form(
                assistant_type,
                _merge_form_patch(current_form, extracted_patch, assistant_type),
            )
    system_prompt = _build_assistant_system_prompt(assistant_type, current_form, context)
    payload = {
        "model": runtime["model"],
        "temperature": 0.2,
        "messages": _build_chat_messages(system_prompt, messages, [] if runtime["provider"] in {"doubao", "volcengine", "ark"} else input_images),
        "tools": [_get_tool_schema(assistant_type)],
        "tool_choice": "auto",
    }

    try:
        response = _post_json(runtime["chat_url"], payload, runtime["api_key"])
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 502

    choice = ((response.get("choices") or [{}])[0]) or {}
    message = choice.get("message") or {}
    tool_calls = message.get("tool_calls") or []

    if tool_calls:
        function_call = tool_calls[0].get("function") or {}
        try:
            form_patch = json.loads(function_call.get("arguments") or "{}")
        except json.JSONDecodeError:
            return jsonify({"error": "AI 返回的工具参数不是合法 JSON"}), 502

        merged_form = _post_process_form(assistant_type, _merge_form_patch(current_form, form_patch, assistant_type))
        missing = _get_missing_required_fields(merged_form, assistant_type)
        latest_user = messages[-1]["content"] if messages else ""
        _append_ai_session_message(session_id, "user", latest_user)
        if missing:
            reply = _fallback_question(merged_form, assistant_type)
            _append_ai_session_message(session_id, "assistant", reply)
            _update_ai_session_state(session_id, merged_form, missing, False)
            return jsonify(
                {
                    "reply": reply,
                    "completed": False,
                    "assistant_type": assistant_type,
                    "session_id": session_id,
                    "form_patch": form_patch,
                    "current_form": merged_form,
                    "missing_required_fields": missing,
                }
            )

        _append_ai_session_message(session_id, "assistant", _get_assistant_config(assistant_type)["completion_reply"])
        _update_ai_session_state(session_id, merged_form, [], True)
        return jsonify(
            {
                "reply": _get_assistant_config(assistant_type)["completion_reply"],
                "completed": True,
                "assistant_type": assistant_type,
                "session_id": session_id,
                "form_patch": form_patch,
                "current_form": merged_form,
                "missing_required_fields": [],
                "tool_name": function_call.get("name"),
            }
        )

    reply = _clean_text(message.get("content")) or _fallback_question(current_form, assistant_type)
    latest_user = messages[-1]["content"] if messages else ""
    _append_ai_session_message(session_id, "user", latest_user)
    _append_ai_session_message(session_id, "assistant", reply)
    _update_ai_session_state(session_id, current_form, _get_missing_required_fields(current_form, assistant_type), False)
    return jsonify(
        {
            "reply": reply,
            "completed": False,
            "assistant_type": assistant_type,
            "session_id": session_id,
            "form_patch": {},
            "current_form": current_form,
            "missing_required_fields": _get_missing_required_fields(current_form, assistant_type),
        }
    )


@ai_bp.route("/assistant/transcribe", methods=["POST"])
@token_required
def api_assistant_transcribe(current_user):
    runtime = _get_transcription_runtime_config()
    if not runtime["url"] or not runtime["model"]:
        return jsonify(
            {
                "error": "当前 AI 提供商未配置语音转写能力，请单独配置 AI_TRANSCRIPTION_URL / AI_TRANSCRIPTION_MODEL / AI_TRANSCRIPTION_API_KEY。"
            }
        ), 400

    audio = request.files.get("audio")
    if audio is None:
        return jsonify({"error": "缺少音频文件"}), 400

    filename = _clean_text(audio.filename) or "recording.webm"
    content = audio.read()
    if not content:
        return jsonify({"error": "音频文件为空"}), 400

    content_type = _clean_text(audio.mimetype) or mimetypes.guess_type(filename)[0] or "application/octet-stream"
    try:
        response = _post_multipart(
            runtime["url"],
            fields={"model": runtime["model"], "language": "zh"},
            files=[
                {
                    "field_name": "file",
                    "filename": filename,
                    "content": content,
                    "content_type": content_type,
                }
            ],
            api_key=runtime["api_key"],
        )
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 502

    text = _clean_text(response.get("text"))
    if not text:
        return jsonify({"error": "语音识别结果为空"}), 502
    return jsonify({"text": text})
