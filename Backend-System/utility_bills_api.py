import sqlite3
import json
from datetime import datetime

from flask import Blueprint, jsonify, request

from auth_api import token_required
from common import connect
from utility_account_config import get_utility_account_options


utility_bills_bp = Blueprint("utility_bills", __name__, url_prefix="/api")

UTILITY_TYPE_MAP = {
    "electricity": "electricity",
    "electric": "electricity",
    "电费": "electricity",
    "water": "water",
    "水费": "water",
}

UTILITY_LABELS = {
    "electricity": "电费",
    "water": "水费",
}


def ensure_utility_bills_schema():
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS utility_bills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            utility_type TEXT NOT NULL,
            subject TEXT NOT NULL,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            amount REAL NOT NULL DEFAULT 0,
            payer TEXT DEFAULT '',
            remarks TEXT DEFAULT '',
            bill_images TEXT DEFAULT '[]',
            created_at DATETIME DEFAULT (DATETIME('now')),
            updated_at DATETIME DEFAULT (DATETIME('now')),
            UNIQUE (utility_type, subject, year, month)
        )
        """
    )
    cursor.execute("PRAGMA table_info(utility_bills)")
    columns = {row[1] for row in cursor.fetchall()}
    if "bill_images" not in columns:
        cursor.execute("ALTER TABLE utility_bills ADD COLUMN bill_images TEXT DEFAULT '[]'")
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_utility_bills_year_type
        ON utility_bills (year, utility_type, subject, month)
        """
    )
    cursor.execute(
        "DROP TABLE IF EXISTS utility_bill_notes"
    )
    conn.commit()
    conn.close()


def _normalize_utility_type(value):
    return UTILITY_TYPE_MAP.get(str(value or "").strip().lower())


def _utility_label(utility_type):
    return UTILITY_LABELS.get(utility_type, utility_type)


def _parse_year(value):
    raw = str(value or "").strip()
    year = datetime.now().year if raw == "" else int(raw)
    if year < 2000 or year > 2100:
        raise ValueError("年份必须在 2000 到 2100 之间")
    return year


def _parse_month(value):
    month = int(value)
    if month < 1 or month > 12:
        raise ValueError("月份必须在 1 到 12 之间")
    return month


def _parse_amount(value):
    amount = round(float(value), 2)
    if amount < 0:
        raise ValueError("金额不能小于 0")
    return amount


def _clean_text(value):
    return str(value or "").strip()


def _parse_bill_images(value):
    if isinstance(value, list):
        values = value
    else:
        text = str(value or "").strip()
        if text == "":
            return []
        try:
            parsed = json.loads(text)
            values = parsed if isinstance(parsed, list) else [text]
        except Exception:
            values = [part.strip() for part in text.split(",")]

    normalized = []
    for item in values:
        text = str(item or "").strip()
        if text and text not in normalized:
            normalized.append(text)
    return normalized


def _dump_bill_images(images):
    return json.dumps(_parse_bill_images(images), ensure_ascii=False)


def _extract_bill_images_from_payload(data):
    payload = data if isinstance(data, dict) else {}
    raw = payload.get("bill_images")
    if isinstance(raw, list):
        return _parse_bill_images(raw)
    return _parse_bill_images(payload.get("bill_image") or raw)


def _row_to_bill(row):
    bill_images = _parse_bill_images(row["bill_images"] if "bill_images" in row.keys() else "")
    return {
        "id": row["id"],
        "utility_type": row["utility_type"],
        "utility_label": _utility_label(row["utility_type"]),
        "account": row["subject"] or "",
        "subject": row["subject"] or "",
        "year": int(row["year"] or 0),
        "month": int(row["month"] or 0),
        "amount": round(float(row["amount"] or 0), 2),
        "payer": row["payer"] or "",
        "remarks": row["remarks"] or "",
        "bill_images": bill_images,
        "bill_image": bill_images[0] if len(bill_images) > 0 else "",
        "created_at": row["created_at"] or "",
        "updated_at": row["updated_at"] or "",
    }


def _empty_summary(utility_type):
    return {
        "type": utility_type,
        "label": _utility_label(utility_type),
        "annualTotal": 0,
        "subjectCount": 0,
        "monthlyTotals": {str(month): 0 for month in range(1, 13)},
        "subjects": [],
        "records": [],
    }


