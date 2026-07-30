import base64
import json
import os
import re
import sqlite3
from datetime import date, datetime

from flask import Blueprint, request, jsonify

from aliyun_ocr_utils import aliyun_ocr_is_configured, recognize_cn_id_card
from ai_client import call_configured_ai, get_active_ai_model
from auth_api import token_required
from common import connect, parse_fields_arg, parse_pagination_args, paginate_list, project_fields
from local_ai_settings import load_ai_settings
from ocr_settings import build_ocr_status, record_ocr_usage
from rent_ledger_api import _rebuild_rent_ledger_year
from rooms_api import _compose_room_no, _find_room_by_no, _normalize_building_code
from tenant_stays_service import (
    checkout_current_stay,
    create_tenant_stay,
    ensure_tenant_stays_schema,
    get_current_stay,
    sync_legacy_tenant_from_stay,
)


tenants_bp = Blueprint('tenants', __name__, url_prefix='/api')
SQL_TODAY = "DATE('now','localtime')"
ID_CARD_PATTERN = re.compile(r"^\d{17}[\dXx]$")
TENANT_AI_TIMEOUT_SECONDS = int(os.getenv("TENANT_AI_TIMEOUT_SECONDS", "180"))


def _resolve_room_for_tenant(conn, room_no_input, building_input=''):
    room_no_text = str(room_no_input or '').strip()
    if room_no_text == '':
        return None

    exact = _find_room_by_no(conn, room_no_text)
    if exact:
        return exact

    building_code = _normalize_building_code(building_input)
    if building_code:
        composed = _compose_room_no(building_code, room_no_text)
        exact = _find_room_by_no(conn, composed)
        if exact:
            return exact

    cursor = conn.cursor()
    normalized_digits = ''.join(ch for ch in room_no_text if ch.isdigit())
    if normalized_digits:
        cursor.execute(
            """
            SELECT id, room_no
            FROM rooms
            WHERE REPLACE(REPLACE(UPPER(room_no), '-', ''), '_', '') = ?
            """,
            (f"{building_code}{normalized_digits}" if building_code else normalized_digits,),
        )
        row = cursor.fetchone()
        if row:
            return row

    return None


def _refresh_tenant_statuses(conn):
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE tenants
        SET status = CASE WHEN EXISTS (
                SELECT 1 FROM tenant_stays s
                WHERE s.tenant_id = tenants.id AND s.status = '在住'
            ) THEN '在住' ELSE '已退租' END,
            room_id = COALESCE(
                (SELECT s.room_id FROM tenant_stays s WHERE s.tenant_id = tenants.id AND s.status = '在住' ORDER BY s.id DESC LIMIT 1),
                (SELECT s.room_id FROM tenant_stays s WHERE s.tenant_id = tenants.id ORDER BY s.check_in_date DESC, s.id DESC LIMIT 1)
            ),
            check_in_date = COALESCE(
                (SELECT s.check_in_date FROM tenant_stays s WHERE s.tenant_id = tenants.id AND s.status = '在住' ORDER BY s.id DESC LIMIT 1),
                (SELECT s.check_in_date FROM tenant_stays s WHERE s.tenant_id = tenants.id ORDER BY s.check_in_date DESC, s.id DESC LIMIT 1)
            ),
            check_out_date = COALESCE(
                (SELECT COALESCE(NULLIF(s.actual_check_out_date, ''), s.planned_check_out_date) FROM tenant_stays s WHERE s.tenant_id = tenants.id AND s.status = '在住' ORDER BY s.id DESC LIMIT 1),
                (SELECT COALESCE(NULLIF(s.actual_check_out_date, ''), s.planned_check_out_date) FROM tenant_stays s WHERE s.tenant_id = tenants.id ORDER BY s.check_in_date DESC, s.id DESC LIMIT 1)
            )
        """
    )


def _refresh_room_statuses(conn):
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE rooms
        SET status = CASE
            WHEN EXISTS (
                SELECT 1 FROM tenant_stays s
                WHERE s.room_id = rooms.id
                  AND s.status = '在住'
                  AND DATE('now','localtime') >= DATE(s.check_in_date)
                  AND (
                    COALESCE(TRIM(s.planned_check_out_date), '') = ''
                    OR DATE('now','localtime') <= DATE(s.planned_check_out_date)
                  )
            ) THEN '已入住'
            ELSE '空闲'
        END
        """
    )


def _checkout_tenant(conn, where_clause, params):
    cursor = conn.cursor()
    affected_years = _load_tenant_ledger_years(conn, where_clause, params)
    cursor.execute(
        f"SELECT id FROM tenants WHERE {where_clause} LIMIT 1",
        params,
    )
    row = cursor.fetchone()
    if not row:
        return None
    result = checkout_current_stay(conn, int(row[0]))
    if not result:
        return None
    _, today = result
    _refresh_tenant_statuses(conn)
    _refresh_room_statuses(conn)
    _sync_rent_ledger_years(conn, affected_years)
    return today


def _derive_birth_date_from_id_card(id_card):
    raw = str(id_card or "").strip()
    if not ID_CARD_PATTERN.match(raw):
        return ""
    year = raw[6:10]
    month = raw[10:12]
    day = raw[12:14]
    return f"{year}-{month}-{day}"


def _clean_text(value):
    return str(value or "").strip()


def _parse_amount(value, default_value=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default_value)


