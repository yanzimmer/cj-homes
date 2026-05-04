import json
import os
import secrets
import sqlite3
from datetime import datetime

from flask import Blueprint, jsonify, request

from auth_api import token_required
from common import BASE_DIR, connect
from inventory_sync_service import dump_inventory_usages, list_warehouse_stock_options, validate_inventory_usages
from procurement_api import _dump_procurement_images, _to_float, ensure_procurement_schema
from repair_records_api import (
    _dump_repair_images,
    _get_primary_room_no,
    _normalize_repair_scope_type,
    _normalize_room_nos_text,
    _resolve_repair_building,
    ensure_repair_records_schema,
)
from warehouse_api import _dump_warehouse_images, ensure_warehouse_schema


public_entry_bp = Blueprint("public_entry_links", __name__, url_prefix="/api")
SUPPORTED_BUSINESS_TYPES = {"repair", "procurement", "warehouse"}
BUSINESS_LABELS = {
    "repair": "维修记录",
    "procurement": "采购管理",
    "warehouse": "库存管理",
}


def ensure_public_entry_schema():
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS public_entry_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business_type TEXT UNIQUE NOT NULL,
            token TEXT UNIQUE NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS public_entry_submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            link_id INTEGER,
            business_type TEXT NOT NULL,
            payload_json TEXT,
            created_record_id INTEGER,
            submitted_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (link_id) REFERENCES public_entry_links(id) ON DELETE SET NULL
        )
        """
    )
    conn.commit()
    conn.close()


def _business_exists(business_type):
    return business_type in SUPPORTED_BUSINESS_TYPES


def _now_text():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _format_report_by_option(building, room_no, name):
    building_text = str(building or "").strip()
    room_text = str(room_no or "").strip()
    name_text = str(name or "").strip()
    if not name_text:
        return ""
    room_part = room_text
    if building_text and room_text:
        normalized_room = room_text.replace("栋", "").replace("_", "-")
        prefixes = [f"{building_text}-", f"{building_text}栋-", building_text]
        for prefix in prefixes:
            if normalized_room.startswith(prefix):
                room_part = normalized_room[len(prefix):].lstrip("-")
                break
    if building_text and room_part:
        return f"{building_text}-{room_part}-{name_text}"
    if room_text:
        return f"{room_text}-{name_text}"
    return name_text


def _list_public_tenant_names():
    conn = connect()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT DISTINCT r.building, r.room_no, t.name
            FROM tenants t
            LEFT JOIN rooms r ON t.room_id = r.id
            WHERE name IS NOT NULL AND TRIM(name) <> ''
            ORDER BY r.room_no, t.name COLLATE NOCASE
            """
        )
        options = []
        seen = set()
        for row in cur.fetchall():
            label = _format_report_by_option(row[0], row[1], row[2])
            if label and label not in seen:
                seen.add(label)
                options.append(label)
        return options
    finally:
        conn.close()


def _get_link_with_count(business_type):
    ensure_public_entry_schema()
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            l.id, l.business_type, l.token, l.status, l.created_at,
            (SELECT COUNT(*) FROM public_entry_submissions s WHERE s.link_id = l.id) AS submission_count
        FROM public_entry_links l
        WHERE l.business_type = ?
        LIMIT 1
        """,
        (business_type,),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "id": row[0],
        "business_type": row[1],
        "business_label": BUSINESS_LABELS.get(row[1], row[1]),
        "token": row[2],
        "status": row[3],
        "created_at": row[4],
        "submission_count": int(row[5] or 0),
    }


def _insert_submission_log(link_id, business_type, payload, record_id):
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO public_entry_submissions (link_id, business_type, payload_json, created_record_id)
        VALUES (?, ?, ?, ?)
        """,
        (link_id, business_type, json.dumps(payload or {}, ensure_ascii=False), record_id),
    )
    conn.commit()
    conn.close()


