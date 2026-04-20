import argparse
import hashlib
import json
import os
import shutil
import sys
from datetime import date

# Allow importing common.py from Backend-System root
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from common import DB_NAME, connect


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def ensure_tables():
    """Create all required tables and ensure compatible columns exist."""
    conn = connect()
    cur = conn.cursor()

    # rooms
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS rooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            building TEXT,
            floor INTEGER,
            room_no TEXT UNIQUE NOT NULL,
            room_type TEXT,
            price REAL,
            deposit REAL DEFAULT 0,
            status TEXT DEFAULT '空闲',
            water_meter_img TEXT,
            electricity_meter_img TEXT
        )
        """
    )
    cur.execute("PRAGMA table_info(rooms)")
    room_cols = {row[1] for row in cur.fetchall()}
    if "deposit" not in room_cols:
        cur.execute("ALTER TABLE rooms ADD COLUMN deposit REAL DEFAULT 0")
    if "water_meter_img" not in room_cols:
        cur.execute("ALTER TABLE rooms ADD COLUMN water_meter_img TEXT")
    if "electricity_meter_img" not in room_cols:
        cur.execute("ALTER TABLE rooms ADD COLUMN electricity_meter_img TEXT")

    # tenants
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS tenants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            gender TEXT,
            nation TEXT,
            birth_date DATE,
            id_card TEXT UNIQUE,
            address TEXT,
            issuing_authority TEXT,
            valid_from DATE,
            valid_to DATE,
            front_img TEXT,
            back_img TEXT,
            phone TEXT,
            emergency_contact_name TEXT,
            emergency_contact_phone TEXT,
            check_in_date DATE,
            check_out_date DATE,
            room_id INTEGER,
            remarks TEXT,
            status TEXT DEFAULT '在租',
            FOREIGN KEY (room_id) REFERENCES rooms(id)
        )
        """
    )

    # tenant moves
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS tenant_moves (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER,
            old_room_id INTEGER,
            new_room_id INTEGER,
            move_date DATE,
            remarks TEXT,
            FOREIGN KEY (tenant_id) REFERENCES tenants(id),
            FOREIGN KEY (old_room_id) REFERENCES rooms(id),
            FOREIGN KEY (new_room_id) REFERENCES rooms(id)
        )
        """
    )

    # admins
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT,
            created_at DATE DEFAULT (DATE('now'))
        )
        """
    )
    cur.execute("PRAGMA table_info(admins)")
    admin_cols = {row[1] for row in cur.fetchall()}
    if "recovery_phrase_hash" not in admin_cols:
        cur.execute("ALTER TABLE admins ADD COLUMN recovery_phrase_hash TEXT")
    if "security_question" not in admin_cols:
        cur.execute("ALTER TABLE admins ADD COLUMN security_question TEXT")
    if "security_answer_hash" not in admin_cols:
        cur.execute("ALTER TABLE admins ADD COLUMN security_answer_hash TEXT")

    # repair records
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS repair_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            building TEXT,
            room_no TEXT NOT NULL,
            repair_type TEXT,
            description TEXT,
            report_date DATE,
            report_by TEXT,
            status TEXT DEFAULT '待处理',
            repair_date DATE,
            repair_cost REAL,
            repair_person TEXT,
            remarks TEXT,
            repair_image_before TEXT,
            repair_image_after TEXT,
            repair_image TEXT,
            FOREIGN KEY (room_no) REFERENCES rooms(room_no)
        )
        """
    )
    cur.execute("PRAGMA table_info(repair_records)")
    repair_cols = {row[1] for row in cur.fetchall()}
    if "repair_image" not in repair_cols:
        cur.execute("ALTER TABLE repair_records ADD COLUMN repair_image TEXT")
    if "repair_image_before" not in repair_cols:
        cur.execute("ALTER TABLE repair_records ADD COLUMN repair_image_before TEXT")
    if "repair_image_after" not in repair_cols:
        cur.execute("ALTER TABLE repair_records ADD COLUMN repair_image_after TEXT")

    # contract templates
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS contract_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            content_html TEXT NOT NULL,
            created_at DATETIME DEFAULT (DATETIME('now')),
            updated_at DATETIME DEFAULT (DATETIME('now'))
        )
        """
    )

    # contracts
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS contracts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER,
            room_id INTEGER,
            template_id INTEGER NOT NULL,
            tenant_name TEXT,
            id_card TEXT,
            room_no TEXT,
            start_date TEXT,
            end_date TEXT,
            rent REAL,
            rendered_html TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT,
            FOREIGN KEY (tenant_id) REFERENCES tenants(id),
            FOREIGN KEY (room_id) REFERENCES rooms(id),
            FOREIGN KEY (template_id) REFERENCES contract_templates(id)
        )
        """
    )

    # procurements
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS procurements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            procurement_date DATE NOT NULL,
            item_name TEXT NOT NULL,
            specification TEXT,
            quantity INTEGER NOT NULL,
            unit_price REAL DEFAULT 0,
            unit TEXT,
            total_amount REAL NOT NULL,
            remarks TEXT,
            procurement_images TEXT,
            created_at DATETIME DEFAULT (DATETIME('now')),
            updated_at DATETIME DEFAULT (DATETIME('now'))
        )
        """
    )

    # warehouse
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS warehouse_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_name TEXT NOT NULL,
            category TEXT,
            quantity REAL NOT NULL DEFAULT 0,
            unit TEXT,
            location TEXT,
            image TEXT,
            remarks TEXT,
            created_at DATETIME DEFAULT (DATETIME('now')),
            updated_at DATETIME DEFAULT (DATETIME('now'))
        )
        """
    )

    conn.commit()
    conn.close()


def seed_demo_data():
    """Insert a small demo dataset. Skip if rooms or tenants already exist."""
    conn = connect()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM rooms")
    room_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM tenants")
    tenant_count = cur.fetchone()[0]
    if room_count > 0 or tenant_count > 0:
        conn.close()
        print("ℹ️ 跳过演示数据：数据库已有房间或租户记录")
        return False

    rooms = [
        ("A栋", 1, "A101", "单人间", 198.0),
        ("A栋", 1, "A102", "双人间", 258.0),
        ("B栋", 2, "B201", "套房", 428.0),
        ("B栋", 2, "B202", "单人间", 218.0),
    ]
    for building, floor, room_no, room_type, price in rooms:
        cur.execute(
            "INSERT INTO rooms (building, floor, room_no, room_type, price, deposit, status) VALUES (?, ?, ?, ?, ?, ?, '空闲')",
            (building, floor, room_no, room_type, price, price),
        )

    cur.execute("SELECT id, room_no FROM rooms")
    room_map = {r[1]: r[0] for r in cur.fetchall()}

    tenants = [
        {
            "name": "张三",
            "gender": "男",
            "nation": "汉族",
            "birth_date": "1992-03-15",
            "id_card": "11010519920315001X",
            "phone": "13800000001",
            "check_in_date": "2025-01-01",
            "check_out_date": "2026-12-31",
            "room_no": "A101",
            "status": "在租",
            "remarks": "长期租",
        },
        {
            "name": "李四",
            "gender": "女",
            "nation": "汉族",
            "birth_date": "1995-08-20",
            "id_card": "110105199508200029",
            "phone": "13800000002",
            "check_in_date": "2025-06-01",
            "check_out_date": "2026-06-01",
            "room_no": "B201",
            "status": "在租",
            "remarks": "公司入住",
        },
    ]

    for t in tenants:
        room_id = room_map.get(t["room_no"])
        cur.execute(
            """
            INSERT INTO tenants (
                name, gender, nation, birth_date, id_card, address, issuing_authority,
                valid_from, valid_to, front_img, back_img,
                phone, emergency_contact_name, emergency_contact_phone,
                check_in_date, check_out_date, room_id, remarks, status
            ) VALUES (?, ?, ?, ?, ?, '', '', '', '', '', '', ?, '', '', ?, ?, ?, ?, ?)
            """,
            (
                t["name"],
                t["gender"],
                t.get("nation", "汉族"),
                t.get("birth_date"),
                t["id_card"],
                t["phone"],
                t["check_in_date"],
                t["check_out_date"],
                room_id,
                t.get("remarks", ""),
                t.get("status", "在租"),
            ),
        )

    cur.execute(
        """
        INSERT INTO repair_records (
            building, room_no, repair_type, description, report_date, report_by,
            status, repair_date, repair_cost, repair_person, remarks,
            repair_image_before, repair_image_after, repair_image
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "A栋",
            "A102",
            "空调维修",
            "空调不制冷，已安排检修",
            "2025-02-18",
            "李四",
            "已完成",
            "2025-02-19",
            320.0,
            "张师傅",
            "保内处理",
            "[]",
            "[]",
            "[]",
        ),
    )

    cur.execute("SELECT COUNT(*) FROM contract_templates")
    if cur.fetchone()[0] == 0:
        cur.execute(
            "INSERT INTO contract_templates (name, description, content_html, updated_at) VALUES (?, ?, ?, DATETIME('now'))",
            ("标准租赁合同", "默认模板", "<h1>租赁合同</h1><p>示例模板内容</p>"),
        )

    cur.execute(
        """
        UPDATE rooms
        SET status = CASE
            WHEN EXISTS (
                SELECT 1 FROM tenants t
                WHERE t.room_id = rooms.id
                  AND t.status = '在租'
                  AND DATE('now') BETWEEN t.check_in_date AND t.check_out_date
            ) THEN '已入住'
            ELSE '空闲'
        END
        """
    )

    conn.commit()
    conn.close()
    print("✅ 已插入演示数据：房间、租户、维修和合同模板")
    return True


