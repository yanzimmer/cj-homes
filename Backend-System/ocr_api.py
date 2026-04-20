import os
import re
import json
from datetime import datetime
from urllib.parse import urlparse

from flask import Blueprint, request, jsonify, current_app

from auth_api import token_required


# PaddleOCR availability detection
try:
    from paddleocr import PaddleOCR
    PADDLE_OCR_AVAILABLE = True
except Exception:
    PADDLE_OCR_AVAILABLE = False
    PaddleOCR = None

ocr_bp = Blueprint('ocr', __name__, url_prefix='/api')


def _ensure_upload_dir():
    base_dir = os.path.dirname(__file__)
    upload_dir = os.path.join(base_dir, 'static', 'uploads', 'idcards')
    os.makedirs(upload_dir, exist_ok=True)
    return upload_dir


def _load_ocr_config():
    base_dir = os.path.dirname(__file__)
    cfg_path = os.path.join(base_dir, 'config', 'ocr_config.json')
    default = {
        "preferred_engine": "paddleocr",
        "paddleocr": {
            "lang": "ch",
            "use_angle_cls": True,
            "ocr": {
                "det": True,
                "rec": True,
                "cls": True
            }
        },
    }
    try:
        with open(cfg_path, 'r', encoding='utf-8') as f:
            user_cfg = json.load(f)
        def deep_update(dst, src):
            for k, v in src.items():
                if isinstance(v, dict) and isinstance(dst.get(k), dict):
                    deep_update(dst[k], v)
                else:
                    dst[k] = v
            return dst
        return deep_update(default, user_cfg)
    except Exception:
        return default


def _filter_none(d):
    return {k: v for k, v in (d or {}).items() if v is not None}


def _normalize_date_str(s):
    if not s:
        return None
    s = s.strip()
    s = s.replace('年', '-').replace('月', '-').replace('日', '')
    s = s.replace('.', '-')
    parts = re.findall(r"\d{4}-\d{1,2}-\d{1,2}", s)
    if parts:
        y, m, d = parts[0].split('-')
        return f"{y}-{int(m):02d}-{int(d):02d}"
    m2 = re.search(r"(\d{4})(\d{2})(\d{2})", s)
    if m2:
        y, m, d = m2.groups()
        return f"{y}-{m}-{d}"
    return None


def _parse_valid_period(s):
    if not s:
        return None, None
    s = s.strip().replace('至', '-').replace('—', '-').replace('－', '-').replace('~', '-')
    s = s.replace('年', '-').replace('月', '-').replace('日', '').replace(' ', '')
    s = s.replace('.', '-')
    m = re.search(r"(\d{4}-\d{1,2}-\d{1,2}).*?(\d{4}-\d{1,2}-\d{1,2})", s)
    if m:
        start = _normalize_date_str(m.group(1))
        end = _normalize_date_str(m.group(2))
        return start, end
    return None, None


def _extract_idcard_fields(text):
    def find(pattern, idx=1):
        m = re.search(pattern, text)
        return m.group(idx).strip() if m else ''

    name = find(r"濮撳悕[锛? ]?([^\n]{2,20})")
    gender = find(r"鎬у埆[锛? ]?(鐢穦濂?")
    nation = find(r"姘戞棌[锛? ]?([^\n]{1,10})")
    birth_raw = find(r"鍑虹敓[锛? ]?([0-9]{4}[骞碶-/\.][0-9]{1,2}[鏈圽-/\.][0-9]{1,2}鏃?)")
    birth_date = _normalize_date_str(birth_raw)
    id_card = ''
    m_id = re.search(r"(鍏皯韬唤鍙风爜|韬唤璇佸彿)[锛? ]?([0-9Xx]{15,18})", text)
    if m_id:
        id_card = m_id.group(2)
    address = find(r"浣忓潃[锛? ]?(.+)")
    issuer = find(r"绛惧彂鏈哄叧[锛? ]?(.+)")
    valid_raw = find(r"鏈夋晥鏈熼檺[锛? ]?(.+)") or find(r"鏈夋晥鏈焄锛? ]?(.+)")
    valid_start, valid_end = _parse_valid_period(valid_raw)
    valid_period = ''
    if valid_start and valid_end:
        valid_period = f"{valid_start} 鑷?{valid_end}"

    return {
        'name': name,
        'gender': gender,
        'nation': nation,
        'birth_date': birth_date,
        'id_card': id_card,
        'address': address,
        'issuing_authority': issuer,
        'issuer': issuer,
        'valid_period': valid_period,
        'valid_start': valid_start,
        'valid_end': valid_end,
    }


