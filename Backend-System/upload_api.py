import json
import math
import os
import re
import shutil
import uuid
from datetime import datetime

from flask import Blueprint, jsonify, request

from auth_api import token_required


upload_bp = Blueprint('upload', __name__, url_prefix='/api')


def _session_root():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base_dir, 'tmp', 'chunk_uploads')
    os.makedirs(path, exist_ok=True)
    return path


def _upload_root():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base_dir, 'static', 'uploads')
    os.makedirs(path, exist_ok=True)
    return path


def _safe_segment(value, default='general'):
    text = str(value or '').strip()
    text = re.sub(r'[^0-9A-Za-z_\-]', '_', text)
    text = re.sub(r'_+', '_', text).strip('._-')
    return text or default


def _safe_sub_dir(value):
    raw = str(value or '').replace('\\', '/').strip('/')
    if raw == '':
        return ''
    parts = []
    for part in raw.split('/'):
        cleaned = _safe_segment(part, default='')
        if cleaned:
            parts.append(cleaned)
    return '/'.join(parts)


def _safe_ext(filename, mime_type=''):
    ext = os.path.splitext(str(filename or ''))[1].lower()
    if ext in ('.png', '.jpg', '.jpeg', '.webp', '.avif', '.gif', '.bmp', '.heic', '.heif', '.zip'):
        return ext
    mt = str(mime_type or '').lower()
    if mt in ('image/jpeg', 'image/jpg'):
        return '.jpg'
    if mt == 'image/png':
        return '.png'
    if mt == 'image/webp':
        return '.webp'
    if mt == 'image/avif':
        return '.avif'
    if mt == 'image/gif':
        return '.gif'
    if mt in ('application/zip', 'application/x-zip-compressed', 'multipart/x-zip'):
        return '.zip'
    return '.bin'


def _session_dir(upload_id):
    return os.path.join(_session_root(), _safe_segment(upload_id, default=''))


def _meta_path(upload_id):
    return os.path.join(_session_dir(upload_id), 'meta.json')


def _chunks_dir(upload_id):
    return os.path.join(_session_dir(upload_id), 'chunks')


def _read_meta(upload_id):
    path = _meta_path(upload_id)
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def _write_meta(upload_id, data):
    session_path = _session_dir(upload_id)
    os.makedirs(session_path, exist_ok=True)
    with open(_meta_path(upload_id), 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)


def _uploaded_indices(upload_id, total_chunks):
    cdir = _chunks_dir(upload_id)
    if not os.path.isdir(cdir):
        return []
    out = []
    for name in os.listdir(cdir):
        if not name.endswith('.part'):
            continue
        idx_text = name[:-5]
        if not idx_text.isdigit():
            continue
        idx = int(idx_text)
        if 0 <= idx < total_chunks:
            out.append(idx)
    out.sort()
    return out


@upload_bp.route('/uploads/chunk/init', methods=['POST'])
@token_required
def init_chunk_upload(current_user):
    data = request.get_json(silent=True) or {}
    filename = str(data.get('filename') or '').strip()
    if filename == '':
        return jsonify({'error': 'filename 不能为空'}), 400

    try:
        total_size = int(data.get('total_size') or 0)
        chunk_size = int(data.get('chunk_size') or 0)
        total_chunks = int(data.get('total_chunks') or 0)
    except Exception:
        return jsonify({'error': '分片参数格式错误'}), 400

    if total_size <= 0:
        return jsonify({'error': 'total_size 必须大于 0'}), 400
    if chunk_size <= 0:
        return jsonify({'error': 'chunk_size 必须大于 0'}), 400
    if chunk_size > 20 * 1024 * 1024:
        return jsonify({'error': 'chunk_size 不能超过 20MB'}), 400

    calc_total = int(math.ceil(total_size / float(chunk_size)))
    if total_chunks <= 0:
        total_chunks = calc_total
    if total_chunks != calc_total:
        return jsonify({'error': 'total_chunks 与大小不匹配'}), 400

    category = _safe_segment(data.get('category'), default='general')
    sub_dir = _safe_sub_dir(data.get('sub_dir'))
    mime_type = str(data.get('mime_type') or '').strip()

    upload_id = uuid.uuid4().hex
    os.makedirs(_chunks_dir(upload_id), exist_ok=True)
    meta = {
        'upload_id': upload_id,
        'filename': filename,
        'ext': _safe_ext(filename, mime_type),
        'total_size': total_size,
        'chunk_size': chunk_size,
        'total_chunks': total_chunks,
        'category': category,
        'sub_dir': sub_dir,
        'mime_type': mime_type,
        'created_at': datetime.utcnow().isoformat(),
    }
    _write_meta(upload_id, meta)

    return jsonify({
        'upload_id': upload_id,
        'total_chunks': total_chunks,
        'chunk_size': chunk_size,
        'category': category,
        'sub_dir': sub_dir,
    })


