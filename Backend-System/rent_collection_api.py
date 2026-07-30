import base64
import json
import secrets
import sqlite3
import uuid
from datetime import date, datetime
from urllib.parse import quote

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from flask import Blueprint, jsonify, request

from auth_api import token_required
from common import connect
from payment_settings import build_payment_status, load_payment_settings
from rent_ledger_api import _parse_amount, _parse_date, _parse_images, _rebuild_rent_ledger_year


rent_collection_bp = Blueprint("rent_collection", __name__, url_prefix="/api")

RENT_LINK_STATUSES = {"active", "disabled"}
RENT_ORDER_STATUSES = {"created", "pending", "paid", "failed", "closed"}
PAYMENT_PROVIDER_LABELS = {
    "wechat": "微信支付",
    "alipay": "支付宝",
}


def ensure_rent_collection_schema():
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS rent_collection_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER NOT NULL UNIQUE,
            token TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (room_id) REFERENCES rooms(id)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS rent_payment_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            link_id INTEGER,
            room_id INTEGER NOT NULL,
            tenant_id INTEGER NOT NULL,
            tenant_name TEXT DEFAULT '',
            building TEXT DEFAULT '',
            room_no TEXT DEFAULT '',
            provider TEXT NOT NULL,
            out_trade_no TEXT NOT NULL UNIQUE,
            external_trade_no TEXT DEFAULT '',
            subject TEXT DEFAULT '',
            amount REAL NOT NULL DEFAULT 0,
            currency TEXT DEFAULT 'CNY',
            selected_periods_json TEXT DEFAULT '[]',
            period_summary TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'created',
            provider_payload TEXT DEFAULT '{}',
            provider_code_url TEXT DEFAULT '',
            provider_redirect_url TEXT DEFAULT '',
            callback_verified INTEGER NOT NULL DEFAULT 0,
            callback_count INTEGER NOT NULL DEFAULT 0,
            paid_amount REAL NOT NULL DEFAULT 0,
            paid_at TEXT DEFAULT '',
            payment_completed_at TEXT DEFAULT '',
            remarks TEXT DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (link_id) REFERENCES rent_collection_links(id) ON DELETE SET NULL,
            FOREIGN KEY (room_id) REFERENCES rooms(id),
            FOREIGN KEY (tenant_id) REFERENCES tenants(id)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS rent_payment_callbacks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider TEXT NOT NULL,
            out_trade_no TEXT DEFAULT '',
            external_trade_no TEXT DEFAULT '',
            verify_status TEXT DEFAULT '',
            payload_json TEXT DEFAULT '',
            headers_json TEXT DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        )
        """
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_rent_payment_orders_room ON rent_payment_orders (room_id, tenant_id, status)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_rent_payment_orders_trade_no ON rent_payment_orders (out_trade_no, provider)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_rent_payment_callbacks_trade_no ON rent_payment_callbacks (out_trade_no, provider)")
    conn.commit()
    conn.close()


def _clean_text(value):
    return str(value or "").strip()


def _now_text():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _today_text():
    return date.today().strftime("%Y-%m-%d")


def _normalize_link_status(value):
    text = _clean_text(value).lower()
    return text if text in RENT_LINK_STATUSES else "active"


def _normalize_order_status(value):
    text = _clean_text(value).lower()
    return text if text in RENT_ORDER_STATUSES else "created"


def _parse_json_list(value):
    if isinstance(value, list):
        items = value
    else:
        raw = _clean_text(value)
        if not raw:
            return []
        try:
            items = json.loads(raw)
        except Exception:
            return []
    return items if isinstance(items, list) else []


def _dump_json(value):
    return json.dumps(value, ensure_ascii=False)


def _to_minor_units(amount):
    return int(round(float(amount or 0) * 100))


def _from_minor_units(value):
    try:
        return round(float(value) / 100.0, 2)
    except Exception:
        return 0.0


def _append_text_line(existing_value, new_line):
    existing = _clean_text(existing_value)
    line = _clean_text(new_line)
    if not line:
        return existing
    if not existing:
        return line
    if line in existing:
        return existing
    return f"{existing}\n{line}"


def _load_room_row(conn, room_id):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, room_no, building, room_type, price, price_unit, deposit, status
        FROM rooms
        WHERE id = ?
        LIMIT 1
        """,
        (room_id,),
    )
    row = cur.fetchone()
    if not row:
        return None
    return {
        "id": int(row[0]),
        "room_no": _clean_text(row[1]),
        "building": _clean_text(row[2]),
        "room_type": _clean_text(row[3]),
        "price": round(float(row[4] or 0), 2),
        "price_unit": _clean_text(row[5]) or "月",
        "deposit": round(float(row[6] or 0), 2),
        "status": _clean_text(row[7]) or "空闲",
    }


def _room_display_label(room):
    room_no = _clean_text(room.get("room_no"))
    building = _clean_text(room.get("building"))
    if building and room_no and not room_no.upper().startswith(f"{building.upper()}-"):
        return f"{building}-{room_no}"
    return room_no or building


