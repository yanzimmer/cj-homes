import os
import json
import sqlite3
import zipfile
import io
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.request
import uuid
import tempfile
from urllib.parse import urlparse
from threading import Lock, Thread
from datetime import datetime
from flask import Blueprint, request, jsonify, send_file, current_app
from auth_api import token_required
from common import connect, DB_NAME, BASE_DIR
from room_feature_config import get_room_feature_options, save_room_feature_options
from utility_account_config import get_utility_account_options, save_utility_account_options
from ocr_settings import build_ocr_status, load_ocr_settings, save_ocr_settings
from local_ai_settings import ALLOWED_PROCUREMENT_MODELS, load_ai_settings, save_ai_settings
from payment_settings import serialize_payment_settings, save_payment_settings

system_bp = Blueprint('system', __name__, url_prefix='/api/system')

# Define paths
PROJECT_ROOT = os.path.dirname(BASE_DIR)
CONFIG_DIR = os.path.join(BASE_DIR, 'config')
UPLOADS_DIR = os.path.join(BASE_DIR, 'static', 'uploads')
SQL_DIR = os.path.join(BASE_DIR, 'sql')
SNAPSHOTS_DIR = os.path.join(BASE_DIR, 'snapshots', 'system')
LEGACY_ROLLBACK_DIR = os.path.join(BASE_DIR, 'tmp', 'system_import_rollback')
LEGACY_ROLLBACK_ZIP_PATH = os.path.join(LEGACY_ROLLBACK_DIR, 'last_import_rollback.zip')
LEGACY_ROLLBACK_META_PATH = os.path.join(LEGACY_ROLLBACK_DIR, 'last_import_rollback.json')
EXPORT_INTERVAL_SECONDS = 120
_export_lock = Lock()
_restore_lock = Lock()
_last_export_ts = 0.0
OLLAMA_BASE_URL = os.getenv('OLLAMA_BASE_URL', 'http://127.0.0.1:11434').rstrip('/')
AI_SWITCH_TIMEOUT_SECONDS = int(os.getenv('AI_SWITCH_TIMEOUT_SECONDS', '120'))
_ai_switch_lock = Lock()
_snapshot_task_lock = Lock()
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
_snapshot_task_status = {
    'id': '',
    'action': '',
    'status': 'idle',
    'phase': '',
    'message': '未执行快照任务',
    'progress': 0,
    'snapshot_id': '',
    'snapshot_name': '',
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


def _set_snapshot_task_status(**updates):
    with _snapshot_task_lock:
        _snapshot_task_status.update(updates)
        return dict(_snapshot_task_status)


def _get_snapshot_task_status():
    with _snapshot_task_lock:
        return dict(_snapshot_task_status)


def _is_local_ollama_url(value):
    raw = str(value or '').strip()
    if not raw:
        return True
    parsed = urlparse(raw if '://' in raw else f'http://{raw}')
    host = (parsed.hostname or '').strip().lower()
    if host in ('', 'localhost', '127.0.0.1', '::1'):
        return True
    try:
        local_hosts = {socket.gethostname().lower()}
        local_hosts.add(socket.getfqdn().lower())
        local_ips = {'127.0.0.1', '::1'}
        for info in socket.getaddrinfo(socket.gethostname(), None):
            local_ips.add(info[4][0])
        return host in local_hosts or host in local_ips
    except Exception:
        return False


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


def _get_available_ollama_models(settings=None):
    current = settings or load_ai_settings()
    ollama_base_url = _normalize_url_for_test(current.get('ollama_base_url'), 'http') or OLLAMA_BASE_URL
    req = urllib.request.Request(f"{ollama_base_url}/api/tags", method='GET')
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode('utf-8'))
    models = data.get('models') or []
    result = []
    for item in models:
        if not isinstance(item, dict):
            continue
        name = str(item.get('name') or item.get('model') or '').strip()
        if name:
            result.append(name)
    return result


def _serialize_ai_settings(settings=None):
    current = settings or load_ai_settings()
    available_models = list(ALLOWED_PROCUREMENT_MODELS)
    if str(current.get('provider') or 'ollama').strip().lower() != 'api':
        try:
            installed_models = _get_available_ollama_models(current)
            if installed_models:
                available_models = installed_models
        except Exception:
            pass
    return {
        'enabled': current.get('enabled', True),
        'provider': current.get('provider', 'ollama'),
        'procurement_model': current.get('procurement_model'),
        'ollama_base_url': current.get('ollama_base_url'),
        'base_url': current.get('base_url', ''),
        'chat_completions_url': current.get('chat_completions_url', ''),
        'responses_url': current.get('responses_url', ''),
        'model': current.get('model', ''),
        'api_key': current.get('api_key', ''),
        'available_procurement_models': available_models,
        'updated_at': current.get('updated_at', ''),
        'switch_status': _get_ai_switch_status(),
    }


def _validate_api_ai_settings(settings):
    if not str(settings.get('model') or '').strip():
        return '请填写 API 模型名'
    if not str(settings.get('api_key') or '').strip():
        return '请填写 API Key'
    if not (str(settings.get('chat_completions_url') or '').strip() or str(settings.get('base_url') or '').strip()):
        return '请填写 API 地址'
    return ''


def _normalize_url_for_test(value, default_scheme):
    text = str(value or '').strip().rstrip('/')
    if not text:
        return ''
    if text.startswith(('http://', 'https://')):
        return text
    return f'{default_scheme}://{text}'


def _resolve_ai_test_chat_url(settings):
    direct = _normalize_url_for_test(settings.get('chat_completions_url'), 'https')
    if direct:
        return direct
    base_url = _normalize_url_for_test(settings.get('base_url'), 'https')
    if not base_url:
        return ''
    return f'{base_url}/chat/completions'


def _resolve_ai_models_url(settings):
    base_url = _normalize_url_for_test(settings.get('base_url'), 'https')
    if base_url:
        return f'{base_url}/models'

    direct = _normalize_url_for_test(settings.get('chat_completions_url'), 'https')
    if direct and '/chat/completions' in direct:
        return direct.rsplit('/chat/completions', 1)[0] + '/models'
    return ''