def _list_public_room_options():
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT building, room_no
        FROM rooms
        ORDER BY building ASC, room_no ASC
        """
    )
    rows = cur.fetchall()
    conn.close()
    return [
        {
            "building": str(row[0] or "").strip(),
            "room_no": str(row[1] or "").strip(),
        }
        for row in rows
        if str(row[0] or "").strip() and str(row[1] or "").strip()
    ]


def _ensure_public_entry_upload_dir():
    path = os.path.join(BASE_DIR, "static", "uploads", "public_entries")
    os.makedirs(path, exist_ok=True)
    return path


def _save_public_entry_image(business_type, upload_file):
    ext = os.path.splitext(str(upload_file.filename or ""))[1].lower() or ".png"
    if ext not in (".png", ".jpg", ".jpeg", ".webp", ".avif"):
        raise ValueError("仅支持 png/jpg/jpeg/webp/avif 图片")
    root = _ensure_public_entry_upload_dir()
    target_dir = os.path.join(root, business_type)
    os.makedirs(target_dir, exist_ok=True)
    filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{secrets.token_hex(6)}{ext}"
    save_path = os.path.join(target_dir, filename)
    upload_file.save(save_path)
    return f"/static/uploads/public_entries/{business_type}/{filename}"


def _create_repair_from_public(data):
    ensure_repair_records_schema()
    conn = connect()
    cur = conn.cursor()
    scope_type = _normalize_repair_scope_type(data.get("scope_type"))
    room_nos_text = _normalize_room_nos_text(data.get("room_nos"), data.get("room_no"))
    room_no = _get_primary_room_no(scope_type, data.get("room_no"), room_nos_text)
    building = _resolve_repair_building(cur, room_no, data.get("building"))
    if scope_type == "单个房间" and not room_no:
        conn.close()
        raise ValueError("单个房间维修必须填写房间号")
    if scope_type == "多个房间" and not room_nos_text:
        conn.close()
        raise ValueError("多个房间维修必须填写房间号")

    repair_type = str(data.get("repair_type") or "").strip()
    description = str(data.get("description") or "").strip()
    report_by = str(data.get("report_by") or "").strip()
    if not repair_type or not description or not report_by:
        conn.close()
        raise ValueError("请填写维修类型、问题描述和报修人")

    report_date = str(data.get("report_date") or "").strip() or datetime.now().strftime("%Y-%m-%d")
    status = str(data.get("status") or "").strip() or "待处理"
    amount = data.get("amount")
    try:
        amount = None if amount in (None, "") else float(amount)
    except Exception:
        conn.close()
        raise ValueError("金额格式不正确")
    images = [str(v).strip() for v in (data.get("images") or []) if str(v).strip()]
    payment_images = [str(v).strip() for v in (data.get("payment_images") or []) if str(v).strip()]
    payment_person = str(data.get("payment_person") or "").strip()
    inventory_usages = validate_inventory_usages(conn, data.get("inventory_usages") or [])

    cur.execute(
        """
        INSERT INTO repair_records (
            building, room_no, scope_type, room_nos, location_text, repair_type, description, report_date, report_by, status,
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
            repair_type,
            description,
            report_date,
            report_by,
            status,
            str(data.get("repair_date") or "").strip() or None,
            amount,
            amount,
            str(data.get("repair_person") or "").strip(),
            payment_person,
            str(data.get("remarks") or "").strip(),
            dump_inventory_usages(inventory_usages),
            "[]",
            "[]",
            "[]",
            _dump_repair_images(payment_images),
        ),
    )
    record_id = cur.lastrowid
    if images:
        payload = _dump_repair_images(images)
        cur.execute(
            """
            UPDATE repair_records
            SET repair_image_before = ?, repair_image = ?
            WHERE id = ?
            """,
            (payload, payload, record_id),
        )
    conn.commit()
    conn.close()
    return record_id