def _load_active_tenants_for_room(conn, room_id):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT t.id, t.name, s.check_in_date, s.planned_check_out_date, s.status, s.id
        FROM tenant_stays s
        JOIN tenants t ON t.id = s.tenant_id
        WHERE s.room_id = ? AND s.status = '在住'
        ORDER BY s.check_in_date ASC, s.id ASC
        """,
        (room_id,),
    )
    rows = cur.fetchall()
    return [
        {
            "id": int(row[0]),
            "name": _clean_text(row[1]),
            "check_in_date": _clean_text(row[2]),
            "check_out_date": _clean_text(row[3]),
            "status": _clean_text(row[4]) or "在住",
            "stay_id": int(row[5]),
        }
        for row in rows
    ]


def _collect_years_for_tenant(tenant):
    lease_start = _parse_date(tenant.get("check_in_date"))
    lease_end = _parse_date(tenant.get("check_out_date"))
    if not lease_start:
        return set()
    if not lease_end or lease_end < lease_start:
        lease_end = max(lease_start, date.today())
    end_year = max(lease_end.year, date.today().year)
    max_year = min(end_year, lease_start.year + 20)
    return set(range(lease_start.year, max_year + 1))


def _ensure_room_ledger_years(conn, room_id):
    years = {date.today().year}
    for tenant in _load_active_tenants_for_room(conn, room_id):
        years.update(_collect_years_for_tenant(tenant))
    for year in sorted(int(item) for item in years if item):
        _rebuild_rent_ledger_year(conn, year)
    conn.commit()


def _load_room_entries(conn, room_id):
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        SELECT *
        FROM rent_ledger_entries
        WHERE room_id = ?
        ORDER BY period_start ASC, period_index ASC, id ASC
        """,
        (room_id,),
    )
    return cur.fetchall()


def _load_tenant_entries(conn, tenant_id, stay_id=None):
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        SELECT *
        FROM rent_ledger_entries
        WHERE tenant_id = ? AND (? IS NULL OR stay_id = ?)
        ORDER BY period_start ASC, period_index ASC, id ASC
        """,
        (tenant_id, stay_id, stay_id),
    )
    return cur.fetchall()


def _serialize_entry(row):
    due_amount = round(float(row["due_amount"] or 0), 2)
    actual_amount = round(float(row["actual_amount"] or 0), 2)
    allocated_amount = round(float(row["allocated_amount"] if "allocated_amount" in row.keys() else row["actual_amount"] or 0), 2)
    outstanding_amount = round(max(due_amount - allocated_amount, 0), 2)
    return {
        "id": int(row["id"]),
        "tenant_id": int(row["tenant_id"]),
        "stay_id": int(row["stay_id"]) if row["stay_id"] is not None else None,
        "tenant_name": _clean_text(row["tenant_name"]),
        "period_index": int(row["period_index"] or 0),
        "period_label": _clean_text(row["period_label"]),
        "period_start": _clean_text(row["period_start"]),
        "period_end": _clean_text(row["period_end"]),
        "due_amount": due_amount,
        "actual_amount": actual_amount,
        "allocated_amount": allocated_amount,
        "outstanding_amount": outstanding_amount,
        "status": _clean_text(row["status"]) or "未交",
        "payment_date": _clean_text(row["payment_date"]),
        "payment_method": _clean_text(row["payment_method"]),
        "payment_person": _clean_text(row["payment_person"]),
        "payment_images": _parse_images(row["payment_images"]),
    }


def _build_room_overview(conn, room_id):
    room = _load_room_row(conn, room_id)
    if not room:
        return None
    _ensure_room_ledger_years(conn, room_id)
    active_tenants = _load_active_tenants_for_room(conn, room_id)
    rows = _load_room_entries(conn, room_id)
    entries = [_serialize_entry(row) for row in rows]
    outstanding_periods = [item for item in entries if item["outstanding_amount"] > 0]
    paid_history_count = sum(1 for item in entries if item["status"] in {"已交", "部分已交"})
    paid_period_count = sum(1 for item in entries if item["status"] == "已交")
    partial_period_count = sum(1 for item in entries if item["status"] == "部分已交")
    unpaid_period_count = sum(1 for item in entries if item["outstanding_amount"] > 0)
    outstanding_amount = round(sum(item["outstanding_amount"] for item in outstanding_periods), 2)
    due_total = round(sum(item["due_amount"] for item in entries), 2)
    actual_total = round(sum(item["actual_amount"] for item in entries), 2)
    current_tenant_names = [item["name"] for item in active_tenants if item.get("name")]
    tenant_options = [
        {
            "id": item["id"],
            "name": item["name"],
            "label": f"{_room_display_label(room)} · {item['name']}",
            "check_in_date": item["check_in_date"],
            "check_out_date": item["check_out_date"],
            "stay_id": item["stay_id"],
        }
        for item in active_tenants
    ]
    suggested_amount = outstanding_periods[0]["outstanding_amount"] if outstanding_periods else 0
    latest_paid = ""
    for item in reversed(entries):
        if item["status"] in {"已交", "部分已交"} and item["payment_date"]:
            latest_paid = item["payment_date"]
            break
    return {
        "room": {
            **room,
            "room_display": _room_display_label(room),
        },
        "tenant_options": tenant_options,
        "current_tenant_names": current_tenant_names,
        "stats": {
            "due_total": due_total,
            "actual_total": actual_total,
            "outstanding_amount": outstanding_amount,
            "paid_history_count": paid_history_count,
            "paid_period_count": paid_period_count,
            "partial_period_count": partial_period_count,
            "unpaid_period_count": unpaid_period_count,
            "latest_paid_at": latest_paid,
            "suggested_amount": suggested_amount,
        },
        "outstanding_periods": outstanding_periods,
    }


def _build_room_summary_map(conn, room_ids):
    summary = {}
    for room_id in [int(item) for item in room_ids if str(item).isdigit()]:
        overview = _build_room_overview(conn, room_id)
        if not overview:
            continue
        summary[str(room_id)] = overview["stats"]
    return summary


def _serialize_link(row):
    return {
        "id": int(row[0]),
        "room_id": int(row[1]),
        "token": _clean_text(row[2]),
        "status": _normalize_link_status(row[3]),
        "created_at": _clean_text(row[4]),
    }


def ensure_default_rent_collection_link(conn, room_id):
    room = _load_room_row(conn, room_id)
    if not room:
        raise ValueError("房间不存在")
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, room_id, token, status, created_at
        FROM rent_collection_links
        WHERE room_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (room_id,),
    )
    existing = cur.fetchone()
    if existing:
        return _serialize_link(existing), False

    token = secrets.token_urlsafe(24)
    cur.execute(
        """
        INSERT INTO rent_collection_links (room_id, token, status)
        VALUES (?, ?, 'active')
        """,
        (room_id, token),
    )
    cur.execute(
        """
        SELECT id, room_id, token, status, created_at
        FROM rent_collection_links
        WHERE id = ?
        LIMIT 1
        """,
        (cur.lastrowid,),
    )
    created = cur.fetchone()
    return _serialize_link(created), True


def _list_room_links(conn, room_id):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, room_id, token, status, created_at
        FROM rent_collection_links
        WHERE room_id = ?
        ORDER BY id DESC
        """,
        (room_id,),
    )
    return [_serialize_link(row) for row in cur.fetchall()]


