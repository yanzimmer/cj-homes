# 该文件负责聚合首页运营总览所需的房间、租户、维修和到期预警统计接口。
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
                },
                "procurements": {
                    "total": procurement_total,
                    "totalAmount": round(procurement_total_amount, 2),
                },
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