def _build_summary(conn, year):
    cursor = conn.cursor()
    result = {
        "year": year,
        "months": list(range(1, 13)),
        "availableYears": [],
        "summaries": {
            "electricity": _empty_summary("electricity"),
            "water": _empty_summary("water"),
        },
    }

    cursor.execute(
        """
        SELECT year
        FROM utility_bills
        ORDER BY year DESC
        """
    )
    result["availableYears"] = [int(row["year"]) for row in cursor.fetchall() if row["year"] is not None]
    if year not in result["availableYears"]:
        result["availableYears"].insert(0, year)

    cursor.execute(
        """
        SELECT id, utility_type, subject, year, month, amount, payer, remarks, bill_images, created_at, updated_at
        FROM utility_bills
        WHERE year = ?
        ORDER BY utility_type, subject COLLATE NOCASE, month ASC, id ASC
        """,
        (year,),
    )
    subject_maps = {
        "electricity": {},
        "water": {},
    }
    for row in cursor.fetchall():
        bill = _row_to_bill(row)
        utility_type = bill["utility_type"]
        if utility_type not in result["summaries"]:
            continue
        summary = result["summaries"][utility_type]
        summary["records"].append(bill)
        summary["annualTotal"] = round(summary["annualTotal"] + bill["amount"], 2)
        month_key = str(bill["month"])
        summary["monthlyTotals"][month_key] = round(summary["monthlyTotals"][month_key] + bill["amount"], 2)

        subject_key = bill["subject"]
        if subject_key not in subject_maps[utility_type]:
            subject_maps[utility_type][subject_key] = {
                "account": subject_key,
                "subject": subject_key,
                "totalAmount": 0,
                "months": {},
            }
        subject_entry = subject_maps[utility_type][subject_key]
        subject_entry["months"][month_key] = bill
        subject_entry["totalAmount"] = round(subject_entry["totalAmount"] + bill["amount"], 2)

    for utility_type, summary in result["summaries"].items():
        subjects = list(subject_maps[utility_type].values())
        subjects.sort(key=lambda item: item["subject"])
        summary["subjects"] = subjects
        summary["subjectCount"] = len(subjects)

    return result


def _load_bill_by_id(cursor, bill_id):
    cursor.execute(
        """
        SELECT id, utility_type, subject, year, month, amount, payer, remarks, bill_images, created_at, updated_at
        FROM utility_bills
        WHERE id = ?
        """,
        (bill_id,),
    )
    return cursor.fetchone()


@utility_bills_bp.route("/utility-bills/account-options", methods=["GET"])
@token_required
def get_utility_bill_account_options(current_user):
    return jsonify(get_utility_account_options())