def _selected_period_summary(periods):
    labels = []
    for item in periods:
        label = _clean_text(item.get("period_label")) or _clean_text(item.get("period_start"))
        if label and label not in labels:
            labels.append(label)
    if len(labels) <= 3:
        return "、".join(labels)
    return f"{'、'.join(labels[:3])} 等{len(labels)}期"


def _select_periods_for_payment(conn, tenant_id, amount, requested_period_starts=None):
    requested = []
    for value in requested_period_starts or []:
        text = _clean_text(value)
        if text and text not in requested:
            requested.append(text)

    stay_row = conn.execute(
        "SELECT id FROM tenant_stays WHERE tenant_id = ? AND status = '在住' ORDER BY id DESC LIMIT 1",
        (tenant_id,),
    ).fetchone()
    current_stay_id = int(stay_row[0]) if stay_row else None
    outstanding_entries = []
    for row in _load_tenant_entries(conn, tenant_id, current_stay_id):
        entry = _serialize_entry(row)
        if entry["outstanding_amount"] > 0:
            outstanding_entries.append(entry)

    if not outstanding_entries:
        raise ValueError("当前租客没有待缴房租")

    if requested:
        filtered = [item for item in outstanding_entries if item["period_start"] in requested]
        if not filtered:
            raise ValueError("选择的账期当前没有待缴金额")
        outstanding_entries = filtered

    remaining = round(float(amount or 0), 2)
    selected = []
    for entry in outstanding_entries:
        if remaining <= 0:
            break
        applied_amount = round(min(remaining, entry["outstanding_amount"]), 2)
        if applied_amount <= 0:
            continue
        selected.append(
            {
                "entry_id": entry["id"],
                "period_label": entry["period_label"],
                "period_start": entry["period_start"],
                "period_end": entry["period_end"],
                "outstanding_amount": entry["outstanding_amount"],
                "applied_amount": applied_amount,
            }
        )
        remaining = round(remaining - applied_amount, 2)

    if not selected:
        raise ValueError("没有可支付的账期")
    return selected, remaining


def _generate_out_trade_no(provider, room_id):
    prefix = "WX" if provider == "wechat" else "AL"
    return f"RC{prefix}{datetime.now().strftime('%Y%m%d%H%M%S')}{int(room_id):04d}{secrets.token_hex(3).upper()}"


def _headers_snapshot():
    kept = {}
    for key, value in request.headers.items():
        lower = str(key).lower()
        if lower in {"wechatpay-timestamp", "wechatpay-nonce", "wechatpay-serial", "wechatpay-signature", "user-agent"}:
            kept[key] = value
    return kept


def _insert_callback_log(provider, payload, verify_status="", out_trade_no="", external_trade_no=""):
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO rent_payment_callbacks (
            provider, out_trade_no, external_trade_no, verify_status, payload_json, headers_json
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            provider,
            _clean_text(out_trade_no),
            _clean_text(external_trade_no),
            _clean_text(verify_status),
            _dump_json(payload),
            _dump_json(_headers_snapshot()),
        ),
    )
    conn.commit()
    conn.close()


def _get_wechat_notify_url(settings):
    return f"{settings['notify_base_url']}/api/payment-callbacks/wechat"


def _get_alipay_notify_url(settings):
    return f"{settings['notify_base_url']}/api/payment-callbacks/alipay"


def _load_private_key(pem_text):
    return serialization.load_pem_private_key(str(pem_text or "").encode("utf-8"), password=None)


def _load_public_key(pem_text):
    return serialization.load_pem_public_key(str(pem_text or "").encode("utf-8"))


