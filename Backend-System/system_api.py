import os
import json
import sqlite3
import zipfile
import io
import shutil
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from threading import Lock, Thread
from datetime import datetime
from flask import Blueprint, request, jsonify, send_file, current_app
from auth_api import token_required
from common import connect, DB_NAME, BASE_DIR
from room_feature_config import get_room_feature_options, save_room_feature_options
from ocr_settings import build_ocr_status, load_ocr_settings, save_ocr_settings
from local_ai_settings import ALLOWED_PROCUREMENT_MODELS, load_ai_settings, save_ai_settings

system_bp = Blueprint('system', __name__, url_prefix='/api/system')

# Define paths
PROJECT_ROOT = os.path.dirname(BASE_DIR)
CONFIG_DIR = os.path.join(BASE_DIR, 'config')
UPLOADS_DIR = os.path.join(BASE_DIR, 'static', 'uploads')
SQL_DIR = os.path.join(BASE_DIR, 'sql')
EXPORT_INTERVAL_SECONDS = 120
_export_lock = Lock()
_last_export_ts = 0.0
OLLAMA_BASE_URL = os.getenv('OLLAMA_BASE_URL', 'http://127.0.0.1:11434').rstrip('/')
AI_SWITCH_TIMEOUT_SECONDS = int(os.getenv('AI_SWITCH_TIMEOUT_SECONDS', '120'))
_ai_switch_lock = Lock()
_ai_switch_status = {
    'id': '',
    'status': 'idle',
    'phase': '',
    'message': '未执行切换',
    'from_model': '',
    'to_model': '',
    'started_at': '',
    'finished_at': '',
    'error': '',
}

EXCLUDED_SQLITE_TABLES = {"sqlite_sequence"}
ENV_EXPORT_DIRS = [
    PROJECT_ROOT,
    BASE_DIR,
    os.path.join(PROJECT_ROOT, 'homes-frontend'),
]
ENV_EXPORT_SKIP_DIRS = {'venv', 'node_modules', '.git', '__pycache__'}


def _set_ai_switch_status(**updates):
    with _ai_switch_lock:
        _ai_switch_status.update(updates)
        return dict(_ai_switch_status)


def _get_ai_switch_status():
    with _ai_switch_lock:
        return dict(_ai_switch_status)