@utility_bills_bp.route("/utility-bills/summary", methods=["GET"])
@token_required
def get_utility_bill_summary(current_user):
    try:
        year = _parse_year(request.args.get("year"))
    except (TypeError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400

    conn = connect()
    conn.row_factory = sqlite3.Row
    try:
        payload = _build_summary(conn, year)
        payload["accountOptions"] = get_utility_account_options()
    finally:
        conn.close()
    return jsonify(payload)


@utility_bills_bp.route("/utility-bills", methods=["POST"])
@token_required
def upsert_utility_bill(current_user):
    data = request.json or {}
    utility_type = _normalize_utility_type(data.get("utility_type"))
    if not utility_type:
        return jsonify({"error": "费用类型必须是电费或水费"}), 400

    subject = _clean_text(data.get("account") or data.get("subject"))
    if subject == "":
        return jsonify({"error": "请填写账户"}), 400

    try:
        year = _parse_year(data.get("year"))
        month = _parse_month(data.get("month"))
        amount = _parse_amount(data.get("amount", 0))
    except (TypeError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400

    payer = _clean_text(data.get("payer"))
    remarks = _clean_text(data.get("remarks"))
    bill_images = _extract_bill_images_from_payload(data)

    conn = connect()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id
        FROM utility_bills
        WHERE utility_type = ? AND subject = ? AND year = ? AND month = ?
        """,
        (utility_type, subject, year, month),
    )
    existing = cursor.fetchone()

    try:
        if existing:
            cursor.execute(
                """
                UPDATE utility_bills
                SET amount = ?, payer = ?, remarks = ?, bill_images = ?, updated_at = DATETIME('now')
                WHERE id = ?
                """,
                (amount, payer, remarks, _dump_bill_images(bill_images), existing["id"]),
            )
            bill_id = int(existing["id"])
            message = "水电费账单已更新"
        else:
            cursor.execute(
                """
                INSERT INTO utility_bills (utility_type, subject, year, month, amount, payer, remarks, bill_images, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, DATETIME('now'), DATETIME('now'))
                """,
                (utility_type, subject, year, month, amount, payer, remarks, _dump_bill_images(bill_images)),
            )
            bill_id = int(cursor.lastrowid)
            message = "水电费账单已新增"

        row = _load_bill_by_id(cursor, bill_id)
        conn.commit()
        return jsonify({"message": message, "bill": _row_to_bill(row)}), 200
    except sqlite3.Error as exc:
        conn.rollback()
        return jsonify({"error": str(exc)}), 500
    finally:
        conn.close()


@utility_bills_bp.route("/utility-bills/<int:bill_id>", methods=["PUT"])
@token_required
def update_utility_bill(current_user, bill_id):
    data = request.json or {}
    utility_type = _normalize_utility_type(data.get("utility_type"))
    if not utility_type:
        return jsonify({"error": "费用类型必须是电费或水费"}), 400

    subject = _clean_text(data.get("account") or data.get("subject"))
    if subject == "":
        return jsonify({"error": "请填写账户"}), 400

    try:
        year = _parse_year(data.get("year"))
        month = _parse_month(data.get("month"))
        amount = _parse_amount(data.get("amount", 0))
    except (TypeError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400

    payer = _clean_text(data.get("payer"))
    remarks = _clean_text(data.get("remarks"))
    bill_images = _extract_bill_images_from_payload(data)

    conn = connect()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM utility_bills WHERE id = ?", (bill_id,))
    existing = cursor.fetchone()
    if not existing:
        conn.close()
        return jsonify({"error": f"水电费账单 {bill_id} 不存在"}), 404

    cursor.execute(
        """
        SELECT id
        FROM utility_bills
        WHERE utility_type = ? AND subject = ? AND year = ? AND month = ? AND id <> ?
        """,
        (utility_type, subject, year, month, bill_id),
    )
    duplicate = cursor.fetchone()
    if duplicate:
        conn.close()
        return jsonify({"error": "该房号在当前年月已经存在账单，请直接修改原记录"}), 400

    try:
        cursor.execute(
            """
            UPDATE utility_bills
            SET utility_type = ?, subject = ?, year = ?, month = ?, amount = ?, payer = ?, remarks = ?, bill_images = ?, updated_at = DATETIME('now')
            WHERE id = ?
            """,
            (utility_type, subject, year, month, amount, payer, remarks, _dump_bill_images(bill_images), bill_id),
        )
        row = _load_bill_by_id(cursor, bill_id)
        conn.commit()
        return jsonify({"message": "水电费账单已更新", "bill": _row_to_bill(row)}), 200
    except sqlite3.Error as exc:
        conn.rollback()
        return jsonify({"error": str(exc)}), 500
    finally:
        conn.close()


@utility_bills_bp.route("/utility-bills/<int:bill_id>/images", methods=["PUT"])
@token_required
def update_utility_bill_images(current_user, bill_id):
    data = request.json if isinstance(request.json, dict) else {}
    bill_images = _extract_bill_images_from_payload(data)

    conn = connect()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM utility_bills WHERE id = ?", (bill_id,))
    existing = cursor.fetchone()
    if not existing:
        conn.close()
        return jsonify({"error": f"水电费账单 {bill_id} 不存在"}), 404

    try:
        cursor.execute(
            """
            UPDATE utility_bills
            SET bill_images = ?, updated_at = DATETIME('now')
            WHERE id = ?
            """,
            (_dump_bill_images(bill_images), bill_id),
        )
        row = _load_bill_by_id(cursor, bill_id)
        conn.commit()
        return jsonify({"message": "账单图片已更新", "bill": _row_to_bill(row)}), 200
    except sqlite3.Error as exc:
        conn.rollback()
        return jsonify({"error": str(exc)}), 500
    finally:
        conn.close()


@utility_bills_bp.route("/utility-bills/<int:bill_id>", methods=["DELETE"])
@token_required
def delete_utility_bill(current_user, bill_id):
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM utility_bills WHERE id = ?", (bill_id,))
    existing = cursor.fetchone()
    if not existing:
        conn.close()
        return jsonify({"error": f"水电费账单 {bill_id} 不存在"}), 404

    try:
        cursor.execute("DELETE FROM utility_bills WHERE id = ?", (bill_id,))
        conn.commit()
        return jsonify({"message": f"水电费账单 {bill_id} 已删除"}), 200
    except sqlite3.Error as exc:
        conn.rollback()
        return jsonify({"error": str(exc)}), 500
    finally:
        conn.close()