def _create_procurement_from_public(data):
    ensure_procurement_schema()
    procurement_date = str(data.get("procurement_date") or "").strip()
    item_name = str(data.get("item_name") or "").strip()
    if not procurement_date or not item_name:
        raise ValueError("请填写时间和采购物品")
    quantity = _to_float(data.get("quantity"), 0)
    if quantity <= 0:
        raise ValueError("数量必须大于 0")
    unit_price = _to_float(data.get("unit_price"), 0)
    total_amount = _to_float(data.get("total_amount"), 0)
    if unit_price <= 0 and quantity > 0 and total_amount > 0:
        unit_price = total_amount / quantity
    if total_amount <= 0 and quantity > 0 and unit_price > 0:
        total_amount = quantity * unit_price
    images = [str(v).strip() for v in (data.get("images") or []) if str(v).strip()]

    conn = connect()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO procurements (
            procurement_date, item_name, specification, quantity, unit_price, unit,
            total_amount, remarks, procurement_images
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, '[]')
        """,
        (
            procurement_date,
            item_name,
            str(data.get("specification") or "").strip(),
            quantity,
            unit_price,
            str(data.get("unit") or "").strip(),
            total_amount,
            str(data.get("remarks") or "").strip(),
        )
    )
    record_id = cur.lastrowid
    if images:
        cur.execute(
            "UPDATE procurements SET procurement_images = ? WHERE id = ?",
            (_dump_procurement_images(images), record_id),
        )
    conn.commit()
    conn.close()
    return record_id


def _create_warehouse_from_public(data):
    ensure_warehouse_schema()
    item_name = str(data.get("item_name") or "").strip()
    if not item_name:
        raise ValueError("请填写物品")
    try:
        quantity = float(data.get("quantity", 0))
    except Exception:
        raise ValueError("数量格式不正确")
    if quantity < 0:
        raise ValueError("数量不能小于 0")
    images = [str(v).strip() for v in (data.get("images") or []) if str(v).strip()]

    conn = connect()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO warehouse_items (procurement_date, item_name, specification, category, quantity, unit_price, unit, location, image, remarks, created_at, updated_at)
        VALUES (?, ?, ?, '', ?, ?, ?, ?, '[]', ?, DATETIME('now'), DATETIME('now'))
        """,
        (
            str(data.get("procurement_date") or "").strip(),
            item_name,
            str(data.get("specification") or data.get("category") or "").strip(),
            quantity,
            0,
            str(data.get("unit") or "").strip(),
            str(data.get("location") or "").strip(),
            str(data.get("remarks") or "").strip(),
        ),
    )
    record_id = cur.lastrowid
    if images:
        cur.execute(
            "UPDATE warehouse_items SET image = ? WHERE id = ?",
            (_dump_warehouse_images(images), record_id),
        )
    conn.commit()
    conn.close()
    return record_id


def _create_record_by_business(business_type, data):
    if business_type == "repair":
        return _create_repair_from_public(data)
    if business_type == "procurement":
        return _create_procurement_from_public(data)
    if business_type == "warehouse":
        return _create_warehouse_from_public(data)
    raise ValueError("不支持的业务类型")


@public_entry_bp.route("/public-entry-links/<business_type>", methods=["GET"])
@token_required
def api_get_public_entry_link(current_user, business_type):
    business_type = str(business_type or "").strip().lower()
    if not _business_exists(business_type):
        return jsonify({"error": "不支持的业务类型"}), 400
    return jsonify({"link": _get_link_with_count(business_type)})


@public_entry_bp.route("/public-entry-links/<business_type>", methods=["POST"])
@token_required
def api_create_public_entry_link(current_user, business_type):
    business_type = str(business_type or "").strip().lower()
    if not _business_exists(business_type):
        return jsonify({"error": "不支持的业务类型"}), 400
    ensure_public_entry_schema()
    existing = _get_link_with_count(business_type)
    if existing:
        return jsonify({"error": "当前业务已有填写链接，请先删除原链接后再生成新链接"}), 400

    conn = connect()
    cur = conn.cursor()
    token = secrets.token_urlsafe(24)
    cur.execute(
        """
        INSERT INTO public_entry_links (business_type, token, status)
        VALUES (?, ?, 'active')
        """,
        (business_type, token),
    )
    link_id = cur.lastrowid
    conn.commit()
    conn.close()
    return jsonify(
        {
            "link": {
                "id": link_id,
                "business_type": business_type,
                "business_label": BUSINESS_LABELS.get(business_type, business_type),
                "token": token,
                "status": "active",
                "created_at": _now_text(),
                "submission_count": 0,
            }
        }
    )


@public_entry_bp.route("/public-entry-links/<int:link_id>/disable", methods=["POST"])
@token_required
def api_disable_public_entry_link(current_user, link_id):
    ensure_public_entry_schema()
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT id, status FROM public_entry_links WHERE id = ?", (link_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "填写链接不存在"}), 404
    if row[1] == "disabled":
        conn.close()
        return jsonify({"message": "填写链接已停用"})
    cur.execute("UPDATE public_entry_links SET status = 'disabled' WHERE id = ?", (link_id,))
    conn.commit()
    conn.close()
    return jsonify({"message": "填写链接已停用"})


