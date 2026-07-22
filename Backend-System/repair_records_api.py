import json
import os
import re
import sqlite3
import uuid
import base64
from datetime import datetime

from flask import Blueprint, jsonify, request

from auth_api import token_required
from ai_client import call_configured_ai, get_active_ai_model
from common import connect, parse_fields_arg, parse_pagination_args, paginate_list, project_fields
from local_ai_settings import load_ai_settings
from inventory_sync_service import (
    _parse_inventory_usages,
    apply_inventory_usage,
    dump_inventory_usages,
    ensure_inventory_sync_schema,
    list_warehouse_stock_options,
    restore_inventory_usage,
    validate_inventory_usages,
)


repair_bp = Blueprint("repair_records", __name__, url_prefix="/api")
MAX_REPAIR_IMAGES = 50
VALID_REPAIR_IMAGE_TYPES = {"before", "after"}
REPAIR_SCOPE_TYPES = {"单个房间", "多个房间", "公共区域", "整层", "整栋", "楼栋"}
REPAIR_TYPES = {"水电维修", "家具维修", "电器维修", "清洁费用", "其他"}
REPAIR_STATUS_VALUES = {"待处理", "处理中", "已完成"}
REPAIR_AI_TIMEOUT_SECONDS = int(os.getenv("REPAIR_AI_TIMEOUT_SECONDS", "120"))


def _clean_text(value):
    return str(value or "").strip()


def _today_text():
    return datetime.now().strftime("%Y-%m-%d")


def _to_float(value, default=0.0):
    try:
        if value is None or str(value).strip() == "":
            return float(default)
        return float(value)
    except Exception:
        return float(default)


def _extract_json_object(text):
    raw = str(text or "").strip()
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.S | re.I).strip()
    raw = re.sub(r"^```(?:json)?", "", raw, flags=re.I).strip()
    raw = re.sub(r"```$", "", raw).strip()
    try:
        return json.loads(raw)
    except Exception:
        pass

    start = raw.find("{")
    if start < 0:
        raise ValueError("AI 未返回 JSON")
    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(raw)):
        ch = raw[index]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(raw[start:index + 1])
    raise ValueError("AI 返回 JSON 不完整")


def _normalize_repair_type(value):
    text = _clean_text(value)
    return text if text in REPAIR_TYPES else "其他"


def _normalize_repair_status(value):
    text = _clean_text(value)
    return text if text in REPAIR_STATUS_VALUES else "待处理"


def _normalize_ai_repair_payload(payload):
    data = payload if isinstance(payload, dict) else {}
    scope_type = _normalize_repair_scope_type(data.get("scope_type"))
    room_nos = _normalize_room_nos_text(data.get("room_nos"), data.get("room_no"))
    room_no = _get_primary_room_no(scope_type, data.get("room_no"), room_nos)

    return {
        "scope_type": scope_type,
        "building": _clean_text(data.get("building")),
        "room_no": room_no,
        "room_nos": room_nos,
        "repair_type": _normalize_repair_type(data.get("repair_type")),
        "description": _clean_text(data.get("description")),
        "report_by": _clean_text(data.get("report_by")),
        "report_date": _clean_text(data.get("report_date")) or _today_text(),
        "status": _normalize_repair_status(data.get("status")),
        "repair_date": _clean_text(data.get("repair_date")),
        "amount": round(_to_float(data.get("amount"), 0), 2),
        "repair_person": _clean_text(data.get("repair_person")),
        "payment_person": _clean_text(data.get("payment_person")),
        "remarks": _clean_text(data.get("remarks")),
    }