def _test_ollama_settings(settings):
    ollama_base_url = _normalize_url_for_test(settings.get('ollama_base_url'), 'http') or OLLAMA_BASE_URL
    selected_model = str(settings.get('procurement_model') or '').strip()
    req = urllib.request.Request(f"{ollama_base_url}/api/tags", method='GET')
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode('utf-8'))
    models = data.get('models') or []
    available_models = [str(item.get('name') or item.get('model') or '').strip() for item in models if isinstance(item, dict)]
    available_models = [name for name in available_models if name]
    if selected_model and selected_model not in available_models:
        return {
            'ok': False,
            'provider': 'ollama',
            'model': selected_model,
            'base_url': ollama_base_url,
            'message': f'Ollama 服务已连接，但未找到模型 {selected_model}',
            'available_models': available_models,
        }
    return {
        'ok': True,
        'provider': 'ollama',
        'model': selected_model,
        'base_url': ollama_base_url,
        'message': f'Ollama 连接正常，已找到模型 {selected_model or "未指定"}',
        'available_models': available_models,
    }


def _test_api_settings(settings):
    error_message = _validate_api_ai_settings(settings)
    if error_message:
        return {
            'ok': False,
            'provider': 'api',
            'model': str(settings.get('model') or '').strip(),
            'base_url': _normalize_url_for_test(settings.get('base_url'), 'https'),
            'message': error_message,
        }

    url = _resolve_ai_test_chat_url(settings)
    model = str(settings.get('model') or '').strip()
    api_key = str(settings.get('api_key') or '').strip()
    payload = {
        'model': model,
        'messages': [{'role': 'user', 'content': 'ping'}],
        'temperature': 0,
        'max_tokens': 8,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}',
        },
        method='POST',
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        raw = json.loads(resp.read().decode('utf-8'))
    choices = raw.get('choices') or []
    preview_text = ''
    if isinstance(choices, list) and choices:
        preview_text = str((choices[0].get('message') or {}).get('content') or '').strip()
    return {
        'ok': True,
        'provider': 'api',
        'model': model,
        'base_url': _normalize_url_for_test(settings.get('base_url'), 'https'),
        'message': f'API 连接正常，模型 {model} 可用',
        'preview': preview_text[:120],
    }