def _wechat_sign(method, canonical_url, body_text, settings):
    timestamp = str(int(datetime.utcnow().timestamp()))
    nonce = secrets.token_hex(16)
    message = f"{method}\n{canonical_url}\n{timestamp}\n{nonce}\n{body_text}\n"
    private_key = _load_private_key(settings["wechat_private_key_pem"])
    signature = private_key.sign(message.encode("utf-8"), padding.PKCS1v15(), hashes.SHA256())
    signature_text = base64.b64encode(signature).decode("utf-8")
    authorization = (
        'WECHATPAY2-SHA256-RSA2048 '
        f'mchid="{settings["wechat_mchid"]}",'
        f'nonce_str="{nonce}",'
        f'serial_no="{settings["wechat_serial_no"]}",'
        f'timestamp="{timestamp}",'
        f'signature="{signature_text}"'
    )
    return {
        "Authorization": authorization,
        "Wechatpay-Serial": settings["wechat_serial_no"],
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def _wechat_request(method, path, payload=None, settings=None):
    current = settings or load_payment_settings()
    body_text = _dump_json(payload or {}) if payload is not None else ""
    headers = _wechat_sign(method, path, body_text, current)
    url = f"https://api.mch.weixin.qq.com{path}"
    response = requests.request(method, url, data=body_text.encode("utf-8") if body_text else None, headers=headers, timeout=15)
    try:
        data = response.json()
    except Exception:
        data = {"raw": response.text}
    if response.status_code >= 400:
        raise RuntimeError(_clean_text(data.get("message") or data.get("detail") or response.text) or "微信支付请求失败")
    return data


def _create_wechat_native_order(order_row, selected_periods, settings):
    payload = {
        "appid": settings["wechat_appid"],
        "mchid": settings["wechat_mchid"],
        "description": _clean_text(order_row["subject"]) or f"{order_row['room_no']} 房租缴费",
        "out_trade_no": order_row["out_trade_no"],
        "notify_url": _get_wechat_notify_url(settings),
        "attach": _dump_json(
            {
                "room_id": order_row["room_id"],
                "tenant_id": order_row["tenant_id"],
                "order_id": order_row["id"],
                "provider": "wechat",
            }
        ),
        "amount": {
            "total": _to_minor_units(order_row["amount"]),
            "currency": "CNY",
        },
    }
    result = _wechat_request("POST", "/v3/pay/transactions/native", payload=payload, settings=settings)
    return {
        "provider_payload": result,
        "provider_code_url": _clean_text(result.get("code_url")),
        "provider_redirect_url": "",
        "status": "pending",
    }


def _query_wechat_order(out_trade_no, settings):
    path = f"/v3/pay/transactions/out-trade-no/{quote(out_trade_no)}?mchid={quote(settings['wechat_mchid'])}"
    result = _wechat_request("GET", path, payload=None, settings=settings)
    trade_state = _clean_text(result.get("trade_state")).upper()
    if trade_state == "SUCCESS":
        return {
            "paid": True,
            "external_trade_no": _clean_text(result.get("transaction_id")),
            "paid_at": _clean_text(result.get("success_time"))[:19].replace("T", " "),
            "paid_amount": _from_minor_units((result.get("amount") or {}).get("payer_total")),
            "payload": result,
        }
    if trade_state in {"NOTPAY", "USERPAYING"}:
        return {"paid": False, "payload": result}
    if trade_state in {"CLOSED", "REVOKED", "PAYERROR"}:
        return {"paid": False, "closed": True, "payload": result}
    return {"paid": False, "payload": result}


def _wechat_verify_signature(body_text, settings):
    timestamp = request.headers.get("Wechatpay-Timestamp", "")
    nonce = request.headers.get("Wechatpay-Nonce", "")
    signature_text = request.headers.get("Wechatpay-Signature", "")
    if not (timestamp and nonce and signature_text):
        raise ValueError("微信支付回调签名头缺失")
    message = f"{timestamp}\n{nonce}\n{body_text}\n"
    public_key = _load_public_key(settings["wechat_platform_public_key_pem"])
    public_key.verify(
        base64.b64decode(signature_text),
        message.encode("utf-8"),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )


def _wechat_decrypt_resource(resource, settings):
    ciphertext = base64.b64decode(resource.get("ciphertext") or "")
    nonce = str(resource.get("nonce") or "").encode("utf-8")
    associated_data = str(resource.get("associated_data") or "").encode("utf-8")
    aesgcm = AESGCM(settings["wechat_api_v3_key"].encode("utf-8"))
    plaintext = aesgcm.decrypt(nonce, ciphertext, associated_data)
    return json.loads(plaintext.decode("utf-8"))


def _alipay_build_sign_content(params):
    pairs = []
    for key in sorted(params.keys()):
        if key in {"sign"}:
            continue
        value = params.get(key)
        if value is None or value == "":
            continue
        pairs.append(f"{key}={value}")
    return "&".join(pairs)


def _alipay_sign(params, settings):
    sign_content = _alipay_build_sign_content(params)
    private_key = _load_private_key(settings["alipay_merchant_private_key_pem"])
    signature = private_key.sign(sign_content.encode("utf-8"), padding.PKCS1v15(), hashes.SHA256())
    return base64.b64encode(signature).decode("utf-8")


def _alipay_verify(params, settings):
    sign_text = _clean_text(params.get("sign"))
    if not sign_text:
        raise ValueError("支付宝回调签名缺失")
    sign_content = _alipay_build_sign_content({key: value for key, value in params.items() if key not in {"sign", "sign_type"}})
    public_key = _load_public_key(settings["alipay_public_key_pem"])
    public_key.verify(base64.b64decode(sign_text), sign_content.encode("utf-8"), padding.PKCS1v15(), hashes.SHA256())


def _alipay_gateway_request(method_name, biz_content, settings):
    params = {
        "app_id": settings["alipay_app_id"],
        "method": method_name,
        "format": "JSON",
        "charset": "utf-8",
        "sign_type": "RSA2",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "version": "1.0",
        "notify_url": _get_alipay_notify_url(settings),
        "biz_content": _dump_json(biz_content),
    }
    params["sign"] = _alipay_sign(params, settings)
    response = requests.post(settings["alipay_gateway"], data=params, timeout=15)
    try:
        payload = response.json()
    except Exception:
        raise RuntimeError(_clean_text(response.text) or "支付宝请求失败")
    response_key = f"{method_name.replace('.', '_')}_response"
    result = payload.get(response_key) or {}
    if _clean_text(result.get("code")) != "10000":
        raise RuntimeError(_clean_text(result.get("sub_msg") or result.get("msg") or "支付宝请求失败"))
    return result, payload


def _create_alipay_precreate_order(order_row, selected_periods, settings):
    biz_content = {
        "out_trade_no": order_row["out_trade_no"],
        "total_amount": f"{float(order_row['amount']):.2f}",
        "subject": _clean_text(order_row["subject"]) or f"{order_row['room_no']} 房租缴费",
        "body": _selected_period_summary(selected_periods) or "房租缴费",
        "store_id": str(order_row["room_id"]),
        "passback_params": _dump_json(
            {
                "room_id": order_row["room_id"],
                "tenant_id": order_row["tenant_id"],
                "order_id": order_row["id"],
                "provider": "alipay",
            }
        ),
    }
    result, payload = _alipay_gateway_request("alipay.trade.precreate", biz_content, settings)
    return {
        "provider_payload": payload,
        "provider_code_url": _clean_text(result.get("qr_code")),
        "provider_redirect_url": "",
        "status": "pending",
    }


def _query_alipay_order(out_trade_no, settings):
    result, payload = _alipay_gateway_request("alipay.trade.query", {"out_trade_no": out_trade_no}, settings)
    trade_status = _clean_text(result.get("trade_status")).upper()
    if trade_status in {"TRADE_SUCCESS", "TRADE_FINISHED"}:
        return {
            "paid": True,
            "external_trade_no": _clean_text(result.get("trade_no")),
            "paid_at": _clean_text(result.get("send_pay_date")).replace("T", " "),
            "paid_amount": _parse_amount(result.get("total_amount"), 0),
            "payload": payload,
        }
    if trade_status in {"WAIT_BUYER_PAY"}:
        return {"paid": False, "payload": payload}
    if trade_status in {"TRADE_CLOSED"}:
        return {"paid": False, "closed": True, "payload": payload}
    return {"paid": False, "payload": payload}


def _create_provider_order(order_row, selected_periods):
    settings = load_payment_settings()
    status = build_payment_status(settings)
    provider = order_row["provider"]
    if not status.get("enabled"):
        raise ValueError("支付功能尚未启用，请先在系统维护页面配置支付参数")
    if provider == "wechat":
        if not status["wechat"]["enabled"] or not status["wechat"]["configured"]:
            raise ValueError(status["wechat"]["reason"] or "微信支付尚未配置")
        return _create_wechat_native_order(order_row, selected_periods, settings)
    if provider == "alipay":
        if not status["alipay"]["enabled"] or not status["alipay"]["configured"]:
            raise ValueError(status["alipay"]["reason"] or "支付宝尚未配置")
        return _create_alipay_precreate_order(order_row, selected_periods, settings)
    raise ValueError("不支持的支付方式")


def _query_provider_order(order_row):
    settings = load_payment_settings()
    provider = order_row["provider"]
    if provider == "wechat":
        return _query_wechat_order(order_row["out_trade_no"], settings)
    if provider == "alipay":
        return _query_alipay_order(order_row["out_trade_no"], settings)
    return {"paid": False}


def _load_order_row(conn, out_trade_no):
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        SELECT *
        FROM rent_payment_orders
        WHERE out_trade_no = ?
        LIMIT 1
        """,
        (out_trade_no,),
    )
    return cur.fetchone()


def _load_order_by_id(conn, order_id):
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        SELECT *
        FROM rent_payment_orders
        WHERE id = ?
        LIMIT 1
        """,
        (order_id,),
    )
    return cur.fetchone()


