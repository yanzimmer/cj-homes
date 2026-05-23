import sqlite3
from datetime import date, datetime

from flask import Blueprint, jsonify

from auth_api import token_required
from common import connect
import expiry_notification_config as notify_config
from ocr_settings import build_ocr_status
from tenants_api import _refresh_room_statuses, _refresh_tenant_statuses


dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/api/dashboard")


def _safe_parse_date(value):
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None


def _load_advance_days():
    config = notify_config.get_config() or {}
    try:
        return max(0, int(config.get("advance_days", 7)))
    except Exception:
        return 7


def _load_monthly_repair_stats(cursor, limit=12):
    cursor.execute(
        """
        SELECT
            substr(report_date, 1, 7) AS month,
            COUNT(*) AS total,
            COALESCE(SUM(COALESCE(amount, repair_cost, 0)), 0) AS total_amount,
            SUM(CASE WHEN status = '待处理' THEN 1 ELSE 0 END) AS pending,
            SUM(CASE WHEN status = '处理中' THEN 1 ELSE 0 END) AS in_progress,
            SUM(CASE WHEN status = '已完成' THEN 1 ELSE 0 END) AS completed
        FROM repair_records
        WHERE report_date IS NOT NULL
          AND TRIM(report_date) <> ''
          AND length(TRIM(report_date)) >= 7
        GROUP BY substr(report_date, 1, 7)
        ORDER BY month DESC
        LIMIT ?
        """,
        (limit,),
    )
    return [
        {
            "month": row["month"],
            "total": int(row["total"] or 0),
            "totalAmount": round(float(row["total_amount"] or 0), 2),
            "pending": int(row["pending"] or 0),
            "inProgress": int(row["in_progress"] or 0),
            "completed": int(row["completed"] or 0),
        }
        for row in cursor.fetchall()
    ]


def _load_monthly_procurement_stats(cursor, limit=12):
    cursor.execute(
        """
        SELECT
            substr(procurement_date, 1, 7) AS month,
            COUNT(*) AS total,
            COALESCE(SUM(COALESCE(total_amount, 0)), 0) AS total_amount
        FROM procurements
        WHERE procurement_date IS NOT NULL
          AND TRIM(procurement_date) <> ''
          AND length(TRIM(procurement_date)) >= 7
        GROUP BY substr(procurement_date, 1, 7)
        ORDER BY month DESC
        LIMIT ?
        """,
        (limit,),
    )
    return [
        {
            "month": row["month"],
            "total": int(row["total"] or 0),
            "totalAmount": round(float(row["total_amount"] or 0), 2),
        }
        for row in cursor.fetchall()
    ]


def _load_monthly_utility_stats(cursor, year):
    cursor.execute(
        """
        SELECT
            month,
            utility_type,
            COALESCE(SUM(COALESCE(amount, 0)), 0) AS total_amount,
            COUNT(*) AS total_count
        FROM utility_bills
        WHERE year = ?
        GROUP BY month, utility_type
        ORDER BY month ASC, utility_type ASC
        """,
        (year,),
    )
    monthly_map = {}
    electricity_total = 0.0
    water_total = 0.0
    record_count = 0
    for row in cursor.fetchall():
        month = int(row["month"] or 0)
        utility_type = str(row["utility_type"] or "")
        total_amount = round(float(row["total_amount"] or 0), 2)
        total_count = int(row["total_count"] or 0)
        monthly = monthly_map.setdefault(
            month,
            {
                "month": f"{year}-{month:02d}",
                "totalAmount": 0.0,
                "electricityAmount": 0.0,
                "waterAmount": 0.0,
                "recordCount": 0,
            },
        )
        monthly["totalAmount"] = round(monthly["totalAmount"] + total_amount, 2)
        monthly["recordCount"] += total_count
        record_count += total_count
        if utility_type == "electricity":
            monthly["electricityAmount"] = round(monthly["electricityAmount"] + total_amount, 2)
            electricity_total = round(electricity_total + total_amount, 2)
        elif utility_type == "water":
            monthly["waterAmount"] = round(monthly["waterAmount"] + total_amount, 2)
            water_total = round(water_total + total_amount, 2)

    monthly_list = []
    for month in range(1, 13):
        item = monthly_map.get(
            month,
            {
                "month": f"{year}-{month:02d}",
                "totalAmount": 0.0,
                "electricityAmount": 0.0,
                "waterAmount": 0.0,
                "recordCount": 0,
            },
        )
        monthly_list.append(item)

    return {
        "year": year,
        "totalAmount": round(electricity_total + water_total, 2),
        "electricityTotal": round(electricity_total, 2),
        "waterTotal": round(water_total, 2),
        "recordCount": record_count,
        "monthly": monthly_list,
    }