def _clean_ai_field(value, placeholders=()):
    text = _clean_text(value)
    if not text:
        return ""
    for placeholder in placeholders:
        if text == placeholder or placeholder in text:
            return ""
    return text


def _today_text():
    return date.today().strftime("%Y-%m-%d")


def _parse_iso_date(value):
    text = _clean_text(value)
    if text == "":
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None


def _collect_lease_years(check_in_date, check_out_date):
    lease_start = _parse_iso_date(check_in_date)
    if not lease_start:
        return set()
    lease_end = _parse_iso_date(check_out_date) or lease_start
    if lease_end < lease_start:
        lease_end = lease_start
    return set(range(lease_start.year, lease_end.year + 1))


def _load_tenant_ledger_years(conn, where_clause, params):
    cursor = conn.cursor()
    cursor.execute(
        f"""
        SELECT s.check_in_date, COALESCE(NULLIF(s.actual_check_out_date, ''), s.planned_check_out_date)
        FROM tenant_stays s
        JOIN tenants t ON t.id = s.tenant_id
        WHERE {where_clause.replace('id_card', 't.id_card').replace('id =', 't.id =')}
        """,
        params,
    )
    years = set()
    for check_in_date, check_out_date in cursor.fetchall():
        years.update(_collect_lease_years(check_in_date, check_out_date))
    return years


def _sync_rent_ledger_years(conn, years):
    for year in sorted(int(year) for year in set(years) if year):
        _rebuild_rent_ledger_year(conn, year)


def _update_current_stay_from_tenant_fields(conn, tenant_id, update_data):
    stay = get_current_stay(conn, tenant_id)
    if not stay:
        return
    assignments = []
    values = []
    field_map = {
        "check_in_date": "check_in_date",
        "check_out_date": "planned_check_out_date",
        "room_id": "room_id",
        "remarks": "remarks",
    }
    for source_field, stay_field in field_map.items():
        if source_field in update_data:
            assignments.append(f"{stay_field} = ?")
            values.append(update_data[source_field])
    if not assignments:
        return
    assignments.append("updated_at = datetime('now','localtime')")
    values.append(int(stay["id"]))
    conn.execute(
        f"UPDATE tenant_stays SET {', '.join(assignments)} WHERE id = ?",
        tuple(values),
    )
    sync_legacy_tenant_from_stay(conn, tenant_id, int(stay["id"]))


def _serialize_stay(row):
    return {
        "id": int(row[0]),
        "tenant_id": int(row[1]),
        "room_id": row[2],
        "room_no": row[3] or "",
        "building": _normalize_building_code(row[4]),
        "check_in_date": row[5] or "",
        "planned_check_out_date": row[6] or "",
        "actual_check_out_date": row[7] or "",
        "rent_amount": round(float(row[8] or 0), 2),
        "rent_unit": row[9] or "月",
        "deposit_amount": round(float(row[10] or 0), 2),
        "status": row[11] or "已退租",
        "remarks": row[12] or "",
        "created_at": row[13] or "",
    }


def _extract_json_object(text):
    raw = _clean_text(text)
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?", "", raw, flags=re.IGNORECASE).strip()
        raw = re.sub(r"```$", "", raw).strip()
    try:
        return json.loads(raw)
    except Exception:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            return json.loads(raw[start:end + 1])
    raise ValueError("AI 未返回有效 JSON")


def _normalize_gender(value):
    text = _clean_text(value)
    if text in ("男", "女"):
        return text
    return "女" if "女" in text else "男"


def _normalize_tenant_status(value):
    text = _clean_text(value)
    return "已退租" if text == "已退租" else "在住"


def _normalize_tenant_ai_payload(data):
    if not isinstance(data, dict):
        data = {}
    id_card = _clean_text(data.get("id_card")).upper()
    birth_date = _clean_text(data.get("birth_date")) or _derive_birth_date_from_id_card(id_card)
    check_in_date = _clean_text(data.get("check_in_date")) or _today_text()
    return {
        "name": _clean_ai_field(data.get("name"), ("姓名",)),
        "gender": _normalize_gender(data.get("gender")),
        "nation": _clean_ai_field(data.get("nation"), ("民族",)) or "汉族",
        "birth_date": birth_date,
        "id_card": id_card,
        "address": _clean_ai_field(data.get("address"), ("身份证地址或住址", "住址")),
        "phone": _clean_ai_field(data.get("phone"), ("联系电话",)),
        "emergency_contact_name": _clean_ai_field(data.get("emergency_contact_name") or data.get("emergency_contact"), ("紧急联系人",)),
        "emergency_contact_phone": _clean_ai_field(data.get("emergency_contact_phone") or data.get("emergency_phone"), ("紧急电话",)),
        "building": _clean_ai_field(data.get("building"), ("楼栋",)),
        "room_no": _clean_ai_field(data.get("room_no"), ("房间号",)),
        "status": _normalize_tenant_status(data.get("status")),
        "check_in_date": check_in_date,
        "check_out_date": _clean_text(data.get("check_out_date")),
        "remarks": _clean_text(data.get("remarks") or data.get("notes")),
    }


