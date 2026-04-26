# 该文件负责初始化酒店管理系统数据库表结构、默认管理员与演示数据。
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
from inventory_sync_service import dump_inventory_usages, ensure_inventory_sync_schema, sync_procurement_create


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
            amount REAL,
            repair_person TEXT,
            payment_person TEXT,
            remarks TEXT,
            repair_image_before TEXT,
            repair_image_after TEXT,
            repair_image TEXT,
            payment_images TEXT,
            FOREIGN KEY (room_no) REFERENCES rooms(room_no)
        )
        """
    )
    cur.execute("PRAGMA table_info(repair_records)")
    repair_cols = {row[1] for row in cur.fetchall()}
    if "repair_image" not in repair_cols:
        cur.execute("ALTER TABLE repair_records ADD COLUMN repair_image TEXT")
    if "amount" not in repair_cols:
        cur.execute("ALTER TABLE repair_records ADD COLUMN amount REAL")
    if "repair_image_before" not in repair_cols:
        cur.execute("ALTER TABLE repair_records ADD COLUMN repair_image_before TEXT")
    if "repair_image_after" not in repair_cols:
        cur.execute("ALTER TABLE repair_records ADD COLUMN repair_image_after TEXT")
    if "payment_person" not in repair_cols:
        cur.execute("ALTER TABLE repair_records ADD COLUMN payment_person TEXT")
    if "payment_images" not in repair_cols:
        cur.execute("ALTER TABLE repair_records ADD COLUMN payment_images TEXT")

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

    # self checkin links
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

    # self checkin submissions
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

    # public business entry links
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS public_entry_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business_type TEXT UNIQUE NOT NULL,
            token TEXT UNIQUE NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS public_entry_submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            link_id INTEGER,
            business_type TEXT NOT NULL,
            payload_json TEXT,
            created_record_id INTEGER,
            submitted_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (link_id) REFERENCES public_entry_links(id) ON DELETE SET NULL
        )
        """
    )

    # OCR usage stats
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS ocr_recognition_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT,
            token TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        )
        """
    )

    # AI session history
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assistant_type TEXT NOT NULL,
            title TEXT,
            current_form_json TEXT DEFAULT '{}',
            missing_fields_json TEXT DEFAULT '[]',
            completed INTEGER DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_session_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (session_id) REFERENCES ai_sessions(id) ON DELETE CASCADE
        )
        """
    )

    conn.commit()
    conn.close()