def _list_api_models(settings):
    error_message = _validate_api_ai_settings(settings)
    if error_message and error_message != '请填写 API 模型名':
        raise RuntimeError(error_message)

    url = _resolve_ai_models_url(settings)
    api_key = str(settings.get('api_key') or '').strip()
    if not url:
        raise RuntimeError('请先填写 API 地址')
    if not api_key:
        raise RuntimeError('请先填写 API Key')

    req = urllib.request.Request(
        url,
        headers={
            'Accept': 'application/json',
            'Authorization': f'Bearer {api_key}',
        },
        method='GET',
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        payload = json.loads(resp.read().decode('utf-8'))

    data = payload.get('data') or []
    models = []
    for item in data:
        if not isinstance(item, dict):
            continue
        model_id = str(item.get('id') or '').strip()
        if not model_id:
            continue
        models.append({
            'id': model_id,
            'owned_by': str(item.get('owned_by') or '').strip(),
            'object': str(item.get('object') or '').strip(),
        })
    return models


def _build_ai_test_settings(data):
    current = load_ai_settings()
    preview = dict(current)
    if not isinstance(data, dict):
        return preview
    if 'provider' in data:
        provider_text = str(data.get('provider') or '').strip().lower()
        preview['provider'] = 'api' if provider_text in {'api', 'openai', 'compatible'} else 'ollama'
    if 'procurement_model' in data:
        preview['procurement_model'] = str(data.get('procurement_model') or '').strip()
    if 'ollama_base_url' in data:
        preview['ollama_base_url'] = data.get('ollama_base_url')
    if 'base_url' in data:
        preview['base_url'] = data.get('base_url')
    if 'chat_completions_url' in data:
        preview['chat_completions_url'] = data.get('chat_completions_url')
    if 'responses_url' in data:
        preview['responses_url'] = data.get('responses_url')
    if 'model' in data:
        preview['model'] = str(data.get('model') or '').strip()
    if 'api_key' in data:
        preview['api_key'] = str(data.get('api_key') or '').strip()
    return preview


def _run_ai_model_switch(task_id, old_model, new_model):
    settings = load_ai_settings()
    is_local_ollama = _is_local_ollama_url(settings.get('ollama_base_url'))
    started_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    _set_ai_switch_status(
        id=task_id,
        status='running',
        phase='stopping_old',
        message=(
            f'正在停止旧模型 {old_model}'
            if is_local_ollama and old_model and old_model != new_model
            else '远程 Ollama 无法关闭旧模型，只切换调用模型'
            if not is_local_ollama and old_model and old_model != new_model
            else '无需停止旧模型'
        ),
        from_model=old_model,
        to_model=new_model,
        started_at=started_at,
        finished_at='',
        error='',
    )
    try:
        if is_local_ollama and old_model and old_model != new_model:
            _stop_ollama_model(old_model)

        _set_ai_switch_status(
            status='running',
            phase='starting_new',
            message=f'正在调用并加载模型 {new_model}',
        )
        _warm_ollama_model(new_model)
        saved = save_ai_settings({'enabled': True, 'procurement_model': new_model})
        _set_ai_switch_status(
            status='completed',
            phase='completed',
            message=(
                f'已切换文本模型到 {new_model}'
                if is_local_ollama
                else f'已切换文本模型到 {new_model}；远程 Ollama 无法从本系统关闭旧模型'
            ),
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
    settings = load_ai_settings()
    is_local_ollama = _is_local_ollama_url(settings.get('ollama_base_url'))
    started_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    _set_ai_switch_status(
        id=task_id,
        status='running',
        phase='stopping_old',
        message=(
            f'正在停止模型 {current_model}'
            if is_local_ollama and current_model
            else '远程 Ollama 无法关闭模型，将只停用系统 AI 功能'
            if not is_local_ollama
            else '正在停用本地 AI 功能'
        ),
        from_model=current_model,
        to_model='',
        started_at=started_at,
        finished_at='',
        error='',
    )
    try:
        stop_warning = ''
        if is_local_ollama and current_model:
            try:
                _stop_ollama_model(current_model)
            except FileNotFoundError:
                stop_warning = '未检测到 ollama 命令，已跳过停止本地模型'
            except Exception as stop_error:
                stop_warning = f'停止本地模型时已跳过：{stop_error}'
        saved = save_ai_settings({'enabled': False})
        completed_message = (
            '本地 AI 功能已停用'
            if is_local_ollama
            else 'AI 功能已停用；远程 Ollama 模型无法从本系统关闭'
        )
        if stop_warning:
            completed_message = f'{completed_message}；{stop_warning}'
        _set_ai_switch_status(
            status='completed',
            phase='disabled',
            message=completed_message,
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
        if current_model:
            _warm_ollama_model(current_model)
        saved = save_ai_settings({'enabled': True, 'procurement_model': current_model})
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


@system_bp.route('/utility-account-options', methods=['GET'])
@token_required
def get_utility_account_options_api(current_user):
    return jsonify(get_utility_account_options())


@system_bp.route('/utility-account-options', methods=['PUT'])
@token_required
def update_utility_account_options_api(current_user):
    data = request.json or {}
    electricity = data.get('electricity')
    water = data.get('water')
    if not isinstance(electricity, list) or not isinstance(water, list):
        return jsonify({'error': 'electricity 和 water 都必须是数组'}), 400
    saved = save_utility_account_options({
        'electricity': electricity,
        'water': water,
    })
    return jsonify(saved)


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


@system_bp.route('/payment-settings', methods=['GET'])
@token_required
def get_payment_settings_api(current_user):
    return jsonify(serialize_payment_settings())


@system_bp.route('/payment-settings', methods=['PUT'])
@token_required
def update_payment_settings_api(current_user):
    data = request.json or {}
    saved = save_payment_settings(data)
    return jsonify(serialize_payment_settings(saved))


@system_bp.route('/ai-settings', methods=['GET'])
@token_required
def get_ai_settings_api(current_user):
    return jsonify(_serialize_ai_settings())


@system_bp.route('/ai-settings', methods=['PUT'])
@token_required
def update_ai_settings_api(current_user):
    data = request.json or {}
    action = str(data.get('action') or 'save_config').strip()
    requested_model = str(data.get('procurement_model') or '').strip()
    provider = str(data.get('provider') or '').strip()
    requested_ollama_base_url = data.get('ollama_base_url')
    requested_enabled = data.get('enabled') if 'enabled' in data else None
    current = load_ai_settings()
    previous_model = str(current.get('procurement_model') or '').strip()
    update_payload = {}
    if provider:
        update_payload['provider'] = provider
    if requested_model:
        update_payload['procurement_model'] = requested_model
    if requested_ollama_base_url is not None:
        update_payload['ollama_base_url'] = requested_ollama_base_url
    if requested_enabled is not None:
        update_payload['enabled'] = bool(requested_enabled)
    if 'base_url' in data:
        update_payload['base_url'] = data.get('base_url')
    if 'chat_completions_url' in data:
        update_payload['chat_completions_url'] = data.get('chat_completions_url')
    if 'responses_url' in data:
        update_payload['responses_url'] = data.get('responses_url')
    if 'model' in data:
        update_payload['model'] = data.get('model')
    if 'api_key' in data:
        update_payload['api_key'] = data.get('api_key')

    current_status = _get_ai_switch_status()
    if current_status.get('status') == 'running':
        return jsonify({'error': '模型正在切换中，请稍后再试'}), 409

    preview = dict(current)
    preview.update(update_payload)
    provider_text = str(preview.get('provider') or 'ollama').strip().lower()
    current_provider = 'api' if provider_text in {'api', 'openai', 'compatible'} else 'ollama'
    current_model = str(preview.get('procurement_model') or previous_model).strip()
    if current_provider == 'ollama' and not current_model:
        return jsonify({'error': '请选择本地 AI 模型'}), 400

    if action == 'save':
        action = 'save_config'

    if action == 'save_config':
        current = save_ai_settings(update_payload) if update_payload else current
        now_text = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        saved_model = current.get('model') if current_provider == 'api' else current.get('procurement_model')
        _set_ai_switch_status(
            id=str(uuid.uuid4()),
            status='completed',
            phase='settings_saved',
            message='AI 配置已保存',
            from_model='',
            to_model=str(saved_model or '').strip(),
            started_at=now_text,
            finished_at=now_text,
            error='',
        )
        return jsonify(_serialize_ai_settings(current))

    if action in {'enable', 'disable'}:
        save_payload = dict(update_payload)
        save_payload['enabled'] = (action == 'enable')
        current = save_ai_settings(save_payload)
        now_text = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        saved_model = current.get('model') if current_provider == 'api' else current.get('procurement_model')
        _set_ai_switch_status(
            id=str(uuid.uuid4()),
            status='completed',
            phase='enabled' if action == 'enable' else 'disabled',
            message='AI 配置显示已开启' if action == 'enable' else 'AI 配置显示已关闭',
            from_model='',
            to_model=str(saved_model or '').strip(),
            started_at=now_text,
            finished_at=now_text,
            error='',
        )
        return jsonify(_serialize_ai_settings(current))

    if current_provider == 'api':
        enabled = current.get('enabled', True)
        if action == 'switch_model':
            enabled = True
        else:
            return jsonify({'error': '不支持的 AI 操作'}), 400

        preview['enabled'] = enabled
        if enabled:
            error_message = _validate_api_ai_settings(preview)
            if error_message:
                return jsonify({'error': error_message}), 400

        save_payload = dict(update_payload)
        save_payload['enabled'] = enabled
        current = save_ai_settings(save_payload)
        now_text = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        phase = 'disabled' if not enabled else 'enabled' if action == 'enable' else 'api_saved'
        message = (
            'AI 功能已停用'
            if not enabled
            else 'AI 功能已启用'
            if action == 'enable'
            else 'API 模式配置已保存'
        )
        _set_ai_switch_status(
            id=str(uuid.uuid4()),
            status='completed',
            phase=phase,
            message=message,
            from_model='',
            to_model=current.get('model') or '',
            started_at=now_text,
            finished_at=now_text,
            error='',
        )
        return jsonify(_serialize_ai_settings(current))

    immediate_payload = dict(update_payload)
    if action == 'switch_model':
        immediate_payload.pop('procurement_model', None)
    if immediate_payload:
        current = save_ai_settings(immediate_payload)

    if action != 'switch_model':
        return jsonify({'error': '不支持的 AI 操作'}), 400

    task_id = str(uuid.uuid4())
    _set_ai_switch_status(
        id=task_id,
        status='running',
        phase='queued',
        message='模型切换任务已开始',
        from_model=previous_model,
        to_model=current_model,
        started_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        finished_at='',
        error='',
    )
    Thread(target=_run_ai_model_switch, args=(task_id, previous_model, current_model), daemon=True).start()
    return jsonify(_serialize_ai_settings(current))


@system_bp.route('/ai-settings/switch-status', methods=['GET'])
@token_required
def get_ai_switch_status_api(current_user):
    return jsonify(_serialize_ai_settings())


@system_bp.route('/ai-settings/test', methods=['POST'])
@token_required
def test_ai_settings_api(current_user):
    preview = _build_ai_test_settings(request.json or {})
    provider = str(preview.get('provider') or 'ollama').strip().lower()
    tested_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    try:
        if provider == 'api':
            result = _test_api_settings(preview)
        else:
            result = _test_ollama_settings(preview)
            result['text_model'] = str(preview.get('procurement_model') or '').strip()
    except urllib.error.HTTPError as e:
        detail = e.read().decode('utf-8', errors='ignore')
        result = {
            'ok': False,
            'provider': provider,
            'model': str(preview.get('model') if provider == 'api' else preview.get('procurement_model') or '').strip(),
            'message': f'连接失败: {detail or e.reason}',
        }
    except Exception as e:
        result = {
            'ok': False,
            'provider': provider,
            'model': str(preview.get('model') if provider == 'api' else preview.get('procurement_model') or '').strip(),
            'message': str(e) or '连接测试失败',
        }
    result['tested_at'] = tested_at
    return jsonify(result)


@system_bp.route('/ai-settings/models', methods=['POST'])
@token_required
def list_ai_models_api(current_user):
    preview = _build_ai_test_settings(request.json or {})
    provider = str(preview.get('provider') or 'ollama').strip().lower()
    tested_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    try:
        if provider == 'api':
            models = _list_api_models(preview)
            return jsonify({
                'ok': True,
                'provider': 'api',
                'models': models,
                'message': f'已获取 {len(models)} 个 API 模型',
                'tested_at': tested_at,
            })

        result = _test_ollama_settings(preview)
        models = [{'id': item, 'owned_by': 'ollama', 'object': 'model'} for item in result.get('available_models') or []]
        return jsonify({
            'ok': True,
            'provider': 'ollama',
            'models': models,
            'message': f'已获取 {len(models)} 个本地模型',
            'tested_at': tested_at,
        })
    except urllib.error.HTTPError as e:
        detail = e.read().decode('utf-8', errors='ignore')
        return jsonify({
            'ok': False,
            'provider': provider,
            'models': [],
            'message': f'获取模型列表失败: {detail or e.reason}',
            'tested_at': tested_at,
        }), 400
    except Exception as e:
        return jsonify({
            'ok': False,
            'provider': provider,
            'models': [],
            'message': str(e) or '获取模型列表失败',
            'tested_at': tested_at,
        }), 400


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


def _format_size(size_bytes):
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    size = float(max(0, int(size_bytes or 0)))
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f'{size:.1f} {unit}' if unit != 'B' else f'{int(size)} B'
        size /= 1024
    return f'{int(size_bytes or 0)} B'


def _snapshot_zip_path(snapshot_id):
    return os.path.join(SNAPSHOTS_DIR, f'{snapshot_id}.zip')


def _snapshot_meta_path(snapshot_id):
    return os.path.join(SNAPSHOTS_DIR, f'{snapshot_id}.json')


def _make_snapshot_id():
    return f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"


def _ensure_snapshots_dir():
    os.makedirs(SNAPSHOTS_DIR, exist_ok=True)


def _progress_reporter(callback, phase, progress, message):
    if callback:
        callback(phase, progress, message)


def _collect_relative_files(base_dir):
    results = []
    if not os.path.isdir(base_dir):
        return results
    for root, _, files in os.walk(base_dir):
        for filename in files:
            file_path = os.path.join(root, filename)
            rel_path = os.path.relpath(file_path, base_dir)
            results.append((file_path, rel_path))
    results.sort(key=lambda item: item[1])
    return results


def _write_system_snapshot_zip(target_path, progress_callback=None):
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    config_files = _collect_relative_files(CONFIG_DIR)
    upload_files = _collect_relative_files(UPLOADS_DIR)
    env_files = _collect_env_files()
    total_items = 1 + len(config_files) + len(upload_files) + len(env_files) + (1 if env_files else 0)
    done = 0

    def mark(phase, message):
        nonlocal done
        done += 1
        progress = min(99, max(1, int(done * 100 / max(total_items, 1))))
        _progress_reporter(progress_callback, phase, progress, message)

    _progress_reporter(progress_callback, 'prepare', 1, '正在整理数据库与文件')
    db_data = _dump_db_to_dict()
    db_json = json.dumps(db_data, ensure_ascii=False, indent=2)

    with zipfile.ZipFile(target_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('database.json', db_json)
        mark('database', '数据库已写入快照')

        for file_path, rel_path in config_files:
            zf.write(file_path, os.path.join('config', rel_path))
            mark('config', f'已写入配置文件 {os.path.basename(rel_path)}')

        for file_path, rel_path in upload_files:
            zf.write(file_path, os.path.join('uploads', rel_path))
            mark('uploads', f'已写入上传文件 {os.path.basename(rel_path)}')

        if env_files:
            zf.writestr(
                'env_files_manifest.json',
                json.dumps([rel_path for _, rel_path in env_files], ensure_ascii=False, indent=2),
            )
            mark('env_manifest', '环境配置清单已写入快照')
            for file_path, rel_path in env_files:
                zf.write(file_path, os.path.join('env_files', rel_path))
                mark('env', f'已写入环境配置 {os.path.basename(rel_path)}')

    _progress_reporter(progress_callback, 'completed', 100, '系统快照已生成')


def _read_snapshot_meta(snapshot_id):
    zip_path = _snapshot_zip_path(snapshot_id)
    if not os.path.isfile(zip_path):
        return None

    payload = {
        'id': snapshot_id,
        'created_at': '',
        'source_name': '',
        'snapshot_type': 'manual',
        'size_bytes': 0,
        'size_text': '',
        'file_name': os.path.basename(zip_path),
    }
    meta_path = _snapshot_meta_path(snapshot_id)
    if os.path.isfile(meta_path):
        try:
            with open(meta_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict):
                payload['created_at'] = str(data.get('created_at') or '').strip()
                payload['source_name'] = str(data.get('source_name') or '').strip()
                payload['snapshot_type'] = str(data.get('snapshot_type') or '').strip() or payload['snapshot_type']
        except Exception:
            pass

    try:
        payload['size_bytes'] = os.path.getsize(zip_path)
    except OSError:
        payload['size_bytes'] = 0
    payload['size_text'] = _format_size(payload['size_bytes'])

    if not payload['created_at']:
        try:
            payload['created_at'] = datetime.fromtimestamp(os.path.getmtime(zip_path)).strftime('%Y-%m-%d %H:%M:%S')
        except OSError:
            payload['created_at'] = ''
    return payload


def _migrate_legacy_snapshot_if_needed():
    if not os.path.isfile(LEGACY_ROLLBACK_ZIP_PATH):
        return
    _ensure_snapshots_dir()
    snapshot_id = _make_snapshot_id()
    target_zip = _snapshot_zip_path(snapshot_id)
    target_meta = _snapshot_meta_path(snapshot_id)
    source_name = '旧版迁移快照'
    snapshot_type = 'legacy'
    created_at = ''
    if os.path.isfile(LEGACY_ROLLBACK_META_PATH):
        try:
            with open(LEGACY_ROLLBACK_META_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict):
                source_name = str(data.get('source_name') or '').strip() or source_name
                snapshot_type = str(data.get('snapshot_type') or '').strip() or snapshot_type
                created_at = str(data.get('created_at') or '').strip()
        except Exception:
            pass
    if not created_at:
        try:
            created_at = datetime.fromtimestamp(os.path.getmtime(LEGACY_ROLLBACK_ZIP_PATH)).strftime('%Y-%m-%d %H:%M:%S')
        except OSError:
            created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    try:
        os.replace(LEGACY_ROLLBACK_ZIP_PATH, target_zip)
        with open(target_meta, 'w', encoding='utf-8') as f:
            json.dump({
                'id': snapshot_id,
                'created_at': created_at,
                'source_name': source_name,
                'snapshot_type': snapshot_type,
            }, f, ensure_ascii=False, indent=2)
        if os.path.exists(LEGACY_ROLLBACK_META_PATH):
            os.remove(LEGACY_ROLLBACK_META_PATH)
    except Exception:
        pass


def _list_snapshots():
    _ensure_snapshots_dir()
    _migrate_legacy_snapshot_if_needed()
    snapshots = []
    for filename in os.listdir(SNAPSHOTS_DIR):
        if not filename.endswith('.zip'):
            continue
        snapshot_id = filename[:-4]
        payload = _read_snapshot_meta(snapshot_id)
        if payload:
            snapshots.append(payload)
    snapshots.sort(key=lambda item: (item.get('created_at') or '', item.get('id') or ''), reverse=True)
    return snapshots


def _latest_snapshot():
    snapshots = _list_snapshots()
    return snapshots[0] if snapshots else None


def _load_last_import_rollback_status():
    latest = _latest_snapshot()
    if not latest:
        return {
            'available': False,
            'created_at': '',
            'source_name': '',
            'size_bytes': 0,
            'size_text': '',
            'snapshot_id': '',
            'count': 0,
        }
    payload = dict(latest)
    payload['available'] = True
    payload['snapshot_id'] = latest['id']
    payload['count'] = len(_list_snapshots())
    return payload


def _delete_snapshot(snapshot_id):
    zip_path = _snapshot_zip_path(snapshot_id)
    meta_path = _snapshot_meta_path(snapshot_id)
    if not os.path.isfile(zip_path):
        raise FileNotFoundError('快照不存在')
    os.remove(zip_path)
    if os.path.exists(meta_path):
        os.remove(meta_path)


def _write_snapshot_metadata(snapshot_id, created_at, source_name, snapshot_type='manual'):
    with open(_snapshot_meta_path(snapshot_id), 'w', encoding='utf-8') as f:
        json.dump({
            'id': snapshot_id,
            'created_at': created_at,
            'source_name': str(source_name or '').strip(),
            'snapshot_type': str(snapshot_type or 'manual').strip(),
        }, f, ensure_ascii=False, indent=2)


def _create_snapshot_archive(source_name='', snapshot_type='manual', progress_callback=None):
    _ensure_snapshots_dir()
    snapshot_id = _make_snapshot_id()
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    temp_snapshot_fd, temp_snapshot_path = tempfile.mkstemp(prefix='homes_snapshot_', suffix='.zip')
    target_zip_path = _snapshot_zip_path(snapshot_id)
    try:
        os.close(temp_snapshot_fd)
        _write_system_snapshot_zip(temp_snapshot_path, progress_callback=progress_callback)
        os.replace(temp_snapshot_path, target_zip_path)
        _write_snapshot_metadata(snapshot_id, created_at, source_name, snapshot_type=snapshot_type)
        payload = _read_snapshot_meta(snapshot_id) or {
            'id': snapshot_id,
            'created_at': created_at,
            'source_name': str(source_name or '').strip(),
            'snapshot_type': str(snapshot_type or 'manual').strip(),
            'size_bytes': 0,
            'size_text': '0 B',
            'file_name': os.path.basename(target_zip_path),
        }
        return payload
    finally:
        if os.path.exists(temp_snapshot_path):
            os.remove(temp_snapshot_path)


def _clear_last_import_rollback():
    latest = _latest_snapshot()
    if latest:
        _delete_snapshot(latest['id'])


def _save_last_import_rollback(temp_zip_path, source_name='', snapshot_type='manual'):
    _ensure_snapshots_dir()
    snapshot_id = _make_snapshot_id()
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    os.replace(temp_zip_path, _snapshot_zip_path(snapshot_id))
    _write_snapshot_metadata(snapshot_id, created_at, source_name, snapshot_type=snapshot_type)


def _create_or_update_snapshot(source_name='', snapshot_type='manual'):
    return _create_snapshot_archive(source_name=source_name, snapshot_type=snapshot_type)


def _safe_extract_target(base_dir, relative_path, label):
    normalized_rel = os.path.normpath(str(relative_path or ''))
    if normalized_rel in ('', '.'):
        raise ValueError(f'{label} 路径不合法')
    if normalized_rel.startswith('..') or os.path.isabs(normalized_rel):
        raise ValueError(f'{label} 路径不合法')
    target_path = os.path.normpath(os.path.join(base_dir, normalized_rel))
    base_path = os.path.normpath(base_dir)
    if target_path != base_path and not target_path.startswith(base_path + os.sep):
        raise ValueError(f'{label} 路径不合法')
    return target_path


def _extract_zip_tree(zf, prefix, target_root, label):
    extracted = []
    for member in zf.namelist():
        if not member.startswith(prefix):
            continue
        if member.endswith('/'):
            continue
        relative_path = os.path.relpath(member, prefix)
        target_path = _safe_extract_target(target_root, relative_path, label)
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        with zf.open(member) as source, open(target_path, 'wb') as target:
            shutil.copyfileobj(source, target)
        extracted.append(relative_path.replace('\\', '/'))
    extracted.sort()
    return extracted


def _clear_directory(directory):
    if os.path.isdir(directory):
        shutil.rmtree(directory)
    os.makedirs(directory, exist_ok=True)


def _copy_directory_contents(source_dir, target_dir):
    os.makedirs(target_dir, exist_ok=True)
    if not os.path.isdir(source_dir):
        return
    for current_root, dirnames, filenames in os.walk(source_dir):
        rel_root = os.path.relpath(current_root, source_dir)
        dest_root = target_dir if rel_root == '.' else os.path.join(target_dir, rel_root)
        os.makedirs(dest_root, exist_ok=True)
        for dirname in dirnames:
            os.makedirs(os.path.join(dest_root, dirname), exist_ok=True)
        for filename in filenames:
            shutil.copy2(os.path.join(current_root, filename), os.path.join(dest_root, filename))


def _snapshot_directory(source_dir, snapshot_dir):
    if os.path.isdir(source_dir):
        shutil.copytree(source_dir, snapshot_dir)
        return True
    return False


def _load_env_manifest(zf):
    if 'env_files_manifest.json' not in zf.namelist():
        return None
    with zf.open('env_files_manifest.json') as manifest_file:
        data = json.load(manifest_file)
    if not isinstance(data, list):
        raise ValueError('备份文件中的环境配置清单格式不正确')
    manifest = []
    for item in data:
        text = str(item or '').strip().replace('\\', '/')
        if text == '':
            continue
        if text in manifest:
            continue
        manifest.append(text)
    return manifest


def _current_exportable_env_paths():
    return [rel_path for _, rel_path in _collect_env_files()]


def _clear_exportable_env_files(rel_paths):
    for rel_path in rel_paths or []:
        target_path = _safe_extract_target(PROJECT_ROOT, rel_path, '环境配置文件')
        if os.path.isfile(target_path):
            os.remove(target_path)


def _snapshot_env_files(snapshot_root):
    manifest = []
    for abs_path, rel_path in _collect_env_files():
        manifest.append(rel_path)
        target_path = _safe_extract_target(snapshot_root, rel_path, '环境配置文件')
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        shutil.copy2(abs_path, target_path)
    return manifest


def _restore_env_files_from_staging(staging_root, manifest):
    _clear_exportable_env_files(_current_exportable_env_paths())
    for rel_path in manifest or []:
        source_path = _safe_extract_target(staging_root, rel_path, '环境配置文件')
        if not os.path.isfile(source_path):
            raise FileNotFoundError(f'备份文件缺少环境配置文件: {rel_path}')
        target_path = _safe_extract_target(PROJECT_ROOT, rel_path, '环境配置文件')
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        shutil.copy2(source_path, target_path)


def _snapshot_live_db(snapshot_path):
    os.makedirs(os.path.dirname(snapshot_path), exist_ok=True)
    source_conn = connect()
    try:
        backup_conn = sqlite3.connect(snapshot_path)
        try:
            source_conn.backup(backup_conn)
            backup_conn.commit()
        finally:
            backup_conn.close()
    finally:
        source_conn.close()


def _restore_live_db(snapshot_path):
    if not os.path.isfile(snapshot_path):
        raise FileNotFoundError('数据库快照不存在，无法回滚')
    target_conn = connect()
    try:
        source_conn = sqlite3.connect(snapshot_path)
        try:
            source_conn.backup(target_conn)
            target_conn.commit()
        finally:
            source_conn.close()
    finally:
        target_conn.close()


def _prepare_import_staging(zip_path, progress_callback=None):
    staging_root = tempfile.mkdtemp(prefix='homes_import_stage_')
    db_data = None
    env_manifest = []
    try:
        _progress_reporter(progress_callback, 'reading', 8, '正在读取快照文件')
        with zipfile.ZipFile(zip_path, 'r') as zf:
            names = set(zf.namelist())
            if 'database.json' not in names:
                raise ValueError('备份文件缺少 database.json，无法恢复数据库')
            with zf.open('database.json') as db_file:
                db_data = json.load(db_file)

            config_stage_dir = os.path.join(staging_root, 'config')
            uploads_stage_dir = os.path.join(staging_root, 'uploads')
            env_stage_dir = os.path.join(staging_root, 'env_files')
            _progress_reporter(progress_callback, 'extracting', 22, '正在解压配置与上传文件')
            _extract_zip_tree(zf, 'config/', config_stage_dir, '配置文件')
            _extract_zip_tree(zf, 'uploads/', uploads_stage_dir, '上传文件')
            extracted_env_paths = _extract_zip_tree(zf, 'env_files/', env_stage_dir, '环境配置文件')
            env_manifest = _load_env_manifest(zf)
            if env_manifest is None:
                env_manifest = extracted_env_paths
            else:
                missing_env_paths = [rel_path for rel_path in env_manifest if rel_path not in extracted_env_paths]
                if missing_env_paths:
                    raise ValueError(f'备份文件缺少环境配置文件: {missing_env_paths[0]}')
        _progress_reporter(progress_callback, 'staged', 35, '快照内容已准备完成')

        return {
            'root': staging_root,
            'db_data': db_data,
            'config_dir': os.path.join(staging_root, 'config'),
            'uploads_dir': os.path.join(staging_root, 'uploads'),
            'env_dir': os.path.join(staging_root, 'env_files'),
            'env_manifest': env_manifest,
        }
    except Exception:
        shutil.rmtree(staging_root, ignore_errors=True)
        raise


def _apply_staged_import(staging, progress_callback=None):
    rollback_root = tempfile.mkdtemp(prefix='homes_import_rollback_')
    db_snapshot_path = os.path.join(rollback_root, 'db_snapshot.sqlite3')
    config_snapshot_dir = os.path.join(rollback_root, 'config')
    uploads_snapshot_dir = os.path.join(rollback_root, 'uploads')
    env_snapshot_dir = os.path.join(rollback_root, 'env_files')
    env_snapshot_manifest = []
    config_snapshot_exists = False
    uploads_snapshot_exists = False
    db_snapshot_ready = False

    try:
        _progress_reporter(progress_callback, 'backup_current', 42, '正在备份当前系统状态')
        _snapshot_live_db(db_snapshot_path)
        db_snapshot_ready = True
        config_snapshot_exists = _snapshot_directory(CONFIG_DIR, config_snapshot_dir)
        uploads_snapshot_exists = _snapshot_directory(UPLOADS_DIR, uploads_snapshot_dir)
        env_snapshot_manifest = _snapshot_env_files(env_snapshot_dir)

        _progress_reporter(progress_callback, 'restore_db', 58, '正在恢复数据库')
        success, msg = _restore_db_from_dict(staging['db_data'])
        if not success:
            raise RuntimeError(f'数据库恢复失败: {msg}')

        _progress_reporter(progress_callback, 'restore_config', 72, '正在恢复配置文件')
        _clear_directory(CONFIG_DIR)
        _copy_directory_contents(staging['config_dir'], CONFIG_DIR)

        _progress_reporter(progress_callback, 'restore_uploads', 86, '正在恢复上传文件')
        _clear_directory(UPLOADS_DIR)
        _copy_directory_contents(staging['uploads_dir'], UPLOADS_DIR)

        _progress_reporter(progress_callback, 'restore_env', 96, '正在恢复环境配置')
        _restore_env_files_from_staging(staging['env_dir'], staging['env_manifest'])
        _progress_reporter(progress_callback, 'completed', 100, '系统状态恢复完成')
    except Exception:
        rollback_errors = []
        if db_snapshot_ready:
            try:
                _restore_live_db(db_snapshot_path)
            except Exception as rollback_error:
                rollback_errors.append(f'数据库回滚失败: {rollback_error}')
        try:
            _clear_directory(CONFIG_DIR)
            if config_snapshot_exists:
                _copy_directory_contents(config_snapshot_dir, CONFIG_DIR)
        except Exception as rollback_error:
            rollback_errors.append(f'配置回滚失败: {rollback_error}')
        try:
            _clear_directory(UPLOADS_DIR)
            if uploads_snapshot_exists:
                _copy_directory_contents(uploads_snapshot_dir, UPLOADS_DIR)
        except Exception as rollback_error:
            rollback_errors.append(f'上传文件回滚失败: {rollback_error}')
        try:
            _restore_env_files_from_staging(env_snapshot_dir, env_snapshot_manifest)
        except Exception as rollback_error:
            rollback_errors.append(f'环境配置文件回滚失败: {rollback_error}')

        if rollback_errors:
            raise RuntimeError('导入失败，且回滚不完整：' + '；'.join(rollback_errors))
        raise
    finally:
        shutil.rmtree(rollback_root, ignore_errors=True)

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


def _run_create_snapshot_job(task_id, source_name, snapshot_type):
    def report(phase, progress, message):
        _set_snapshot_task_status(
            phase=phase,
            progress=progress,
            message=message,
        )

    try:
        snapshot = _create_snapshot_archive(source_name=source_name, snapshot_type=snapshot_type, progress_callback=report)
        _set_snapshot_task_status(
            status='completed',
            phase='completed',
            progress=100,
            message='系统快照已创建',
            snapshot_id=snapshot.get('id', ''),
            snapshot_name=snapshot.get('source_name', ''),
            finished_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            error='',
        )
    except Exception as e:
        _set_snapshot_task_status(
            status='failed',
            phase='failed',
            progress=0,
            message='创建快照失败',
            finished_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            error=str(e),
        )
    finally:
        _restore_lock.release()


def _run_restore_snapshot_job(task_id, snapshot_id):
    staging = None

    def report(phase, progress, message):
        _set_snapshot_task_status(
            phase=phase,
            progress=progress,
            message=message,
        )

    try:
        snapshot = _read_snapshot_meta(snapshot_id)
        if not snapshot:
            raise FileNotFoundError('快照不存在')
        staging = _prepare_import_staging(_snapshot_zip_path(snapshot_id), progress_callback=report)
        _apply_staged_import(staging, progress_callback=report)
        _set_snapshot_task_status(
            status='completed',
            phase='completed',
            progress=100,
            message='已回滚到所选快照对应的系统状态',
            snapshot_id=snapshot.get('id', ''),
            snapshot_name=snapshot.get('source_name', ''),
            finished_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            error='',
        )
    except Exception as e:
        _set_snapshot_task_status(
            status='failed',
            phase='failed',
            progress=0,
            message='回滚快照失败',
            finished_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            error=str(e),
        )
    finally:
        if staging and staging.get('root'):
            shutil.rmtree(staging['root'], ignore_errors=True)
        _restore_lock.release()

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


@system_bp.route('/import-rollback-status', methods=['GET'])
@token_required
def get_import_rollback_status_api(current_user):
    return jsonify(_load_last_import_rollback_status())


@system_bp.route('/snapshot-task-status', methods=['GET'])
@token_required
def get_snapshot_task_status_api(current_user):
    return jsonify(_get_snapshot_task_status())


@system_bp.route('/snapshots', methods=['GET'])
@token_required
def list_snapshots_api(current_user):
    snapshots = _list_snapshots()
    return jsonify({
        'snapshots': snapshots,
        'count': len(snapshots),
        'latest_snapshot_id': snapshots[0]['id'] if snapshots else '',
    })


@system_bp.route('/snapshots', methods=['POST'])
@token_required
def create_snapshot_async_api(current_user):
    current_status = _get_snapshot_task_status()
    if current_status.get('status') == 'running':
        return jsonify({'error': '已有快照任务正在执行，请稍后再试'}), 409
    if not _restore_lock.acquire(blocking=False):
        return jsonify({'error': '系统正在执行导入、回滚或创建快照，请稍后再试'}), 429

    task_id = str(uuid.uuid4())
    _set_snapshot_task_status(
        id=task_id,
        action='create',
        status='running',
        phase='queued',
        message='系统快照创建任务已开始',
        progress=1,
        snapshot_id='',
        snapshot_name='手动创建',
        started_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        finished_at='',
        error='',
    )
    try:
        Thread(target=_run_create_snapshot_job, args=(task_id, '手动创建', 'manual'), daemon=True).start()
    except Exception:
        _restore_lock.release()
        raise
    return jsonify(_get_snapshot_task_status())


@system_bp.route('/snapshots/<snapshot_id>/restore', methods=['POST'])
@token_required
def restore_snapshot_async_api(current_user, snapshot_id):
    snapshot = _read_snapshot_meta(snapshot_id)
    if not snapshot:
        return jsonify({'error': '快照不存在'}), 404
    current_status = _get_snapshot_task_status()
    if current_status.get('status') == 'running':
        return jsonify({'error': '已有快照任务正在执行，请稍后再试'}), 409
    if not _restore_lock.acquire(blocking=False):
        return jsonify({'error': '系统正在执行导入、回滚或创建快照，请稍后再试'}), 429

    task_id = str(uuid.uuid4())
    _set_snapshot_task_status(
        id=task_id,
        action='restore',
        status='running',
        phase='queued',
        message='快照回滚任务已开始',
        progress=1,
        snapshot_id=snapshot.get('id', ''),
        snapshot_name=snapshot.get('source_name', ''),
        started_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        finished_at='',
        error='',
    )
    try:
        Thread(target=_run_restore_snapshot_job, args=(task_id, snapshot_id), daemon=True).start()
    except Exception:
        _restore_lock.release()
        raise
    return jsonify(_get_snapshot_task_status())


@system_bp.route('/snapshots/<snapshot_id>', methods=['DELETE'])
@token_required
def delete_snapshot_api(current_user, snapshot_id):
    current_status = _get_snapshot_task_status()
    if current_status.get('status') == 'running':
        return jsonify({'error': '快照任务执行中，暂时不能删除快照'}), 409
    try:
        _delete_snapshot(snapshot_id)
        snapshots = _list_snapshots()
        return jsonify({
            'message': '快照已删除',
            'snapshots': snapshots,
            'count': len(snapshots),
        }), 200
    except FileNotFoundError as e:
        return jsonify({'error': str(e)}), 404


@system_bp.route('/snapshot', methods=['POST'])
@token_required
def create_system_snapshot_api(current_user):
    return create_snapshot_async_api(current_user)


@system_bp.route('/import-rollback', methods=['POST'])
@token_required
def rollback_last_import_api(current_user):
    latest = _latest_snapshot()
    if not latest:
        return jsonify({'error': '当前没有可回滚的系统快照'}), 404
    try:
        return restore_snapshot_async_api(current_user, latest['id'])
    except Exception as e:
        current_app.logger.error(f"Rollback start failed: {e}")
        return jsonify({'error': f'启动回滚失败: {str(e)}'}), 500

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
    staging = None
    source_name = ''

    if not _restore_lock.acquire(blocking=False):
        return jsonify({'error': '系统正在执行导入、回滚或创建快照，请稍后再试'}), 429

    try:
        if 'file' in request.files:
            file = request.files['file']
            if not file.filename.lower().endswith('.zip'):
                return jsonify({'error': '文件格式错误，请上传 ZIP 备份文件'}), 400
            source_name = str(file.filename or '').strip()
            file.save(temp_zip_path)
        else:
            data = request.get_json(silent=True) or {}
            file_url = data.get('file_url')
            if not file_url:
                return jsonify({'error': '未找到备份文件'}), 400
            source_zip_path = _resolve_upload_url_to_path(file_url)
            source_name = str(data.get('source_name') or '').strip() or os.path.basename(source_zip_path)
            shutil.copyfile(source_zip_path, temp_zip_path)

        staging = _prepare_import_staging(temp_zip_path)
        snapshot_source_name = f'导入前自动创建（{source_name}）' if source_name else '导入前自动创建'
        _create_or_update_snapshot(source_name=snapshot_source_name, snapshot_type='import_auto')
        _apply_staged_import(staging)

        return jsonify({"message": "系统数据导入成功"}), 200


    except FileNotFoundError as e:
        return jsonify({'error': str(e)}), 404
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Import failed: {e}")
        return jsonify({"error": f"导入系统数据失败: {str(e)}"}), 500
    finally:
        if staging and staging.get('root'):
            shutil.rmtree(staging['root'], ignore_errors=True)
        if os.path.exists(temp_zip_path):
            os.remove(temp_zip_path)
        _restore_lock.release()
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