def create_default_admin(username: str = "admin", password: str = "123456", full_name: str = "管理员"):
    """Create default admin if missing."""
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT id FROM admins WHERE username = ?", (username,))
    if cur.fetchone():
        conn.close()
        return False, f"管理员 {username} 已存在"

    cur.execute(
        "INSERT INTO admins (username, password_hash, full_name) VALUES (?, ?, ?)",
        (username, sha256(password), full_name),
    )
    conn.commit()
    conn.close()
    return True, f"管理员 {username} 已创建"


def summarize(compact: bool = False):
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    tables = [r[0] for r in cur.fetchall()]

    if compact:
        parts = []
        for t in tables:
            cur.execute(f"SELECT COUNT(*) FROM {t}")
            parts.append(f"{t}:{cur.fetchone()[0]}")
        print("DB:" + DB_NAME)
        print(" | ".join(parts))
        conn.close()
        return

    summary = {"db_path": DB_NAME, "tables": {}}
    for t in tables:
        try:
            cur.execute(f"SELECT COUNT(*) FROM {t}")
            count = cur.fetchone()[0]
            cur.execute(f"PRAGMA table_info({t})")
            cols = [{"name": c[1], "type": c[2]} for c in cur.fetchall()]
            summary["tables"][t] = {"count": count, "columns": cols}
        except Exception as e:
            summary["tables"][t] = {"error": str(e)}

    conn.close()
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def ensure_sql_dir_and_migrate_db():
    """Move old DB file from Backend-System root to sql folder if needed."""
    base_dir = os.path.dirname(os.path.dirname(__file__))
    old_path = os.path.join(base_dir, "hotel.db")
    new_path = DB_NAME

    os.makedirs(os.path.dirname(new_path), exist_ok=True)
    if os.path.exists(old_path) and not os.path.exists(new_path):
        try:
            shutil.move(old_path, new_path)
            print(f"已迁移数据库到: {new_path}")
        except Exception as e:
            print(f"迁移数据库失败: {e}")


def main():
    parser = argparse.ArgumentParser(description="初始化/检查酒店管理数据库")
    parser.add_argument("--init", action="store_true", help="创建缺失的表和必要列")
    parser.add_argument("--create-default-admin", action="store_true", help="若无管理员则创建 admin/123456")
    parser.add_argument("--summarize", action="store_true", help="输出当前数据库概览")
    parser.add_argument("--compact", action="store_true", help="紧凑格式输出统计")
    parser.add_argument("--seed-demo-data", action="store_true", help="插入演示数据（若已有数据则跳过）")
    args = parser.parse_args()

    ensure_sql_dir_and_migrate_db()

    if args.init:
        ensure_tables()
        print("✅ 表结构已确保存在并更新")

    if args.create_default_admin:
        created, msg = create_default_admin()
        print(("✅ " if created else "ℹ️ ") + msg)

    if args.seed_demo_data:
        seed_demo_data()

    if args.summarize or (not args.init and not args.create_default_admin and not args.seed_demo_data):
        summarize(compact=args.compact)


if __name__ == "__main__":
    main()
