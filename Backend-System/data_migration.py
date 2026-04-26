# 该文件负责执行数据库与配置数据的迁移、导入导出及兼容处理。
import json
import sqlite3
import argparse
import os
import sys
from datetime import datetime

# Add parent directory to path to import common
sys.path.append(os.path.dirname(__file__))
from common import connect, DB_NAME

# Define table order for import to respect foreign keys
TABLE_ORDER = [
    "rooms",
    "contract_templates",
    "admins",
    "tenants",
    "tenant_moves",
    "repair_records",
    "contracts"
]

def export_data(output_file):
    """Export all data from database to a JSON file."""
    conn = connect()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    data = {}
    
    print(f"正在导出数据到 {output_file} ...")
    
    try:
        # Get list of all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        tables = [row['name'] for row in cursor.fetchall()]
        
        for table in tables:
            print(f"  - 正在导出表: {table}")
            cursor.execute(f"SELECT * FROM {table}")
            rows = [dict(row) for row in cursor.fetchall()]
            data[table] = rows
            
        # Add metadata
        export_data = {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "version": "1.0"
            },
            "tables": data
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
            
        print(f"✅ 导出成功！文件已保存至: {os.path.abspath(output_file)}")
        return True
        
    except Exception as e:
        print(f"❌ 导出失败: {e}")
        return False
    finally:
        conn.close()

def import_data(input_file, force=False):
    """Import data from a JSON file into the database."""
    if not os.path.exists(input_file):
        print(f"❌ 错误: 文件 {input_file} 不存在")
        return False
        
    print(f"正在从 {input_file} 导入数据...")
    
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        tables_data = data.get("tables", {})
        
        conn = connect()
        cursor = conn.cursor()
        
        # Disable foreign keys temporarily to allow truncating tables
        cursor.execute("PRAGMA foreign_keys = OFF")
        
        # Begin transaction
        cursor.execute("BEGIN TRANSACTION")
        
        try:
            # 1. Clear existing data if forced
            if force:
                print("  - 清空现有数据...")
                for table in reversed(TABLE_ORDER):
                    if table in tables_data:
                        cursor.execute(f"DELETE FROM {table}")
            
            # 2. Insert new data
            for table in TABLE_ORDER:
                if table not in tables_data:
                    continue
                
                rows = tables_data[table]
                if not rows:
                    continue
                    
                print(f"  - 正在导入表: {table} ({len(rows)} 条记录)")
                
                columns = rows[0].keys()
                placeholders = ", ".join(["?"] * len(columns))
                column_names = ", ".join(columns)
                
                sql = f"INSERT OR REPLACE INTO {table} ({column_names}) VALUES ({placeholders})"
                
                for row in rows:
                    cursor.execute(sql, list(row.values()))
            
            conn.commit()
            print("✅ 导入成功！")
            return True
            
        except Exception as e:
            conn.rollback()
            print(f"❌ 导入过程中出错 (已回滚): {e}")
            return False
        finally:
            cursor.execute("PRAGMA foreign_keys = ON")
            conn.close()
            
    except Exception as e:
        print(f"❌ 读取文件失败: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="数据库数据导出/导入工具")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--export', metavar='FILE', help='导出数据到指定 JSON 文件')
    group.add_argument('--import', dest='import_file', metavar='FILE', help='从指定 JSON 文件导入数据')
    
    parser.add_argument('--force', action='store_true', help='导入前清空现有数据 (仅用于导入模式)')
    
    args = parser.parse_args()
    
    if args.export:
        export_data(args.export)
    elif args.import_file:
        import_data(args.import_file, args.force)

if __name__ == "__main__":
    main()
