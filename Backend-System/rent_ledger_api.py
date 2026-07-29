import calendar
import json
import sqlite3
from datetime import date, datetime, timedelta

from flask import Blueprint, jsonify, request

from auth_api import token_required
from common import connect


rent_ledger_bp = Blueprint("rent_ledger", __name__, url_prefix="/api")

RENT_UNITS = {"月", "年"}
RENT_STATUSES = {"未交", "已交", "部分已交"}
TENANT_STATUSES = {"在住", "已退租"}


def ensure_rent_ledger_schema():
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS rent_ledger_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER NOT NULL,
            room_id INTEGER,
            building TEXT DEFAULT '',
            room_no TEXT DEFAULT '',
            tenant_name TEXT DEFAULT '',
            lease_start TEXT DEFAULT '',
            lease_end TEXT DEFAULT '',
            rent_amount REAL NOT NULL DEFAULT 0,
            rent_unit TEXT DEFAULT '月',
            period_index INTEGER NOT NULL DEFAULT 1,
            period_label TEXT NOT NULL,
            period_start TEXT NOT NULL,
            period_end TEXT NOT NULL,
            due_amount REAL NOT NULL DEFAULT 0,
            actual_amount REAL NOT NULL DEFAULT 0,
            allocated_amount REAL NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT '未交',
            payment_date TEXT DEFAULT '',
            payment_person TEXT DEFAULT '',
            payment_method TEXT DEFAULT '',
            remarks TEXT DEFAULT '',
            payment_images TEXT DEFAULT '[]',
            created_at DATETIME DEFAULT (DATETIME('now')),
            updated_at DATETIME DEFAULT (DATETIME('now')),
            UNIQUE (tenant_id, period_start)
        )
        """
    )
    cursor.execute("PRAGMA table_info(rent_ledger_entries)")
    columns = {row[1] for row in cursor.fetchall()}
    if "payment_images" not in columns:
        cursor.execute("ALTER TABLE rent_ledger_entries ADD COLUMN payment_images TEXT DEFAULT '[]'")
    if "payment_person" not in columns:
        cursor.execute("ALTER TABLE rent_ledger_entries ADD COLUMN payment_person TEXT DEFAULT ''")
    if "allocated_amount" not in columns:
        cursor.execute("ALTER TABLE rent_ledger_entries ADD COLUMN allocated_amount REAL NOT NULL DEFAULT 0")
    cursor.execute(
        """
        UPDATE rent_ledger_entries
        SET allocated_amount = COALESCE(actual_amount, 0)
        WHERE COALESCE(allocated_amount, 0) = 0
          AND COALESCE(actual_amount, 0) > 0
          AND COALESCE(TRIM(status), '未交') <> '未交'
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_rent_ledger_period_start
        ON rent_ledger_entries (period_start, status, tenant_id)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_rent_ledger_room
        ON rent_ledger_entries (room_id, tenant_id)
        """
    )
    conn.commit()
    conn.close()


def _clean_text(value):
    return str(value or "").strip()


def _normalize_rent_unit(value):
    text = _clean_text(value)
    return text if text in RENT_UNITS else "月"


def _normalize_status(value):
    text = _clean_text(value)
    return text if text in RENT_STATUSES else "未交"


def _normalize_tenant_status(value):
    text = _clean_text(value)
    return text if text in TENANT_STATUSES else "在住"


def _parse_amount(value, default_value=0):
    try:
        amount = round(float(value), 2)
    except Exception:
        amount = float(default_value or 0)
    if amount < 0:
        amount = 0
    return round(amount, 2)


def _parse_images(value):
    if isinstance(value, list):
        items = value
    else:
        raw = _clean_text(value)
        if raw == "":
            return []
        try:
            parsed = json.loads(raw)
            items = parsed if isinstance(parsed, list) else [raw]
        except Exception:
            items = [part.strip() for part in raw.split(",")]

    results = []
    for item in items:
        text = _clean_text(item)
        if text and text not in results:
            results.append(text)
    return results[:20]


def _dump_images(images):
    return json.dumps(_parse_images(images), ensure_ascii=False)


def _allocated_amount_from_row(row):
    if not row:
        return 0.0
    try:
        keys = row.keys()
    except Exception:
        keys = []
    if "allocated_amount" in keys:
        return _parse_amount(row["allocated_amount"], row["actual_amount"] if "actual_amount" in keys else 0)
    return _parse_amount(row["actual_amount"] if "actual_amount" in keys else 0, 0)


def _merge_images(existing_images, new_images):
    results = []
    for item in _parse_images(existing_images) + _parse_images(new_images):
        if item and item not in results:
            results.append(item)
    return results[:20]


def _parse_date(value):
    text = _clean_text(value)
    if text == "":
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _date_text(value):
    return value.isoformat() if isinstance(value, date) else ""


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


def _add_months(base_date, months):
    month_index = base_date.month - 1 + months
    year = base_date.year + month_index // 12
    month = month_index % 12 + 1
    day = min(base_date.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _next_period_start(start_date, rent_unit):
    if rent_unit == "年":
        return _add_months(start_date, 12)
    return _add_months(start_date, 1)


def _advance_period_start(start_date, periods, rent_unit):
    current = start_date
    for _ in range(max(int(periods or 0), 0)):
        current = _next_period_start(current, rent_unit)
    return current


def _normalize_lease_end_boundary(lease_start, lease_end, rent_unit):
    if rent_unit != "月":
        return lease_end
    if not isinstance(lease_start, date) or not isinstance(lease_end, date) or lease_end <= lease_start:
        return lease_end

    month_diff = (lease_end.year - lease_start.year) * 12 + (lease_end.month - lease_start.month)
    if month_diff <= 0:
        return lease_end

    # Older lease presets used a single "same day next N months" rule which can
    # leave a trailing 1-day rent period at month-end. Align those dates to the
    # actual month-by-month ledger boundary so rebuilt periods stay whole.
    legacy_boundary = _add_months(lease_start, month_diff)
    if legacy_boundary != lease_end:
        return lease_end

    normalized_boundary = _advance_period_start(lease_start, month_diff, rent_unit)
    if normalized_boundary < lease_end:
        return normalized_boundary
    return lease_end


def _format_period_label(period_index, period_start, period_end, rent_unit):
    unit_label = "年租" if rent_unit == "年" else "月租"
    return f"第{period_index}期 {unit_label} {period_start.isoformat()} ~ {period_end.isoformat()}"


def _iter_periods(lease_start, lease_end, rent_unit):
    if not isinstance(lease_start, date):
        return []

    end_limit = _normalize_lease_end_boundary(lease_start, lease_end, rent_unit)
    if not isinstance(end_limit, date) or end_limit <= lease_start:
        end_limit = _next_period_start(lease_start, rent_unit)

    periods = []
    current = lease_start
    period_index = 1
    max_periods = 240
    while current < end_limit and period_index <= max_periods:
        next_start = _next_period_start(current, rent_unit)
        display_end = min(end_limit - timedelta(days=1), next_start - timedelta(days=1))
        periods.append(
            {
                "period_index": period_index,
                "period_start": current,
                "period_end": display_end,
                "period_label": _format_period_label(period_index, current, display_end, rent_unit),
            }
        )
        current = next_start
        period_index += 1
    return periods


def _has_meaningful_entry_data(row):
    if not row:
        return False
    if _normalize_status(row["status"]) != "未交":
        return True
    if _parse_amount(row["actual_amount"], 0) > 0:
        return True
    if _allocated_amount_from_row(row) > 0:
        return True
    if _clean_text(row["payment_date"]) != "":
        return True
    if _clean_text(row["payment_person"]) != "":
        return True
    if _clean_text(row["payment_method"]) != "":
        return True
    if _clean_text(row["remarks"]) != "":
        return True
    if len(_parse_images(row["payment_images"] if "payment_images" in row.keys() else "")) > 0:
        return True
    return False


def _normalize_rebuilt_entry_state(source_row, due_amount):
    status = _normalize_status(source_row["status"]) if source_row else "未交"
    actual_amount = _parse_amount(source_row["actual_amount"] if source_row else 0, 0)
    allocated_amount = _allocated_amount_from_row(source_row)
    original_allocated_amount = allocated_amount
    payment_date = _clean_text(source_row["payment_date"]) if source_row else ""
    payment_person = _clean_text(source_row["payment_person"]) if source_row else ""
    payment_method = _clean_text(source_row["payment_method"]) if source_row else ""
    remarks = _clean_text(source_row["remarks"]) if source_row else ""
    payment_images = _parse_images(source_row["payment_images"] if source_row else [])

    if status == "已交":
        if allocated_amount <= 0:
            allocated_amount = due_amount
        if actual_amount <= 0 and original_allocated_amount <= 0:
            actual_amount = due_amount
    elif status == "部分已交":
        if allocated_amount <= 0:
            if actual_amount > 0:
                allocated_amount = min(actual_amount, due_amount)
            else:
                status = "未交"
    else:
        if allocated_amount > 0:
            status = "部分已交" if allocated_amount < due_amount else "已交"
        elif actual_amount > 0:
            allocated_amount = min(actual_amount, due_amount)
            status = "部分已交" if allocated_amount < due_amount else "已交"
        else:
            actual_amount = 0
            allocated_amount = 0
            payment_date = ""
            payment_person = ""
            payment_method = ""
            payment_images = []

    if allocated_amount > due_amount and due_amount > 0:
        allocated_amount = due_amount
    if status == "部分已交" and allocated_amount <= 0:
        status = "未交"
    if status == "已交" and allocated_amount < due_amount:
        allocated_amount = due_amount
    if actual_amount < 0:
        actual_amount = 0

    return {
        "status": status,
        "actual_amount": actual_amount,
        "allocated_amount": allocated_amount,
        "payment_date": payment_date,
        "payment_person": payment_person,
        "payment_method": payment_method,
        "remarks": remarks,
        "payment_images": payment_images,
    }


def _build_rebuilt_entry_payload(tenant_row, period, source_row=None):
    due_amount = _parse_amount(tenant_row["rent_amount"], 0)
    state = _normalize_rebuilt_entry_state(source_row, due_amount)
    return (
        int(tenant_row["tenant_id"]),
        tenant_row["room_id"],
        _clean_text(tenant_row["building"]),
        _clean_text(tenant_row["room_no"]),
        _clean_text(tenant_row["tenant_name"]),
        _clean_text(tenant_row["lease_start"]),
        _clean_text(tenant_row["lease_end"]),
        due_amount,
        _normalize_rent_unit(tenant_row["rent_unit"]),
        period["period_index"],
        period["period_label"],
        _date_text(period["period_start"]),
        _date_text(period["period_end"]),
        due_amount,
        state["actual_amount"],
        state["allocated_amount"],
        state["status"],
        state["payment_date"],
        state["payment_person"],
        state["payment_method"],
        state["remarks"],
        _dump_images(state["payment_images"]),
    )


def _orphan_sort_key(row):
    payment_date = _parse_date(row["payment_date"])
    period_start = _parse_date(row["period_start"])
    effective_date = payment_date or period_start or date.max
    return (effective_date, period_start or effective_date, int(row["id"]))


def _row_to_entry(row):
    payment_images = _parse_images(row["payment_images"] if "payment_images" in row.keys() else "")
    allocated_amount = _allocated_amount_from_row(row)
    outstanding = round(max(float(row["due_amount"] or 0) - allocated_amount, 0), 2)
    return {
        "id": int(row["id"]),
        "tenant_id": int(row["tenant_id"]),
        "room_id": row["room_id"],
        "building": row["building"] or "",
        "room_no": row["room_no"] or "",
        "room_display": row["room_no"] or "",
        "tenant_name": row["tenant_name"] or "",
        "tenant_status": _normalize_tenant_status(row["tenant_status"] if "tenant_status" in row.keys() else ""),
        "lease_start": row["lease_start"] or "",
        "lease_end": row["lease_end"] or "",
        "rent_amount": round(float(row["rent_amount"] or 0), 2),
        "rent_unit": _normalize_rent_unit(row["rent_unit"]),
        "period_index": int(row["period_index"] or 0),
        "period_label": row["period_label"] or "",
        "period_start": row["period_start"] or "",
        "period_end": row["period_end"] or "",
        "due_amount": round(float(row["due_amount"] or 0), 2),
        "actual_amount": round(float(row["actual_amount"] or 0), 2),
        "allocated_amount": allocated_amount,
        "outstanding_amount": outstanding,
        "status": _normalize_status(row["status"]),
        "payment_date": row["payment_date"] or "",
        "payment_person": row["payment_person"] or "",
        "payment_method": row["payment_method"] or "",
        "remarks": row["remarks"] or "",
        "payment_images": payment_images,
        "payment_image": payment_images[0] if payment_images else "",
        "created_at": row["created_at"] or "",
        "updated_at": row["updated_at"] or "",
    }


def _resolve_status_by_amount(due_amount, allocated_amount):
    due = _parse_amount(due_amount, 0)
    allocated = _parse_amount(allocated_amount, 0)
    if allocated <= 0:
        return "未交"
    if due > 0 and allocated < due:
        return "部分已交"
    return "已交"


def _update_entry_payment_fields(
    cursor,
    row,
    actual_amount,
    allocated_amount,
    payment_date,
    payment_person,
    payment_method,
    remarks,
    payment_images,
    replace_payment_images=False,
    preserve_empty_text_fields=True,
):
    due_amount = _parse_amount(row["due_amount"], 0)
    current_payment_date = _clean_text(row["payment_date"])
    current_payment_person = _clean_text(row["payment_person"])
    current_payment_method = _clean_text(row["payment_method"])
    current_remarks = _clean_text(row["remarks"])
    current_payment_images = _parse_images(row["payment_images"] if "payment_images" in row.keys() else "")

    next_status = _resolve_status_by_amount(due_amount, allocated_amount)
    if next_status == "未交":
        next_actual_amount = 0
        next_allocated_amount = 0
        next_payment_date = ""
        next_payment_person = ""
        next_payment_method = ""
        next_remarks = current_remarks if preserve_empty_text_fields and remarks == "" else remarks
        next_payment_images = []
    else:
        next_actual_amount = _parse_amount(actual_amount, row["actual_amount"])
        next_allocated_amount = min(_parse_amount(allocated_amount, _allocated_amount_from_row(row)), due_amount) if due_amount > 0 else _parse_amount(allocated_amount, _allocated_amount_from_row(row))
        next_payment_date = (
            payment_date
            if payment_date != ""
            else (current_payment_date or date.today().isoformat()) if preserve_empty_text_fields else ""
        )
        next_payment_person = current_payment_person if preserve_empty_text_fields and payment_person == "" else payment_person
        next_payment_method = current_payment_method if preserve_empty_text_fields and payment_method == "" else payment_method
        if preserve_empty_text_fields:
            next_remarks = _append_text_line(current_remarks, remarks) if remarks != "" else current_remarks
        else:
            next_remarks = remarks
        if replace_payment_images:
            next_payment_images = _parse_images(payment_images)
        else:
            next_payment_images = _merge_images(current_payment_images, payment_images)

    cursor.execute(
        """
        UPDATE rent_ledger_entries
        SET actual_amount = ?, allocated_amount = ?, status = ?, payment_date = ?, payment_person = ?, payment_method = ?,
            remarks = ?, payment_images = ?, updated_at = DATETIME('now')
        WHERE id = ?
        """,
        (
            next_actual_amount,
            next_allocated_amount,
            next_status,
            next_payment_date,
            next_payment_person,
            next_payment_method,
            next_remarks,
            _dump_images(next_payment_images),
            int(row["id"]),
        ),
    )


def _allocate_payment_forward(conn, start_row, total_amount, payment_date, payment_person, payment_method, remarks, payment_images):
    cursor = conn.cursor()
    tenant_id = int(start_row["tenant_id"])
    start_period = _clean_text(start_row["period_start"])
    start_period_index = int(start_row["period_index"] or 0)
    start_id = int(start_row["id"])

    cursor.execute(
        """
        SELECT *
        FROM rent_ledger_entries
        WHERE tenant_id = ?
          AND (
                period_start > ?
                OR (period_start = ? AND (period_index > ? OR (period_index = ? AND id >= ?)))
              )
        ORDER BY period_start ASC, period_index ASC, id ASC
        """,
        (tenant_id, start_period, start_period, start_period_index, start_period_index, start_id),
    )
    rows = cursor.fetchall()

    remaining = _parse_amount(total_amount, 0)
    affected_entry_ids = []
    affected_period_labels = []

    for row in rows:
        if remaining <= 0:
            break
        due_amount = _parse_amount(row["due_amount"], 0)
        current_actual = _parse_amount(row["actual_amount"], 0)
        current_allocated = _allocated_amount_from_row(row)
        outstanding_amount = round(max(due_amount - current_allocated, 0), 2)
        if outstanding_amount <= 0:
            continue
        applied_amount = round(min(outstanding_amount, remaining), 2)
        if applied_amount <= 0:
            continue
        next_actual_amount = _parse_amount(total_amount if int(row["id"]) == start_id else 0, 0)
        next_allocated_amount = round(current_allocated + applied_amount, 2)
        _update_entry_payment_fields(
            cursor,
            row,
            next_actual_amount,
            next_allocated_amount,
            payment_date,
            payment_person,
            payment_method,
            remarks,
            payment_images,
        )
        affected_entry_ids.append(int(row["id"]))
        period_label = _clean_text(row["period_label"]) or _clean_text(row["period_start"])
        if period_label and period_label not in affected_period_labels:
            affected_period_labels.append(period_label)
        remaining = round(remaining - applied_amount, 2)

    return {
        "affected_entry_ids": affected_entry_ids,
        "affected_period_labels": affected_period_labels,
        "unallocated_amount": remaining,
    }


def _load_tenant_ledger_rows(conn, tenant_id):
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT *
        FROM rent_ledger_entries
        WHERE tenant_id = ?
        ORDER BY period_start ASC, period_index ASC, id ASC
        """,
        (tenant_id,),
    )
    return cursor.fetchall()