@public_entry_bp.route("/public-entry-links/<int:link_id>/enable", methods=["POST"])
@token_required
def api_enable_public_entry_link(current_user, link_id):
    ensure_public_entry_schema()
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT id, status FROM public_entry_links WHERE id = ?", (link_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "填写链接不存在"}), 404
    if row[1] == "active":
        conn.close()
        return jsonify({"message": "填写链接已启用"})
    cur.execute("UPDATE public_entry_links SET status = 'active' WHERE id = ?", (link_id,))
    conn.commit()
    conn.close()
    return jsonify({"message": "填写链接已启用"})


@public_entry_bp.route("/public-entry-links/<int:link_id>", methods=["DELETE"])
@token_required
def api_delete_public_entry_link(current_user, link_id):
    ensure_public_entry_schema()
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT id FROM public_entry_links WHERE id = ?", (link_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "填写链接不存在"}), 404
    cur.execute("DELETE FROM public_entry_links WHERE id = ?", (link_id,))
    conn.commit()
    conn.close()
    return jsonify({"message": "填写链接已删除"}), 200


@public_entry_bp.route("/public-entry/<business_type>/<token>", methods=["GET"])
def api_get_public_entry_form(business_type, token):
    business_type = str(business_type or "").strip().lower()
    if not _business_exists(business_type):
        return jsonify({"error": "不支持的业务类型"}), 400
    ensure_public_entry_schema()
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, business_type, token, status, created_at
        FROM public_entry_links
        WHERE business_type = ? AND token = ?
        LIMIT 1
        """,
        (business_type, token),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return jsonify({"error": "填写链接不存在"}), 404
    if row[3] != "active":
        return jsonify({"error": "填写链接已失效"}), 400
    payload = {
        "link": {
            "id": row[0],
            "business_type": row[1],
            "business_label": BUSINESS_LABELS.get(row[1], row[1]),
            "token": row[2],
            "status": row[3],
            "created_at": row[4],
        }
    }
    if business_type == "repair":
        payload["inventory_options"] = list_warehouse_stock_options()
        payload["room_options"] = _list_public_room_options()
        payload["tenant_names"] = _list_public_tenant_names()
    return jsonify(payload)


@public_entry_bp.route("/public-entry/<business_type>/<token>/upload-image", methods=["POST"])
def api_upload_public_entry_image(business_type, token):
    business_type = str(business_type or "").strip().lower()
    if not _business_exists(business_type):
        return jsonify({"error": "不支持的业务类型"}), 400
    ensure_public_entry_schema()
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, status FROM public_entry_links WHERE business_type = ? AND token = ? LIMIT 1",
        (business_type, token),
    )
    link = cur.fetchone()
    conn.close()
    if not link:
        return jsonify({"error": "填写链接不存在"}), 404
    if link[1] != "active":
        return jsonify({"error": "填写链接已失效"}), 400
    if "file" not in request.files:
        return jsonify({"error": "请上传图片文件"}), 400
    upload_file = request.files["file"]
    if not upload_file or not str(upload_file.filename or "").strip():
        return jsonify({"error": "请选择图片文件"}), 400
    try:
        file_url = _save_public_entry_image(business_type, upload_file)
        return jsonify({"message": "图片上传成功", "file_url": file_url})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e) or "图片上传失败"}), 500


@public_entry_bp.route("/public-entry/<business_type>/<token>/submit", methods=["POST"])
def api_submit_public_entry_form(business_type, token):
    business_type = str(business_type or "").strip().lower()
    if not _business_exists(business_type):
        return jsonify({"error": "不支持的业务类型"}), 400
    ensure_public_entry_schema()
    data = request.json or {}
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, status
        FROM public_entry_links
        WHERE business_type = ? AND token = ?
        LIMIT 1
        """,
        (business_type, token),
    )
    link = cur.fetchone()
    conn.close()
    if not link:
        return jsonify({"error": "填写链接不存在"}), 404
    if link[1] != "active":
        return jsonify({"error": "填写链接已失效"}), 400

    try:
        record_id = _create_record_by_business(business_type, data)
        _insert_submission_log(link[0], business_type, data, record_id)
        return jsonify({"message": f"{BUSINESS_LABELS[business_type]}已提交", "id": record_id})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except sqlite3.Error as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({"error": str(e) or "提交失败"}), 500