def _ollama_generate(payload, timeout=AI_SWITCH_TIMEOUT_SECONDS):
    settings = load_ai_settings()
    ollama_base_url = settings.get('ollama_base_url') or OLLAMA_BASE_URL
    req = urllib.request.Request(
        f"{ollama_base_url.rstrip('/')}/api/generate",
        data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode('utf-8')
        return json.loads(body)


def _stop_ollama_model(model):
    if not model:
        return
    result = subprocess.run(
        ['ollama', 'stop', model],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if result.returncode != 0:
        message = (result.stderr or result.stdout or '').strip()
        raise RuntimeError(message or f'停止模型 {model} 失败')


def _warm_ollama_model(model):
    _ollama_generate({
        'model': model,
        'prompt': 'ping',
        'stream': False,
        'think': False,
        'keep_alive': '30m',
        'options': {'num_predict': 1, 'temperature': 0},
    })


def _run_ai_model_switch(task_id, old_model, new_model):
    started_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    _set_ai_switch_status(
        id=task_id,
        status='running',
        phase='stopping_old',
        message=f'正在停止旧模型 {old_model}' if old_model and old_model != new_model else '无需停止旧模型',
        from_model=old_model,
        to_model=new_model,
        started_at=started_at,
        finished_at='',
        error='',
    )
    try:
        if old_model and old_model != new_model:
            _stop_ollama_model(old_model)

        _set_ai_switch_status(
            status='running',
            phase='starting_new',
            message=f'正在启动新模型 {new_model}',
        )
        _warm_ollama_model(new_model)

        saved = save_ai_settings({'enabled': True, 'procurement_model': new_model})
        _set_ai_switch_status(
            status='completed',
            phase='completed',
            message=f'已切换到 {new_model}',
            finished_at=saved.get('updated_at') or datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            error='',
        )
    except Exception as e:
        _set_ai_switch_status(
            status='failed',
            phase='failed',
            message='模型切换失败',
            finished_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            error=str(e),
        )


def _run_ai_disable(task_id, current_model):
    started_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    _set_ai_switch_status(
        id=task_id,
        status='running',
        phase='stopping_old',
        message=f'正在停止模型 {current_model}' if current_model else '正在停用本地 AI 功能',
        from_model=current_model,
        to_model='',
        started_at=started_at,
        finished_at='',
        error='',
    )
    try:
        if current_model:
            _stop_ollama_model(current_model)
        saved = save_ai_settings({'enabled': False})
        _set_ai_switch_status(
            status='completed',
            phase='disabled',
            message='本地 AI 功能已停用',
            finished_at=saved.get('updated_at') or datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            error='',
        )
    except Exception as e:
        _set_ai_switch_status(
            status='failed',
            phase='failed',
            message='停用本地 AI 功能失败',
            finished_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            error=str(e),
        )


def _run_ai_enable(task_id, current_model):
    started_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    _set_ai_switch_status(
        id=task_id,
        status='running',
        phase='starting_new',
        message=f'正在启动模型 {current_model}',
        from_model=current_model,
        to_model=current_model,
        started_at=started_at,
        finished_at='',
        error='',
    )
    try:
        _warm_ollama_model(current_model)
        saved = save_ai_settings({'enabled': True})
        _set_ai_switch_status(
            status='completed',
            phase='enabled',
            message='本地 AI 功能已启用',
            finished_at=saved.get('updated_at') or datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            error='',
        )
    except Exception as e:
        _set_ai_switch_status(
            status='failed',
            phase='failed',
            message='启用本地 AI 功能失败',
            finished_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            error=str(e),
        )


@system_bp.route('/room-feature-options', methods=['GET'])
@token_required
def get_room_feature_options_api(current_user):
    return jsonify({'options': get_room_feature_options()})


@system_bp.route('/room-feature-options', methods=['PUT'])
@token_required
def update_room_feature_options_api(current_user):
    data = request.json or {}
    options = data.get('options')
    if not isinstance(options, list):
        return jsonify({'error': 'options 必须是数组'}), 400
    saved = save_room_feature_options(options)
    return jsonify({'options': saved})


@system_bp.route('/ocr-settings', methods=['GET'])
@token_required
def get_ocr_settings_api(current_user):
    settings = load_ocr_settings()
    status = build_ocr_status()
    payload = dict(settings)
    payload.update(status)
    return jsonify(payload)


@system_bp.route('/ocr-settings', methods=['PUT'])
@token_required
def update_ocr_settings_api(current_user):
    data = request.json or {}
    saved = save_ocr_settings(data)
    status = build_ocr_status()
    payload = dict(saved)
    payload.update(status)
    return jsonify(payload)


@system_bp.route('/ai-settings', methods=['GET'])
@token_required
def get_ai_settings_api(current_user):
    settings = load_ai_settings()
    return jsonify({
        'enabled': settings.get('enabled', True),
        'procurement_model': settings.get('procurement_model'),
        'ollama_base_url': settings.get('ollama_base_url'),
        'available_procurement_models': ALLOWED_PROCUREMENT_MODELS,
        'updated_at': settings.get('updated_at', ''),
        'switch_status': _get_ai_switch_status(),
    })


@system_bp.route('/ai-settings', methods=['PUT'])
@token_required
def update_ai_settings_api(current_user):
    data = request.json or {}
    action = str(data.get('action') or 'switch_model').strip()
    model = str(data.get('procurement_model') or '').strip()
    requested_ollama_base_url = data.get('ollama_base_url')
    if model not in ALLOWED_PROCUREMENT_MODELS:
        return jsonify({'error': '不支持的采购 AI 模型'}), 400
    current = load_ai_settings()
    if requested_ollama_base_url is not None:
        current = save_ai_settings({'ollama_base_url': requested_ollama_base_url})
    old_model = current.get('procurement_model') or ''
    current_status = _get_ai_switch_status()
    if current_status.get('status') == 'running':
        return jsonify({'error': '模型正在切换中，请稍后再试'}), 409

    task_id = str(uuid.uuid4())
    if action == 'disable':
        _set_ai_switch_status(
            id=task_id,
            status='running',
            phase='stopping_old',
            message='本地 AI 功能停用任务已开始',
            from_model=old_model,
            to_model='',
            started_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            finished_at='',
            error='',
        )
        Thread(target=_run_ai_disable, args=(task_id, old_model), daemon=True).start()
        return jsonify({
            'enabled': current.get('enabled', True),
            'procurement_model': old_model,
            'ollama_base_url': current.get('ollama_base_url'),
            'available_procurement_models': ALLOWED_PROCUREMENT_MODELS,
            'updated_at': current.get('updated_at', ''),
            'switch_status': _get_ai_switch_status(),
        })

    if action == 'enable':
        _set_ai_switch_status(
            id=task_id,
            status='running',
            phase='starting_new',
            message='本地 AI 功能启用任务已开始',
            from_model=old_model,
            to_model=old_model,
            started_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            finished_at='',
            error='',
        )
        Thread(target=_run_ai_enable, args=(task_id, old_model), daemon=True).start()
        return jsonify({
            'enabled': current.get('enabled', True),
            'procurement_model': old_model,
            'ollama_base_url': current.get('ollama_base_url'),
            'available_procurement_models': ALLOWED_PROCUREMENT_MODELS,
            'updated_at': current.get('updated_at', ''),
            'switch_status': _get_ai_switch_status(),
        })

    if action != 'switch_model':
        return jsonify({'error': '不支持的 AI 操作'}), 400

    _set_ai_switch_status(
        id=task_id,
        status='running',
        phase='queued',
        message='模型切换任务已开始',
        from_model=old_model,
        to_model=model,
        started_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        finished_at='',
        error='',
    )
    Thread(target=_run_ai_model_switch, args=(task_id, old_model, model), daemon=True).start()
    return jsonify({
        'enabled': current.get('enabled', True),
        'procurement_model': old_model,
        'ollama_base_url': current.get('ollama_base_url'),
        'available_procurement_models': ALLOWED_PROCUREMENT_MODELS,
        'updated_at': current.get('updated_at', ''),
        'switch_status': _get_ai_switch_status(),
    })


@system_bp.route('/ai-settings/switch-status', methods=['GET'])
@token_required
def get_ai_switch_status_api(current_user):
    settings = load_ai_settings()
    return jsonify({
        'enabled': settings.get('enabled', True),
        'procurement_model': settings.get('procurement_model'),
        'ollama_base_url': settings.get('ollama_base_url'),
        'available_procurement_models': ALLOWED_PROCUREMENT_MODELS,
        'updated_at': settings.get('updated_at', ''),
        'switch_status': _get_ai_switch_status(),
    })

def _resolve_upload_url_to_path(file_url):
    raw = str(file_url or '').strip()
    if raw == '':
        raise ValueError('缺少 file_url')

    normalized = raw.split('?', 1)[0].replace('\\', '/')
    if normalized.startswith('http://') or normalized.startswith('https://'):
        raise ValueError('file_url 必须是 /static/uploads/ 下的本地路径')
    if not normalized.startswith('/static/uploads/'):
        raise ValueError('file_url 必须以 /static/uploads/ 开头')

    local_rel = normalized.lstrip('/').replace('/', os.sep)
    abs_path = os.path.normpath(os.path.join(BASE_DIR, local_rel))
    upload_root = os.path.normpath(UPLOADS_DIR)

    if abs_path != upload_root and not abs_path.startswith(upload_root + os.sep):
        raise ValueError('file_url 路径不合法')
    if not os.path.isfile(abs_path):
        raise FileNotFoundError('上传文件不存在')
    if not abs_path.lower().endswith('.zip'):
        raise ValueError('文件格式错误，请上传 ZIP 备份文件')
    return abs_path

def _ensure_rooms_meter_columns(conn):
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(rooms)")
    existing_columns = {row[1] for row in cursor.fetchall()}

    if "water_meter_img" not in existing_columns:
        cursor.execute("ALTER TABLE rooms ADD COLUMN water_meter_img TEXT")
    if "electricity_meter_img" not in existing_columns:
        cursor.execute("ALTER TABLE rooms ADD COLUMN electricity_meter_img TEXT")


def _is_exportable_env_file(filename):
    name = str(filename or '')
    if not name.startswith('.env'):
        return False
    lower = name.lower()
    if lower.endswith('.example') or lower.endswith('.sample'):
        return False
    return True


def _collect_env_files():
    files = []
    seen = set()
    for root_dir in ENV_EXPORT_DIRS:
        if not os.path.isdir(root_dir):
            continue
        for current_root, dirnames, filenames in os.walk(root_dir):
            rel_depth = os.path.relpath(current_root, root_dir).count(os.sep)
            dirnames[:] = [d for d in dirnames if d not in ENV_EXPORT_SKIP_DIRS]
            if rel_depth > 1:
                dirnames[:] = []
            for filename in filenames:
                if not _is_exportable_env_file(filename):
                    continue
                abs_path = os.path.join(current_root, filename)
                rel_path = os.path.relpath(abs_path, PROJECT_ROOT)
                if rel_path in seen:
                    continue
                seen.add(rel_path)
                files.append((abs_path, rel_path))
    files.sort(key=lambda item: item[1])
    return files

def _dump_db_to_dict():
    """Dump entire database to a dictionary."""
    conn = connect()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    data = {}
    schemas = {}
    table_order = []
    try:
        cursor.execute(
            """
            SELECT name, sql
            FROM sqlite_master
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        )
        table_defs = cursor.fetchall()
        tables = [row['name'] for row in table_defs]
        
        for row in table_defs:
            table = row['name']
            table_order.append(table)
            schemas[table] = row['sql']
            cursor.execute(f"SELECT * FROM {table}")
            rows = [dict(row) for row in cursor.fetchall()]
            data[table] = rows
            
        return {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "version": "1.0"
            },
            "schemas": schemas,
            "table_order": table_order,
            "tables": data
        }
    finally:
        conn.close()

def _restore_db_from_dict(data, force=True):
    """Restore database from dictionary."""
    tables_data = data.get("tables", {}) if isinstance(data, dict) else {}
    schemas = data.get("schemas", {}) if isinstance(data, dict) else {}
    table_order = data.get("table_order", []) if isinstance(data, dict) else []
    if not isinstance(tables_data, dict):
        return False, "备份文件中的 tables 数据格式不正确"
    conn = connect()
    cursor = conn.cursor()
    
    cursor.execute("PRAGMA foreign_keys = OFF")
    cursor.execute("BEGIN TRANSACTION")
    
    try:
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        existing_tables = [row[0] for row in cursor.fetchall() if row[0] not in EXCLUDED_SQLITE_TABLES]
        tables_to_restore = list(table_order) if table_order else list(tables_data.keys())

        for table in tables_to_restore:
            if table in EXCLUDED_SQLITE_TABLES:
                continue
            if table not in existing_tables:
                create_sql = schemas.get(table)
                if create_sql:
                    cursor.execute(create_sql)
                    existing_tables.append(table)

        if force:
            for table in existing_tables:
                try:
                    cursor.execute(f'DELETE FROM "{table}"')
                except sqlite3.OperationalError:
                    pass
            try:
                cursor.execute("DELETE FROM sqlite_sequence")
            except sqlite3.OperationalError:
                pass
        
        for table in tables_to_restore:
            if table not in tables_data:
                continue
            if table in EXCLUDED_SQLITE_TABLES:
                continue
            rows = tables_data[table]
            if not isinstance(rows, list):
                continue
            if not rows:
                continue
            if table not in existing_tables:
                return False, f"导入失败，缺少表：{table}"

            columns = list(rows[0].keys())
            placeholders = ", ".join(["?"] * len(columns))
            column_names = ", ".join([f'"{col}"' for col in columns])
            sql = f'INSERT OR REPLACE INTO "{table}" ({column_names}) VALUES ({placeholders})'

            for row in rows:
                cursor.execute(sql, [row.get(col) for col in columns])
        
        conn.commit()
        return True, "数据库恢复成功"
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
        return jsonify({"error": f"导出过于频繁，请 {wait_seconds} 秒后再试"}), 429
    if not _export_lock.acquire(blocking=False):
        return jsonify({"error": "系统正在执行导出，请稍后再试"}), 429
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

            env_files = _collect_env_files()
            if env_files:
                zf.writestr(
                    'env_files_manifest.json',
                    json.dumps([rel_path for _, rel_path in env_files], ensure_ascii=False, indent=2),
                )
                for file_path, rel_path in env_files:
                    zf.write(file_path, os.path.join('env_files', rel_path))
                        
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
        return jsonify({"error": f"导出系统数据失败: {str(e)}"}), 500
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
                return jsonify({'error': '文件格式错误，请上传 ZIP 备份文件'}), 400
            file.save(temp_zip_path)
        else:
            data = request.get_json(silent=True) or {}
            file_url = data.get('file_url')
            if not file_url:
                return jsonify({'error': '未找到备份文件'}), 400
            source_zip_path = _resolve_upload_url_to_path(file_url)
            shutil.copyfile(source_zip_path, temp_zip_path)

        with zipfile.ZipFile(temp_zip_path, 'r') as zf:
            # 1. Restore Database
            if 'database.json' in zf.namelist():
                with zf.open('database.json') as f:
                    db_data = json.load(f)
                    success, msg = _restore_db_from_dict(db_data)
                    if not success:
                        raise Exception(f"数据库恢复失败: {msg}")

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

            for member in zf.namelist():
                if member.startswith('env_files/'):
                    if member.endswith('/'):
                        continue
                    relative_path = os.path.relpath(member, 'env_files')
                    target_path = os.path.normpath(os.path.join(PROJECT_ROOT, relative_path))
                    if not target_path.startswith(PROJECT_ROOT):
                        raise ValueError('环境配置文件路径不合法')
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                    with zf.open(member) as source, open(target_path, 'wb') as target:
                        shutil.copyfileobj(source, target)

        return jsonify({"message": "系统数据导入成功"}), 200


    except FileNotFoundError as e:
        return jsonify({'error': str(e)}), 404
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Import failed: {e}")
        return jsonify({"error": f"导入系统数据失败: {str(e)}"}), 500
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
             return jsonify({"message": "系统已有数据，请先重置后再生成演示数据"}), 400

        seed_demo_data()
        return jsonify({"message": "演示数据生成成功"}), 200
    except Exception as e:
        current_app.logger.error(f"Seeding failed: {e}")
        return jsonify({"error": f"生成演示数据失败: {str(e)}"}), 500

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
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        tables_to_clear = [
            row[0]
            for row in cursor.fetchall()
            if row[0] not in EXCLUDED_SQLITE_TABLES and row[0] != "admins"
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
                    
        return jsonify({"message": "系统已重置，所有业务数据已清空"}), 200

    except Exception as e:
        conn.rollback()
        current_app.logger.error(f"Reset failed: {e}")
        return jsonify({"error": f"重置系统失败: {str(e)}"}), 500
    finally:
        cursor.execute("PRAGMA foreign_keys = ON")
        conn.close()
