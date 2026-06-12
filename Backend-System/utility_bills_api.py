import sqlite3
import json
import re
import os
import base64
from datetime import datetime

from flask import Blueprint, jsonify, request

from auth_api import token_required
from ai_client import call_configured_ai, get_active_ai_model
from common import connect
from local_ai_settings import load_ai_settings
from utility_account_config import get_utility_account_options


utility_bills_bp = Blueprint("utility_bills", __name__, url_prefix="/api")
UTILITY_AI_TIMEOUT_SECONDS = int(os.getenv("UTILITY_AI_TIMEOUT_SECONDS", "120"))

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


def _normalize_match_key(value):
    text = _clean_text(value).lower()
    if text == "":
        return ""
    text = re.sub(r"(用户编号|用户号|客户编号|客户号|户号|账号|账户|房号|缴费地址|用电地址|用水地址)", "", text)
    text = re.sub(r"[\s\-_:/\\,，.。()（）\[\]{}<>]+", "", text)
    return text


def _extract_digits(value):
    return re.sub(r"\D+", "", _clean_text(value))


def _longest_common_digit_run(left, right):
    a = _extract_digits(left)
    b = _extract_digits(right)
    if len(a) < 3 or len(b) < 3:
        return ""

    best = ""
    dp = [0] * (len(b) + 1)
    for i in range(1, len(a) + 1):
        next_dp = [0] * (len(b) + 1)
        for j in range(1, len(b) + 1):
            if a[i - 1] == b[j - 1]:
                next_dp[j] = dp[j - 1] + 1
                if next_dp[j] > len(best):
                    best = a[i - next_dp[j]:i]
        dp = next_dp
    return best if len(best) >= 3 else ""


def _normalize_account_list(values):
    normalized = []
    for value in values or []:
        if isinstance(value, dict):
            text = _clean_text(value.get("account") or value.get("subject"))
        else:
            text = _clean_text(value)
        if text and text not in normalized:
            normalized.append(text)
    return normalized


def _get_known_utility_accounts():
    payload = get_utility_account_options()
    if not isinstance(payload, dict):
        payload = {}
    return {
        "electricity": payload.get("electricity") or [],
        "water": payload.get("water") or [],
    }


def _build_known_accounts_text(known_accounts):
    electricity = "、".join(_normalize_account_list(known_accounts.get("electricity") or [])) or "无"
    water = "、".join(_normalize_account_list(known_accounts.get("water") or [])) or "无"
    return f"电费账户：{electricity}\n水费账户：{water}"


def _today_text():
    return datetime.now().strftime("%Y-%m-%d")


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


def _normalize_ai_utility_payload(payload):
    data = payload if isinstance(payload, dict) else {}
    utility_type = _normalize_utility_type(data.get("utility_type")) or "electricity"
    today = datetime.now()

    try:
        year = _parse_year(data.get("year"))
    except Exception:
        year = today.year

    try:
        month = _parse_month(data.get("month"))
    except Exception:
        month = today.month

    try:
        amount = _parse_amount(data.get("amount", 0))
    except Exception:
        amount = 0

    recognized_account = _clean_text(data.get("account") or data.get("subject"))
    recognized_user_code = _clean_text(
        data.get("user_code")
        or data.get("user_id")
        or data.get("customer_code")
        or data.get("meter_code")
    )
    recognized_address = _clean_text(
        data.get("address")
        or data.get("payment_address")
        or data.get("service_address")
    )

    return {
        "utility_type": utility_type,
        "account": recognized_account,
        "year": year,
        "month": month,
        "amount": amount,
        "payer": _clean_text(data.get("payer")),
        "remarks": _clean_text(data.get("remarks")),
        "recognized_account": recognized_account,
        "recognized_user_code": recognized_user_code,
        "recognized_address": recognized_address,
    }


