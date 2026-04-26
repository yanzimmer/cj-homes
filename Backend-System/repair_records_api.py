# 该文件负责处理维修记录的增删改查、图片上传与数据格式转换。
import json
import os
import re
import sqlite3
import uuid
from datetime import datetime

from flask import Blueprint, jsonify, request

from auth_api import token_required
from common import connect, parse_fields_arg, parse_pagination_args, paginate_list, project_fields
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


def ensure_repair_records_schema():
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(repair_records)")
    cols = {row[1] for row in cursor.fetchall()}
    if "repair_image" not in cols:
        cursor.execute("ALTER TABLE repair_records ADD COLUMN repair_image TEXT")
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


def _repair_record_to_dict(row):
    before_images = _parse_repair_images(row[15])
    after_images = _parse_repair_images(row[16])
    legacy_images = _parse_repair_images(row[17])
    payment_images = _parse_repair_images(row[18])
    amount = row[10] if row[10] is not None else row[9]
    inventory_usages = _parse_inventory_usages(row[14])

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
        "repair_type": row[3],
        "description": row[4],
        "report_date": row[5],
        "report_by": row[6],
        "status": row[7],
        "repair_date": row[8],
        "repair_cost": row[9],
        "amount": amount,
        "repair_person": row[11],
        "payment_person": row[12],
        "remarks": row[13],
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
            id, building, room_no, repair_type, description,
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
            or q in str(item.get('repair_type', '')).lower()
            or q in str(item.get('description', '')).lower()
            or q in str(item.get('report_by', '')).lower()
            or q in str(item.get('remarks', '')).lower()
        ]

    if repair_type_filter:
        records = [item for item in records if str(item.get('repair_type') or '') == repair_type_filter]

    if status_filter:
        records = [item for item in records if str(item.get('status') or '') == status_filter]

    if sort_by in ('id', 'building', 'room_no', 'repair_type', 'report_date', 'status', 'repair_date', 'repair_cost', 'amount'):
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
            id, building, room_no, repair_type, description,
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
    required_fields = ["room_no", "repair_type", "description", "report_by"]

    if not all(k in data for k in required_fields):
        return jsonify({"error": "缺少必要参数", "required": required_fields}), 400

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("SELECT building FROM rooms WHERE room_no = ?", (data["room_no"],))
    room = cursor.fetchone()
    if not room:
        conn.close()
        return jsonify({"error": f"房间 {data['room_no']} 不存在"}), 404

    building = room[0]
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
                building, room_no, repair_type, description,
                report_date, report_by, status,
                repair_date, repair_cost, amount, repair_person, payment_person, remarks, inventory_usages,
                repair_image_before, repair_image_after, repair_image, payment_images
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                building,
                data["room_no"],
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
        return jsonify({"message": "维修记录已添加", "id": record_id, "room_no": data["room_no"]})
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
        "repair_type",
        "description",
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
        "SELECT id, repair_image_before, repair_image_after, repair_image, inventory_usages, payment_images FROM repair_records WHERE id = ?",
        (record_id,),
    )
    record = cursor.fetchone()
    if not record:
        conn.close()
        return jsonify({"error": f"维修记录 {record_id} 不存在"}), 404

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
            id, building, room_no, repair_type, description,
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