def _mask_idcard(idv: str):
    if not idv:
        return ''
    idv = str(idv)
    if len(idv) <= 8:
        return idv
    return f"{idv[:6]}****{idv[-4:]}"


def _ocr_extract_text(save_path, cfg):
    """Return (text, engine) according to preferred_engine; no cross-engine fallback when set."""
    preferred = (cfg.get('preferred_engine') or '').lower()

    # PaddleOCR only when preferred
    if preferred == 'paddleocr':
        if PADDLE_OCR_AVAILABLE and PaddleOCR is not None:
            try:
                pcfg = cfg.get('paddleocr', {})
                lang = pcfg.get('lang', 'ch')
                use_angle_cls = pcfg.get('use_angle_cls', True)
                ocr_args = pcfg.get('ocr', {}) or {}
                det = ocr_args.get('det', True)
                rec = ocr_args.get('rec', True)
                cls = ocr_args.get('cls', True)

                reader = PaddleOCR(use_angle_cls=use_angle_cls, lang=lang)
                result = reader.ocr(save_path, det=det, rec=rec, cls=cls)

                lines = []
                if isinstance(result, list):
                    for img_res in result:
                        if isinstance(img_res, list):
                            for item in img_res:
                                try:
                                    txt = item[1][0] if isinstance(item[1], (list, tuple)) else None
                                    if txt:
                                        lines.append(str(txt))
                                except Exception:
                                    pass
                text = '\n'.join(lines).strip()
                return text, 'paddleocr'
            except Exception:
                pass
        return '', 'none'

    return '', 'none'


@ocr_bp.route('/ocr/idcard', methods=['POST'])
@token_required
def api_ocr_idcard(current_user):
    """
    韬唤璇丱CR璇嗗埆
    ---
    tags:
      - OCR
    security:
      - Bearer: []
    consumes:
      - multipart/form-data
    parameters:
      - in: formData
        name: image
        type: file
        required: true
        description: 韬唤璇佸浘鐗囨枃浠?      - in: formData
        name: side
        type: string
        default: front
        description: 韬唤璇佹鍙嶉潰 (front/back)
    responses:
      200:
        description: 璇嗗埆鎴愬姛
        schema:
          type: object
          properties:
            engine:
              type: string
            text:
              type: string
            fields:
              type: object
              properties:
                name:
                  type: string
                id_card:
                  type: string
                id_card_masked:
                  type: string
            image_url:
              type: string
      400:
        description: 璇蜂笂浼犲浘鐗囨枃浠?      501:
        description: PaddleOCR鏈畨瑁?    """
    if 'image' not in request.files:
        return jsonify({'error': '请上传图片文件（字段名 image）'}), 400
    side = request.form.get('side', 'front')
    file = request.files['image']
    upload_dir = _ensure_upload_dir()
    filename = datetime.now().strftime('%Y%m%d%H%M%S') + f"_{side}.png"
    save_path = os.path.join(upload_dir, filename)
    file.save(save_path)

    cfg = _load_ocr_config()
    preferred = (cfg.get('preferred_engine') or '').lower()
    if not PADDLE_OCR_AVAILABLE:
        return jsonify({'error': '服务器未安装 PaddleOCR（请先 pip install paddleocr）'}), 501

    text, engine = _ocr_extract_text(save_path, cfg)
    fields = _extract_idcard_fields(text)

    # 鏋勫缓闈欐€佽祫婧?URL
    rel = save_path.replace(os.path.dirname(__file__), '')
    static_url = request.host_url.rstrip('/') + '/static' + rel.replace('\\', '/').replace('/static', '')

    # 璁板綍璇嗗埆鏃ュ織锛堣劚鏁忓鐞嗭紝浠呮墦鍗扮墖娈碉級
    try:
        snippet = (text or '').replace('\n', ' ')[:300]
        current_app.logger.info(
            "OCR engine=%s side=%s name=%s id_card=%s text_snippet=%s image=%s",
            engine,
            side,
            fields.get('name', ''),
            _mask_idcard(fields.get('id_card', '')),
            snippet,
            static_url,
        )
    except Exception:
        pass

    return jsonify({
        'engine': engine,
        'text': text,
        'fields': {
            **fields,
            'id_card_masked': _mask_idcard(fields.get('id_card', '')),
        },
        'image_url': static_url,
    })