def _build_repair_ai_prompt(user_text, image_count):
    today = _today_text()
    return f"""
你是房屋管理系统的维修记录录入助手。用户可能会给你一大段很乱的文字、聊天记录、转述、图片说明或多条消息。请先在脑中整理内容，再提取成一条可保存的维修记录。只返回一个 JSON 对象，不要解释，不要 Markdown。

今天日期：{today}
图片数量：{image_count}

输出 JSON 格式：
{{
  "scope_type": "单个房间",
  "building": "A栋",
  "room_no": "101",
  "room_nos": "",
  "repair_type": "水电维修",
  "description": "问题描述",
  "report_by": "报修人",
  "report_date": "YYYY-MM-DD",
  "status": "待处理",
  "repair_date": "",
  "amount": 0,
  "repair_person": "",
  "payment_person": "",
  "remarks": ""
}}

规则：
- 先整理原文含义，再填字段；不要要求用户按固定格式输入。
- 如果是一大段聊天记录，请忽略问候、重复、无关内容，抓取真正的报修事项。
- 如果同一段里出现多个问题，优先选择最明确、最需要录入的一条维修事项；其他问题可简短放入 remarks。
- description 要整理成简洁、完整的问题描述，不要照抄整段原文。
- 楼栋和房间号可从“A栋301”“A-301”“3楼公共区域”“整栋水管”等自然语言里推断。
- scope_type 只能是：单个房间、多个房间、公共区域、整层、整栋、楼栋；无法判断时用“单个房间”。
- repair_type 只能是：水电维修、家具维修、电器维修、清洁费用、其他；无法判断时用“其他”。
- status 只能是：待处理、处理中、已完成；无法判断时用“待处理”。
- 日期无法判断时 report_date 用今天日期；repair_date 不确定就留空。
- 金额不知道填 0。
- 报修人、维修人员、支付人员只在原文明确出现时填写；不确定就留空。
- 图片如果是报修截图、聊天记录、现场照片、支付截图或手写单据，请识别楼栋、房间、问题、人员、金额、备注。
- 所有数字只用数字，不要单位符号。

用户文字：
{_clean_text(user_text)}
""".strip()

def _call_ollama_generate(prompt, images):
    return call_configured_ai(
        prompt,
        images,
        ollama_model_fallback=os.getenv("REPAIR_AI_MODEL", "qwen2.5vl:3b"),
        timeout_seconds=REPAIR_AI_TIMEOUT_SECONDS,
    )


