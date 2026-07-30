import logging
import sqlite3
from datetime import date, datetime, timedelta

from common import connect
import expiry_notification_config as notify_config
from rent_ledger_api import _rebuild_rent_ledger_year


logger = logging.getLogger("notification_worker")
DELIVERY_BATCH_SIZE = 8


def ensure_notification_delivery_schema(conn=None):
    owns_connection = conn is None
    conn = conn or connect()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS notification_delivery_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel TEXT NOT NULL,
                scene TEXT NOT NULL,
                event_key TEXT NOT NULL,
                endpoint_id TEXT NOT NULL,
                attempted_on TEXT NOT NULL,
                success INTEGER NOT NULL DEFAULT 0,
                error TEXT DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                UNIQUE (channel, event_key, endpoint_id, attempted_on)
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_notification_delivery_event
            ON notification_delivery_log (channel, event_key, endpoint_id, success)
            """
        )
        conn.commit()
    finally:
        if owns_connection:
            conn.close()


def _parse_date(value):
    try:
        return datetime.strptime(str(value or "").strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def _days_text(days):
    if days < 0:
        return f"逾期 {abs(days)} 天"
    if days == 0:
        return "今天到期"
    return f"{days} 天后"


def _money(value):
    return f"¥{float(value or 0):,.2f}"


def _room_text(item):
    building = str(item.get("building") or "").strip()
    room_no = str(item.get("room_no") or "").strip()
    return " ".join(part for part in [building, room_no] if part) or "未设置房间"


def _load_lease_events(conn, today, advance_days):
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT
            s.id AS stay_id,
            s.planned_check_out_date,
            s.rent_amount,
            s.rent_unit,
            t.name AS tenant_name,
            r.building,
            r.room_no
        FROM tenant_stays s
        JOIN tenants t ON t.id = s.tenant_id
        LEFT JOIN rooms r ON r.id = s.room_id
        WHERE s.status = '在住'
          AND COALESCE(TRIM(s.planned_check_out_date), '') <> ''
          AND date(s.planned_check_out_date) <= date(?)
        ORDER BY date(s.planned_check_out_date), s.id
        """,
        ((today + timedelta(days=advance_days)).isoformat(),),
    ).fetchall()

    events = []
    for row in rows:
        due_date = _parse_date(row["planned_check_out_date"])
        if not due_date:
            continue
        events.append(
            {
                "event_key": f"lease:{row['stay_id']}:{due_date.isoformat()}",
                "scene": "lease_expiry",
                "tenant_name": row["tenant_name"] or "未填写租户",
                "building": row["building"] or "",
                "room_no": row["room_no"] or "",
                "due_date": due_date.isoformat(),
                "days": (due_date - today).days,
                "rent_amount": float(row["rent_amount"] or 0),
                "rent_unit": row["rent_unit"] or "月",
            }
        )
    return events


def _load_rent_events(conn, today, advance_days):
    target_date = today + timedelta(days=advance_days)
    for year in sorted({today.year, target_date.year}):
        if _rebuild_rent_ledger_year(conn, year) > 0:
            conn.commit()

    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT
            e.id,
            e.tenant_id,
            e.stay_id,
            e.room_id,
            e.period_start,
            e.due_amount,
            COALESCE(e.allocated_amount, e.actual_amount, 0) AS paid_amount,
            e.tenant_name,
            e.building,
            e.room_no
        FROM rent_ledger_entries e
        LEFT JOIN tenant_stays s ON s.id = e.stay_id
        WHERE COALESCE(TRIM(e.period_start), '') <> ''
          AND date(e.period_start) <= date(?)
          AND COALESCE(e.due_amount, 0) > COALESCE(e.allocated_amount, e.actual_amount, 0)
          AND COALESCE(TRIM(e.status), '未交') <> '已交'
          AND COALESCE(TRIM(s.status), '在住') <> '已退租'
        ORDER BY date(e.period_start), e.id
        """,
        (target_date.isoformat(),),
    ).fetchall()

    events = []
    for row in rows:
        due_date = _parse_date(row["period_start"])
        outstanding = round(max(float(row["due_amount"] or 0) - float(row["paid_amount"] or 0), 0), 2)
        if not due_date or outstanding <= 0:
            continue
        if row["stay_id"]:
            stay_key = f"stay:{row['stay_id']}"
        else:
            stay_key = f"tenant:{row['tenant_id']}:room:{row['room_id'] or 0}"
        events.append(
            {
                "event_key": f"rent:{stay_key}:{due_date.isoformat()}",
                "scene": "rent_reminder",
                "tenant_name": row["tenant_name"] or "未填写租户",
                "building": row["building"] or "",
                "room_no": row["room_no"] or "",
                "due_date": due_date.isoformat(),
                "days": (due_date - today).days,
                "outstanding_amount": outstanding,
            }
        )
    return events


def _claim_events(conn, events, endpoint_id, attempted_on, max_deliveries):
    claimed = []
    conn.execute("BEGIN IMMEDIATE")
    try:
        for event in events:
            success_count = conn.execute(
                """
                SELECT COUNT(*) FROM notification_delivery_log
                WHERE channel = 'bark' AND event_key = ? AND endpoint_id = ? AND success = 1
                """,
                (event["event_key"], endpoint_id),
            ).fetchone()[0]
            if int(success_count or 0) >= max_deliveries:
                continue
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO notification_delivery_log (
                    channel, scene, event_key, endpoint_id, attempted_on, success, error
                ) VALUES ('bark', ?, ?, ?, ?, 0, 'pending')
                """,
                (event["scene"], event["event_key"], endpoint_id, attempted_on),
            )
            if cursor.rowcount:
                claimed.append(event)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return claimed