def _resolve_uploaded_file_path(image_url):
    if not image_url:
        return ''
    raw = str(image_url).strip()
    parsed = urlparse(raw)
    path = parsed.path if parsed.scheme else raw
    path = path.split('?', 1)[0].replace('\\', '/')
    if not path.startswith('/'):
        path = '/' + path
    if not path.startswith('/static/uploads/'):
        return ''

    base_dir = os.path.abspath(os.path.dirname(__file__))
    static_root = os.path.abspath(os.path.join(base_dir, 'static'))
    full_path = os.path.abspath(os.path.join(base_dir, path.lstrip('/')))
    if not full_path.startswith(static_root):
        return ''
    return full_path


def _to_public_url(image_url):
    value = str(image_url or '').strip()
    if value == '':
        return ''
    if value.startswith('http://') or value.startswith('https://'):
        return value
    if not value.startswith('/'):
        value = '/' + value
    return request.host_url.rstrip('/') + value


@ocr_bp.route('/ocr/idcard/url', methods=['POST'])
@token_required
def api_ocr_idcard_url(current_user):
    data = request.get_json(silent=True) or {}
    image_url = str(data.get('image_url') or '').strip()
    side = str(data.get('side') or 'front').strip().lower()

    if image_url == '':
        return jsonify({'error': 'image_url 不能为空'}), 400
    if side not in ('front', 'back'):
        side = 'front'

    save_path = _resolve_uploaded_file_path(image_url)
    if save_path == '' or (not os.path.exists(save_path)):
        return jsonify({'error': '图片不存在或路径不合法'}), 404

    if not PADDLE_OCR_AVAILABLE:
        return jsonify({'error': '服务器未安装 PaddleOCR'}), 501

    cfg = _load_ocr_config()
    text, engine = _ocr_extract_text(save_path, cfg)
    fields = _extract_idcard_fields(text)

    public_url = _to_public_url(image_url)
    ocr_data = {
        **fields,
        'id_card_masked': _mask_idcard(fields.get('id_card', '')),
    }
    if side == 'front':
        ocr_data['front_img'] = public_url
    else:
        ocr_data['back_img'] = public_url

    try:
        snippet = (text or '').replace('\n', ' ')[:300]
        current_app.logger.info(
            "OCR(url) engine=%s side=%s name=%s id_card=%s text_snippet=%s image=%s",
            engine,
            side,
            fields.get('name', ''),
            _mask_idcard(fields.get('id_card', '')),
            snippet,
            public_url,
        )
    except Exception:
        pass

    return jsonify({
        'engine': engine,
        'text': text,
        'raw_text': text,
        'fields': ocr_data,
        'data': ocr_data,
        'image_url': public_url,
    })