def ensure_repair_records_schema():
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(repair_records)")
    cols = {row[1] for row in cursor.fetchall()}
    cursor.execute("PRAGMA foreign_key_list(repair_records)")
    repair_fks = cursor.fetchall()
    has_room_fk = any(row[2] == "rooms" and row[3] == "room_no" for row in repair_fks)
    if has_room_fk:
        cursor.execute("PRAGMA foreign_keys = OFF")
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS repair_records__new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                building TEXT,
                room_no TEXT NOT NULL,
                scope_type TEXT DEFAULT '单个房间',
                room_nos TEXT,
                location_text TEXT,
                repair_type TEXT,
                description TEXT,
                report_date DATE,
                report_by TEXT,
                status TEXT DEFAULT '待处理',
                repair_date DATE,
                repair_cost REAL,
                amount REAL,
                repair_person TEXT,
                payment_person TEXT,
                remarks TEXT,
                inventory_usages TEXT,
                repair_image_before TEXT,
                repair_image_after TEXT,
                repair_image TEXT,
                payment_images TEXT
            )
            """
        )
        cursor.execute(
            f"""
            INSERT INTO repair_records__new (
                id, building, room_no, scope_type, room_nos, location_text, repair_type, description,
                report_date, report_by, status, repair_date, repair_cost,
                amount, repair_person, payment_person, remarks, inventory_usages,
                repair_image_before, repair_image_after, repair_image, payment_images
            )
            SELECT
                id,
                building,
                room_no,
                '单个房间',
                room_no,
                '',
                repair_type,
                description,
                report_date,
                report_by,
                status,
                repair_date,
                repair_cost,
                {"amount" if "amount" in cols else "repair_cost"},
                repair_person,
                {"payment_person" if "payment_person" in cols else "''"},
                remarks,
                {"inventory_usages" if "inventory_usages" in cols else "''"},
                {"repair_image_before" if "repair_image_before" in cols else "''"},
                {"repair_image_after" if "repair_image_after" in cols else "''"},
                {"repair_image" if "repair_image" in cols else "''"},
                {"payment_images" if "payment_images" in cols else "''"}
            FROM repair_records
            """
        )
        cursor.execute("DROP TABLE repair_records")
        cursor.execute("ALTER TABLE repair_records__new RENAME TO repair_records")
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute("PRAGMA table_info(repair_records)")
        cols = {row[1] for row in cursor.fetchall()}
    if "repair_image" not in cols:
        cursor.execute("ALTER TABLE repair_records ADD COLUMN repair_image TEXT")
    if "scope_type" not in cols:
        cursor.execute("ALTER TABLE repair_records ADD COLUMN scope_type TEXT DEFAULT '单个房间'")
    if "room_nos" not in cols:
        cursor.execute("ALTER TABLE repair_records ADD COLUMN room_nos TEXT")
    if "location_text" not in cols:
        cursor.execute("ALTER TABLE repair_records ADD COLUMN location_text TEXT")
    if "repair_image_before" not in cols:
        cursor.execute("ALTER TABLE repair_records ADD COLUMN repair_image_before TEXT")
    if "repair_image_after" not in cols:
        cursor.execute("ALTER TABLE repair_records ADD COLUMN repair_image_after TEXT")
    if "amount" not in cols:
        cursor.execute("ALTER TABLE repair_records ADD COLUMN amount REAL")
    if "payment_person" not in cols:
        cursor.execute("ALTER TABLE repair_records ADD COLUMN payment_person TEXT")
    if "payment_images" not in cols:
        cursor.execute("ALTER TABLE repair_records ADD COLUMN payment_images TEXT")
    cursor.execute("UPDATE repair_records SET scope_type = '楼栋' WHERE scope_type = '跨楼栋'")
    cursor.execute("UPDATE repair_records SET scope_type = '单个房间' WHERE scope_type IS NULL OR TRIM(scope_type) = ''")
    cursor.execute("UPDATE repair_records SET room_nos = room_no WHERE (room_nos IS NULL OR TRIM(room_nos) = '') AND room_no IS NOT NULL AND TRIM(room_no) <> ''")
    cursor.execute("UPDATE repair_records SET amount = repair_cost WHERE amount IS NULL AND repair_cost IS NOT NULL")
    conn.commit()
    conn.close()
    ensure_inventory_sync_schema()


def _ensure_repair_upload_dir():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    upload_dir = os.path.join(base_dir, "static", "uploads", "repair_records")
    os.makedirs(upload_dir, exist_ok=True)
    return upload_dir


def _parse_repair_images(value):
    if value is None:
        return []
    text = str(value).strip()
    if text == "":
        return []
    if text.startswith("["):
        try:
            arr = json.loads(text)
            if isinstance(arr, list):
                result = []
                for item in arr:
                    item_text = str(item).strip()
                    if item_text:
                        result.append(item_text)
                return result[:MAX_REPAIR_IMAGES]
        except Exception:
            pass
    return [text]


def _dump_repair_images(images):
    clean = []
    for item in images or []:
        text = str(item).strip()
        if text:
            clean.append(text)
    return json.dumps(clean[:MAX_REPAIR_IMAGES], ensure_ascii=False)


def _extract_images_from_payload(data, list_key, single_key):
    if data is None:
        return None
    if list_key in data:
        raw = data.get(list_key)
        if isinstance(raw, list):
            return _parse_repair_images(json.dumps(raw, ensure_ascii=False))
        return _parse_repair_images(raw)
    if single_key in data:
        return _parse_repair_images(data.get(single_key))
    return None


def _extract_repair_image_fields_from_payload(data):
    before_images = _extract_images_from_payload(data, "repair_images_before", "repair_image_before")
    after_images = _extract_images_from_payload(data, "repair_images_after", "repair_image_after")
    legacy_images = _extract_images_from_payload(data, "repair_images", "repair_image")
    payment_images = _extract_images_from_payload(data, "payment_images", "payment_image")
    return before_images, after_images, legacy_images, payment_images


def _merge_repair_images(*groups):
    merged = []
    seen = set()
    for group in groups:
        if not group:
            continue
        for item in group:
            text = str(item).strip()
            if not text or text in seen:
                continue
            merged.append(text)
            seen.add(text)
            if len(merged) >= MAX_REPAIR_IMAGES:
                return merged
    return merged


def _safe_dir_component(value):
    text = str(value or "").strip()
    if not text:
        return "unknown"
    text = re.sub(r"[\\/:*?\"<>|]+", "_", text)
    text = re.sub(r"\s+", "", text)
    return text or "unknown"


def _normalize_repair_scope_type(value):
    text = str(value or "").strip()
    if text == "跨楼栋":
        return "楼栋"
    return text if text in REPAIR_SCOPE_TYPES else "单个房间"


def _split_room_nos(value):
    if isinstance(value, list):
        items = value
    else:
        items = re.split(r"[\n,，、;；\s]+", str(value or "").strip())
    result = []
    seen = set()
    for item in items:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        result.append(text)
        seen.add(text)
    return result


def _normalize_room_nos_text(value, fallback_room_no=""):
    room_list = _split_room_nos(value)
    if not room_list and str(fallback_room_no or "").strip():
        room_list = [str(fallback_room_no).strip()]
    return "，".join(room_list)


def _get_primary_room_no(scope_type, room_no, room_nos_text):
    room_text = str(room_no or "").strip()
    if room_text:
        return room_text
    room_list = _split_room_nos(room_nos_text)
    if scope_type == "多个房间" and room_list:
        return room_list[0]
    return ""


def _resolve_repair_building(cursor, room_no, fallback_building=""):
    room_text = str(room_no or "").strip()
    fallback_text = str(fallback_building or "").strip()
    if not room_text:
        return fallback_text
    cursor.execute("SELECT building FROM rooms WHERE room_no = ?", (room_text,))
    room = cursor.fetchone()
    if room and room[0]:
        return str(room[0]).strip()
    return fallback_text


def _repair_record_to_dict(row):
    before_images = _parse_repair_images(row[18])
    after_images = _parse_repair_images(row[19])
    legacy_images = _parse_repair_images(row[20])
    payment_images = _parse_repair_images(row[21])
    amount = row[13] if row[13] is not None else row[12]
    inventory_usages = _parse_inventory_usages(row[17])

    # Old data only had repair_image. Keep it visible as "before" by default.
    if not before_images and not after_images and legacy_images:
        before_images = legacy_images[:MAX_REPAIR_IMAGES]

    combined_images = _merge_repair_images(before_images, after_images)
    if not combined_images and legacy_images:
        combined_images = legacy_images[:MAX_REPAIR_IMAGES]

    return {
        "id": row[0],
        "building": row[1],
        "room_no": row[2],
        "scope_type": _normalize_repair_scope_type(row[3]),
        "room_nos": str(row[4] or "").strip(),
        "location_text": str(row[5] or "").strip(),
        "repair_type": row[6],
        "description": row[7],
        "report_date": row[8],
        "report_by": row[9],
        "status": row[10],
        "repair_date": row[11],
        "repair_cost": row[12],
        "amount": amount,
        "repair_person": row[14],
        "payment_person": row[15],
        "remarks": row[16],
        "inventory_usages": inventory_usages,
        "repair_images_before": before_images,
        "repair_image_before": before_images[0] if before_images else "",
        "repair_images_after": after_images,
        "repair_image_after": after_images[0] if after_images else "",
        "repair_images": combined_images,
        "repair_image": combined_images[0] if combined_images else "",
        "payment_images": payment_images,
        "payment_image": payment_images[0] if payment_images else "",
    }


@repair_bp.route("/repair-records/ai-draft", methods=["POST"])
def api_create_repair_ai_draft():
    user_text = ""
    images = []

    if request.content_type and request.content_type.startswith("multipart/form-data"):
        user_text = request.form.get("text") or ""
        for file in request.files.getlist("images"):
            if not file or not file.filename:
                continue
            if not str(file.mimetype or "").startswith("image/"):
                return jsonify({"error": "仅支持图片文件"}), 400
            data = file.read()
            if len(data) > 8 * 1024 * 1024:
                return jsonify({"error": "单张图片请控制在 8MB 以内"}), 400
            images.append(base64.b64encode(data).decode("ascii"))
    else:
        data = request.json or {}
        user_text = data.get("text") or ""
        raw_images = data.get("images") or []
        if isinstance(raw_images, list):
            for item in raw_images[:4]:
                value = str(item or "").strip()
                if value.startswith("data:image/") and "," in value:
                    value = value.split(",", 1)[1]
                if value:
                    images.append(value)

    if not _clean_text(user_text) and not images:
        return jsonify({"error": "请提供文字或图片"}), 400
    if len(images) > 4:
        return jsonify({"error": "最多支持 4 张图片"}), 400

    prompt = _build_repair_ai_prompt(user_text, len(images))
    try:
        result = _call_ollama_generate(prompt, images)
        response_text = result.get("response") or ""
        parsed = _extract_json_object(response_text)
        draft = _normalize_ai_repair_payload(parsed)
        return jsonify({
            "draft": draft,
            "model": result.get("model") or get_active_ai_model(),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 502


@repair_bp.route("/repair-records", methods=["GET"])
@token_required
def api_list_repair_records(current_user):
    q = (request.args.get('q') or request.args.get('search') or '').strip().lower()
    repair_type_filter = (request.args.get('repair_type') or '').strip()
    status_filter = (request.args.get('status') or '').strip()
    sort_by = (request.args.get('sort_by') or '').strip()
    sort_order = (request.args.get('sort_order') or 'desc').strip().lower()

    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            id, building, room_no, scope_type, room_nos, location_text, repair_type, description,
            report_date, report_by, status,
            repair_date, repair_cost, amount, repair_person, payment_person, remarks, inventory_usages,
            repair_image_before, repair_image_after, repair_image, payment_images
        FROM repair_records
        ORDER BY report_date DESC
        """
    )
    rows = cursor.fetchall()
    conn.close()

    records = [_repair_record_to_dict(row) for row in rows]

    if q:
        records = [
            item
            for item in records
            if q in str(item.get('room_no', '')).lower()
            or q in str(item.get('room_nos', '')).lower()
            or q in str(item.get('location_text', '')).lower()
            or q in str(item.get('scope_type', '')).lower()
            or q in str(item.get('building', '')).lower()
            or q in str(item.get('repair_type', '')).lower()
            or q in str(item.get('description', '')).lower()
            or q in str(item.get('report_by', '')).lower()
            or q in str(item.get('remarks', '')).lower()
        ]

    if repair_type_filter:
        records = [item for item in records if str(item.get('repair_type') or '') == repair_type_filter]

    if status_filter:
        records = [item for item in records if str(item.get('status') or '') == status_filter]

    if sort_by in ('id', 'building', 'room_no', 'scope_type', 'repair_type', 'report_date', 'status', 'repair_date', 'repair_cost', 'amount'):
        reverse = sort_order == 'desc'
        records.sort(key=lambda x: x.get(sort_by), reverse=reverse)

    total = len(records)

    page, page_size, paging_enabled = parse_pagination_args(
        request.args,
        default_page=1,
        default_page_size=10,
        max_page_size=200,
    )
    if paging_enabled:
        records, pagination = paginate_list(records, page, page_size)
    else:
        pagination = {
            'page': 1,
            'page_size': total if total > 0 else 0,
            'total': total,
            'total_pages': 1,
        }

    allowed_fields = [
        'id',
        'building',
        'room_no',
        'scope_type',
        'room_nos',
        'location_text',
        'repair_type',
        'description',
        'report_date',
        'report_by',
        'status',
        'repair_date',
        'repair_cost',
        'amount',
        'repair_person',
        'payment_person',
        'remarks',
        'inventory_usages',
        'repair_images_before',
        'repair_image_before',
        'repair_images_after',
        'repair_image_after',
        'repair_images',
        'repair_image',
        'payment_images',
        'payment_image',
    ]
    selected_fields = parse_fields_arg(request.args, allowed_fields)
    records = project_fields(records, selected_fields, always_include=['id'])

    return jsonify({'repair_records': records, 'total': total, 'pagination': pagination})


