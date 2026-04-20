import os
import json
import sqlite3
import zipfile
import io
import shutil
import time
from threading import Lock
from datetime import datetime
from flask import Blueprint, request, jsonify, send_file, current_app
from auth_api import token_required
from common import connect, DB_NAME, BASE_DIR

system_bp = Blueprint('system', __name__, url_prefix='/api/system')

# Define paths
CONFIG_DIR = os.path.join(BASE_DIR, 'config')
UPLOADS_DIR = os.path.join(BASE_DIR, 'static', 'uploads')
SQL_DIR = os.path.join(BASE_DIR, 'sql')
EXPORT_INTERVAL_SECONDS = 120
_export_lock = Lock()
_last_export_ts = 0.0

# Tables to export in order
TABLE_ORDER = [
    "rooms",
    "contract_templates",
    "admins",
    "tenants",
    "tenant_moves",
    "repair_records",
    "contracts",
    "procurements",
    "warehouse_items",
]

def _resolve_upload_url_to_path(file_url):
    raw = str(file_url or '').strip()
    if raw == '':
        raise ValueError('file_url is required')

    normalized = raw.split('?', 1)[0].replace('\\', '/')
    if normalized.startswith('http://') or normalized.startswith('https://'):
        raise ValueError('file_url must be a local path under /static/uploads/')
    if not normalized.startswith('/static/uploads/'):
        raise ValueError('file_url must start with /static/uploads/')

    local_rel = normalized.lstrip('/').replace('/', os.sep)
    abs_path = os.path.normpath(os.path.join(BASE_DIR, local_rel))
    upload_root = os.path.normpath(UPLOADS_DIR)

    if abs_path != upload_root and not abs_path.startswith(upload_root + os.sep):
        raise ValueError('invalid file_url path')
    if not os.path.isfile(abs_path):
        raise FileNotFoundError('uploaded file not found')
    if not abs_path.lower().endswith('.zip'):
        raise ValueError('invalid file format. Please upload a ZIP file.')
    return abs_path