def _match_known_utility_account(draft, known_accounts):
    utility_type = _normalize_utility_type(draft.get("utility_type")) or "electricity"
    raw_options = known_accounts.get(utility_type) or []
    if not raw_options:
        return {
            "matched_account": "",
            "match_confidence": "none",
            "match_reason": "",
        }

    indexed_options = [
        {
            "account": _clean_text(item),
            "normalized": _normalize_match_key(item),
        }
        for item in raw_options
        if _clean_text(item)
    ]

    candidates = [
        ("账户", draft.get("recognized_account") or draft.get("account")),
        ("用户编号", draft.get("recognized_user_code")),
        ("缴费地址", draft.get("recognized_address")),
    ]

    for label, raw in candidates:
        normalized = _normalize_match_key(raw)
        if not normalized:
            continue
        for option in indexed_options:
            if normalized == option["normalized"]:
                return {
                    "matched_account": option["account"],
                    "match_confidence": "high",
                    "match_reason": f"{label}与系统账户完全一致",
                }

    for label, raw in candidates:
        normalized = _normalize_match_key(raw)
        if not normalized:
            continue
        for option in indexed_options:
            comparable_keys = [option["normalized"]] if option["normalized"] else []
            if any(len(normalized) >= 3 and len(key) >= 3 and (normalized in key or key in normalized) for key in comparable_keys):
                return {
                    "matched_account": option["account"],
                    "match_confidence": "medium",
                    "match_reason": f"{label}与系统账户部分匹配",
                }

    return {
        "matched_account": "",
        "match_confidence": "none",
        "match_reason": "未匹配到系统账户",
    }


def _build_utility_ai_prompt(user_text, image_count, known_accounts):
    today = datetime.now()
    return f"""
你是房屋管理系统的水电费录入助手。请根据用户文字和图片识别账单信息，只返回一个 JSON 对象，不要解释，不要 Markdown。

今天日期：{today.strftime('%Y-%m-%d')}
图片数量：{image_count}
系统已存在水电费账户：
{_build_known_accounts_text(known_accounts)}

输出 JSON 格式：
{{
  "utility_type": "electricity 或 water",
  "account": "账户名称",
  "user_code": "用户编号/户号/客户编号",
  "address": "缴费地址/用电地址/用水地址",
  "year": {today.year},
  "month": {today.month},
  "amount": 0,
  "payer": "",
  "remarks": ""
}}

规则：
- utility_type 只能是 electricity 或 water。电费、电、水费、水都要自动归一化。
- account 只填写图片或文字里明确出现的账户、房号、户号、账单名称；不要凭空猜系统账户。
- user_code 尽量提取“用户编号”“户号”“客户号”等唯一编号，没有就留空。
- address 尽量提取“缴费地址”“用电地址”“用水地址”等地址信息，没有就留空。
- 年月优先识别账单上的缴费年月；无法判断时用今天的年月。
- amount 只保留数字，不要货币符号。
- payer 只有明确出现时才填写。
- remarks 可简短记录来源，例如“微信缴费截图”“支付宝账单”。
- 图片可能是账单截图、支付记录、聊天截图、手写记录，请提取最适合录入的一条水费或电费账单。

用户文字：
{_clean_text(user_text)}
""".strip()


def _call_utility_ai(prompt, images):
    return call_configured_ai(
        prompt,
        images,
        ollama_model_fallback=os.getenv("UTILITY_AI_MODEL", "qwen2.5vl:3b"),
        timeout_seconds=UTILITY_AI_TIMEOUT_SECONDS,
    )


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


@utility_bills_bp.route("/utility-bills/ai-draft", methods=["POST"])
@token_required
def create_utility_bill_ai_draft(current_user):
    if not load_ai_settings().get("enabled", True):
        return jsonify({"error": "AI 功能已停用，请在系统维护页面启用后再使用"}), 503

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

    known_accounts = _get_known_utility_accounts()
    prompt = _build_utility_ai_prompt(user_text, len(images), known_accounts)
    try:
        result = _call_utility_ai(prompt, images)
        parsed = _extract_json_object(result.get("response") or "")
        draft = _normalize_ai_utility_payload(parsed)
        match = _match_known_utility_account(draft, known_accounts)
        draft["matched_account"] = match["matched_account"]
        draft["match_confidence"] = match["match_confidence"]
        draft["match_reason"] = match["match_reason"]
        draft["known_accounts"] = _normalize_account_list(known_accounts.get(draft["utility_type"], []))
        if match["matched_account"]:
            draft["account"] = match["matched_account"]
        return jsonify({
            "draft": draft,
            "model": result.get("model") or get_active_ai_model(),
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 502


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