@repair_bp.route("/repair-records/<int:record_id>", methods=["GET"])
@token_required
def api_get_repair_record(current_user, record_id):
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            id, building, room_no, scope_type, room_nos, location_text, repair_type, description,
            report_date, report_by, status,
            repair_date, repair_cost, amount, repair_person, payment_person, remarks, inventory_usages,
            repair_image_before, repair_image_after, repair_image, payment_images
        FROM repair_records
        WHERE id = ?
        """,
        (record_id,),
    )
    row = cursor.fetchone()
    conn.close()

    if not row:
        return jsonify({"error": f"维修记录 {record_id} 不存在"}), 404

    return jsonify({"repair_record": _repair_record_to_dict(row)})


@repair_bp.route("/repair-records", methods=["POST"])
@token_required
def api_add_repair_record(current_user):
    data = request.json or {}
    required_fields = ["repair_type", "description", "report_by"]

    if not all(k in data for k in required_fields):
        return jsonify({"error": "缺少必要参数", "required": required_fields}), 400

    conn = connect()
    cursor = conn.cursor()

    scope_type = _normalize_repair_scope_type(data.get("scope_type"))
    room_nos_text = _normalize_room_nos_text(data.get("room_nos"), data.get("room_no"))
    room_no = _get_primary_room_no(scope_type, data.get("room_no"), room_nos_text)
    if scope_type == "单个房间" and not room_no:
        conn.close()
        return jsonify({"error": "单个房间维修必须填写房间号"}), 400
    if scope_type == "多个房间" and not room_nos_text:
        conn.close()
        return jsonify({"error": "多个房间维修必须填写房间号"}), 400
    building = _resolve_repair_building(cursor, room_no, data.get("building"))
    report_date = data.get("report_date", datetime.now().strftime("%Y-%m-%d"))
    status = data.get("status", "待处理")
    remarks = data.get("remarks", "")
    amount = data.get("amount")
    if amount in (None, ""):
        amount = data.get("repair_cost")
    payment_person = data.get("payment_person", "")
    inventory_usages = data.get("inventory_usages") or []

    before_images, after_images, legacy_images, payment_images = _extract_repair_image_fields_from_payload(data)
    if before_images is None:
        before_images = legacy_images or []
    if after_images is None:
        after_images = []
    if payment_images is None:
        payment_images = []
    combined_images = _merge_repair_images(before_images, after_images)
    if not combined_images and legacy_images:
        combined_images = legacy_images[:MAX_REPAIR_IMAGES]

    try:
        normalized_usages = validate_inventory_usages(conn, inventory_usages)
        apply_inventory_usage(conn, normalized_usages)
        cursor.execute(
            """
            INSERT INTO repair_records (
                building, room_no, scope_type, room_nos, location_text, repair_type, description,
                report_date, report_by, status,
                repair_date, repair_cost, amount, repair_person, payment_person, remarks, inventory_usages,
                repair_image_before, repair_image_after, repair_image, payment_images
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                building,
                room_no,
                scope_type,
                room_nos_text,
                "",
                data["repair_type"],
                data["description"],
                report_date,
                data["report_by"],
                status,
                data.get("repair_date"),
                amount,
                amount,
                data.get("repair_person"),
                payment_person,
                remarks,
                dump_inventory_usages(normalized_usages),
                _dump_repair_images(before_images),
                _dump_repair_images(after_images),
                _dump_repair_images(combined_images),
                _dump_repair_images(payment_images),
            ),
        )
        record_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return jsonify({"message": "维修记录已添加", "id": record_id, "room_no": room_no})
    except sqlite3.Error as e:
        conn.close()
        return jsonify({"error": str(e)}), 500