@upload_bp.route('/uploads/chunk/<upload_id>', methods=['POST'])
@token_required
def upload_chunk(current_user, upload_id):
    meta = _read_meta(upload_id)
    if not meta:
        return jsonify({'error': 'upload_id 不存在或已过期'}), 404

    if 'chunk' not in request.files:
        return jsonify({'error': '请上传分片文件（字段名 chunk）'}), 400
    try:
        index = int(request.form.get('index', -1))
    except Exception:
        return jsonify({'error': 'index 参数格式错误'}), 400

    total_chunks = int(meta.get('total_chunks') or 0)
    if index < 0 or index >= total_chunks:
        return jsonify({'error': 'index 超出范围'}), 400

    cdir = _chunks_dir(upload_id)
    os.makedirs(cdir, exist_ok=True)
    chunk_file = request.files['chunk']
    save_path = os.path.join(cdir, f'{index}.part')
    chunk_file.save(save_path)

    uploaded = _uploaded_indices(upload_id, total_chunks)
    return jsonify({
        'message': '分片上传成功',
        'index': index,
        'uploaded_count': len(uploaded),
        'total_chunks': total_chunks,
    })


@upload_bp.route('/uploads/chunk/<upload_id>/status', methods=['GET'])
@token_required
def chunk_upload_status(current_user, upload_id):
    meta = _read_meta(upload_id)
    if not meta:
        return jsonify({'error': 'upload_id 不存在或已过期'}), 404

    total_chunks = int(meta.get('total_chunks') or 0)
    uploaded = _uploaded_indices(upload_id, total_chunks)
    percent = 0 if total_chunks <= 0 else int(len(uploaded) * 100 / total_chunks)
    return jsonify({
        'upload_id': upload_id,
        'total_chunks': total_chunks,
        'uploaded_chunks': uploaded,
        'uploaded_count': len(uploaded),
        'percent': percent,
    })


@upload_bp.route('/uploads/chunk/<upload_id>/complete', methods=['POST'])
@token_required
def complete_chunk_upload(current_user, upload_id):
    meta = _read_meta(upload_id)
    if not meta:
        return jsonify({'error': 'upload_id 不存在或已过期'}), 404

    total_chunks = int(meta.get('total_chunks') or 0)
    uploaded = set(_uploaded_indices(upload_id, total_chunks))
    missing = [idx for idx in range(total_chunks) if idx not in uploaded]
    if missing:
        return jsonify({'error': '存在未上传分片', 'missing_chunks': missing[:50]}), 400

    category = _safe_segment(meta.get('category'), default='general')
    sub_dir = _safe_sub_dir(meta.get('sub_dir'))
    final_dir = os.path.join(_upload_root(), category)
    if sub_dir:
        final_dir = os.path.join(final_dir, *sub_dir.split('/'))
    os.makedirs(final_dir, exist_ok=True)

    base_name = _safe_segment(os.path.splitext(meta.get('filename', 'upload'))[0], default='upload')
    ext = _safe_ext(meta.get('filename', ''), meta.get('mime_type', ''))
    final_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{base_name}_{uuid.uuid4().hex[:8]}{ext}"
    final_path = os.path.join(final_dir, final_name)

    cdir = _chunks_dir(upload_id)
    written = 0
    with open(final_path, 'wb') as out:
        for idx in range(total_chunks):
            part_path = os.path.join(cdir, f'{idx}.part')
            with open(part_path, 'rb') as part:
                while True:
                    block = part.read(1024 * 1024)
                    if not block:
                        break
                    out.write(block)
                    written += len(block)

    expected = int(meta.get('total_size') or 0)
    if expected > 0 and written != expected:
        try:
            os.remove(final_path)
        except Exception:
            pass
        return jsonify({'error': '合并后文件大小校验失败'}), 400

    shutil.rmtree(_session_dir(upload_id), ignore_errors=True)

    rel_parts = ['static', 'uploads', category]
    if sub_dir:
        rel_parts.extend(sub_dir.split('/'))
    rel_parts.append(final_name)
    file_url = '/' + '/'.join(rel_parts)

    return jsonify({
        'message': '上传完成',
        'file_url': file_url,
        'size': written,
        'category': category,
    })