def _finish_claims(conn, events, endpoint_id, attempted_on, success, error=""):
    conn.executemany(
        """
        UPDATE notification_delivery_log
        SET success = ?, error = ?, updated_at = datetime('now','localtime')
        WHERE channel = 'bark' AND event_key = ? AND endpoint_id = ? AND attempted_on = ?
        """,
        [
            (1 if success else 0, str(error or "")[:300], event["event_key"], endpoint_id, attempted_on)
            for event in events
        ],
    )
    conn.commit()


def _chunks(items, size=DELIVERY_BATCH_SIZE):
    for index in range(0, len(items), size):
        yield items[index:index + size]


def _render_batch(scene, events):
    if scene == "lease_expiry":
        title = f"租期到期提醒｜{len(events)} 项"
        lines = [
            f"{index}. {_room_text(item)}｜{item['tenant_name']}｜{item['due_date']}（{_days_text(item['days'])}）｜{_money(item['rent_amount'])}/{item['rent_unit']}"
            for index, item in enumerate(events, 1)
        ]
        return title, "\n".join(lines + ["请及时确认续租或退租安排。"])

    title = f"待收房租提醒｜{len(events)} 项"
    lines = [
        f"{index}. {_room_text(item)}｜{item['tenant_name']}｜待收 {_money(item['outstanding_amount'])}｜{item['due_date']}（{_days_text(item['days'])}）"
        for index, item in enumerate(events, 1)
    ]
    return title, "\n".join(lines + ["请及时核对收款情况。"])


def _valid_send_time(value):
    try:
        return datetime.strptime(str(value or "09:00"), "%H:%M").time()
    except ValueError:
        return datetime.strptime("09:00", "%H:%M").time()


def run_due_bark_notifications(now=None, force=False):
    now = now or datetime.now()
    today = now.date()
    config = notify_config.get_runtime_config() or {}
    bark_config = config.get("bark_config") or {}

    if not config.get("enabled", True):
        return {"status": "skipped", "reason": "通知系统已停用", "sent": 0, "failed": 0}
    if not bark_config.get("enabled", True):
        return {"status": "skipped", "reason": "Bark 推送已停用", "sent": 0, "failed": 0}
    if not force and not bark_config.get("auto_send_enabled", True):
        return {"status": "skipped", "reason": "Bark 自动推送已停用", "sent": 0, "failed": 0}
    if not force and now.time() < _valid_send_time(bark_config.get("send_time")):
        return {"status": "skipped", "reason": "尚未到每日发送时间", "sent": 0, "failed": 0}

    endpoints = [item for item in bark_config.get("endpoints", []) if item.get("enabled", True)]
    if not endpoints:
        return {"status": "skipped", "reason": "没有启用的 Bark 地址", "sent": 0, "failed": 0}

    try:
        max_deliveries = max(1, int(config.get("reminder_count", 1) or 1))
    except (TypeError, ValueError):
        max_deliveries = 1
    try:
        lease_days = max(0, int(config.get("lease_advance_days", 7)))
    except (TypeError, ValueError):
        lease_days = 7
    try:
        rent_days = max(0, int(config.get("rent_advance_days", 7)))
    except (TypeError, ValueError):
        rent_days = 7

    conn = connect()
    sent = 0
    failed = 0
    claimed_count = 0
    try:
        ensure_notification_delivery_schema(conn)
        scenes = []
        if bark_config.get("lease_expiry_enabled", True):
            scenes.append(("lease_expiry", _load_lease_events(conn, today, lease_days)))
        if bark_config.get("rent_reminder_enabled", True):
            scenes.append(("rent_reminder", _load_rent_events(conn, today, rent_days)))

        from notify_api import send_bark_notification

        attempted_on = today.isoformat()
        for scene, events in scenes:
            for endpoint in endpoints:
                for event_batch in _chunks(events):
                    batch = _claim_events(conn, event_batch, endpoint["id"], attempted_on, max_deliveries)
                    claimed_count += len(batch)
                    if not batch:
                        continue
                    title, content = _render_batch(scene, batch)
                    try:
                        result = send_bark_notification(title, content, endpoint_ids=[endpoint["id"]])
                        success = result.get("failure_count", 0) == 0
                        error = "" if success else (result.get("results") or [{}])[0].get("error", "推送失败")
                    except Exception as exc:
                        success = False
                        error = str(exc)
                    _finish_claims(conn, batch, endpoint["id"], attempted_on, success, error)
                    if success:
                        sent += 1
                    else:
                        failed += 1
                        logger.error("Bark 自动推送失败: scene=%s endpoint=%s error=%s", scene, endpoint.get("remark") or endpoint["id"], error)
    finally:
        conn.close()

    return {
        "status": "completed",
        "date": today.isoformat(),
        "claimed_events": claimed_count,
        "sent": sent,
        "failed": failed,
    }