def _build_tenant_ai_prompt(user_text, image_count):
    today = _today_text()
    return f"""
你是房屋管理系统的租户录入助手。请从用户文字和图片中提取一条租户记录，只返回一个 JSON 对象，不要解释，不要 Markdown。

今天日期：{today}
图片数量：{image_count}

输出 JSON 格式：
{{
  "name": "姓名",
  "gender": "男",
  "nation": "汉族",
  "birth_date": "YYYY-MM-DD",
  "id_card": "公民身份证号",
  "address": "身份证地址或住址",
  "phone": "联系电话",
  "emergency_contact_name": "紧急联系人",
  "emergency_contact_phone": "紧急电话",
  "building": "A栋",
  "room_no": "301",
  "status": "在住",
  "check_in_date": "YYYY-MM-DD",
  "check_out_date": "",
  "remarks": ""
}}

规则：
- 用户可能输入一大段聊天记录、转述、身份证照片、入住登记截图或手写信息；先整理含义，再提取字段。
- 图片如果是中国居民身份证正面，请识别姓名、性别、民族、出生日期、公民身份证号、住址。
- 身份证号必须尽量只保留 18 位数字或末位 X；无法确认就留空。
- gender 只能是“男”或“女”；无法判断用“男”。
- nation 不要带“族”以外的多余描述；无法判断用“汉族”。
- 日期统一 YYYY-MM-DD；入住日期无法判断时用今天日期；退房日期不确定留空。
- status 只能是“在住”或“已退租”；无法判断用“在住”。
- 房间可从“A栋301”“A-301”“301房”等自然语言推断；room_no 尽量填写系统里常用的房间号文本。
- 电话只保留电话号码文本，不要加说明。
- 不要自动提交，只生成表单草稿需要的 JSON。

用户文字：
{_clean_text(user_text)}
""".strip()


def _build_tenant_ai_prompt_with_ocr(user_text, ocr_fields):
    today = _today_text()
    ocr_json = json.dumps(ocr_fields or {}, ensure_ascii=False)
    return f"""
你是房屋管理系统的租户录入助手。请基于用户文字和已经识别出的 OCR 字段，整理成一条租户记录，只返回一个 JSON 对象，不要解释，不要 Markdown。

今天日期：{today}

OCR 已识别字段（这些字段优先级最高，尤其身份证号不要改写）：
{ocr_json}

输出 JSON 格式：
{{
  "name": "姓名",
  "gender": "男",
  "nation": "汉族",
  "birth_date": "YYYY-MM-DD",
  "id_card": "公民身份证号",
  "address": "身份证地址或住址",
  "phone": "联系电话",
  "emergency_contact_name": "紧急联系人",
  "emergency_contact_phone": "紧急电话",
  "building": "A栋",
  "room_no": "301",
  "status": "在住",
  "check_in_date": "YYYY-MM-DD",
  "check_out_date": "",
  "remarks": ""
}}

规则：
- OCR 已识别出的姓名、性别、民族、出生日期、公民身份证号、住址，优先直接采用，不要随意覆盖。
- 身份证号必须只保留 18 位数字或末位 X；如果 OCR 已给出身份证号，直接使用。
- gender 只能是“男”或“女”；无法判断用 OCR 结果，再不行用“男”。
- nation 无法判断时用 OCR 结果，再不行用“汉族”。
- 日期统一 YYYY-MM-DD；入住日期无法判断时用今天日期；退房日期不确定留空。
- status 只能是“在住”或“已退租”；无法判断用“在住”。
- 房间可从“A栋301”“A-301”“301房”等自然语言推断；room_no 尽量填写系统里常用的房间号文本。
- 电话只保留电话号码文本，不要加说明。
- 不要自动提交，只生成表单草稿需要的 JSON。

用户文字：
{_clean_text(user_text)}
""".strip()


def _merge_tenant_fields_with_ocr(draft, ocr_fields):
    merged = dict(draft or {})
    fields = dict(ocr_fields or {})
    for key in ("name", "gender", "nation", "birth_date", "id_card", "address"):
        value = _clean_text(fields.get(key))
        if value:
            merged[key] = value
    return merged


def _try_recognize_tenant_id_card_from_images(images, current_user):
    if not images:
        return None
    ocr_status = build_ocr_status()
    if not ocr_status.get("configured") or not ocr_status.get("enabled") or not aliyun_ocr_is_configured():
        return None

    for image_base64 in images:
        try:
            image_bytes = base64.b64decode(str(image_base64 or "").strip(), validate=False)
            if not image_bytes:
                continue
            result = recognize_cn_id_card(image_bytes)
            birth_date = result["fields"].get("birth_date") or _derive_birth_date_from_id_card(result["fields"].get("id_card"))
            result["fields"]["birth_date"] = birth_date
            record_ocr_usage(source="tenant_ai_draft", token=current_user.get("username", ""))
            return result
        except Exception:
            continue
    return None


def _call_ollama_generate(prompt, images):
    return call_configured_ai(
        prompt,
        images,
        ollama_model_fallback=os.getenv("TENANT_AI_MODEL", "qwen2.5vl:3b"),
        timeout_seconds=TENANT_AI_TIMEOUT_SECONDS,
    )