@repair_bp.route("/repair-records/<int:record_id>", methods=["PUT"])
@token_required
def api_update_repair_record(current_user, record_id):
    data = request.json or {}
    if not data:
        return jsonify({"error": "缺少更新数据"}), 400

    allowed_fields = [
        "building",
        "room_no",
        "scope_type",
        "room_nos",
        "repair_type",
        "description",
        "report_by",
        "report_date",
        "status",
        "repair_date",
        "repair_cost",
        "amount",
        "repair_person",
        "payment_person",
        "remarks",
        "inventory_usages",
    ]
    update_data = {k: v for k, v in data.items() if k in allowed_fields}

    has_image_fields = any(
        key in data
        for key in [
            "repair_images_before",
            "repair_image_before",
            "repair_images_after",
            "repair_image_after",
            "repair_images",
            "repair_image",
            "payment_images",
            "payment_image",
        ]
    )

    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, repair_image_before, repair_image_after, repair_image, inventory_usages, payment_images, scope_type, room_no, room_nos, location_text, building FROM repair_records WHERE id = ?",
        (record_id,),
    )
    record = cursor.fetchone()
    if not record:
        conn.close()
        return jsonify({"error": f"维修记录 {record_id} 不存在"}), 404

    if "room_no" in update_data:
        update_data["room_no"] = str(update_data.get("room_no") or "").strip()
    if "building" in update_data:
        update_data["building"] = str(update_data.get("building") or "").strip()
    if "scope_type" in update_data:
        update_data["scope_type"] = _normalize_repair_scope_type(update_data.get("scope_type"))
    elif record[6]:
        update_data["scope_type"] = _normalize_repair_scope_type(record[6])
    if "room_nos" in update_data:
        update_data["room_nos"] = _normalize_room_nos_text(update_data.get("room_nos"), update_data.get("room_no", record[7]))
    elif record[8]:
        update_data["room_nos"] = str(record[8] or "").strip()
    scope_type = _normalize_repair_scope_type(update_data.get("scope_type", record[6]))
    room_nos_text = _normalize_room_nos_text(update_data.get("room_nos", record[8]), update_data.get("room_no", record[7]))
    room_no = _get_primary_room_no(scope_type, update_data.get("room_no", record[7]), room_nos_text)
    if scope_type == "单个房间" and not room_no:
        conn.close()
        return jsonify({"error": "单个房间维修必须填写房间号"}), 400
    if scope_type == "多个房间" and not room_nos_text:
        conn.close()
        return jsonify({"error": "多个房间维修必须填写房间号"}), 400
    update_data["scope_type"] = scope_type
    update_data["room_nos"] = room_nos_text
    update_data["room_no"] = room_no
    update_data["building"] = _resolve_repair_building(
        cursor,
        room_no,
        update_data.get("building", record[10]),
    )

    if has_image_fields:
        current_before = _parse_repair_images(record[1])
        current_after = _parse_repair_images(record[2])
        current_legacy = _parse_repair_images(record[3])
        current_payment = _parse_repair_images(record[5])
        if not current_before and not current_after and current_legacy:
            current_before = current_legacy[:MAX_REPAIR_IMAGES]

        before_images, after_images, legacy_images, payment_images = _extract_repair_image_fields_from_payload(data)
        has_new_before = "repair_images_before" in data or "repair_image_before" in data
        has_new_after = "repair_images_after" in data or "repair_image_after" in data
        has_legacy = "repair_images" in data or "repair_image" in data
        has_payment = "payment_images" in data or "payment_image" in data

        if before_images is None:
            before_images = current_before
        if after_images is None:
            after_images = current_after
        if payment_images is None:
            payment_images = current_payment

        # Backward compatibility: old clients only send repair_images/repair_image.
        if has_legacy and not has_new_before and not has_new_after:
            before_images = legacy_images or []
            after_images = []

        combined_images = _merge_repair_images(before_images, after_images)
        if not combined_images and legacy_images:
            combined_images = legacy_images[:MAX_REPAIR_IMAGES]

        update_data["repair_image_before"] = _dump_repair_images(before_images)
        update_data["repair_image_after"] = _dump_repair_images(after_images)
        update_data["repair_image"] = _dump_repair_images(combined_images)
        if has_payment or payment_images != current_payment:
            update_data["payment_images"] = _dump_repair_images(payment_images)

    if "amount" in update_data and "repair_cost" not in update_data:
        update_data["repair_cost"] = update_data["amount"]
    if "repair_cost" in update_data and "amount" not in update_data:
        update_data["amount"] = update_data["repair_cost"]
    old_usages = _parse_inventory_usages(record[4])
    if "inventory_usages" in data:
        normalized_usages = validate_inventory_usages(conn, data.get("inventory_usages") or [])
        restore_inventory_usage(conn, old_usages)
        apply_inventory_usage(conn, normalized_usages)
        update_data["inventory_usages"] = dump_inventory_usages(normalized_usages)

    if not update_data:
        conn.close()
        return jsonify({"error": "没有有效的更新字段"}), 400

    try:
        for key, value in update_data.items():
            cursor.execute(f"UPDATE repair_records SET {key} = ? WHERE id = ?", (value, record_id))
        conn.commit()
        conn.close()
        return jsonify({"message": f"维修记录 {record_id} 已更新"})
    except sqlite3.Error as e:
        conn.close()
        return jsonify({"error": str(e)}), 500


