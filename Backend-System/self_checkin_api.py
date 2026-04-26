# 该文件负责处理租客自助入住链接、待确认提交记录与管理员确认入库流程。
import re
import secrets
import sqlite3
from datetime import datetime

from flask import Blueprint, jsonify, request

from aliyun_ocr_utils import aliyun_ocr_is_configured, recognize_cn_id_card
from auth_api import token_required
from common import connect
from ocr_settings import build_ocr_status, record_ocr_usage
from tenants_api import _refresh_room_statuses, _refresh_tenant_statuses


self_checkin_bp = Blueprint("self_checkin", __name__, url_prefix="/api")


def ensure_self_checkin_schema():
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS self_checkin_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER NOT NULL,
            token TEXT UNIQUE NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            max_submissions INTEGER NOT NULL DEFAULT 20,
            expires_at TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (room_id) REFERENCES rooms(id)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS self_checkin_submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            link_id INTEGER,
            room_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            name TEXT NOT NULL,
            gender TEXT,
            nation TEXT,
            birth_date TEXT,
            id_card TEXT,
            address TEXT,
            phone TEXT,
            emergency_contact_name TEXT,
            emergency_contact_phone TEXT,
            check_in_date TEXT,
            check_out_date TEXT,
            remarks TEXT,
            submitted_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            approved_at TEXT,
            approved_tenant_id INTEGER,
            reject_reason TEXT,
            FOREIGN KEY (link_id) REFERENCES self_checkin_links(id) ON DELETE SET NULL,
            FOREIGN KEY (room_id) REFERENCES rooms(id)
        )
        """
    )
    cur.execute("PRAGMA table_info(self_checkin_submissions)")
    columns = cur.fetchall()
    link_id_col = next((col for col in columns if col[1] == "link_id"), None)
    needs_submission_migration = bool(link_id_col and link_id_col[3] == 1)
    if needs_submission_migration:
        cur.execute("ALTER TABLE self_checkin_submissions RENAME TO self_checkin_submissions_old")
        cur.execute(
            """
            CREATE TABLE self_checkin_submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                link_id INTEGER,
                room_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                name TEXT NOT NULL,
                gender TEXT,
                nation TEXT,
                birth_date TEXT,
                id_card TEXT,
                address TEXT,
                phone TEXT,
                emergency_contact_name TEXT,
                emergency_contact_phone TEXT,
                check_in_date TEXT,
                check_out_date TEXT,
                remarks TEXT,
                submitted_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                approved_at TEXT,
                approved_tenant_id INTEGER,
                reject_reason TEXT,
                FOREIGN KEY (link_id) REFERENCES self_checkin_links(id) ON DELETE SET NULL,
                FOREIGN KEY (room_id) REFERENCES rooms(id)
            )
            """
        )
        cur.execute(
            """
            INSERT INTO self_checkin_submissions (
                id, link_id, room_id, status, name, gender, nation, birth_date, id_card,
                address, phone, emergency_contact_name, emergency_contact_phone, check_in_date,
                check_out_date, remarks, submitted_at, approved_at, approved_tenant_id, reject_reason
            )
            SELECT
                id, link_id, room_id, status, name, gender, nation, birth_date, id_card,
                address, phone, emergency_contact_name, emergency_contact_phone, check_in_date,
                check_out_date, remarks, submitted_at, approved_at, approved_tenant_id, reject_reason
            FROM self_checkin_submissions_old
            """
        )
        cur.execute("DROP TABLE self_checkin_submissions_old")
    conn.commit()
    conn.close()


def _room_to_dict(row):
    return {
        "id": row[0],
        "room_no": row[1],
        "building": row[2],
        "room_type": row[3],
        "price": row[4],
        "deposit": row[5],
        "status": row[6],
    }


def _submission_to_dict(row):
    return {
        "id": row[0],
        "link_id": row[1],
        "room_id": row[2],
        "status": row[3],
        "name": row[4],
        "gender": row[5],
        "nation": row[6],
        "birth_date": row[7],
        "id_card": row[8],
        "address": row[9],
        "phone": row[10],
        "emergency_contact_name": row[11],
        "emergency_contact_phone": row[12],
        "check_in_date": row[13],
        "check_out_date": row[14],
        "remarks": row[15],
        "submitted_at": row[16],
        "approved_at": row[17],
        "approved_tenant_id": row[18],
        "reject_reason": row[19],
    }


def _now_text():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _today_text():
    return datetime.now().strftime("%Y-%m-%d")


ID_CARD_PATTERN = re.compile(r"^\d{17}[\dXx]$")
PHONE_PATTERN = re.compile(r"^1[3-9]\d{9}$")


def _derive_birth_date_from_id_card(id_card):
    raw = str(id_card or "").strip()
    if not ID_CARD_PATTERN.match(raw):
        return ""
    try:
        birth = datetime.strptime(raw[6:14], "%Y%m%d")
        return birth.strftime("%Y-%m-%d")
    except ValueError:
        return ""


@self_checkin_bp.route("/self-checkin/rooms/<int:room_id>/links", methods=["GET"])
@token_required
def api_list_self_checkin_links(current_user, room_id):
    ensure_self_checkin_schema()
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, token, status, max_submissions, expires_at, created_at
        FROM self_checkin_links
        WHERE room_id = ?
        ORDER BY id DESC
        """,
        (room_id,),
    )
    rows = cur.fetchall()
    conn.close()
    return jsonify(
        {
            "links": [
                {
                    "id": row[0],
                    "token": row[1],
                    "status": row[2],
                    "max_submissions": row[3],
                    "expires_at": row[4],
                    "created_at": row[5],
                }
                for row in rows
            ]
        }
    )