def _build_payment_source_from_row(row, override=None):
    if not row:
        return None

    status = _normalize_status(row["status"])
    actual_amount = _parse_amount(row["actual_amount"], 0)
    payment_date = _clean_text(row["payment_date"])
    payment_person = _clean_text(row["payment_person"])
    payment_method = _clean_text(row["payment_method"])
    remarks = _clean_text(row["remarks"])
    payment_images = _parse_images(row["payment_images"] if "payment_images" in row.keys() else "")

    if isinstance(override, dict):
        status = _normalize_status(override.get("status") or status)
        actual_amount = _parse_amount(override.get("actual_amount"), actual_amount)
        payment_date = _clean_text(override.get("payment_date"))
        payment_person = _clean_text(override.get("payment_person"))
        payment_method = _clean_text(override.get("payment_method"))
        remarks = _clean_text(override.get("remarks"))
        payment_images = _parse_images(override.get("payment_images"))

    if status == "未交" or actual_amount <= 0:
        return None

    return {
        "entry_id": int(row["id"]),
        "period_start": _clean_text(row["period_start"]),
        "period_index": int(row["period_index"] or 0),
        "actual_amount": actual_amount,
        "payment_date": payment_date or date.today().isoformat(),
        "payment_person": payment_person,
        "payment_method": payment_method,
        "remarks": remarks,
        "payment_images": payment_images,
    }