def seed_demo_data():
    """Insert a current demo dataset matching the latest business structure."""
    conn = connect()
    cur = conn.cursor()

    ensure_inventory_sync_schema()

    tables_to_check = [
        "rooms",
        "tenants",
        "repair_records",
        "procurements",
        "warehouse_items",
        "self_checkin_links",
        "public_entry_links",
    ]
    has_data = False
    for table in tables_to_check:
        try:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            if int(cur.fetchone()[0] or 0) > 0:
                has_data = True
                break
        except sqlite3.OperationalError:
            pass
    if has_data:
        conn.close()
        print("ℹ️ 跳过演示数据：当前数据库已有业务记录")
        return False

    cur.execute("PRAGMA table_info(rooms)")
    room_cols = {row[1] for row in cur.fetchall()}
    room_has_features = "features_json" in room_cols
    room_has_description = "description" in room_cols

    rooms = [
        {"building": "A栋", "floor": 1, "room_no": "A101", "room_type": "单人间", "price": 198.0, "deposit": 198.0, "description": "朝南采光好", "features_json": json.dumps(["床", "热水器"], ensure_ascii=False)},
        {"building": "A栋", "floor": 1, "room_no": "A102", "room_type": "双人间", "price": 258.0, "deposit": 258.0, "description": "带独立卫浴", "features_json": json.dumps(["床", "热水器", "冰箱"], ensure_ascii=False)},
        {"building": "B栋", "floor": 2, "room_no": "B201", "room_type": "套房", "price": 428.0, "deposit": 428.0, "description": "拎包入住", "features_json": json.dumps(["床", "热水器", "冰箱", "抽油烟机"], ensure_ascii=False)},
        {"building": "B栋", "floor": 2, "room_no": "B202", "room_type": "单人间", "price": 218.0, "deposit": 218.0, "description": "近楼梯口", "features_json": json.dumps(["床"], ensure_ascii=False)},
        {"building": "C栋", "floor": 3, "room_no": "C301", "room_type": "双人间", "price": 318.0, "deposit": 318.0, "description": "新装修", "features_json": json.dumps(["床", "热水器", "空调"], ensure_ascii=False)},
        {"building": "C栋", "floor": 3, "room_no": "C302", "room_type": "单人间", "price": 228.0, "deposit": 228.0, "description": "带阳台", "features_json": json.dumps(["床", "热水器"], ensure_ascii=False)},
    ]
    for room in rooms:
        columns = ["building", "floor", "room_no", "room_type", "price", "deposit", "status"]
        values = [room["building"], room["floor"], room["room_no"], room["room_type"], room["price"], room["deposit"], "空闲"]
        if room_has_description:
            columns.append("description")
            values.append(room["description"])
        if room_has_features:
            columns.append("features_json")
            values.append(room["features_json"])
        placeholders = ", ".join(["?"] * len(columns))
        cur.execute(
            f"INSERT INTO rooms ({', '.join(columns)}) VALUES ({placeholders})",
            values,
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
                name, gender, nation, birth_date, id_card, address, front_img, back_img,
                phone, emergency_contact_name, emergency_contact_phone,
                check_in_date, check_out_date, room_id, remarks, status
            ) VALUES (?, ?, ?, ?, ?, '', '', '', ?, '', '', ?, ?, ?, ?, ?)
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

    demo_procurements = [
        {
            "procurement_date": "2026-04-01",
            "item_name": "LED灯泡",
            "specification": "12W暖白",
            "quantity": 6,
            "unit_price": 10.0,
            "unit": "盏",
            "total_amount": 60.0,
            "remarks": "四月首批照明补货",
        },
        {
            "procurement_date": "2026-04-03",
            "item_name": "水龙头软管",
            "specification": "50cm",
            "quantity": 4,
            "unit_price": 18.0,
            "unit": "根",
            "total_amount": 72.0,
            "remarks": "维修常备材料",
        },
    ]
    procurement_ids = []
    for item in demo_procurements:
        cur.execute(
            """
            INSERT INTO procurements (
                procurement_date, item_name, specification, quantity, unit_price, unit, total_amount, remarks, procurement_images
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, '[]')
            """,
            (
                item["procurement_date"],
                item["item_name"],
                item["specification"],
                item["quantity"],
                item["unit_price"],
                item["unit"],
                item["total_amount"],
                item["remarks"],
            ),
        )
        procurement_id = cur.lastrowid
        procurement_ids.append(procurement_id)
        sync_procurement_create(
            conn,
            procurement_id,
            item["procurement_date"],
            item["item_name"],
            item["specification"],
            item["quantity"],
            item["unit_price"],
            item["unit"],
        )

    cur.execute(
        "SELECT id, item_name, specification, quantity, unit, location FROM warehouse_items WHERE item_name = ? LIMIT 1",
        ("LED灯泡",),
    )
    led_item = cur.fetchone()
    led_usage_payload = dump_inventory_usages([
        {
            "warehouse_item_id": led_item[0],
            "item_name": led_item[1],
            "specification": led_item[2],
            "quantity": 2,
            "unit": led_item[4],
            "location": led_item[5] or "",
        }
    ]) if led_item else "[]"
    if led_item:
        cur.execute(
            "UPDATE warehouse_items SET quantity = quantity - 2 WHERE id = ?",
            (led_item[0],),
        )

    cur.execute(
        """
        INSERT INTO repair_records (
            building, room_no, repair_type, description, report_date, report_by,
            status, repair_date, repair_cost, amount, repair_person, payment_person, remarks, inventory_usages,
            repair_image_before, repair_image_after, repair_image, payment_images
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '[]', '[]', '[]', '[]')
        """,
        (
            "A栋",
            "A102",
            "电器维修",
            "灯具不亮，已更换灯泡并恢复照明",
            "2026-04-05",
            "李四",
            "已完成",
            "2026-04-05",
            20.0,
            20.0,
            "张师傅",
            "王店长",
            "已从库存领用 2 盏灯泡",
            led_usage_payload,
        ),
    )

    cur.execute(
        """
        INSERT INTO repair_records (
            building, room_no, repair_type, description, report_date, report_by,
            status, repair_date, repair_cost, amount, repair_person, payment_person, remarks, inventory_usages,
            repair_image_before, repair_image_after, repair_image, payment_images
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '[]', '[]', '[]', '[]', '[]')
        """,
        (
            "C栋",
            "C301",
            "水电维修",
            "卫生间龙头滴水，等待安排师傅上门",
            "2026-04-22",
            "张三",
            "待处理",
            None,
            None,
            None,
            "",
            "",
            "已登记待处理",
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
        INSERT INTO public_entry_links (business_type, token, status)
        VALUES
            ('repair', 'demo-repair-link', 'active'),
            ('procurement', 'demo-procurement-link', 'active'),
            ('warehouse', 'demo-warehouse-link', 'active')
        """
    )

    room_a101 = room_map.get("A101")
    if room_a101:
        cur.execute(
            """
            INSERT INTO self_checkin_links (room_id, token, status, max_submissions)
            VALUES (?, ?, 'active', 20)
            """,
            (room_a101, "demo-self-checkin-link"),
        )
        link_id = cur.lastrowid
        cur.execute(
            """
            INSERT INTO self_checkin_submissions (
                link_id, room_id, status, name, gender, nation, birth_date, id_card, address,
                phone, emergency_contact_name, emergency_contact_phone, check_in_date, check_out_date, remarks
            ) VALUES (?, ?, 'pending', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                link_id,
                room_a101,
                "演示住户",
                "男",
                "汉族",
                "1998-03-12",
                "320102199803123456",
                "南京市玄武区示例路 1 号",
                "13812345678",
                "杨建国",
                "13912345678",
                "2026-05-01",
                "2027-05-01",
                "演示待确认入住记录",
            ),
        )

    cur.execute(
        """
        INSERT INTO public_entry_submissions (link_id, business_type, payload_json, created_record_id)
        VALUES (?, 'repair', ?, ?)
        """,
        (
            1,
            json.dumps({"building": "A栋", "room_no": "A102", "repair_type": "电器维修"}, ensure_ascii=False),
            1,
        ),
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
    print("✅ 已插入演示数据：房间、租户、维修、采购、库存、公开链接、自助入住和合同模板")
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
