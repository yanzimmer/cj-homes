import os
import json
import sqlite3
import zipfile
import io
import shutil
from datetime import datetime
from flask import Blueprint, request, jsonify, send_file, current_app
from auth_api import token_required
from common import connect, DB_NAME, BASE_DIR

system_bp = Blueprint('system', __name__, url_prefix='/api/system')

# Define paths
CONFIG_DIR = os.path.join(BASE_DIR, 'config')
UPLOADS_DIR = os.path.join(BASE_DIR, 'static', 'uploads')
SQL_DIR = os.path.join(BASE_DIR, 'sql')

# Tables to export in order
TABLE_ORDER = [
    "rooms",
    "contract_templates",
    "admins",
    "tenants",
    "tenant_moves",
    "repair_records",
    "contracts"
]

def _dump_db_to_dict():
    """Dump entire database to a dictionary."""
    conn = connect()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    data = {}
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        tables = [row['name'] for row in cursor.fetchall()]
        
        for table in tables:
            cursor.execute(f"SELECT * FROM {table}")
            rows = [dict(row) for row in cursor.fetchall()]
            data[table] = rows
            
        return {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "version": "1.0"
            },
            "tables": data
        }
    finally:
        conn.close()

def _restore_db_from_dict(data, force=True):
    """Restore database from dictionary."""
    tables_data = data.get("tables", {})
    conn = connect()
    cursor = conn.cursor()
    
    cursor.execute("PRAGMA foreign_keys = OFF")
    cursor.execute("BEGIN TRANSACTION")
    
    try:
        # Clear existing data
        if force:
            for table in reversed(TABLE_ORDER):
                if table in tables_data:
                    try:
                        cursor.execute(f"DELETE FROM {table}")
                    except sqlite3.OperationalError:
                        pass # Table might not exist yet, which is fine
        
        # Insert new data
        for table in TABLE_ORDER:
            if table not in tables_data:
                continue
            
            rows = tables_data[table]
            if not rows:
                continue
            
            # Ensure table exists (rudimentary check, assumes schema is initialized)
            # Ideally schema should be initialized by init scripts, but we can assume it exists here
            
            columns = rows[0].keys()
            placeholders = ", ".join(["?"] * len(columns))
            column_names = ", ".join(columns)
            
            sql = f"INSERT OR REPLACE INTO {table} ({column_names}) VALUES ({placeholders})"
            
            for row in rows:
                cursor.execute(sql, list(row.values()))
        
        conn.commit()
        return True, "Database restored successfully"
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        cursor.execute("PRAGMA foreign_keys = ON")
        conn.close()

@system_bp.route('/export', methods=['GET'])
@token_required
def export_system_data(current_user):
    """
    导出系统完整数据（数据库 + 配置 + 上传文件）
    ---
    tags:
      - System
    security:
      - Bearer: []
    responses:
      200:
        description: Returns a ZIP file containing the system backup
    """
    try:
        # 1. Prepare DB Dump
        db_data = _dump_db_to_dict()
        db_json = json.dumps(db_data, ensure_ascii=False, indent=2)
        
        # 2. Create ZIP in memory
        memory_file = io.BytesIO()
        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Add DB Dump
            zf.writestr('database.json', db_json)
            
            # Add Config Files
            if os.path.exists(CONFIG_DIR):
                for root, _, files in os.walk(CONFIG_DIR):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.join('config', os.path.relpath(file_path, CONFIG_DIR))
                        zf.write(file_path, arcname)
            
            # Add Uploaded Files
            if os.path.exists(UPLOADS_DIR):
                for root, _, files in os.walk(UPLOADS_DIR):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.join('uploads', os.path.relpath(file_path, UPLOADS_DIR))
                        zf.write(file_path, arcname)
                        
        memory_file.seek(0)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return send_file(
            memory_file,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f'homes_backup_{timestamp}.zip'
        )
        
    except Exception as e:
        current_app.logger.error(f"Export failed: {e}")
        return jsonify({"error": f"导出失败: {str(e)}"}), 500