def _load_monthly_rent_ledger_stats(cursor, year):
    cursor.execute(
        """
        SELECT
            substr(period_start, 1, 7) AS month,
            COUNT(*) AS total_periods,
            SUM(CASE WHEN status = '已交' THEN 1 ELSE 0 END) AS paid_periods,
            SUM(CASE WHEN status = '部分已交' THEN 1 ELSE 0 END) AS partial_periods,
            SUM(CASE WHEN status = '未交' THEN 1 ELSE 0 END) AS unpaid_periods,
            COALESCE(SUM(COALESCE(due_amount, 0)), 0) AS due_amount,
            COALESCE(SUM(COALESCE(actual_amount, 0)), 0) AS actual_amount
        FROM rent_ledger_entries
        WHERE substr(period_start, 1, 4) = ?
        GROUP BY substr(period_start, 1, 7)
        ORDER BY month ASC
        """,
        (f"{year:04d}",),
    )

    monthly_map = {}
    total_periods = 0
    paid_periods = 0
    partial_periods = 0
    unpaid_periods = 0
    due_total = 0.0
    actual_total = 0.0

    for row in cursor.fetchall():
        month = row["month"] or ""
        due_amount = round(float(row["due_amount"] or 0), 2)
        actual_amount = round(float(row["actual_amount"] or 0), 2)
        outstanding_amount = round(max(due_amount - actual_amount, 0), 2)
        item = {
            "month": month,
            "totalPeriods": int(row["total_periods"] or 0),
            "paidPeriods": int(row["paid_periods"] or 0),
            "partialPeriods": int(row["partial_periods"] or 0),
            "unpaidPeriods": int(row["unpaid_periods"] or 0),
            "dueAmount": due_amount,
            "actualAmount": actual_amount,
            "outstandingAmount": outstanding_amount,
        }
        monthly_map[month] = item
        total_periods += item["totalPeriods"]
        paid_periods += item["paidPeriods"]
        partial_periods += item["partialPeriods"]
        unpaid_periods += item["unpaidPeriods"]
        due_total = round(due_total + due_amount, 2)
        actual_total = round(actual_total + actual_amount, 2)

    monthly_list = []
    for month in range(1, 13):
        key = f"{year:04d}-{month:02d}"
        monthly_list.append(
            monthly_map.get(
                key,
                {
                    "month": key,
                    "totalPeriods": 0,
                    "paidPeriods": 0,
                    "partialPeriods": 0,
                    "unpaidPeriods": 0,
                    "dueAmount": 0.0,
                    "actualAmount": 0.0,
                    "outstandingAmount": 0.0,
                },
            )
        )

    outstanding_total = round(max(due_total - actual_total, 0), 2)
    return {
        "year": year,
        "recordCount": total_periods,
        "totalPeriods": total_periods,
        "paidPeriods": paid_periods,
        "partialPeriods": partial_periods,
        "unpaidPeriods": unpaid_periods,
        "dueTotal": due_total,
        "actualTotal": actual_total,
        "outstandingTotal": outstanding_total,
        "collectionRate": round((actual_total / due_total) * 100) if due_total > 0 else 0,
        "monthly": monthly_list,
    }