@self_checkin_bp.route("/self-checkin/rooms/<int:room_id>/links", methods=["POST"])
@token_required
def api_create_self_checkin_link(current_user, room_id):
    ensure_self_checkin_schema()
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, room_no, building, room_type, price, deposit, status
        FROM rooms
        WHERE id = ?
        """,
        (room_id,),
    )
    room = cur.fetchone()
    if not room:
        conn.close()
        return jsonify({"error": f"房间ID {room_id} 不存在"}), 404
    cur.execute(
        """
        SELECT id, token, status, created_at
        FROM self_checkin_links
        WHERE room_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (room_id,),
    )
    existing_link = cur.fetchone()
    if existing_link:
        conn.close()
        return jsonify({"error": "当前房间已有入住链接，请先删除原链接后再生成新链接"}), 400

    token = secrets.token_urlsafe(24)
    cur.execute(
        """
        INSERT INTO self_checkin_links (room_id, token, status, max_submissions)
        VALUES (?, ?, 'active', 20)
        """,
        (room_id, token),
    )
    link_id = cur.lastrowid
    conn.commit()
    conn.close()
    return jsonify(
        {
            "link": {
                "id": link_id,
                "token": token,
                "status": "active",
                "max_submissions": 20,
                "created_at": _now_text(),
            },
            "room": _room_to_dict(room),
        }
    )


@self_checkin_bp.route("/self-checkin/links/<int:link_id>/disable", methods=["POST"])
@token_required
def api_disable_self_checkin_link(current_user, link_id):
    ensure_self_checkin_schema()
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT id, status FROM self_checkin_links WHERE id = ?", (link_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "入住链接不存在"}), 404
    if row[1] == "disabled":
        conn.close()
        return jsonify({"message": "入住链接已停用"})
    cur.execute("UPDATE self_checkin_links SET status = 'disabled' WHERE id = ?", (link_id,))
    conn.commit()
    conn.close()
    return jsonify({"message": "入住链接已停用"})


@self_checkin_bp.route("/self-checkin/links/<int:link_id>/enable", methods=["POST"])
@token_required
def api_enable_self_checkin_link(current_user, link_id):
    ensure_self_checkin_schema()
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT id, status FROM self_checkin_links WHERE id = ?", (link_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "入住链接不存在"}), 404
    if row[1] == "active":
        conn.close()
        return jsonify({"message": "入住链接已启用"})
    cur.execute("UPDATE self_checkin_links SET status = 'active' WHERE id = ?", (link_id,))
    conn.commit()
    conn.close()
    return jsonify({"message": "入住链接已启用"})


@self_checkin_bp.route("/self-checkin/links/<int:link_id>", methods=["DELETE"])
@token_required
def api_delete_self_checkin_link(current_user, link_id):
    ensure_self_checkin_schema()
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT id FROM self_checkin_links WHERE id = ?", (link_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "入住链接不存在"}), 404
    cur.execute("DELETE FROM self_checkin_links WHERE id = ?", (link_id,))
    conn.commit()
    conn.close()
    return jsonify({"message": "入住链接已删除，关联提交记录已保留"})