def _serialize_order(row):
    provider_payload = {}
    raw_payload = row["provider_payload"]
    try:
        provider_payload = json.loads(raw_payload) if raw_payload else {}
    except Exception:
        provider_payload = {}
    return {
        "id": int(row["id"]),
        "link_id": row["link_id"],
        "room_id": int(row["room_id"]),
        "tenant_id": int(row["tenant_id"]),
        "tenant_name": _clean_text(row["tenant_name"]),
        "building": _clean_text(row["building"]),
        "room_no": _clean_text(row["room_no"]),
        "provider": _clean_text(row["provider"]),
        "provider_label": PAYMENT_PROVIDER_LABELS.get(_clean_text(row["provider"]), _clean_text(row["provider"])),
        "out_trade_no": _clean_text(row["out_trade_no"]),
        "external_trade_no": _clean_text(row["external_trade_no"]),
        "subject": _clean_text(row["subject"]),
        "amount": round(float(row["amount"] or 0), 2),
        "currency": _clean_text(row["currency"]) or "CNY",
        "selected_periods": _parse_json_list(row["selected_periods_json"]),
        "period_summary": _clean_text(row["period_summary"]),
        "status": _normalize_order_status(row["status"]),
        "provider_payload": provider_payload,
        "provider_code_url": _clean_text(row["provider_code_url"]),
        "provider_redirect_url": _clean_text(row["provider_redirect_url"]),
        "callback_verified": bool(row["callback_verified"]),
        "callback_count": int(row["callback_count"] or 0),
        "paid_amount": round(float(row["paid_amount"] or 0), 2),
        "paid_at": _clean_text(row["paid_at"]),
        "payment_completed_at": _clean_text(row["payment_completed_at"]),
        "remarks": _clean_text(row["remarks"]),
        "created_at": _clean_text(row["created_at"]),
        "updated_at": _clean_text(row["updated_at"]),
    }


