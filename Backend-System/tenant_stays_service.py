import os
import sqlite3
from datetime import date, datetime

from common import connect


MIGRATION_KEY = "tenant_stays_v1"
ACTIVE_STATUS = "在住"
CHECKED_OUT_STATUS = "已退租"


def _table_exists(cursor, table_name):
    cursor.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    )
    return cursor.fetchone() is not None


def _columns(cursor, table_name):
    if not _table_exists(cursor, table_name):
        return set()
    cursor.execute(f"PRAGMA table_info({table_name})")
    return {row[1] for row in cursor.fetchall()}


def _add_column(cursor, table_name, column_name, definition):
    if column_name not in _columns(cursor, table_name):
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")


def _database_path(conn):
    row = conn.execute("PRAGMA database_list").fetchone()
    return str(row[2] or "") if row else ""


def _backup_before_migration(conn):
    db_path = _database_path(conn)
    if not db_path or db_path == ":memory:" or not os.path.isfile(db_path):
        return ""
    if os.path.getsize(db_path) == 0:
        return ""
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{db_path}.bak_tenant_stays_{stamp}"
    backup_conn = sqlite3.connect(backup_path)
    try:
        conn.backup(backup_conn)
    finally:
        backup_conn.close()
    return backup_path


def _create_tenant_stays_table(cursor):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS tenant_stays (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER NOT NULL,
            room_id INTEGER,
            check_in_date TEXT NOT NULL,
            planned_check_out_date TEXT DEFAULT '',
            actual_check_out_date TEXT DEFAULT '',
            rent_amount REAL NOT NULL DEFAULT 0,
            rent_unit TEXT NOT NULL DEFAULT '月',
            deposit_amount REAL NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT '在住',
            remarks TEXT DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (tenant_id) REFERENCES tenants(id),
            FOREIGN KEY (room_id) REFERENCES rooms(id)
        )
        """
    )
    cursor.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_tenant_stays_one_active
        ON tenant_stays (tenant_id)
        WHERE status = '在住'
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_tenant_stays_room_status
        ON tenant_stays (room_id, status, check_in_date)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_tenant_stays_tenant_dates
        ON tenant_stays (tenant_id, check_in_date, planned_check_out_date)
        """
    )


def _backfill_initial_stays(cursor):
    cursor.execute(
        """
        INSERT INTO tenant_stays (
            tenant_id, room_id, check_in_date, planned_check_out_date,
            actual_check_out_date, rent_amount, rent_unit, deposit_amount,
            status, remarks
        )
        SELECT
            t.id,
            t.room_id,
            COALESCE(NULLIF(TRIM(t.check_in_date), ''), DATE('now','localtime')),
            COALESCE(TRIM(t.check_out_date), ''),
            CASE
                WHEN COALESCE(TRIM(t.status), '') = '已退租'
                THEN COALESCE(NULLIF(TRIM(t.check_out_date), ''), DATE('now','localtime'))
                ELSE ''
            END,
            COALESCE(r.price, 0),
            COALESCE(NULLIF(TRIM(r.price_unit), ''), '月'),
            COALESCE(r.deposit, 0),
            CASE WHEN COALESCE(TRIM(t.status), '') = '已退租' THEN '已退租' ELSE '在住' END,
            COALESCE(t.remarks, '')
        FROM tenants t
        LEFT JOIN rooms r ON r.id = t.room_id
        WHERE NOT EXISTS (
            SELECT 1 FROM tenant_stays s WHERE s.tenant_id = t.id
        )
        """
    )