@self_checkin_bp.route("/self-checkin/rooms/<int:room_id>/submissions", methods=["GET"])
@token_required
def api_list_self_checkin_submissions(current_user, room_id):
    ensure_self_checkin_schema()
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            id, link_id, room_id, status, name, gender, nation, birth_date, id_card,
            address, phone, emergency_contact_name, emergency_contact_phone, check_in_date,
            check_out_date, remarks, submitted_at, approved_at, approved_tenant_id, reject_reason
        FROM self_checkin_submissions
        WHERE room_id = ?
        ORDER BY id DESC
        """,
        (room_id,),
    )
    rows = cur.fetchall()
    conn.close()
    return jsonify({"submissions": [_submission_to_dict(row) for row in rows]})


@self_checkin_bp.route("/self-checkin/submissions/<int:submission_id>/approve", methods=["POST"])
@token_required
def api_approve_self_checkin_submission(current_user, submission_id):
    ensure_self_checkin_schema()
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            id, link_id, room_id, status, name, gender, nation, birth_date, id_card,
            address, phone, emergency_contact_name, emergency_contact_phone, check_in_date,
            check_out_date, remarks, submitted_at, approved_at, approved_tenant_id, reject_reason
        FROM self_checkin_submissions
        WHERE id = ?
        """,
        (submission_id,),
    )
    row = cur.fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "提交记录不存在"}), 404
    submission = _submission_to_dict(row)
    if submission["status"] == "approved":
        conn.close()
        return jsonify({"error": "该提交已确认入库"}), 400

    cur.execute("SELECT id FROM rooms WHERE id = ?", (submission["room_id"],))
    room = cur.fetchone()
    if not room:
        conn.close()
        return jsonify({"error": "关联房间不存在"}), 404

    try:
        birth_date = _derive_birth_date_from_id_card(submission["id_card"]) or submission["birth_date"] or None
        cur.execute(
            """
            INSERT INTO tenants (
                name, gender, nation, birth_date, id_card, address, front_img, back_img,
                phone, emergency_contact_name, emergency_contact_phone,
                check_in_date, check_out_date, room_id, remarks, status
            ) VALUES (?, ?, ?, ?, ?, ?, '', '', ?, ?, ?, ?, ?, ?, ?, '在住')
            """,
            (
                submission["name"],
                submission["gender"] or "",
                submission["nation"] or "汉族",
                birth_date,
                submission["id_card"] or "",
                submission["address"] or "",
                submission["phone"] or "",
                submission["emergency_contact_name"] or "",
                submission["emergency_contact_phone"] or "",
                submission["check_in_date"] or _today_text(),
                submission["check_out_date"] or "",
                submission["room_id"],
                submission["remarks"] or "",
            ),
        )
        tenant_id = cur.lastrowid
        cur.execute(
            """
            UPDATE self_checkin_submissions
            SET status = 'approved',
                approved_at = ?,
                approved_tenant_id = ?
            WHERE id = ?
            """,
            (_now_text(), tenant_id, submission_id),
        )
        _refresh_tenant_statuses(conn)
        _refresh_room_statuses(conn)
        conn.commit()
        conn.close()
        return jsonify({"message": "入住提交已确认入库", "tenant_id": tenant_id})
    except sqlite3.Error as e:
        conn.rollback()
        conn.close()
        return jsonify({"error": str(e)}), 500


@self_checkin_bp.route("/self-checkin/submissions/<int:submission_id>/reject", methods=["POST"])
@token_required
def api_reject_self_checkin_submission(current_user, submission_id):
    ensure_self_checkin_schema()
    data = request.json or {}
    reject_reason = str(data.get("reject_reason") or "").strip()
    if reject_reason == "":
        return jsonify({"error": "请填写驳回原因"}), 400

    conn = connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, status FROM self_checkin_submissions WHERE id = ?",
        (submission_id,),
    )
    row = cur.fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "提交记录不存在"}), 404
    if row[1] == "approved":
        conn.close()
        return jsonify({"error": "该提交已确认入库，无法驳回"}), 400

    cur.execute(
        """
        UPDATE self_checkin_submissions
        SET status = 'rejected',
            reject_reason = ?
        WHERE id = ?
        """,
        (reject_reason, submission_id),
    )
    conn.commit()
    conn.close()
    return jsonify({"message": "入住提交已驳回"})


@self_checkin_bp.route("/self-checkin/submissions/<int:submission_id>", methods=["DELETE"])
@token_required
def api_delete_self_checkin_submission(current_user, submission_id):
    ensure_self_checkin_schema()
    conn = connect()
    cur = conn.cursor()
    cur.execute("DELETE FROM self_checkin_submissions WHERE id = ?", (submission_id,))
    if cur.rowcount == 0:
        conn.close()
        return jsonify({"error": "提交记录不存在"}), 404
    conn.commit()
    conn.close()
    return jsonify({"message": "入住提交记录已删除"})