def _apply_paid_order(conn, order_row, external_trade_no="", paid_amount=None, paid_at="", provider_payload=None, callback_verified=False):
    if _clean_text(order_row["status"]) == "paid":
        return _serialize_order(order_row)

    selected_periods = _parse_json_list(order_row["selected_periods_json"])
    provider_label = PAYMENT_PROVIDER_LABELS.get(_clean_text(order_row["provider"]), _clean_text(order_row["provider"]))
    payment_date = (_clean_text(paid_at)[:10] or _today_text())
    actual_paid_amount = round(float(paid_amount if paid_amount is not None else order_row["amount"] or 0), 2)
    remaining = actual_paid_amount
    cur = conn.cursor()

    for item in selected_periods:
        if remaining <= 0:
            break
        entry_id = int(item.get("entry_id") or 0)
        if not entry_id:
            continue
        cur.execute("SELECT * FROM rent_ledger_entries WHERE id = ?", (entry_id,))
        row = cur.fetchone()
        if not row:
            continue
        due_amount = round(float(row["due_amount"] or 0), 2)
        current_actual = round(float(row["actual_amount"] or 0), 2)
        current_allocated = round(float(row["allocated_amount"] if "allocated_amount" in row.keys() else row["actual_amount"] or 0), 2)
        outstanding = round(max(due_amount - current_allocated, 0), 2)
        if outstanding <= 0:
            continue
        target_amount = round(float(item.get("applied_amount") or 0), 2)
        applied_amount = round(min(outstanding, remaining, target_amount if target_amount > 0 else outstanding), 2)
        if applied_amount <= 0:
            continue
        new_actual = round(current_actual + applied_amount, 2)
        new_allocated = round(current_allocated + applied_amount, 2)
        new_status = "已交" if new_allocated >= due_amount else "部分已交"
        new_remarks = _append_text_line(row["remarks"], f"{provider_label}订单 {order_row['out_trade_no']} 自动入账 {applied_amount:.2f} 元")
        cur.execute(
            """
            UPDATE rent_ledger_entries
            SET actual_amount = ?, allocated_amount = ?, status = ?, payment_date = ?, payment_person = ?, payment_method = ?,
                remarks = ?, updated_at = DATETIME('now')
            WHERE id = ?
            """,
            (
                new_actual,
                new_allocated,
                new_status,
                payment_date,
                provider_label,
                provider_label,
                new_remarks,
                entry_id,
            ),
        )
        remaining = round(remaining - applied_amount, 2)

    order_remarks = _clean_text(order_row["remarks"])
    if remaining > 0:
        order_remarks = _append_text_line(order_remarks, f"仍有 {remaining:.2f} 元未分配到账期")

    cur.execute(
        """
        UPDATE rent_payment_orders
        SET status = 'paid',
            external_trade_no = ?,
            callback_verified = ?,
            paid_amount = ?,
            paid_at = ?,
            payment_completed_at = ?,
            callback_count = callback_count + 1,
            provider_payload = ?,
            remarks = CASE
                WHEN ? = '' THEN remarks
                WHEN COALESCE(TRIM(remarks), '') = '' THEN ?
                WHEN instr(remarks, ?) > 0 THEN remarks
                ELSE remarks || '\n' || ?
            END,
            updated_at = DATETIME('now')
        WHERE id = ?
        """,
        (
            _clean_text(external_trade_no),
            1 if callback_verified else int(order_row["callback_verified"] or 0),
            actual_paid_amount,
            _clean_text(paid_at),
            _now_text(),
            _dump_json(provider_payload or {}),
            _clean_text(order_remarks),
            _clean_text(order_remarks),
            _clean_text(order_remarks),
            _clean_text(order_remarks),
            int(order_row["id"]),
        ),
    )
    cur.execute("SELECT * FROM rent_payment_orders WHERE id = ?", (int(order_row["id"]),))
    updated = cur.fetchone()
    conn.commit()
    return _serialize_order(updated)


@rent_collection_bp.route("/rent-collection/rooms/<int:room_id>/links", methods=["GET"])
@token_required
def api_list_rent_collection_links(current_user, room_id):
    ensure_rent_collection_schema()
    conn = connect()
    try:
        room = _load_room_row(conn, room_id)
        if not room:
            return jsonify({"error": "房间不存在"}), 404
        link, created = ensure_default_rent_collection_link(conn, room_id)
        if created:
            conn.commit()
        links = [link]
        overview = _build_room_overview(conn, room_id)
        return jsonify({"room": room, "links": links, "overview": overview})
    finally:
        conn.close()


@rent_collection_bp.route("/rent-collection/rooms/<int:room_id>/links", methods=["POST"])
@token_required
def api_create_rent_collection_link(current_user, room_id):
    ensure_rent_collection_schema()
    conn = connect()
    try:
        room = _load_room_row(conn, room_id)
        if not room:
            return jsonify({"error": "房间不存在"}), 404
        link, created = ensure_default_rent_collection_link(conn, room_id)
        conn.commit()
        return jsonify({
            "link": link,
            "created": created,
            "message": "缴租链接已生成" if created else "当前房间已存在固定缴租链接",
        })
    finally:
        conn.close()


@rent_collection_bp.route("/rent-collection/links/<int:link_id>/disable", methods=["POST"])
@token_required
def api_disable_rent_collection_link(current_user, link_id):
    ensure_rent_collection_schema()
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT id, status FROM rent_collection_links WHERE id = ?", (link_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "缴租链接不存在"}), 404
    if _normalize_link_status(row[1]) == "disabled":
        conn.close()
        return jsonify({"message": "缴租链接已停用"})
    cur.execute("UPDATE rent_collection_links SET status = 'disabled' WHERE id = ?", (link_id,))
    conn.commit()
    conn.close()
    return jsonify({"message": "缴租链接已停用"})


@rent_collection_bp.route("/rent-collection/links/<int:link_id>/enable", methods=["POST"])
@token_required
def api_enable_rent_collection_link(current_user, link_id):
    ensure_rent_collection_schema()
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT id, status FROM rent_collection_links WHERE id = ?", (link_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "缴租链接不存在"}), 404
    if _normalize_link_status(row[1]) == "active":
        conn.close()
        return jsonify({"message": "缴租链接已启用"})
    cur.execute("UPDATE rent_collection_links SET status = 'active' WHERE id = ?", (link_id,))
    conn.commit()
    conn.close()
    return jsonify({"message": "缴租链接已启用"})


@rent_collection_bp.route("/rent-collection/links/<int:link_id>", methods=["DELETE"])
@token_required
def api_delete_rent_collection_link(current_user, link_id):
    ensure_rent_collection_schema()
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT id FROM rent_collection_links WHERE id = ?", (link_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "缴租链接不存在"}), 404
    cur.execute("DELETE FROM rent_collection_links WHERE id = ?", (link_id,))
    conn.commit()
    conn.close()
    return jsonify({"message": "缴租链接已删除"})