@dashboard_bp.route("/stats", methods=["GET"])
@token_required
def api_dashboard_stats(current_user):
    conn = connect()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        try:
            _refresh_tenant_statuses(conn)
            conn.commit()
        except sqlite3.OperationalError as e:
            if "locked" not in str(e).lower():
                raise

        try:
            _refresh_room_statuses(conn)
            conn.commit()
        except sqlite3.OperationalError as e:
            if "locked" not in str(e).lower():
                raise

        cursor.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN status = '已入住' THEN 1 ELSE 0 END) AS occupied,
                SUM(CASE WHEN status = '空闲' THEN 1 ELSE 0 END) AS vacant
            FROM rooms
            """
        )
        room_row = cursor.fetchone() or {}
        room_total = int(room_row["total"] or 0)
        room_occupied = int(room_row["occupied"] or 0)
        room_vacant = int(room_row["vacant"] or 0)

        cursor.execute(
            """
            SELECT
                t.id,
                t.name,
                t.phone,
                t.status,
                t.check_in_date,
                t.check_out_date,
                r.room_no
            FROM tenants t
            LEFT JOIN rooms r ON r.id = t.room_id
            """
        )
        tenant_rows = cursor.fetchall()

        tenant_total = len(tenant_rows)
        tenant_active = 0
        tenant_inactive = 0
        lease_days_total = 0
        lease_days_count = 0

        today = date.today()
        advance_days = _load_advance_days()
        expiring_list = []

        for row in tenant_rows:
            status = str(row["status"] or "").strip()
            if status == "在住":
                tenant_active += 1
            elif status == "已退租":
                tenant_inactive += 1

            check_in_date = _safe_parse_date(row["check_in_date"])
            check_out_date = _safe_parse_date(row["check_out_date"])
            if check_in_date:
                end_date = check_out_date if status == "已退租" and check_out_date else today
                lease_days = max(0, (end_date - check_in_date).days)
                lease_days_total += lease_days
                lease_days_count += 1

            if status == "在住" and check_out_date:
                days_remaining = (check_out_date - today).days
                if days_remaining <= advance_days:
                    expiring_list.append(
                        {
                            "id": row["id"],
                            "name": row["name"] or "",
                            "room_no": row["room_no"] or "",
                            "phone": row["phone"] or "",
                            "check_out_date": row["check_out_date"] or "",
                            "days_remaining": days_remaining,
                            "status": status,
                        }
                    )

        expiring_list.sort(key=lambda item: item["days_remaining"])

        cursor.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN status = '待处理' THEN 1 ELSE 0 END) AS pending,
                SUM(CASE WHEN status = '处理中' THEN 1 ELSE 0 END) AS in_progress,
                SUM(CASE WHEN status = '已完成' THEN 1 ELSE 0 END) AS completed
            FROM repair_records
            """
        )
        repair_row = cursor.fetchone() or {}
        repair_total = int(repair_row["total"] or 0)
        repair_pending = int(repair_row["pending"] or 0)
        repair_in_progress = int(repair_row["in_progress"] or 0)
        repair_completed = int(repair_row["completed"] or 0)
        cursor.execute(
            """
            SELECT COALESCE(SUM(COALESCE(amount, repair_cost, 0)), 0) AS total_amount
            FROM repair_records
            """
        )
        repair_total_amount = float((cursor.fetchone() or {})["total_amount"] or 0)
        repair_monthly = _load_monthly_repair_stats(cursor)

        cursor.execute(
            """
            SELECT
                COUNT(*) AS total,
                COALESCE(SUM(COALESCE(total_amount, 0)), 0) AS total_amount
            FROM procurements
            """
        )
        procurement_row = cursor.fetchone() or {}
        procurement_total = int(procurement_row["total"] or 0)
        procurement_total_amount = float(procurement_row["total_amount"] or 0)
        procurement_monthly = _load_monthly_procurement_stats(cursor)
        utility_year = date.today().year
        utility_stats = _load_monthly_utility_stats(cursor, utility_year)
        rent_ledger_stats = _load_monthly_rent_ledger_stats(cursor, utility_year)
        ocr_status = build_ocr_status()

        return jsonify(
            {
                "advance_days": advance_days,
                "rooms": {
                    "total": room_total,
                    "occupied": room_occupied,
                    "vacant": room_vacant,
                    "occupancyRate": round((room_occupied / room_total) * 100) if room_total > 0 else 0,
                },
                "tenants": {
                    "total": tenant_total,
                    "active": tenant_active,
                    "inactive": tenant_inactive,
                    "activeRate": round((tenant_active / tenant_total) * 100) if tenant_total > 0 else 0,
                    "averageLeaseDays": round(lease_days_total / lease_days_count) if lease_days_count > 0 else 0,
                },
                "repairs": {
                    "total": repair_total,
                    "pending": repair_pending,
                    "inProgress": repair_in_progress,
                    "completed": repair_completed,
                    "totalAmount": round(repair_total_amount, 2),
                    "completionRate": round((repair_completed / repair_total) * 100) if repair_total > 0 else 0,
                    "monthly": repair_monthly,
                },
                "procurements": {
                    "total": procurement_total,
                    "totalAmount": round(procurement_total_amount, 2),
                    "monthly": procurement_monthly,
                },
                "utilityBills": utility_stats,
                "rentLedger": rent_ledger_stats,
                "expiring": {
                    "count": len(expiring_list),
                    "list": expiring_list,
                },
                "ocr": {
                    "usedCount": int(ocr_status["used_count"] or 0),
                    "remainingCount": ocr_status["remaining_count"],
                    "configuredTotal": int(ocr_status["max_recognitions"] or 0),
                    "enabled": bool(ocr_status["enabled"]),
                    "configured": bool(ocr_status["configured"]),
                    "reason": ocr_status["reason"] or "",
                    "aliyunFreeQuota": 200,
                },
            }
        )
    finally:
        conn.close()