@repair_bp.route("/repair-records/<int:record_id>", methods=["DELETE"])
@token_required
def api_delete_repair_record(current_user, record_id):
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM repair_records WHERE id = ?", (record_id,))
    record = cursor.fetchone()
    if not record:
        conn.close()
        return jsonify({"error": f"维修记录 {record_id} 不存在"}), 404

    try:
        cursor.execute("SELECT inventory_usages FROM repair_records WHERE id = ?", (record_id,))
        usage_row = cursor.fetchone()
        restore_inventory_usage(conn, _parse_inventory_usages(usage_row[0] if usage_row else ""))
        cursor.execute("DELETE FROM repair_records WHERE id = ?", (record_id,))
        conn.commit()
        conn.close()
        return jsonify({"message": f"维修记录 {record_id} 已删除"})
    except sqlite3.Error as e:
        conn.close()
        return jsonify({"error": str(e)}), 500


@repair_bp.route("/repair-records/room/<room_no>", methods=["GET"])
@token_required
def api_get_room_repair_records(current_user, room_no):
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM rooms WHERE room_no = ?", (room_no,))
    room = cursor.fetchone()
    if not room:
        conn.close()
        return jsonify({"error": f"房间 {room_no} 不存在"}), 404

    cursor.execute(
        """
        SELECT
            id, building, room_no, scope_type, room_nos, location_text, repair_type, description,
            report_date, report_by, status,
            repair_date, repair_cost, amount, repair_person, payment_person, remarks, inventory_usages,
            repair_image_before, repair_image_after, repair_image, payment_images
        FROM repair_records
        WHERE room_no = ?
        ORDER BY report_date DESC
        """,
        (room_no,),
    )
    rows = cursor.fetchall()
    conn.close()

    records = [_repair_record_to_dict(row) for row in rows]
    return jsonify({"repair_records": records})