def _backfill_related_stay_ids(cursor):
    if _table_exists(cursor, "contracts"):
        _add_column(cursor, "contracts", "stay_id", "INTEGER")
        cursor.execute(
            """
            UPDATE contracts
            SET stay_id = COALESCE(
                (
                    SELECT s.id
                    FROM tenant_stays s
                    WHERE s.tenant_id = contracts.tenant_id
                      AND (contracts.room_id IS NULL OR s.room_id = contracts.room_id)
                      AND (
                        COALESCE(TRIM(contracts.start_date), '') = ''
                        OR DATE(contracts.start_date) >= DATE(s.check_in_date)
                      )
                    ORDER BY
                        CASE WHEN s.status = '在住' THEN 0 ELSE 1 END,
                        s.check_in_date DESC,
                        s.id DESC
                    LIMIT 1
                ),
                (SELECT s.id FROM tenant_stays s WHERE s.tenant_id = contracts.tenant_id ORDER BY s.id DESC LIMIT 1)
            )
            WHERE stay_id IS NULL AND tenant_id IS NOT NULL
            """
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_contracts_stay ON contracts (stay_id)")

    if _table_exists(cursor, "tenant_moves"):
        _add_column(cursor, "tenant_moves", "stay_id", "INTEGER")
        cursor.execute(
            """
            UPDATE tenant_moves
            SET stay_id = COALESCE(
                (
                    SELECT s.id FROM tenant_stays s
                    WHERE s.tenant_id = tenant_moves.tenant_id
                      AND DATE(tenant_moves.move_date) >= DATE(s.check_in_date)
                    ORDER BY s.check_in_date DESC, s.id DESC
                    LIMIT 1
                ),
                (SELECT s.id FROM tenant_stays s WHERE s.tenant_id = tenant_moves.tenant_id ORDER BY s.id DESC LIMIT 1)
            )
            WHERE stay_id IS NULL AND tenant_id IS NOT NULL
            """
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tenant_moves_stay ON tenant_moves (stay_id)")

    if _table_exists(cursor, "self_checkin_submissions"):
        _add_column(cursor, "self_checkin_submissions", "approved_stay_id", "INTEGER")
        cursor.execute(
            """
            UPDATE self_checkin_submissions
            SET approved_stay_id = (
                SELECT s.id FROM tenant_stays s
                WHERE s.tenant_id = self_checkin_submissions.approved_tenant_id
                  AND (self_checkin_submissions.room_id IS NULL OR s.room_id = self_checkin_submissions.room_id)
                ORDER BY s.check_in_date DESC, s.id DESC
                LIMIT 1
            )
            WHERE approved_stay_id IS NULL AND approved_tenant_id IS NOT NULL
            """
        )


def _rent_ledger_needs_rebuild(cursor):
    if not _table_exists(cursor, "rent_ledger_entries"):
        return False
    cursor.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'rent_ledger_entries'")
    row = cursor.fetchone()
    normalized = " ".join(str(row[0] or "").lower().split()) if row else ""
    return "stay_id" not in _columns(cursor, "rent_ledger_entries") or "unique (tenant_id, period_start)" in normalized


def _backfill_rent_ledger_stay_ids(cursor):
    if "stay_id" not in _columns(cursor, "rent_ledger_entries"):
        return
    cursor.execute(
        """
        UPDATE rent_ledger_entries
        SET stay_id = COALESCE(
            (
                SELECT s.id FROM tenant_stays s
                WHERE s.tenant_id = rent_ledger_entries.tenant_id
                  AND (rent_ledger_entries.room_id IS NULL OR s.room_id = rent_ledger_entries.room_id)
                  AND DATE(rent_ledger_entries.period_start) >= DATE(s.check_in_date)
                ORDER BY s.check_in_date DESC, s.id DESC
                LIMIT 1
            ),
            (SELECT s.id FROM tenant_stays s WHERE s.tenant_id = rent_ledger_entries.tenant_id ORDER BY s.id DESC LIMIT 1)
        )
        WHERE stay_id IS NULL
        """
    )


def _create_rent_ledger_table(cursor):
    cursor.execute(
        """
        CREATE TABLE rent_ledger_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER NOT NULL,
            stay_id INTEGER,
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
            UNIQUE (stay_id, period_start),
            FOREIGN KEY (tenant_id) REFERENCES tenants(id),
            FOREIGN KEY (stay_id) REFERENCES tenant_stays(id),
            FOREIGN KEY (room_id) REFERENCES rooms(id)
        )
        """
    )


def _rebuild_rent_ledger_table(cursor):
    if not _table_exists(cursor, "rent_ledger_entries"):
        _create_rent_ledger_table(cursor)
        return
    old_columns = _columns(cursor, "rent_ledger_entries")
    stay_expression = "e.stay_id" if "stay_id" in old_columns else "NULL"
    allocated_expression = "e.allocated_amount" if "allocated_amount" in old_columns else "e.actual_amount"
    payment_person_expression = "e.payment_person" if "payment_person" in old_columns else "''"
    cursor.execute("ALTER TABLE rent_ledger_entries RENAME TO rent_ledger_entries_before_stays")
    _create_rent_ledger_table(cursor)
    cursor.execute(
        f"""
        INSERT INTO rent_ledger_entries (
            id, tenant_id, stay_id, room_id, building, room_no, tenant_name,
            lease_start, lease_end, rent_amount, rent_unit, period_index,
            period_label, period_start, period_end, due_amount, actual_amount,
            allocated_amount, status, payment_date, payment_person, payment_method,
            remarks, payment_images, created_at, updated_at
        )
        SELECT
            e.id,
            e.tenant_id,
            COALESCE(
                {stay_expression},
                (
                    SELECT s.id FROM tenant_stays s
                    WHERE s.tenant_id = e.tenant_id
                      AND (e.room_id IS NULL OR s.room_id = e.room_id)
                      AND DATE(e.period_start) >= DATE(s.check_in_date)
                    ORDER BY s.check_in_date DESC, s.id DESC
                    LIMIT 1
                ),
                (SELECT s.id FROM tenant_stays s WHERE s.tenant_id = e.tenant_id ORDER BY s.id DESC LIMIT 1)
            ),
            e.room_id, e.building, e.room_no, e.tenant_name,
            e.lease_start, e.lease_end, e.rent_amount, e.rent_unit, e.period_index,
            e.period_label, e.period_start, e.period_end, e.due_amount, e.actual_amount,
            {allocated_expression}, e.status, e.payment_date, {payment_person_expression},
            e.payment_method, e.remarks, e.payment_images, e.created_at, e.updated_at
        FROM rent_ledger_entries_before_stays e
        """
    )
    cursor.execute("DROP TABLE rent_ledger_entries_before_stays")


def _ensure_rent_ledger_indexes(cursor):
    if not _table_exists(cursor, "rent_ledger_entries"):
        return
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
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_rent_ledger_stay
        ON rent_ledger_entries (stay_id, period_start)
        """
    )


def ensure_tenant_stays_schema():
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            migration_key TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL,
            backup_path TEXT DEFAULT ''
        )
        """
    )
    cursor.execute("SELECT 1 FROM schema_migrations WHERE migration_key = ?", (MIGRATION_KEY,))
    already_applied = cursor.fetchone() is not None
    needs_migration = (
        not _table_exists(cursor, "tenant_stays")
        or _rent_ledger_needs_rebuild(cursor)
        or "stay_id" not in _columns(cursor, "contracts")
        or "stay_id" not in _columns(cursor, "tenant_moves")
        or "approved_stay_id" not in _columns(cursor, "self_checkin_submissions")
    )
    backup_path = ""
    if needs_migration and not already_applied and _table_exists(cursor, "tenants"):
        cursor.execute("SELECT COUNT(*) FROM tenants")
        if int(cursor.fetchone()[0] or 0) > 0:
            conn.commit()
            backup_path = _backup_before_migration(conn)

    try:
        conn.execute("BEGIN IMMEDIATE")
        _create_tenant_stays_table(cursor)
        _backfill_initial_stays(cursor)
        _backfill_related_stay_ids(cursor)
        _backfill_rent_ledger_stay_ids(cursor)
        if _rent_ledger_needs_rebuild(cursor):
            _rebuild_rent_ledger_table(cursor)
        _backfill_rent_ledger_stay_ids(cursor)
        _ensure_rent_ledger_indexes(cursor)
        cursor.execute(
            """
            INSERT INTO schema_migrations (migration_key, applied_at, backup_path)
            VALUES (?, datetime('now','localtime'), ?)
            ON CONFLICT(migration_key) DO UPDATE SET
                applied_at = excluded.applied_at,
                backup_path = CASE
                    WHEN schema_migrations.backup_path = '' THEN excluded.backup_path
                    ELSE schema_migrations.backup_path
                END
            """,
            (MIGRATION_KEY, backup_path),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return backup_path


def get_current_stay(conn, tenant_id):
    conn.row_factory = sqlite3.Row
    return conn.execute(
        """
        SELECT s.*, r.room_no, r.building
        FROM tenant_stays s
        LEFT JOIN rooms r ON r.id = s.room_id
        WHERE s.tenant_id = ? AND s.status = '在住'
        ORDER BY s.check_in_date DESC, s.id DESC
        LIMIT 1
        """,
        (tenant_id,),
    ).fetchone()


def create_tenant_stay(conn, tenant_id, room_id, check_in_date, planned_check_out_date, remarks=""):
    check_in_text = str(check_in_date or "").strip()
    check_out_text = str(planned_check_out_date or "").strip()
    if not check_in_text or not check_out_text:
        raise ValueError("入住日期和计划退房日期不能为空")
    try:
        check_in_value = datetime.strptime(check_in_text, "%Y-%m-%d").date()
        check_out_value = datetime.strptime(check_out_text, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError("入住日期或计划退房日期格式不正确") from exc
    if check_out_value < check_in_value:
        raise ValueError("计划退房日期不能早于入住日期")
    if get_current_stay(conn, tenant_id):
        raise ValueError("该租户已有一条在住记录，请先办理退租")
    room = conn.execute(
        "SELECT price, COALESCE(NULLIF(TRIM(price_unit), ''), '月'), COALESCE(deposit, 0) FROM rooms WHERE id = ?",
        (room_id,),
    ).fetchone()
    if not room:
        raise ValueError("房间不存在")
    if float(room[0] or 0) <= 0:
        raise ValueError("房间租金为 0，请先设置租金")
    cursor = conn.execute(
        """
        INSERT INTO tenant_stays (
            tenant_id, room_id, check_in_date, planned_check_out_date,
            actual_check_out_date, rent_amount, rent_unit, deposit_amount,
            status, remarks
        ) VALUES (?, ?, ?, ?, '', ?, ?, ?, '在住', ?)
        """,
        (tenant_id, room_id, check_in_text, check_out_text, float(room[0]), room[1], float(room[2]), str(remarks or "")),
    )
    stay_id = cursor.lastrowid
    sync_legacy_tenant_from_stay(conn, tenant_id, stay_id)
    return stay_id


def sync_legacy_tenant_from_stay(conn, tenant_id, stay_id=None):
    if stay_id is None:
        stay = get_current_stay(conn, tenant_id)
        if not stay:
            stay = conn.execute(
                "SELECT * FROM tenant_stays WHERE tenant_id = ? ORDER BY check_in_date DESC, id DESC LIMIT 1",
                (tenant_id,),
            ).fetchone()
    else:
        stay = conn.execute("SELECT * FROM tenant_stays WHERE id = ? AND tenant_id = ?", (stay_id, tenant_id)).fetchone()
    if not stay:
        return
    keys = stay.keys() if hasattr(stay, "keys") else []
    actual = stay["actual_check_out_date"] if "actual_check_out_date" in keys else stay[5]
    planned = stay["planned_check_out_date"] if "planned_check_out_date" in keys else stay[4]
    status = stay["status"] if "status" in keys else stay[9]
    room_id = stay["room_id"] if "room_id" in keys else stay[2]
    check_in = stay["check_in_date"] if "check_in_date" in keys else stay[3]
    conn.execute(
        """
        UPDATE tenants
        SET room_id = ?, check_in_date = ?, check_out_date = ?, status = ?
        WHERE id = ?
        """,
        (room_id, check_in, actual or planned or "", status, tenant_id),
    )


def checkout_current_stay(conn, tenant_id, checkout_date=None):
    stay = get_current_stay(conn, tenant_id)
    if not stay:
        return None
    checkout_text = str(checkout_date or date.today().isoformat())
    conn.execute(
        """
        UPDATE tenant_stays
        SET status = '已退租', actual_check_out_date = ?, updated_at = datetime('now','localtime')
        WHERE id = ?
        """,
        (checkout_text, int(stay["id"])),
    )
    sync_legacy_tenant_from_stay(conn, tenant_id, int(stay["id"]))
    return int(stay["id"]), checkout_text