@tenants_bp.route('/tenants', methods=['GET'])
@token_required
def api_list_tenants(current_user):
    """
    获取租户列表
    ---
    tags:
      - Tenants
    security:
      - Bearer: []
    responses:
      200:
        description: 成功获取租户列表
        schema:
          type: object
          properties:
            tenants:
              type: array
              items:
                type: object
                properties:
                  id:
                    type: integer
                  name:
                    type: string
                  gender:
                    type: string
                  nation:
                    type: string
                  birth_date:
                    type: string
                  id_card:
                    type: string
                  address:
                    type: string
                  phone:
                    type: string
                  room_no:
                    type: string
                  status:
                    type: string
                    description: 在住/已退租
                  check_in_date:
                    type: string
                  check_out_date:
                    type: string
    """
    ensure_tenant_stays_schema()
    conn = connect()
    cursor = conn.cursor()

    # 尝试进行自动状态更新；若数据库繁忙（锁定），则跳过更新以保证查询可用
    try:
        _refresh_tenant_statuses(conn)
        conn.commit()
    except sqlite3.OperationalError as e:
        if 'locked' in str(e).lower():
            pass
        else:
            conn.close()
            return jsonify({'error': str(e)}), 500

    try:
        _refresh_room_statuses(conn)
        conn.commit()
    except sqlite3.OperationalError as e:
        if 'locked' in str(e).lower():
            pass
        else:
            conn.close()
            return jsonify({'error': str(e)}), 500

    cursor.execute(
        """
        SELECT t.id, t.name, t.gender, t.nation, t.birth_date, t.id_card,
               t.address, t.phone, t.emergency_contact_name, t.emergency_contact_phone, 
               s.check_in_date,
               COALESCE(NULLIF(s.actual_check_out_date, ''), s.planned_check_out_date),
               r.room_no, r.building, t.remarks,
               COALESCE(s.status, t.status), s.id,
               (SELECT COUNT(*) FROM tenant_stays history WHERE history.tenant_id = t.id)
        FROM tenants t
        LEFT JOIN tenant_stays s ON s.id = (
            SELECT current_stay.id
            FROM tenant_stays current_stay
            WHERE current_stay.tenant_id = t.id
            ORDER BY CASE WHEN current_stay.status = '在住' THEN 0 ELSE 1 END,
                     current_stay.check_in_date DESC, current_stay.id DESC
            LIMIT 1
        )
        LEFT JOIN rooms r ON s.room_id = r.id
        ORDER BY r.room_no, t.name
        """
    )
    rows = cursor.fetchall()
    conn.close()

    tenants = []
    for row in rows:
        tenants.append({
            'id': row[0],
            'name': row[1],
            'gender': row[2],
            'nation': row[3],
            'birth_date': row[4],
            'id_card': row[5],
            'address': row[6],
            'phone': row[7],
            'emergency_contact_name': row[8],
            'emergency_contact_phone': row[9],
            'check_in_date': row[10],
            'check_out_date': row[11],
            'room_no': row[12],
            'building': _normalize_building_code(row[13]),
            'remarks': row[14],
            'status': row[15],
            'current_stay_id': row[16],
            'stay_count': int(row[17] or 0),
        })

    q = (request.args.get('q') or request.args.get('search') or '').strip().lower()
    status_filter = (request.args.get('status') or '').strip()
    building_filter = (request.args.get('building') or '').strip()
    room_no_filter = (request.args.get('room_no') or '').strip()
    sort_by = (request.args.get('sort_by') or '').strip()
    sort_order = (request.args.get('sort_order') or 'asc').strip().lower()

    if q:
        tenants = [
            item
            for item in tenants
            if q in str(item.get('name', '')).lower()
            or q in str(item.get('id_card', '')).lower()
            or q in str(item.get('phone', '')).lower()
            or q in str(item.get('room_no', '')).lower()
        ]

    if status_filter:
        tenants = [item for item in tenants if str(item.get('status') or '') == status_filter]

    if building_filter:
        tenants = [item for item in tenants if str(item.get('building') or '') == building_filter]

    if room_no_filter:
        tenants = [item for item in tenants if str(item.get('room_no') or '') == room_no_filter]

    if sort_by in ('id', 'name', 'gender', 'nation', 'birth_date', 'id_card', 'phone', 'building', 'room_no', 'status', 'check_in_date', 'check_out_date'):
        reverse = sort_order == 'desc'
        tenants.sort(key=lambda x: x.get(sort_by), reverse=reverse)

    total = len(tenants)

    page, page_size, paging_enabled = parse_pagination_args(
        request.args,
        default_page=1,
        default_page_size=20,
        max_page_size=200,
    )
    if paging_enabled:
        tenants, pagination = paginate_list(tenants, page, page_size)
    else:
        pagination = {
            'page': 1,
            'page_size': total if total > 0 else 0,
            'total': total,
            'total_pages': 1,
        }

    allowed_fields = [
        'id', 'name', 'gender', 'nation', 'birth_date', 'id_card', 'address',
        'phone',
        'emergency_contact_name', 'emergency_contact_phone',
        'check_in_date', 'check_out_date', 'room_no', 'building',
        'remarks', 'status', 'current_stay_id', 'stay_count'
    ]
    selected_fields = parse_fields_arg(request.args, allowed_fields)
    tenants = project_fields(tenants, selected_fields, always_include=['id'])

    return jsonify({'tenants': tenants, 'total': total, 'pagination': pagination})


@tenants_bp.route('/tenants/<id_card>/checkout', methods=['POST'])
@token_required
def api_checkout_tenant(current_user, id_card):
    """
    办理退租
    ---
    tags:
      - Tenants
    security:
      - Bearer: []
    parameters:
      - in: path
        name: id_card
        type: string
        required: true
        description: 身份证号
    responses:
      200:
        description: 退租成功
      404:
        description: 未找到该租户或已退租
    """
    conn = connect()
    today = _checkout_tenant(conn, "id_card = ?", (id_card,))
    if not today:
        conn.close()
        return jsonify({'error': '未找到该租户或租户已退租'}), 404
    conn.commit()
    conn.close()
    return jsonify({'message': '租户退租成功', 'checkout_date': today})