@repair_bp.route("/repair-records/inventory-options", methods=["GET"])
@token_required
def api_list_repair_inventory_options(current_user):
    return jsonify({"items": list_warehouse_stock_options()})


@repair_bp.route("/repair-records/<int:record_id>/image", methods=["POST"])
@token_required
def api_upload_repair_record_image(current_user, record_id):
    if "file" not in request.files:
        return jsonify({"error": "请上传图片文件（字段名 file）"}), 400

    file = request.files["file"]
    if file.filename is None or str(file.filename).strip() == "":
        return jsonify({"error": "文件名无效"}), 400

    image_type = str(request.form.get("type", "before") or "before").strip().lower()
    if image_type not in VALID_REPAIR_IMAGE_TYPES:
        return jsonify({"error": "type 参数必须是 before 或 after"}), 400

    ext = os.path.splitext(str(file.filename))[1].lower()
    if ext == "":
        ext = ".png"
    if ext not in (".png", ".jpg", ".jpeg", ".webp", ".avif"):
        return jsonify({"error": "仅支持 png/jpg/jpeg/webp/avif 图片"}), 400

    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, building, room_no, repair_image_before, repair_image_after, repair_image FROM repair_records WHERE id = ?",
        (record_id,),
    )
    record = cursor.fetchone()
    if not record:
        conn.close()
        return jsonify({"error": f"维修记录 {record_id} 不存在"}), 404

    before_images = _parse_repair_images(record[3])
    after_images = _parse_repair_images(record[4])
    legacy_images = _parse_repair_images(record[5])
    if not before_images and not after_images and legacy_images:
        before_images = legacy_images[:MAX_REPAIR_IMAGES]

    target_images = before_images if image_type == "before" else after_images
    if len(target_images) >= MAX_REPAIR_IMAGES:
        conn.close()
        return jsonify({"error": f"最多仅支持上传 {MAX_REPAIR_IMAGES} 张图片"}), 400

    upload_dir = _ensure_repair_upload_dir()
    room_segment = f"{_safe_dir_component(record[1])}_{_safe_dir_component(record[2])}"
    typed_dir = os.path.join(upload_dir, image_type, room_segment)
    os.makedirs(typed_dir, exist_ok=True)

    unique_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{record_id}_{uuid.uuid4().hex[:8]}{ext}"
    save_path = os.path.join(typed_dir, unique_name)
    file.save(save_path)

    relative_url = f"/static/uploads/repair_records/{image_type}/{room_segment}/{unique_name}".replace("\\", "/")
    target_images.append(relative_url)

    if image_type == "before":
        before_images = target_images
    else:
        after_images = target_images

    combined_images = _merge_repair_images(before_images, after_images)

    try:
        cursor.execute(
            """
            UPDATE repair_records
            SET repair_image_before = ?, repair_image_after = ?, repair_image = ?
            WHERE id = ?
            """,
            (
                _dump_repair_images(before_images),
                _dump_repair_images(after_images),
                _dump_repair_images(combined_images),
                record_id,
            ),
        )
        conn.commit()
        conn.close()
        return jsonify(
            {
                "message": "上传成功",
                "upload_type": image_type,
                "repair_images_before": before_images,
                "repair_image_before": before_images[0] if before_images else "",
                "repair_images_after": after_images,
                "repair_image_after": after_images[0] if after_images else "",
                "repair_images": combined_images,
                "repair_image": combined_images[0] if combined_images else "",
            }
        )
    except sqlite3.Error as e:
        if os.path.exists(save_path):
            os.remove(save_path)
        conn.close()
        return jsonify({"error": str(e)}), 500