@rent_collection_bp.route("/rent-collection/rooms/summary", methods=["GET"])
@token_required
def api_get_rent_collection_room_summaries(current_user):
    ensure_rent_collection_schema()
    raw_ids = _clean_text(request.args.get("room_ids"))
    if raw_ids:
        room_ids = [item for item in raw_ids.split(",") if item.strip().isdigit()]
    else:
        conn = connect()
        cur = conn.cursor()
        cur.execute("SELECT id FROM rooms ORDER BY id ASC")
        room_ids = [str(row[0]) for row in cur.fetchall()]
        conn.close()
    conn = connect()
    try:
        return jsonify({"summaries": _build_room_summary_map(conn, room_ids)})
    finally:
        conn.close()


@rent_collection_bp.route("/public/rent-collection/<token>", methods=["GET"])
def api_get_public_rent_collection_page(token):
    ensure_rent_collection_schema()
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, room_id, token, status, created_at
        FROM rent_collection_links
        WHERE token = ?
        LIMIT 1
        """,
        (token,),
    )
    row = cur.fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "缴租链接不存在"}), 404
    link = _serialize_link(row)
    if link["status"] != "active":
        conn.close()
        return jsonify({"error": "缴租链接已失效"}), 400
    overview = _build_room_overview(conn, link["room_id"])
    conn.close()
    if not overview:
        return jsonify({"error": "房间不存在"}), 404
    provider_status = build_payment_status()
    public_channels = {
        "wechat": {
            "label": "微信支付",
            "enabled": bool(provider_status["enabled"] and provider_status["wechat"]["enabled"] and provider_status["wechat"]["configured"]),
            "mode": provider_status["wechat"]["mode"],
            "reason": provider_status["wechat"]["reason"] if not provider_status["wechat"]["configured"] else "",
        },
        "alipay": {
            "label": "支付宝",
            "enabled": bool(provider_status["enabled"] and provider_status["alipay"]["enabled"] and provider_status["alipay"]["configured"]),
            "mode": provider_status["alipay"]["mode"],
            "reason": provider_status["alipay"]["reason"] if not provider_status["alipay"]["configured"] else "",
        },
    }
    return jsonify({"link": link, "overview": overview, "providers": public_channels})


@rent_collection_bp.route("/public/rent-collection/<token>/orders", methods=["POST"])
def api_create_public_rent_collection_order(token):
    ensure_rent_collection_schema()
    data = request.json or {}
    provider = _clean_text(data.get("provider")).lower()
    if provider not in {"wechat", "alipay"}:
        return jsonify({"error": "请选择支付方式"}), 400
    amount = _parse_amount(data.get("amount"), 0)
    if amount <= 0:
        return jsonify({"error": "支付金额必须大于 0"}), 400

    conn = connect()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, room_id, token, status, created_at
        FROM rent_collection_links
        WHERE token = ?
        LIMIT 1
        """,
        (token,),
    )
    link_row = cur.fetchone()
    if not link_row:
        conn.close()
        return jsonify({"error": "缴租链接不存在"}), 404
    link = _serialize_link(link_row)
    if link["status"] != "active":
        conn.close()
        return jsonify({"error": "缴租链接已失效"}), 400

    overview = _build_room_overview(conn, link["room_id"])
    if not overview:
        conn.close()
        return jsonify({"error": "房间不存在"}), 404
    try:
        tenant_id = int(data.get("tenant_id") or 0)
    except Exception:
        conn.close()
        return jsonify({"error": "请选择租客"}), 400

    tenant_options = {int(item["id"]): item for item in overview["tenant_options"]}
    if tenant_id not in tenant_options:
        conn.close()
        return jsonify({"error": "租客不属于当前房间或已退租"}), 400

    tenant_option = tenant_options[tenant_id]
    try:
        selected_periods, unallocated_amount = _select_periods_for_payment(conn, tenant_id, amount, data.get("selected_period_starts") or [])
    except ValueError as exc:
        conn.close()
        return jsonify({"error": str(exc)}), 400

    room = overview["room"]
    out_trade_no = _generate_out_trade_no(provider, room["id"])
    subject = f"{room['room_display']} 房租缴费"
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO rent_payment_orders (
            link_id, room_id, tenant_id, tenant_name, building, room_no, provider, out_trade_no,
            subject, amount, currency, selected_periods_json, period_summary, status, provider_payload,
            provider_code_url, provider_redirect_url, remarks, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'CNY', ?, ?, 'created', '{}', '', '', ?, ?, ?)
        """,
        (
            link["id"],
            room["id"],
            tenant_id,
            tenant_option["name"],
            room["building"],
            room["room_no"],
            provider,
            out_trade_no,
            subject,
            round(amount, 2),
            _dump_json(selected_periods),
            _selected_period_summary(selected_periods),
            f"未自动分配金额 {unallocated_amount:.2f} 元" if unallocated_amount > 0 else "",
            _now_text(),
            _now_text(),
        ),
    )
    order_id = cur.lastrowid
    cur.execute("SELECT * FROM rent_payment_orders WHERE id = ?", (order_id,))
    order_row = cur.fetchone()
    try:
        provider_result = _create_provider_order(order_row, selected_periods)
    except Exception as exc:
        cur.execute(
            """
            UPDATE rent_payment_orders
            SET status = 'failed', remarks = ?, updated_at = DATETIME('now')
            WHERE id = ?
            """,
            (_clean_text(str(exc)) or "创建支付订单失败", order_id),
        )
        conn.commit()
        conn.close()
        return jsonify({"error": str(exc) or "创建支付订单失败"}), 400

    cur.execute(
        """
        UPDATE rent_payment_orders
        SET status = ?, provider_payload = ?, provider_code_url = ?, provider_redirect_url = ?, updated_at = DATETIME('now')
        WHERE id = ?
        """,
        (
            provider_result["status"],
            _dump_json(provider_result.get("provider_payload") or {}),
            _clean_text(provider_result.get("provider_code_url")),
            _clean_text(provider_result.get("provider_redirect_url")),
            order_id,
        ),
    )
    cur.execute("SELECT * FROM rent_payment_orders WHERE id = ?", (order_id,))
    updated_order = cur.fetchone()
    conn.commit()
    conn.close()
    return jsonify(
        {
            "message": "支付订单已创建",
            "order": _serialize_order(updated_order),
            "unallocated_amount": unallocated_amount,
        }
    )


@rent_collection_bp.route("/public/rent-collection/<token>/orders/<out_trade_no>", methods=["GET"])
def api_get_public_rent_collection_order(token, out_trade_no):
    ensure_rent_collection_schema()
    conn = connect()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        SELECT l.id
        FROM rent_collection_links l
        JOIN rent_payment_orders o ON o.link_id = l.id
        WHERE l.token = ? AND o.out_trade_no = ?
        LIMIT 1
        """,
        (token, out_trade_no),
    )
    exists = cur.fetchone()
    if not exists:
        conn.close()
        return jsonify({"error": "支付订单不存在"}), 404
    order_row = _load_order_row(conn, out_trade_no)
    if not order_row:
        conn.close()
        return jsonify({"error": "支付订单不存在"}), 404

    order = _serialize_order(order_row)
    if order["status"] in {"created", "pending"}:
        try:
            query_result = _query_provider_order(order)
            if query_result.get("paid"):
                updated = _apply_paid_order(
                    conn,
                    order_row,
                    external_trade_no=query_result.get("external_trade_no", ""),
                    paid_amount=query_result.get("paid_amount", order["amount"]),
                    paid_at=query_result.get("paid_at", ""),
                    provider_payload=query_result.get("payload") or {},
                    callback_verified=order["callback_verified"],
                )
                conn.close()
                return jsonify({"order": updated})
            if query_result.get("closed"):
                cur.execute(
                    "UPDATE rent_payment_orders SET status = 'closed', provider_payload = ?, updated_at = DATETIME('now') WHERE id = ?",
                    (_dump_json(query_result.get("payload") or {}), order["id"]),
                )
                conn.commit()
                cur.execute("SELECT * FROM rent_payment_orders WHERE id = ?", (order["id"],))
                closed_row = cur.fetchone()
                conn.close()
                return jsonify({"order": _serialize_order(closed_row)})
        except Exception:
            pass
    conn.close()
    return jsonify({"order": order})