@tenants_bp.route('/tenants/by-id/<int:tenant_id>/checkout', methods=['POST'])
@token_required
def api_checkout_tenant_by_id(current_user, tenant_id):
    """
    按租户记录 ID 办理退租。用于身份证号为空或重复的历史数据。
    """
    conn = connect()
    today = _checkout_tenant(conn, "id = ?", (tenant_id,))
    if not today:
        conn.close()
        return jsonify({'error': '未找到该租户或租户已退租'}), 404
    conn.commit()
    conn.close()
    return jsonify({'message': '租户退租成功', 'checkout_date': today})


@tenants_bp.route('/tenants/by-id/<int:tenant_id>/stays', methods=['GET'])
@token_required
def api_list_tenant_stays(current_user, tenant_id):
    ensure_tenant_stays_schema()
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM tenants WHERE id = ?", (tenant_id,))
    if not cursor.fetchone():
        conn.close()
        return jsonify({'error': f'租户 #{tenant_id} 不存在'}), 404
    cursor.execute(
        """
        SELECT s.id, s.tenant_id, s.room_id, r.room_no, r.building,
               s.check_in_date, s.planned_check_out_date, s.actual_check_out_date,
               s.rent_amount, s.rent_unit, s.deposit_amount, s.status,
               s.remarks, s.created_at
        FROM tenant_stays s
        LEFT JOIN rooms r ON r.id = s.room_id
        WHERE s.tenant_id = ?
        ORDER BY s.check_in_date DESC, s.id DESC
        """,
        (tenant_id,),
    )
    stays = [_serialize_stay(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify({'stays': stays, 'total': len(stays)})


@tenants_bp.route('/tenants/by-id/<int:tenant_id>/stays', methods=['POST'])
@token_required
def api_create_tenant_stay(current_user, tenant_id):
    ensure_tenant_stays_schema()
    data = request.json or {}
    required_fields = ['room_no', 'check_in_date', 'check_out_date']
    if not all(str(data.get(field) or '').strip() for field in required_fields):
        return jsonify({'error': '请选择房间、入住日期和计划退房日期'}), 400
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM tenants WHERE id = ?", (tenant_id,))
    tenant = cursor.fetchone()
    if not tenant:
        conn.close()
        return jsonify({'error': f'租户 #{tenant_id} 不存在'}), 404
    room = _resolve_room_for_tenant(conn, data.get('room_no'), data.get('building'))
    if not room:
        conn.close()
        return jsonify({'error': f"房间 {data.get('room_no')} 不存在"}), 404
    try:
        stay_id = create_tenant_stay(
            conn,
            tenant_id,
            int(room[0]),
            data.get('check_in_date'),
            data.get('check_out_date'),
            data.get('remarks', ''),
        )
        _refresh_tenant_statuses(conn)
        _refresh_room_statuses(conn)
        years = _collect_lease_years(data.get('check_in_date'), data.get('check_out_date'))
        _sync_rent_ledger_years(conn, years)
        conn.commit()
        return jsonify({
            'message': f"租户 {tenant[1]} 已再次入住",
            'tenant_id': tenant_id,
            'stay_id': stay_id,
        }), 201
    except (ValueError, sqlite3.IntegrityError) as exc:
        conn.rollback()
        return jsonify({'error': str(exc)}), 400
    except sqlite3.Error as exc:
        conn.rollback()
        return jsonify({'error': str(exc)}), 500
    finally:
        conn.close()


@tenants_bp.route('/tenants', methods=['POST'])
@token_required
def api_add_tenant(current_user):
    data = request.json
    required_fields = [
        'name', 'phone',
        'check_in_date', 'check_out_date', 'room_no',
    ]

    if not data or not all(k in data for k in required_fields):
        return jsonify({'error': '缺少必要参数', 'required': required_fields}), 400

    ensure_tenant_stays_schema()
    conn = connect()
    room = _resolve_room_for_tenant(conn, data.get('room_no'), data.get('building'))
    if not room:
        conn.close()
        return jsonify({'error': f"房间 {data['room_no']} 不存在"}), 404

    room_id = room[0]
    cursor = conn.cursor()
    remarks = data.get('remarks', '')
    gender = _clean_text(data.get('gender'))
    id_card = _clean_text(data.get('id_card')).upper() or None
    birth_date = _clean_text(data.get('birth_date')) or _derive_birth_date_from_id_card(id_card)
    status = _normalize_tenant_status(data.get('status'))
    if id_card:
        cursor.execute("SELECT id, status FROM tenants WHERE id_card = ? LIMIT 1", (id_card,))
        existing = cursor.fetchone()
        if existing:
            can_recheckin = get_current_stay(conn, int(existing[0])) is None
            conn.close()
            return jsonify({
                'error': '该身份证号已有人员档案，请使用“再次入住”保留历史记录',
                'code': 'TENANT_ALREADY_EXISTS',
                'tenant_id': int(existing[0]),
                'can_recheckin': can_recheckin,
            }), 409

    cursor.execute("SELECT room_no, price, price_unit FROM rooms WHERE id = ? LIMIT 1", (room_id,))
    room_row = cursor.fetchone()
    room_display = data.get('room_no') or (room_row[0] if room_row else '')
    room_price = _parse_amount(room_row[1] if room_row else 0, 0)
    room_price_unit = _clean_text(room_row[2] if room_row else '') or '月'
    if room_price <= 0:
        conn.close()
        return jsonify({'error': f"房间 {room_display} 的租金为 0，请先到房间管理设置租金后再新增租户"}), 400

    try:
        cursor.execute(
            """
            INSERT INTO tenants (
                name, gender, nation, birth_date, id_card, address, front_img, back_img,
                phone, emergency_contact_name, emergency_contact_phone,
                check_in_date, check_out_date, room_id, remarks, status
            ) VALUES (?, ?, ?, ?, ?, ?, '', '', ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data['name'],
                gender,
                data.get('nation', '汉族'),
                birth_date or None,
                id_card,
                data.get('address', ''),
                data['phone'],
                data.get('emergency_contact_name', ''),
                data.get('emergency_contact_phone', ''),
                data['check_in_date'],
                data['check_out_date'],
                room_id,
                remarks,
                status,
            ),
        )
        tenant_id = cursor.lastrowid
        stay_id = create_tenant_stay(
            conn,
            tenant_id,
            room_id,
            data['check_in_date'],
            data['check_out_date'],
            remarks,
        )
        if status == '已退租':
            checkout_current_stay(conn, tenant_id, data.get('check_out_date'))
        _refresh_tenant_statuses(conn)
        _refresh_room_statuses(conn)
        _sync_rent_ledger_years(
            conn,
            _collect_lease_years(data.get('check_in_date'), data.get('check_out_date')),
        )
        conn.commit()
        conn.close()

        return jsonify({'message': f"租户 {data['name']} 已添加", 'id': tenant_id, 'stay_id': stay_id, 'id_card': id_card or ''})
    except sqlite3.Error as e:
        conn.close()
        return jsonify({'error': str(e)}), 500


@tenants_bp.route('/tenants/by-id/<int:tenant_id>', methods=['DELETE'])
@token_required
def api_delete_tenant_by_id(current_user, tenant_id):
    conn = connect()
    cursor = conn.cursor()

    try:
        affected_years = _load_tenant_ledger_years(conn, "id = ?", (tenant_id,))
        cursor.execute("SELECT id, status, room_id FROM tenants WHERE id = ? LIMIT 1", (tenant_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return jsonify({'error': f'租户 #{tenant_id} 不存在'}), 404
        tenant_id, status, room_id = row[0], row[1], row[2]
        if status != '已退租':
            conn.close()
            return jsonify({'error': '在住状态不可删除，请先办理退租'}), 400

        cursor.execute("SELECT COUNT(*) FROM tenant_stays WHERE tenant_id = ?", (tenant_id,))
        stay_count = int(cursor.fetchone()[0] or 0)
        if stay_count > 0:
            conn.close()
            return jsonify({'error': f'该人员有 {stay_count} 条入住历史，不能删除人员档案'}), 400

        cursor.execute("DELETE FROM tenant_moves WHERE tenant_id = ?", (tenant_id,))
        moves_deleted = cursor.rowcount

        cursor.execute("DELETE FROM tenants WHERE id = ?", (tenant_id,))
        if cursor.rowcount == 0:
            conn.close()
            return jsonify({'error': f'租户 #{tenant_id} 不存在'}), 404

        if room_id is not None:
            cursor.execute(
                """
                UPDATE rooms
                SET status = CASE
                    WHEN EXISTS (
                        SELECT 1 FROM tenants t
                        WHERE t.room_id = rooms.id
                          AND t.status = '在住'
                          AND DATE('now','localtime') BETWEEN t.check_in_date AND t.check_out_date
                    ) THEN '已入住'
                    ELSE '空闲'
                END
                WHERE id = ?
                """,
                (room_id,)
            )
        _sync_rent_ledger_years(conn, affected_years)
        conn.commit()
        conn.close()
        msg = f'租户 #{tenant_id} 已删除'
        if moves_deleted and moves_deleted > 0:
            msg += f'（已清理搬迁记录 {moves_deleted} 条）'
        return jsonify({'message': msg})
    except sqlite3.IntegrityError:
        try:
            conn2 = connect()
            cur2 = conn2.cursor()
            cur2.execute("SELECT COUNT(*) FROM tenant_moves WHERE tenant_id = ?", (tenant_id,))
            moves_count = cur2.fetchone()[0]
            conn2.close()
            if moves_count > 0:
                return jsonify({'error': f'租户 #{tenant_id} 存在 {moves_count} 条搬迁记录，无法删除；请先删除或归档相关记录'}), 400
        except Exception:
            pass
        return jsonify({'error': '删除失败：存在关联数据约束（如搬迁记录），请先清理关联数据后再尝试'}), 400
    except sqlite3.Error as e:
        conn.close()
        return jsonify({'error': str(e)}), 500


@tenants_bp.route('/tenants/recognize-id-card', methods=['POST'])
@token_required
def api_recognize_tenant_id_card(current_user):
    if "file" not in request.files:
        return jsonify({"error": "请上传身份证图片"}), 400
    image_file = request.files["file"]
    if not image_file or not str(image_file.filename or "").strip():
        return jsonify({"error": "请选择身份证图片"}), 400
    ocr_status = build_ocr_status()
    if not ocr_status["configured"] or not aliyun_ocr_is_configured():
        return jsonify({"error": "服务器未配置阿里云 OCR，请先在系统维护页面填写阿里云 OCR 配置"}), 503
    if not ocr_status["enabled"]:
        return jsonify({"error": ocr_status["reason"] or "身份证识别当前不可用"}), 400

    image_bytes = image_file.read()
    if not image_bytes:
        return jsonify({"error": "上传的图片内容为空"}), 400
    if len(image_bytes) > 10 * 1024 * 1024:
        return jsonify({"error": "身份证图片不能超过 10MB"}), 400

    try:
        result = recognize_cn_id_card(image_bytes)
        birth_date = result["fields"].get("birth_date") or _derive_birth_date_from_id_card(result["fields"].get("id_card"))
        result["fields"]["birth_date"] = birth_date
        record_ocr_usage(source="tenant_form", token=current_user.get("username", ""))
        result["ocr"] = build_ocr_status()
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e) or "身份证识别失败"}), 500


@tenants_bp.route('/tenants/ai-draft', methods=['POST'])
@token_required
def api_create_tenant_ai_draft(current_user):
    images = []

    if request.content_type and request.content_type.startswith('multipart/form-data'):
        user_text = request.form.get('text') or ''
        for file in request.files.getlist('images'):
            if not file or not file.filename:
                continue
            if not str(file.mimetype or '').startswith('image/'):
                return jsonify({'error': '仅支持图片文件'}), 400
            data = file.read()
            if len(data) > 8 * 1024 * 1024:
                return jsonify({'error': '单张图片请控制在 8MB 以内'}), 400
            images.append(base64.b64encode(data).decode('ascii'))
    else:
        data = request.json or {}
        user_text = data.get('text') or ''
        raw_images = data.get('images') or []
        if isinstance(raw_images, list):
            for item in raw_images[:4]:
                value = str(item or '').strip()
                if value.startswith('data:image/') and ',' in value:
                    value = value.split(',', 1)[1]
                if value:
                    images.append(value)

    if not _clean_text(user_text) and not images:
        return jsonify({'error': '请提供文字或图片'}), 400
    if len(images) > 4:
        return jsonify({'error': '最多支持 4 张图片'}), 400

    ocr_result = _try_recognize_tenant_id_card_from_images(images, current_user)
    ocr_fields = (ocr_result or {}).get("fields") or {}
    prompt = _build_tenant_ai_prompt_with_ocr(user_text, ocr_fields) if ocr_fields else _build_tenant_ai_prompt(user_text, len(images))
    try:
        result = _call_ollama_generate(prompt, images)
        response_text = result.get('response') or ''
        parsed = _extract_json_object(response_text)
        draft = _normalize_tenant_ai_payload(parsed)
        draft = _merge_tenant_fields_with_ocr(draft, ocr_fields)
        return jsonify({
            'draft': draft,
            'model': result.get('model') or get_active_ai_model(),
            'ocr_used': bool(ocr_fields),
        })
    except Exception as e:
        if ocr_fields:
            draft = _normalize_tenant_ai_payload(ocr_fields)
            draft = _merge_tenant_fields_with_ocr(draft, ocr_fields)
            return jsonify({
                'draft': draft,
                'model': 'aliyun_ocr',
                'ocr_used': True,
            })
        return jsonify({'error': str(e)}), 502


@tenants_bp.route('/tenants/<id_card>', methods=['PUT'])
@token_required
def api_update_tenant(current_user, id_card):
    data = request.json
    if not data:
        return jsonify({'error': '缺少更新数据'}), 400

    allowed_fields = [
        'name', 'phone', 'emergency_contact_name', 'emergency_contact_phone',
        'check_in_date', 'check_out_date', 'remarks',
    ]
    update_data = {k: v for k, v in data.items() if k in allowed_fields}

    if 'room_no' in data:
        conn = connect()
        room = _resolve_room_for_tenant(conn, data.get('room_no'), data.get('building'))
        if not room:
            conn.close()
            return jsonify({'error': f"房间 {data['room_no']} 不存在"}), 404
        update_data['room_id'] = room[0]
        conn.close()

    if not update_data:
        return jsonify({'error': '没有有效的更新字段'}), 400

    conn = connect()
    cursor = conn.cursor()

    try:
        affected_years = _load_tenant_ledger_years(conn, "id_card = ?", (id_card,))
        for key, value in update_data.items():
            cursor.execute(f"UPDATE tenants SET {key} = ? WHERE id_card = ?", (value, id_card))

        if cursor.rowcount == 0:
            conn.close()
            return jsonify({'error': f'租户 {id_card} 不存在'}), 404

        cursor.execute("SELECT id FROM tenants WHERE id_card = ? LIMIT 1", (id_card,))
        tenant_row = cursor.fetchone()
        if tenant_row:
            _update_current_stay_from_tenant_fields(conn, int(tenant_row[0]), update_data)
        _refresh_tenant_statuses(conn)
        _refresh_room_statuses(conn)
        affected_years.update(_load_tenant_ledger_years(conn, "id_card = ?", (id_card,)))
        _sync_rent_ledger_years(conn, affected_years)
        conn.commit()
        conn.close()

        return jsonify({'message': f'租户 {id_card} 信息已更新'})
    except sqlite3.Error as e:
        conn.close()
        return jsonify({'error': str(e)}), 500


@tenants_bp.route('/tenants/by-id/<int:tenant_id>', methods=['PUT'])
@token_required
def api_update_tenant_by_id(current_user, tenant_id):
    data = request.json
    if not data:
        return jsonify({'error': '缺少更新数据'}), 400

    allowed_fields = [
        'name', 'phone', 'emergency_contact_name', 'emergency_contact_phone',
        'check_in_date', 'check_out_date', 'remarks',
    ]
    update_data = {k: v for k, v in data.items() if k in allowed_fields}

    if 'room_no' in data:
        conn = connect()
        room = _resolve_room_for_tenant(conn, data.get('room_no'), data.get('building'))
        if not room:
            conn.close()
            return jsonify({'error': f"房间 {data['room_no']} 不存在"}), 404
        update_data['room_id'] = room[0]
        conn.close()

    if not update_data:
        return jsonify({'error': '没有有效的更新字段'}), 400

    conn = connect()
    cursor = conn.cursor()

    try:
        affected_years = _load_tenant_ledger_years(conn, "id = ?", (tenant_id,))
        for key, value in update_data.items():
            cursor.execute(f"UPDATE tenants SET {key} = ? WHERE id = ?", (value, tenant_id))

        if cursor.rowcount == 0:
            conn.close()
            return jsonify({'error': f'租户 #{tenant_id} 不存在'}), 404

        _update_current_stay_from_tenant_fields(conn, tenant_id, update_data)
        _refresh_tenant_statuses(conn)
        _refresh_room_statuses(conn)
        affected_years.update(_load_tenant_ledger_years(conn, "id = ?", (tenant_id,)))
        _sync_rent_ledger_years(conn, affected_years)
        conn.commit()
        conn.close()

        return jsonify({'message': f'租户 #{tenant_id} 信息已更新'})
    except sqlite3.Error as e:
        conn.close()
        return jsonify({'error': str(e)}), 500


@tenants_bp.route('/tenants/<id_card>', methods=['DELETE'])
@token_required
def api_delete_tenant(current_user, id_card):
    """
    删除租户
    ---
    tags:
      - Tenants
    security:
      - Bearer: []
    parameters:
      - in: path
        name: id_card
        type: string
        required: true
        description: 身份证号
    responses:
      200:
        description: 删除成功
      400:
        description: 在住状态不可删除，或存在关联数据
      404:
        description: 租户不存在
    """
    conn = connect()
    cursor = conn.cursor()

    try:
        affected_years = _load_tenant_ledger_years(conn, "id_card = ?", (id_card,))
        # 校验租户存在与状态，并获取 room_id 以便精确更新房间状态
        cursor.execute("SELECT id, status, room_id FROM tenants WHERE id_card = ? LIMIT 1", (id_card,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return jsonify({'error': f'租户 {id_card} 不存在'}), 404
        tenant_id, status, room_id = row[0], row[1], row[2]
        if status != '已退租':
            conn.close()
            return jsonify({'error': '在住状态不可删除，请先办理退租'}), 400
        cursor.execute("SELECT COUNT(*) FROM tenant_stays WHERE tenant_id = ?", (tenant_id,))
        stay_count = int(cursor.fetchone()[0] or 0)
        if stay_count > 0:
            conn.close()
            return jsonify({'error': f'该人员有 {stay_count} 条入住历史，不能删除人员档案'}), 400
        # 先级联清理关联的搬迁记录，避免外键约束失败
        cursor.execute("DELETE FROM tenant_moves WHERE tenant_id = ?", (tenant_id,))
        moves_deleted = cursor.rowcount

        # 执行删除租户
        cursor.execute("DELETE FROM tenants WHERE id_card = ?", (id_card,))
        if cursor.rowcount == 0:
            conn.close()
            return jsonify({'error': f'租户 {id_card} 不存在'}), 404

        # 更新房间状态（如有需要）
        # 仅针对受影响的房间更新状态，降低并发锁竞争
        if room_id is not None:
            cursor.execute(
                """
                UPDATE rooms
                SET status = CASE
                    WHEN EXISTS (
                        SELECT 1 FROM tenants t
                        WHERE t.room_id = rooms.id
                          AND t.status = '在住'
                          AND DATE('now','localtime') BETWEEN t.check_in_date AND t.check_out_date
                    ) THEN '已入住'
                    ELSE '空闲'
                END
                WHERE id = ?
                """,
                (room_id,)
            )
        _sync_rent_ledger_years(conn, affected_years)
        conn.commit()
        conn.close()
        msg = f'租户 {id_card} 已删除'
        if moves_deleted and moves_deleted > 0:
            msg += f'（已清理搬迁记录 {moves_deleted} 条）'
        return jsonify({'message': msg})
    except sqlite3.IntegrityError as e:
        # 针对外键约束失败（例如存在关联的搬迁记录）返回明确的业务错误，避免 500
        try:
            # 尝试提供更明确的失败原因
            conn2 = connect()
            cur2 = conn2.cursor()
            # 查出租户ID
            cur2.execute("SELECT id FROM tenants WHERE id_card = ? LIMIT 1", (id_card,))
            r = cur2.fetchone()
            tenant_id = r[0] if r else None
            moves_count = 0
            if tenant_id is not None:
                cur2.execute("SELECT COUNT(*) FROM tenant_moves WHERE tenant_id = ?", (tenant_id,))
                moves_count = cur2.fetchone()[0]
            conn2.close()
            if moves_count > 0:
                return jsonify({'error': f'租户 {id_card} 存在 {moves_count} 条搬迁记录，无法删除；请先删除或归档相关记录'}), 400
        except Exception:
            # 若补充查询失败，也避免抛出 500
            pass
        return jsonify({'error': '删除失败：存在关联数据约束（如搬迁记录），请先清理关联数据后再尝试'}), 400
    except sqlite3.Error as e:
        conn.close()
        return jsonify({'error': str(e)}), 500