@self_checkin_bp.route("/public/self-checkin/<token>", methods=["GET"])
def api_get_public_self_checkin_form(token):
    ensure_self_checkin_schema()
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            l.id, l.room_id, l.token, l.status, l.max_submissions, l.expires_at,
            r.id, r.room_no, r.building, r.room_type, r.price, r.deposit, r.status
        FROM self_checkin_links l
        JOIN rooms r ON r.id = l.room_id
        WHERE l.token = ?
        """,
        (token,),
    )
    row = cur.fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "入住链接不存在"}), 404
    if row[3] != "active":
        conn.close()
        return jsonify({"error": "入住链接已失效"}), 400
    cur.execute(
        "SELECT COUNT(*) FROM self_checkin_submissions WHERE link_id = ?",
        (row[0],),
    )
    submission_count = cur.fetchone()[0]
    conn.close()
    return jsonify(
        {
            "link": {
                "id": row[0],
                "room_id": row[1],
                "token": row[2],
                "status": row[3],
                "max_submissions": row[4],
                "expires_at": row[5],
                "submission_count": submission_count,
            },
            "room": {
                "id": row[6],
                "room_no": row[7],
                "building": row[8],
                "room_type": row[9],
                "price": row[10],
                "deposit": row[11],
                "status": row[12],
            },
            "ocr": build_ocr_status(),
        }
    )


@self_checkin_bp.route("/public/self-checkin/<token>/recognize-id-card", methods=["POST"])
def api_recognize_public_self_checkin_id_card(token):
    ensure_self_checkin_schema()
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, status
        FROM self_checkin_links
        WHERE token = ?
        """,
        (token,),
    )
    link = cur.fetchone()
    conn.close()
    if not link:
        return jsonify({"error": "入住链接不存在"}), 404
    if link[1] != "active":
        return jsonify({"error": "入住链接已失效"}), 400
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
        record_ocr_usage(source="public_self_checkin", token=token)
        result["ocr"] = build_ocr_status()
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e) or "身份证识别失败"}), 500


@self_checkin_bp.route("/public/self-checkin/<token>/submit", methods=["POST"])
def api_submit_public_self_checkin(token):
    ensure_self_checkin_schema()
    data = request.json or {}
    required = [
        "name",
        "gender",
        "id_card",
        "phone",
        "emergency_contact_name",
        "emergency_contact_phone",
        "check_in_date",
        "check_out_date",
    ]
    if not all(str(data.get(key) or "").strip() for key in required):
        return jsonify({"error": "缺少必要参数", "required": required}), 400

    id_card = str(data.get("id_card") or "").strip()
    if not ID_CARD_PATTERN.match(id_card):
        return jsonify({"error": "身份证号格式不正确"}), 400

    birth_date = _derive_birth_date_from_id_card(id_card)
    if not birth_date:
        return jsonify({"error": "身份证号中的出生日期无效"}), 400

    phone = str(data.get("phone") or "").strip()
    emergency_contact_phone = str(data.get("emergency_contact_phone") or "").strip()
    if not PHONE_PATTERN.match(phone):
        return jsonify({"error": "联系电话格式不正确"}), 400
    if not PHONE_PATTERN.match(emergency_contact_phone):
        return jsonify({"error": "紧急联系电话格式不正确"}), 400

    check_in_date = str(data.get("check_in_date") or "").strip()
    check_out_date = str(data.get("check_out_date") or "").strip()
    try:
        check_in_dt = datetime.strptime(check_in_date, "%Y-%m-%d")
        check_out_dt = datetime.strptime(check_out_date, "%Y-%m-%d")
    except ValueError:
        return jsonify({"error": "入住日期或退房日期格式不正确"}), 400
    if check_out_dt <= check_in_dt:
        return jsonify({"error": "退房日期必须晚于入住日期"}), 400

    if not str(data.get("address") or "").strip():
        return jsonify({"error": "请填写住址"}), 400

    conn = connect()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, room_id, status, max_submissions
        FROM self_checkin_links
        WHERE token = ?
        """,
        (token,),
    )
    link = cur.fetchone()
    if not link:
        conn.close()
        return jsonify({"error": "入住链接不存在"}), 404
    if link[2] != "active":
        conn.close()
        return jsonify({"error": "入住链接已失效"}), 400
    cur.execute("SELECT COUNT(*) FROM self_checkin_submissions WHERE link_id = ?", (link[0],))
    count = cur.fetchone()[0]
    if count >= int(link[3] or 20):
        conn.close()
        return jsonify({"error": "该入住链接提交次数已达上限"}), 400

    try:
        cur.execute(
            """
            INSERT INTO self_checkin_submissions (
                link_id, room_id, status, name, gender, nation, birth_date, id_card,
                address, phone, emergency_contact_name, emergency_contact_phone, check_in_date,
                check_out_date, remarks
            ) VALUES (?, ?, 'pending', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                link[0],
                link[1],
                data.get("name", "").strip(),
                data.get("gender", "").strip(),
                data.get("nation", "汉族").strip(),
                birth_date,
                id_card,
                data.get("address", "").strip(),
                phone,
                data.get("emergency_contact_name", "").strip(),
                emergency_contact_phone,
                check_in_date,
                check_out_date,
                data.get("remarks", "").strip(),
            ),
        )
        submission_id = cur.lastrowid
        conn.commit()
        conn.close()
        return jsonify({"message": "入住信息已提交，等待管理员确认", "submission_id": submission_id})
    except sqlite3.Error as e:
        conn.rollback()
        conn.close()
        return jsonify({"error": str(e)}), 500