@system_bp.route('/import', methods=['POST'])
@token_required
def import_system_data(current_user):
    """
    导入系统完整数据
    ---
    tags:
      - System
    security:
      - Bearer: []
    consumes:
      - multipart/form-data
    parameters:
      - in: formData
        name: file
        type: file
        required: true
        description: Backup ZIP file
    responses:
      200:
        description: Import successful
    """
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
        
    file = request.files['file']
    if not file.filename.endswith('.zip'):
        return jsonify({'error': 'Invalid file format. Please upload a ZIP file.'}), 400

    try:
        # Save uploaded zip to temp
        temp_zip_path = os.path.join(BASE_DIR, 'temp_import.zip')
        file.save(temp_zip_path)
        
        with zipfile.ZipFile(temp_zip_path, 'r') as zf:
            # 1. Restore Database
            if 'database.json' in zf.namelist():
                with zf.open('database.json') as f:
                    db_data = json.load(f)
                    success, msg = _restore_db_from_dict(db_data)
                    if not success:
                        raise Exception(f"Database restore failed: {msg}")
            
            # 2. Restore Configs
            for member in zf.namelist():
                if member.startswith('config/'):
                    # Skip directory entries
                    if member.endswith('/'): continue
                    
                    target_path = os.path.join(CONFIG_DIR, os.path.relpath(member, 'config'))
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                    with zf.open(member) as source, open(target_path, 'wb') as target:
                        shutil.copyfileobj(source, target)
                        
            # 3. Restore Uploads
            for member in zf.namelist():
                if member.startswith('uploads/'):
                    # Skip directory entries
                    if member.endswith('/'): continue
                    
                    target_path = os.path.join(UPLOADS_DIR, os.path.relpath(member, 'uploads'))
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                    with zf.open(member) as source, open(target_path, 'wb') as target:
                        shutil.copyfileobj(source, target)
                        
        os.remove(temp_zip_path)
        return jsonify({"message": "系统数据导入成功！"}), 200
        
    except Exception as e:
        if os.path.exists(temp_zip_path):
            os.remove(temp_zip_path)
        current_app.logger.error(f"Import failed: {e}")
        return jsonify({"error": f"导入失败: {str(e)}"}), 500

try:
    from init_scripts.init_hotel_db import seed_demo_data
except ImportError:
    # 兼容在不同目录下运行时的导入路径
    import sys
    # 将 Backend-System 目录添加到 path
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    if backend_dir not in sys.path:
        sys.path.append(backend_dir)
    # 确保 init_scripts 能够被找到
    try:
        from init_scripts.init_hotel_db import seed_demo_data
    except ImportError:
         # 如果还是失败，尝试将 init-scripts (目录名带连字符) 目录直接加入 path
         # 注意：目录名实际上是 'init-scripts' 而不是 'init_scripts'
         init_scripts_dir = os.path.join(backend_dir, 'init-scripts')
         if init_scripts_dir not in sys.path:
             sys.path.append(init_scripts_dir)
         from init_hotel_db import seed_demo_data

@system_bp.route('/seed', methods=['POST'])
@token_required
def seed_system_data(current_user):
    """
    生成模拟演示数据
    ---
    tags:
      - System
    security:
      - Bearer: []
    responses:
      200:
        description: Mock data seeded successfully
    """
    try:
        # Check if DB is empty to avoid conflicts or duplicate seeding logic inside seed_demo_data
        conn = connect()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM rooms")
        count = cursor.fetchone()[0]
        conn.close()
        
        if count > 0:
             return jsonify({"message": "数据库已有数据，跳过模拟数据生成"}), 400

        seed_demo_data()
        return jsonify({"message": "模拟数据生成成功"}), 200
    except Exception as e:
        current_app.logger.error(f"Seeding failed: {e}")
        return jsonify({"error": f"生成模拟数据失败: {str(e)}"}), 500

@system_bp.route('/reset', methods=['POST'])
@token_required
def reset_system(current_user):
    """
    重置系统数据（仅保留管理员账号）
    ---
    tags:
      - System
    security:
      - Bearer: []
    responses:
      200:
        description: System reset successful
    """
    conn = connect()
    cursor = conn.cursor()
    
    cursor.execute("PRAGMA foreign_keys = OFF")
    cursor.execute("BEGIN TRANSACTION")
    
    try:
        # Tables to clear (excluding admins)
        tables_to_clear = [
            "rooms",
            "contract_templates",
            "tenants",
            "tenant_moves",
            "repair_records",
            "contracts"
        ]
        
        for table in tables_to_clear:
            try:
                cursor.execute(f"DELETE FROM {table}")
            except sqlite3.OperationalError:
                pass
        
        # Reset auto-increment counters
        for table in tables_to_clear:
            try:
                cursor.execute("DELETE FROM sqlite_sequence WHERE name=?", (table,))
            except sqlite3.OperationalError:
                pass
            
        conn.commit()
        
        # Clear uploads directory
        if os.path.exists(UPLOADS_DIR):
            for filename in os.listdir(UPLOADS_DIR):
                file_path = os.path.join(UPLOADS_DIR, filename)
                try:
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.unlink(file_path)
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                except Exception as e:
                    current_app.logger.warning(f"Failed to delete {file_path}. Reason: {e}")
                    
        return jsonify({"message": "系统已重置（管理员账号已保留）"}), 200
        
    except Exception as e:
        conn.rollback()
        current_app.logger.error(f"Reset failed: {e}")
        return jsonify({"error": f"重置失败: {str(e)}"}), 500
    finally:
        cursor.execute("PRAGMA foreign_keys = ON")
        conn.close()