@rent_collection_bp.route("/payment-callbacks/wechat", methods=["POST"])
def api_handle_wechat_callback():
    ensure_rent_collection_schema()
    settings = load_payment_settings()
    body_text = request.get_data(as_text=True) or ""
    try:
        _wechat_verify_signature(body_text, settings)
        payload = json.loads(body_text or "{}")
        resource = _wechat_decrypt_resource(payload.get("resource") or {}, settings)
        out_trade_no = _clean_text(resource.get("out_trade_no"))
        external_trade_no = _clean_text(resource.get("transaction_id"))
        paid_amount = _from_minor_units((resource.get("amount") or {}).get("payer_total"))
        paid_at = _clean_text(resource.get("success_time"))[:19].replace("T", " ")
        _insert_callback_log("wechat", resource, verify_status="verified", out_trade_no=out_trade_no, external_trade_no=external_trade_no)
    except Exception as exc:
        _insert_callback_log("wechat", {"raw": body_text}, verify_status=f"failed:{exc}")
        return jsonify({"code": "FAIL", "message": str(exc) or "验签失败"}), 400

    conn = connect()
    order_row = _load_order_row(conn, out_trade_no)
    if not order_row:
        conn.close()
        return jsonify({"code": "SUCCESS", "message": "成功"})
    _apply_paid_order(
        conn,
        order_row,
        external_trade_no=external_trade_no,
        paid_amount=paid_amount,
        paid_at=paid_at,
        provider_payload=resource,
        callback_verified=True,
    )
    conn.close()
    return jsonify({"code": "SUCCESS", "message": "成功"})


@rent_collection_bp.route("/payment-callbacks/alipay", methods=["POST"])
def api_handle_alipay_callback():
    ensure_rent_collection_schema()
    settings = load_payment_settings()
    form = request.form.to_dict(flat=True)
    try:
        _alipay_verify(form, settings)
        trade_status = _clean_text(form.get("trade_status")).upper()
        out_trade_no = _clean_text(form.get("out_trade_no"))
        external_trade_no = _clean_text(form.get("trade_no"))
        _insert_callback_log("alipay", form, verify_status="verified", out_trade_no=out_trade_no, external_trade_no=external_trade_no)
        if trade_status not in {"TRADE_SUCCESS", "TRADE_FINISHED"}:
            return "success"
    except Exception as exc:
        _insert_callback_log("alipay", form or {"raw": request.get_data(as_text=True)}, verify_status=f"failed:{exc}")
        return "fail", 400

    conn = connect()
    order_row = _load_order_row(conn, out_trade_no)
    if not order_row:
        conn.close()
        return "success"
    _apply_paid_order(
        conn,
        order_row,
        external_trade_no=external_trade_no,
        paid_amount=_parse_amount(form.get("total_amount"), order_row["amount"]),
        paid_at=_clean_text(form.get("gmt_payment")).replace("T", " "),
        provider_payload=form,
        callback_verified=True,
    )
    conn.close()
    return "success"