def _rebuild_tenant_payment_allocations(conn, tenant_id, lease_start_text="", lease_end_text="", payment_source_overrides=None):
    _ensure_tenant_ledger_years(conn, tenant_id, lease_start_text, lease_end_text)
    rows = _load_tenant_ledger_rows(conn, tenant_id)
    override_map = payment_source_overrides or {}
    override_by_id = {}
    override_by_period_start = {}

    for key, value in override_map.items():
        if isinstance(key, int):
            override_by_id[int(key)] = value
            continue
        key_text = _clean_text(key)
        if key_text.isdigit():
            override_by_id[int(key_text)] = value
        elif key_text:
            override_by_period_start[key_text] = value

    payment_sources = []
    for row in rows:
        source = _build_payment_source_from_row(
            row,
            override_by_id.get(int(row["id"])) or override_by_period_start.get(_clean_text(row["period_start"])),
        )
        if source:
            payment_sources.append(source)

    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE rent_ledger_entries
        SET actual_amount = 0,
            allocated_amount = 0,
            status = '未交',
            payment_date = '',
            payment_person = '',
            payment_method = '',
            remarks = '',
            payment_images = '[]',
            updated_at = DATETIME('now')
        WHERE tenant_id = ?
        """,
        (tenant_id,),
    )

    rows = _load_tenant_ledger_rows(conn, tenant_id)
    row_map = {int(row["id"]): row for row in rows}
    allocation_results = {}

    for source in sorted(payment_sources, key=lambda item: (item["period_start"], item["period_index"], item["entry_id"])):
        start_row = row_map.get(source["entry_id"])
        if not start_row:
            continue
        allocation_results[source["entry_id"]] = _allocate_payment_forward(
            conn,
            start_row,
            source["actual_amount"],
            source["payment_date"],
            source["payment_person"],
            source["payment_method"],
            source["remarks"],
            source["payment_images"],
        )

    return allocation_results


def _collect_lease_years(lease_start_text, lease_end_text):
    lease_start = _parse_date(lease_start_text)
    lease_end = _parse_date(lease_end_text)
    if not lease_start:
        return []
    if not lease_end or lease_end < lease_start:
        lease_end = lease_start
    end_year = min(max(lease_end.year, lease_start.year), lease_start.year + 20)
    return list(range(lease_start.year, end_year + 1))


def _ensure_tenant_ledger_years(conn, tenant_id, lease_start_text="", lease_end_text=""):
    years = _collect_lease_years(lease_start_text, lease_end_text)
    if not years:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT check_in_date, check_out_date
            FROM tenants
            WHERE id = ?
            LIMIT 1
            """,
            (tenant_id,),
        )
        tenant_row = cursor.fetchone()
        if tenant_row:
            years = _collect_lease_years(tenant_row["check_in_date"], tenant_row["check_out_date"])
    for year in years:
        _rebuild_rent_ledger_year(conn, int(year))