def _ensure_rooms_meter_columns(conn):
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(rooms)")
    existing_columns = {row[1] for row in cursor.fetchall()}

    if "water_meter_img" not in existing_columns:
        cursor.execute("ALTER TABLE rooms ADD COLUMN water_meter_img TEXT")
    if "electricity_meter_img" not in existing_columns:
        cursor.execute("ALTER TABLE rooms ADD COLUMN electricity_meter_img TEXT")

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
    闂佽娴烽弫鎼佸储瑜斿畷鐢割敇閻樻彃顕ч梺鐓庮潟閸婃宕洪悩缁樺€甸柣鐔哄濠€浼存煛閸☆厾绉€殿噮鍋婇幃褔宕煎┑鍫涘亰闂備焦瀵х粙鎴︽偋婵犲洤姹查柣鏃傚帶缁犲弶銇勯弮鍥т汗婵?+ 闂傚倷鐒﹀妯肩矓閸洘鍋?+ 濠电偞鍨堕幐鎼佹晝閿濆洦顫曢柛顐ｆ礀濡﹢鏌涢妷顖炴妞ゆ劒绮欓弻?    ---
    tags:
      - System
    security:
      - Bearer: []
    responses:
      200:
        description: Returns a ZIP file containing the system backup
    """
    global _last_export_ts
    now = time.time()
    if now - _last_export_ts < EXPORT_INTERVAL_SECONDS:
        wait_seconds = int(EXPORT_INTERVAL_SECONDS - (now - _last_export_ts))
        return jsonify({"error": f"????????? {wait_seconds} ????"}), 429
    if not _export_lock.acquire(blocking=False):
        return jsonify({"error": "????????????????"}), 429
    _last_export_ts = now
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
        return jsonify({"error": f"闂佽娴烽弫鎼佸储瑜斿畷鐢割敇閻旈绐為柡澶婄墱閸嬪顤? {str(e)}"}), 500
    finally:
        _export_lock.release()

@system_bp.route('/import', methods=['POST'])
@token_required
def import_system_data(current_user):
    """
    闁诲海鏁搁崢褔宕ｉ崱娆忓闁煎鍊楅崺鐘绘倵閻熺増婀伴柡鍡秮瀵偊鎮ч崼婵堛偊
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
        required: false
        description: Backup ZIP file
      - in: body
        name: body
        schema:
          type: object
          properties:
            file_url:
              type: string
              description: Path returned by chunk upload complete API
    responses:
      200:
        description: Import successful
    """
    temp_zip_path = os.path.join(BASE_DIR, f"temp_import_{int(time.time() * 1000)}.zip")

    try:
        if 'file' in request.files:
            file = request.files['file']
            if not file.filename.lower().endswith('.zip'):
                return jsonify({'error': 'Invalid file format. Please upload a ZIP file.'}), 400
            file.save(temp_zip_path)
        else:
            data = request.get_json(silent=True) or {}
            file_url = data.get('file_url')
            if not file_url:
                return jsonify({'error': 'No file uploaded'}), 400
            source_zip_path = _resolve_upload_url_to_path(file_url)
            shutil.copyfile(source_zip_path, temp_zip_path)

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
                    if member.endswith('/'):
                        continue

                    target_path = os.path.join(CONFIG_DIR, os.path.relpath(member, 'config'))
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                    with zf.open(member) as source, open(target_path, 'wb') as target:
                        shutil.copyfileobj(source, target)

            # 3. Restore Uploads
            for member in zf.namelist():
                if member.startswith('uploads/'):
                    # Skip directory entries
                    if member.endswith('/'):
                        continue

                    target_path = os.path.join(UPLOADS_DIR, os.path.relpath(member, 'uploads'))
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                    with zf.open(member) as source, open(target_path, 'wb') as target:
                        shutil.copyfileobj(source, target)

        return jsonify({"message": "????????"}), 200


    except FileNotFoundError as e:
        return jsonify({'error': str(e)}), 404
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Import failed: {e}")
        return jsonify({"error": f"闁诲海鏁搁崢褔宕ｉ崱妯虹窞閺夊牜鍋夎: {str(e)}"}), 500
    finally:
        if os.path.exists(temp_zip_path):
            os.remove(temp_zip_path)
try:
    from init_scripts.init_hotel_db import seed_demo_data
except ImportError:
    import sys
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    if backend_dir not in sys.path:
        sys.path.append(backend_dir)
    try:
        from init_scripts.init_hotel_db import seed_demo_data
    except ImportError:
        init_scripts_dir = os.path.join(backend_dir, 'init-scripts')
        if init_scripts_dir not in sys.path:
            sys.path.append(init_scripts_dir)
        from init_hotel_db import seed_demo_data

@system_bp.route('/seed', methods=['POST'])
@token_required
def seed_system_data(current_user):
    """
    闂備焦鐪归崹濠氬窗閹版澘鍨傛慨姗嗗劦閻旂厧鐒洪柛鎰╁妿瑜版彃鈹戦悩铏婵﹤顭锋俊闈涱潩鐠虹儤鐎梺缁橆殔閻楀棛绮?
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
        conn = connect()
        cursor = conn.cursor()
        _ensure_rooms_meter_columns(conn)
        # Check if DB is empty to avoid conflicts or duplicate seeding logic inside seed_demo_data
        cursor.execute("SELECT COUNT(*) FROM rooms")
        count = cursor.fetchone()[0]
        conn.close()
        
        if count > 0:
             return jsonify({"message": "????????????????"}), 400

        seed_demo_data()
        return jsonify({"message": "????????"}), 200
    except Exception as e:
        current_app.logger.error(f"Seeding failed: {e}")
        return jsonify({"error": f"????????: {str(e)}"}), 500

@system_bp.route('/reset', methods=['POST'])
@token_required
def reset_system(current_user):
    """
    闂傚倷鐒﹁ぐ鍐矓閸洘鍋柛鈩冪懃鐎垫煡鏌ゆ慨鎰偓妤呭春閻樼粯鐓涘ù锝呮惈椤ｈ偐鈧鎸风欢姘跺极瀹ュ閱囨繝濠傛噽閻撳倹绻涢敐鍛缂佽瀚板鎶藉焵椤掑倻纾奸柣娆忔噽绾惧潡鏌熼纭疯含鐎规洏鍔岃灒闁割煈鍣Σ閬嶆⒑閸涘﹦鎳冮柛銈嗙墱濡?    ---
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
        _ensure_rooms_meter_columns(conn)
        # Tables to clear (excluding admins)
        tables_to_clear = [
            "rooms",
            "contract_templates",
            "tenants",
            "tenant_moves",
            "repair_records",
            "contracts",
            "procurements",
            "warehouse_items",
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
                    
        return jsonify({"message": "???????????????"}), 200
        
    except Exception as e:
        conn.rollback()
        current_app.logger.error(f"Reset failed: {e}")
        return jsonify({"error": f"闂傚倷鐒﹁ぐ鍐矓閸洘鍋柛鈩兠欢鐐哄级閸偄浜悮? {str(e)}"}), 500
    finally:
        cursor.execute("PRAGMA foreign_keys = ON")
        conn.close()