def _load_entry_by_tenant_period(conn, tenant_id, period_start):
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT *
        FROM rent_ledger_entries
        WHERE tenant_id = ? AND period_start = ?
        ORDER BY id ASC
        LIMIT 1
        """,
        (tenant_id, period_start),
    )
    return cursor.fetchone()


def _build_overview(groups):
    overview = {
        "tenantCount": 0,
        "totalPeriods": 0,
        "paidPeriods": 0,
        "partialPeriods": 0,
        "unpaidPeriods": 0,
        "dueAmount": 0,
        "actualAmount": 0,
        "outstandingAmount": 0,
    }
    for group in groups:
        stats = group["stats"]
        overview["tenantCount"] += 1
        overview["totalPeriods"] += int(stats["totalPeriods"])
        overview["paidPeriods"] += int(stats["paidPeriods"])
        overview["partialPeriods"] += int(stats["partialPeriods"])
        overview["unpaidPeriods"] += int(stats["unpaidPeriods"])
        overview["dueAmount"] = round(overview["dueAmount"] + float(stats["dueAmount"]), 2)
        overview["actualAmount"] = round(overview["actualAmount"] + float(stats["actualAmount"]), 2)
        overview["outstandingAmount"] = round(overview["outstandingAmount"] + float(stats["outstandingAmount"]), 2)
    return overview


def _build_grouped_payload(rows):
    group_map = {}
    for row in rows:
        entry = _row_to_entry(row)
        tenant_id = entry["tenant_id"]
        if tenant_id not in group_map:
            group_map[tenant_id] = {
                "tenantId": tenant_id,
                "tenantName": entry["tenant_name"],
                "tenantStatus": entry["tenant_status"],
                "roomId": entry["room_id"],
                "building": entry["building"],
                "roomNo": entry["room_no"],
                "roomDisplay": entry["room_display"],
                "leaseStart": entry["lease_start"],
                "leaseEnd": entry["lease_end"],
                "rentAmount": entry["rent_amount"],
                "rentUnit": entry["rent_unit"],
                "entries": [],
                "stats": {
                    "totalPeriods": 0,
                    "paidPeriods": 0,
                    "partialPeriods": 0,
                    "unpaidPeriods": 0,
                    "dueAmount": 0,
                    "actualAmount": 0,
                    "outstandingAmount": 0,
                },
            }
        group = group_map[tenant_id]
        group["entries"].append(entry)
        group["stats"]["totalPeriods"] += 1
        if entry["status"] == "已交":
            group["stats"]["paidPeriods"] += 1
        elif entry["status"] == "部分已交":
            group["stats"]["partialPeriods"] += 1
        else:
            group["stats"]["unpaidPeriods"] += 1
        group["stats"]["dueAmount"] = round(group["stats"]["dueAmount"] + entry["due_amount"], 2)
        group["stats"]["actualAmount"] = round(group["stats"]["actualAmount"] + entry["actual_amount"], 2)
        group["stats"]["outstandingAmount"] = round(group["stats"]["outstandingAmount"] + entry["outstanding_amount"], 2)

    groups = list(group_map.values())
    for group in groups:
        group["entries"].sort(key=lambda item: (item["period_start"], item["period_index"], item["id"]))
    groups.sort(key=lambda item: (item["building"], item["roomNo"], item["tenantName"], item["tenantId"]))
    return groups


def _rebuild_rent_ledger_year(conn, target_year):
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            t.id AS tenant_id,
            t.name AS tenant_name,
            t.check_in_date AS lease_start,
            t.check_out_date AS lease_end,
            t.room_id AS room_id,
            r.building AS building,
            r.room_no AS room_no,
            r.price AS rent_amount,
            r.price_unit AS rent_unit
        FROM tenants t
        LEFT JOIN rooms r ON t.room_id = r.id
        WHERE t.room_id IS NOT NULL
          AND COALESCE(TRIM(t.check_in_date), '') <> ''
          AND r.id IS NOT NULL
        ORDER BY r.building, r.room_no, t.name
        """
    )
    tenant_rows = cursor.fetchall()
    tenant_ids = [int(row[0]) for row in tenant_rows]
    if len(tenant_ids) == 0:
        cursor.execute(
            """
            DELETE FROM rent_ledger_entries
            WHERE substr(period_start, 1, 4) = ?
            """,
            (f"{target_year:04d}",),
        )
        return 0

    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    placeholders = ",".join("?" for _ in tenant_ids)
    cursor.execute(
        f"""
        SELECT *
        FROM rent_ledger_entries
        WHERE tenant_id IN ({placeholders})
          AND substr(period_start, 1, 4) = ?
        ORDER BY tenant_id, period_start, id
        """,
        (*tenant_ids, f"{target_year:04d}"),
    )

    existing_by_tenant = {}
    for row in cursor.fetchall():
        existing_by_tenant.setdefault(int(row["tenant_id"]), []).append(row)

    rebuilt_rows = []
    for raw_row in tenant_rows:
        tenant_row = {
            "tenant_id": int(raw_row[0]),
            "tenant_name": raw_row[1],
            "lease_start": raw_row[2],
            "lease_end": raw_row[3],
            "room_id": raw_row[4],
            "building": raw_row[5],
            "room_no": raw_row[6],
            "rent_amount": raw_row[7],
            "rent_unit": raw_row[8],
        }
        lease_start = _parse_date(tenant_row["lease_start"])
        lease_end = _parse_date(tenant_row["lease_end"])
        rent_amount = _parse_amount(tenant_row["rent_amount"], 0)
        rent_unit = _normalize_rent_unit(tenant_row["rent_unit"])
        if not lease_start or rent_amount <= 0:
            continue

        periods = [
            period
            for period in _iter_periods(lease_start, lease_end, rent_unit)
            if period["period_start"].year == target_year
        ]
        if len(periods) == 0:
            continue

        existing_rows = existing_by_tenant.get(tenant_row["tenant_id"], [])
        exact_by_start = {row["period_start"]: row for row in existing_rows}
        exact_starts = {_date_text(period["period_start"]) for period in periods}
        orphan_rows = sorted(
            [
                row
                for row in existing_rows
                if row["period_start"] not in exact_starts and _has_meaningful_entry_data(row)
            ],
            key=_orphan_sort_key,
        )

        assigned_sources = []
        candidate_indexes = []
        for index, period in enumerate(periods):
            start_text = _date_text(period["period_start"])
            source_row = exact_by_start.get(start_text)
            assigned_sources.append(source_row)
            if not _has_meaningful_entry_data(source_row):
                candidate_indexes.append(index)

        for orphan_row in orphan_rows:
            orphan_start = _parse_date(orphan_row["period_start"]) or date(target_year, 1, 1)
            target_index = None
            for index in candidate_indexes:
                if periods[index]["period_start"] >= orphan_start:
                    target_index = index
                    break
            if target_index is None and len(candidate_indexes) > 0:
                target_index = candidate_indexes[0]
            if target_index is None:
                continue
            assigned_sources[target_index] = orphan_row
            candidate_indexes.remove(target_index)

        for period, source_row in zip(periods, assigned_sources):
            rebuilt_rows.append(_build_rebuilt_entry_payload(tenant_row, period, source_row=source_row))

    cursor.execute(
        """
        DELETE FROM rent_ledger_entries
        WHERE substr(period_start, 1, 4) = ?
        """,
        (f"{target_year:04d}",),
    )
    cursor.executemany(
        """
        INSERT INTO rent_ledger_entries (
            tenant_id, room_id, building, room_no, tenant_name,
            lease_start, lease_end, rent_amount, rent_unit,
            period_index, period_label, period_start, period_end,
            due_amount, actual_amount, allocated_amount, status, payment_date,
            payment_person, payment_method, remarks, payment_images
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rebuilt_rows,
    )
    return len(rebuilt_rows)


def _parse_year(value):
    raw = _clean_text(value)
    if raw == "":
        return datetime.now().year
    year = int(raw)
    if year < 2000 or year > 2100:
        raise ValueError("年份必须在 2000 到 2100 之间")
    return year


def _build_summary(conn, year, status_filter="", tenant_status_filter=""):
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    rebuilt = _rebuild_rent_ledger_year(conn, year)
    if rebuilt > 0:
        conn.commit()

    cursor.execute(
        """
        SELECT DISTINCT CAST(substr(period_start, 1, 4) AS INTEGER) AS year
        FROM rent_ledger_entries
        WHERE COALESCE(TRIM(period_start), '') <> ''
        ORDER BY year DESC
        """
    )
    available_years = [int(row["year"]) for row in cursor.fetchall() if row["year"]]
    if year not in available_years:
        available_years.insert(0, year)

    params = [f"{year:04d}-%"]
    query = """
        SELECT
            e.*,
            COALESCE(TRIM(t.status), '在住') AS tenant_status
        FROM rent_ledger_entries e
        LEFT JOIN tenants t ON t.id = e.tenant_id
        WHERE e.period_start LIKE ?
    """
    status_text = _normalize_status(status_filter) if _clean_text(status_filter) else ""
    if status_text:
        query += " AND e.status = ?"
        params.append(status_text)
    tenant_status_text = _normalize_tenant_status(tenant_status_filter) if _clean_text(tenant_status_filter) else ""
    if tenant_status_text:
        query += " AND COALESCE(TRIM(t.status), '在住') = ?"
        params.append(tenant_status_text)
    query += " ORDER BY e.building, e.room_no, e.tenant_name, e.period_start, e.period_index, e.id"
    cursor.execute(query, tuple(params))
    groups = _build_grouped_payload(cursor.fetchall())

    return {
        "year": year,
        "availableYears": available_years,
        "statusFilter": status_text,
        "tenantStatusFilter": tenant_status_text,
        "overview": _build_overview(groups),
        "groups": groups,
    }


@rent_ledger_bp.route("/rent-ledger/summary", methods=["GET"])
@token_required
def get_rent_ledger_summary(current_user):
    try:
        year = _parse_year(request.args.get("year"))
    except (TypeError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400

    status_filter = request.args.get("status", "")
    tenant_status_filter = request.args.get("tenant_status", "")
    conn = connect()
    try:
        payload = _build_summary(conn, year, status_filter=status_filter, tenant_status_filter=tenant_status_filter)
    finally:
        conn.close()
    return jsonify(payload)


@rent_ledger_bp.route("/rent-ledger/sync", methods=["POST"])
@token_required
def sync_rent_ledger(current_user):
    target_year = datetime.now().year
    try:
        raw_year = request.args.get("year")
        if request.is_json and isinstance(request.get_json(silent=True), dict):
            raw_year = request.get_json(silent=True).get("year", raw_year)
        if raw_year not in (None, ""):
            target_year = _parse_year(raw_year)
    except (TypeError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400

    conn = connect()
    try:
        rebuilt = _rebuild_rent_ledger_year(conn, target_year=target_year)
        conn.commit()
    except sqlite3.Error as exc:
        conn.rollback()
        conn.close()
        return jsonify({"error": str(exc)}), 500
    finally:
        try:
            conn.close()
        except Exception:
            pass
    message = f"已重建 {target_year} 年 {rebuilt} 条应收期次"
    return jsonify({"message": message, "inserted": rebuilt, "year": target_year})


@rent_ledger_bp.route("/rent-ledger/<int:entry_id>", methods=["PUT"])
@token_required
def update_rent_ledger_entry(current_user, entry_id):
    data = request.json if isinstance(request.json, dict) else {}
    conn = connect()
    try:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM rent_ledger_entries WHERE id = ?", (entry_id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({"error": f"收租台账记录 {entry_id} 不存在"}), 404

        current_entry = _row_to_entry(row)
        status = _normalize_status(data.get("status") or current_entry["status"])
        due_amount = current_entry["due_amount"]
        actual_amount = data.get("actual_amount")
        if actual_amount in (None, ""):
            if status == "已交":
                actual_amount = due_amount
            elif status == "未交":
                actual_amount = 0
            else:
                actual_amount = current_entry["actual_amount"]
        actual_amount = _parse_amount(actual_amount, current_entry["actual_amount"])

        payment_date = _clean_text(data.get("payment_date"))
        payment_person = _clean_text(data.get("payment_person"))
        payment_method = _clean_text(data.get("payment_method"))
        remarks = _clean_text(data.get("remarks"))
        payment_images = _parse_images(data.get("payment_images"))

        should_rebuild_payment_chain = (
            _parse_amount(current_entry["actual_amount"], 0) > 0
            or (status != "未交" and actual_amount > due_amount)
        )

        if should_rebuild_payment_chain:
            period_start = _clean_text(row["period_start"])
            allocation_results = _rebuild_tenant_payment_allocations(
                conn,
                int(row["tenant_id"]),
                row["lease_start"],
                row["lease_end"],
                payment_source_overrides={
                    period_start: {
                        "status": status,
                        "actual_amount": actual_amount,
                        "payment_date": payment_date,
                        "payment_person": payment_person,
                        "payment_method": payment_method,
                        "remarks": remarks,
                        "payment_images": payment_images,
                    }
                },
            )
            updated_row = _load_entry_by_tenant_period(conn, int(row["tenant_id"]), period_start)
            conn.commit()

            allocation_result = allocation_results.get(
                int(updated_row["id"]) if updated_row else int(entry_id),
                {"affected_entry_ids": [int(entry_id)], "affected_period_labels": [], "unallocated_amount": 0},
            )
            message = "收租台账已更新"
            if _parse_amount(current_entry["actual_amount"], 0) > 0:
                message = "已按修改后的实收金额重新计算后续账期"
            elif status != "未交" and actual_amount > due_amount:
                period_preview = "、".join(allocation_result["affected_period_labels"][:3])
                if len(allocation_result["affected_period_labels"]) > 3:
                    period_preview = f"{period_preview} 等{len(allocation_result['affected_period_labels'])}期"
                if not period_preview:
                    period_preview = "所选账期"
                message = f"已按实收金额自动分摊到 {period_preview}"

            if allocation_result["unallocated_amount"] > 0:
                message += f"，超出已生成账期的 {allocation_result['unallocated_amount']:.2f} 元保留在当前这笔实收中"

            response_entry = _row_to_entry(updated_row) if updated_row else None
            if updated_row is None:
                message = f"{message}，请刷新页面查看最新结果"

            return jsonify(
                {
                    "message": message,
                    "entry": response_entry,
                    "affected_entry_ids": allocation_result["affected_entry_ids"],
                    "unallocated_amount": allocation_result["unallocated_amount"],
                }
            ), 200

        if status == "已交":
            allocated_amount = due_amount
            if actual_amount <= 0:
                actual_amount = due_amount
            if payment_date == "":
                payment_date = date.today().isoformat()
        elif status == "未交":
            actual_amount = 0
            allocated_amount = 0
            payment_date = ""
            payment_person = ""
            payment_method = ""
            payment_images = []
        else:
            allocated_amount = min(actual_amount, due_amount) if due_amount > 0 else actual_amount
            status = _resolve_status_by_amount(due_amount, allocated_amount)

        _update_entry_payment_fields(
            cursor,
            row,
            actual_amount,
            allocated_amount if status != "未交" else 0,
            payment_date,
            payment_person,
            payment_method,
            remarks,
            payment_images,
            replace_payment_images=True,
            preserve_empty_text_fields=False,
        )
        cursor.execute("SELECT * FROM rent_ledger_entries WHERE id = ?", (entry_id,))
        updated_row = cursor.fetchone()
        conn.commit()
        message = "收租台账已更新"
        response_entry = _row_to_entry(updated_row) if updated_row else None
        if updated_row is None:
            message = "收租台账已更新，请刷新页面查看最新记录"
        return jsonify({"message": message, "entry": response_entry}), 200
    except sqlite3.Error as exc:
        conn.rollback()
        return jsonify({"error": str(exc)}), 500
    finally:
        conn.close()
