from flask import Blueprint, request, jsonify
from common import connect, parse_fields_arg, parse_pagination_args, project_fields
from inventory_sync_service import ensure_inventory_sync_schema, sync_procurement_create, sync_procurement_delete, sync_procurement_update
from local_ai_settings import load_ai_settings
import sqlite3
import os
import uuid
import json
import re
import base64
import urllib.error
import urllib.request
from datetime import datetime

procurement_bp = Blueprint('procurement_api', __name__)
MAX_PROCUREMENT_IMAGES = 20
PURCHASE_CHANNEL_VALUES = {'线上', '线下'}
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
PROCUREMENT_AI_TIMEOUT_SECONDS = int(os.getenv("PROCUREMENT_AI_TIMEOUT_SECONDS", "120"))


def _to_float(value, default=0.0):
    try:
        if value is None or str(value).strip() == '':
            return float(default)
        return float(value)
    except Exception:
        return float(default)


def _to_int_or_float(value, default=0):
    num = _to_float(value, default)
    if float(num).is_integer():
        return int(num)
    return num


def _clean_text(value):
    return str(value or '').strip()


def _today_text():
    return datetime.now().strftime('%Y-%m-%d')


def _extract_json_object(text):
    raw = str(text or '').strip()
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.S | re.I).strip()
    raw = re.sub(r"^```(?:json)?", "", raw, flags=re.I).strip()
    raw = re.sub(r"```$", "", raw).strip()
    try:
        return json.loads(raw)
    except Exception:
        pass

    start = raw.find('{')
    if start < 0:
        raise ValueError('AI 未返回 JSON')
    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(raw)):
        ch = raw[index]
        if in_string:
            if escape:
                escape = False
            elif ch == '\\':
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return json.loads(raw[start:index + 1])
    raise ValueError('AI 返回 JSON 不完整')


def _normalize_ai_procurement_payload(payload):
    data = payload if isinstance(payload, dict) else {}
    items_raw = data.get('items')
    if not isinstance(items_raw, list):
        single_name = data.get('item_name') or data.get('name')
        items_raw = [
            {
                'item_name': single_name,
                'specification': data.get('specification'),
                'quantity': data.get('quantity'),
                'unit_price': data.get('unit_price'),
                'unit': data.get('unit'),
            }
        ]

    items = []
    for item in items_raw:
        if not isinstance(item, dict):
            continue
        name = _clean_text(item.get('item_name') or item.get('name'))
        if not name:
            continue
        quantity = _to_int_or_float(item.get('quantity'), 1)
        if quantity <= 0:
            quantity = 1
        unit_price = round(_to_float(item.get('unit_price'), 0), 2)
        items.append({
            'item_name': name,
            'specification': _clean_text(item.get('specification')),
            'quantity': quantity,
            'unit_price': unit_price,
            'unit': _clean_text(item.get('unit') or '个'),
        })

    if not items:
        items = [{
            'item_name': '',
            'specification': '',
            'quantity': 1,
            'unit_price': 0,
            'unit': '个',
        }]

    total_amount = round(_to_float(data.get('total_amount'), 0), 2)
    if total_amount <= 0:
        total_amount = round(sum(_to_float(item.get('quantity'), 0) * _to_float(item.get('unit_price'), 0) for item in items), 2)

    return {
        'purchase_mode': 'multi' if len(items) > 1 else 'single',
        'purchase_channel': _normalize_purchase_channel(data.get('purchase_channel')),
        'procurement_date': _clean_text(data.get('procurement_date')) or _today_text(),
        'total_amount': total_amount,
        'payment_person': _clean_text(data.get('payment_person')),
        'remarks': _clean_text(data.get('remarks')),
        'items': items,
    }


def _build_procurement_ai_prompt(user_text, image_count):
    today = _today_text()
    return f"""
你是房屋管理系统的采购录入助手。请从用户文字和图片中提取采购信息，只返回一个 JSON 对象，不要解释，不要 Markdown。

今天日期：{today}
图片数量：{image_count}

输出 JSON 格式：
{{
  "purchase_channel": "线上或线下",
  "procurement_date": "YYYY-MM-DD",
  "total_amount": 0,
  "payment_person": "",
  "remarks": "",
  "items": [
    {{
      "item_name": "采购物品名称",
      "specification": "规格型号",
      "quantity": 1,
      "unit_price": 0,
      "unit": "个"
    }}
  ]
}}

规则：
- 采购渠道只能是“线上”或“线下”；无法判断时用“线下”。
- 日期无法判断时用今天日期。
- 图片如果是收据、购物截图、发票、聊天记录或手写单据，请识别其中物品、数量、金额、支付人、备注。
- 单价不知道就填 0；总金额知道就填 total_amount。
- 多个物品放到 items 数组。
- 所有数字只用数字，不要单位符号。

用户文字：
{_clean_text(user_text)}
""".strip()


def _call_ollama_generate(prompt, images):
    settings = load_ai_settings()
    model = settings.get('procurement_model') or os.getenv("PROCUREMENT_AI_MODEL", "qwen3.5:4b")
    ollama_base_url = settings.get('ollama_base_url') or OLLAMA_BASE_URL
    payload = {
        'model': model,
        'prompt': prompt,
        'stream': False,
        'think': False,
        'options': {
            'temperature': 0,
        },
    }
    if images:
        payload['images'] = images
    req = urllib.request.Request(
        f"{ollama_base_url.rstrip('/')}/api/generate",
        data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=PROCUREMENT_AI_TIMEOUT_SECONDS) as resp:
            body = resp.read().decode('utf-8')
            return json.loads(body)
    except urllib.error.URLError as e:
        raise RuntimeError(f"Ollama 连接失败: {e}") from e


def ensure_procurement_schema():
    conn = connect()
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(procurements)")
    cols = {row[1] for row in cur.fetchall()}
    if "procurement_images" not in cols:
        cur.execute("ALTER TABLE procurements ADD COLUMN procurement_images TEXT")
    if "unit_price" not in cols:
        cur.execute("ALTER TABLE procurements ADD COLUMN unit_price REAL DEFAULT 0")
    if "payment_person" not in cols:
        cur.execute("ALTER TABLE procurements ADD COLUMN payment_person TEXT")
    if "purchase_channel" not in cols:
        cur.execute("ALTER TABLE procurements ADD COLUMN purchase_channel TEXT DEFAULT '线下'")
    if "purchase_batch_no" not in cols:
        cur.execute("ALTER TABLE procurements ADD COLUMN purchase_batch_no TEXT")
    conn.commit()
    conn.close()
    ensure_inventory_sync_schema()


def _normalize_purchase_channel(value):
    text = str(value or '').strip()
    return text if text in PURCHASE_CHANNEL_VALUES else '线下'


def _next_batch_no(conn, procurement_date, purchase_channel):
    channel = _normalize_purchase_channel(purchase_channel)
    day = str(procurement_date or '').replace('-', '')
    prefix = 'CGXS' if channel == '线上' else 'CGXX'
    like_value = f'{prefix}-{day}-%'
    cur = conn.cursor()
    cur.execute(
        """
        SELECT purchase_batch_no
        FROM procurements
        WHERE purchase_batch_no LIKE ?
        ORDER BY purchase_batch_no DESC
        LIMIT 1
        """,
        (like_value,),
    )
    row = cur.fetchone()
    seq = 1
    if row and row[0]:
        try:
            seq = int(str(row[0]).split('-')[-1]) + 1
        except Exception:
            seq = 1
    return f'{prefix}-{day}-{seq:03d}'


def _ensure_procurement_upload_dir():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    upload_dir = os.path.join(base_dir, 'static', 'uploads', 'procurements')
    os.makedirs(upload_dir, exist_ok=True)
    return upload_dir


def _parse_procurement_images(value):
    if value is None:
        return []
    text = str(value).strip()
    if text == "":
        return []
    if text.startswith("["):
        try:
            arr = json.loads(text)
            if isinstance(arr, list):
                result = []
                for item in arr:
                    item_text = str(item).strip()
                    if item_text != "":
                        result.append(item_text)
                return result[:MAX_PROCUREMENT_IMAGES]
        except Exception:
            pass
    return [text]


def _dump_procurement_images(images):
    clean = []
    for item in images:
        text = str(item).strip()
        if text != "":
            clean.append(text)
    return json.dumps(clean[:MAX_PROCUREMENT_IMAGES], ensure_ascii=False)


def _extract_procurement_images_from_payload(data):
    if data is None:
        return []
    raw = data.get('procurement_images')
    if isinstance(raw, list):
        return _parse_procurement_images(json.dumps(raw, ensure_ascii=False))
    raw_single = data.get('procurement_image')
    return _parse_procurement_images(raw_single)


def _procurement_row_to_dict(row):
    item = dict(row)
    quantity = _to_float(item.get('quantity'), 0)
    total_amount = _to_float(item.get('total_amount'), 0)
    unit_price = _to_float(item.get('unit_price'), 0)
    if unit_price <= 0 and quantity > 0:
        unit_price = total_amount / quantity
    item['unit_price'] = unit_price
    images = _parse_procurement_images(item.get('procurement_images'))
    item['procurement_images'] = images
    item['procurement_image'] = images[0] if len(images) > 0 else ''
    return item


def _group_procurements(procurements):
    groups = []
    group_map = {}
    for item in procurements:
        batch_no = str(item.get('purchase_batch_no') or '').strip() or f"SINGLE-{item.get('id')}"
        if batch_no not in group_map:
            summary = {
                'id': batch_no,
                'purchase_batch_no': item.get('purchase_batch_no') or '',
                'procurement_date': item.get('procurement_date') or '',
                'purchase_channel': item.get('purchase_channel') or '',
                'payment_person': item.get('payment_person') or '',
                'remarks': item.get('remarks') or '',
                'item_count': 0,
                'total_amount': 0,
                'item_summary': '',
                'items': [],
            }
            group_map[batch_no] = summary
            groups.append(summary)
        summary = group_map[batch_no]
        summary['items'].append(item)
        summary['item_count'] += 1
        summary['total_amount'] = round(_to_float(summary['total_amount'], 0) + _to_float(item.get('total_amount'), 0), 2)
        if not summary['remarks'] and item.get('remarks'):
            summary['remarks'] = item.get('remarks')
        if not summary['payment_person'] and item.get('payment_person'):
            summary['payment_person'] = item.get('payment_person')

    for summary in groups:
        names = [str(item.get('item_name') or '').strip() for item in summary['items'] if str(item.get('item_name') or '').strip()]
        if len(names) <= 2:
            summary['item_summary'] = '、'.join(names)
        else:
            summary['item_summary'] = f"{'、'.join(names[:2])} 等{len(names)}项"
    return groups


@procurement_bp.route('/api/procurements/ai-draft', methods=['POST'])
def create_procurement_ai_draft():
    if not load_ai_settings().get('enabled', True):
        return jsonify({'error': '本地 AI 功能已停用，请在系统维护页面启用后再使用'}), 503

    user_text = ''
    images = []

    if request.content_type and request.content_type.startswith('multipart/form-data'):
        user_text = request.form.get('text') or ''
        for file in request.files.getlist('images'):
            if not file or not file.filename:
                continue
            if not str(file.mimetype or '').startswith('image/'):
                return jsonify({'error': '仅支持图片文件'}), 400
            data = file.read()
            if len(data) > 8 * 1024 * 1024:
                return jsonify({'error': '单张图片请控制在 8MB 以内'}), 400
            images.append(base64.b64encode(data).decode('ascii'))
    else:
        data = request.json or {}
        user_text = data.get('text') or ''
        raw_images = data.get('images') or []
        if isinstance(raw_images, list):
            for item in raw_images[:4]:
                value = str(item or '').strip()
                if value.startswith('data:image/') and ',' in value:
                    value = value.split(',', 1)[1]
                if value:
                    images.append(value)

    if not _clean_text(user_text) and not images:
        return jsonify({'error': '请提供文字或图片'}), 400
    if len(images) > 4:
        return jsonify({'error': '最多支持 4 张图片'}), 400

    prompt = _build_procurement_ai_prompt(user_text, len(images))
    try:
        result = _call_ollama_generate(prompt, images)
        response_text = result.get('response') or ''
        parsed = _extract_json_object(response_text)
        draft = _normalize_ai_procurement_payload(parsed)
        return jsonify({
            'draft': draft,
            'model': load_ai_settings().get('procurement_model'),
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 502


@procurement_bp.route('/api/procurements', methods=['GET'])
def list_procurements():
    """List procurements with search and pagination."""
    page, page_size, _ = parse_pagination_args(
        request.args,
        default_page=1,
        default_page_size=10,
        max_page_size=200,
    )
    search = (request.args.get('search') or '').strip()
    grouped_mode = str(request.args.get('grouped') or '').strip().lower() in {'1', 'true', 'yes', 'order', 'batch'}

    conn = connect()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    try:
        query_base = "FROM procurements WHERE 1=1"
        params = []

        if search:
            query_base += " AND (item_name LIKE ? OR remarks LIKE ? OR purchase_batch_no LIKE ? OR purchase_channel LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%", f"%{search}%", f"%{search}%"])

        cur.execute(f"SELECT * {query_base} ORDER BY procurement_date DESC, id DESC", params)
        rows = cur.fetchall()
        procurements = [_procurement_row_to_dict(row) for row in rows]

        if grouped_mode:
            grouped_rows = _group_procurements(procurements)
            total = len(grouped_rows)
            total_pages = max(1, (total + page_size - 1) // page_size) if page_size > 0 else 1
            page = max(1, min(page, total_pages))
            offset = (page - 1) * page_size
            paged_groups = grouped_rows[offset:offset + page_size]
            return jsonify({
                'procurement_orders': paged_groups,
                'total': total,
                'page': page,
                'page_size': page_size,
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total': total,
                    'total_pages': total_pages,
                },
            })

        total = len(procurements)
        total_pages = max(1, (total + page_size - 1) // page_size) if page_size > 0 else 1
        page = max(1, min(page, total_pages))
        offset = (page - 1) * page_size
        procurements = procurements[offset:offset + page_size]

        allowed_fields = [
            'id', 'procurement_date', 'item_name', 'specification', 'quantity',
            'unit_price', 'unit', 'total_amount', 'payment_person', 'purchase_channel', 'purchase_batch_no', 'remarks',
            'procurement_images', 'procurement_image', 'created_at', 'updated_at'
        ]
        selected_fields = parse_fields_arg(request.args, allowed_fields)
        procurements = project_fields(procurements, selected_fields, always_include=['id'])

        return jsonify({
            'procurements': procurements,
            'total': total,
            'page': page,
            'page_size': page_size,
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total': total,
                'total_pages': total_pages,
            },
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@procurement_bp.route('/api/procurements', methods=['POST'])
def create_procurement():
    """Create a new procurement record."""
    data = request.json
    items = data.get('items') if isinstance(data, dict) else None
    procurement_images = _extract_procurement_images_from_payload(data)

    conn = connect()
    cur = conn.cursor()
    
    try:
        purchase_channel = _normalize_purchase_channel(data.get('purchase_channel'))
        if isinstance(items, list) and len(items) > 0:
            procurement_date = data.get('procurement_date')
            if not procurement_date:
                return jsonify({'error': 'Missing required field: procurement_date'}), 400
            total_amount = _to_float(data.get('total_amount'), 0)
            batch_no = _next_batch_no(conn, procurement_date, purchase_channel)

            normalized_items = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                item_name = str(item.get('item_name') or '').strip()
                quantity = _to_float(item.get('quantity'), 0)
                unit = str(item.get('unit') or '').strip()
                unit_price = _to_float(item.get('unit_price'), 0)
                if not item_name or quantity <= 0 or not unit:
                    return jsonify({'error': '多物品采购单里的每个物品都必须填写采购物品、数量和单位'}), 400
                normalized_items.append(
                    {
                        'item_name': item_name,
                        'specification': str(item.get('specification') or '').strip(),
                        'quantity': quantity,
                        'unit': unit,
                        'unit_price': unit_price,
                    }
                )
            if not normalized_items:
                return jsonify({'error': 'items 不能为空'}), 400

            if total_amount <= 0:
                total_amount = round(
                    sum(_to_float(item.get('quantity'), 0) * _to_float(item.get('unit_price'), 0) for item in normalized_items),
                    2
                )
            if total_amount <= 0:
                return jsonify({'error': 'Missing required field: total_amount'}), 400

            created_ids = []
            has_any_unit_price = any(item['unit_price'] > 0 for item in normalized_items)
            allocated_total = 0.0
            for index, item in enumerate(normalized_items):
                if has_any_unit_price:
                    unit_price = item['unit_price']
                    line_total = round(item['quantity'] * unit_price, 2)
                else:
                    split_total = round(total_amount / len(normalized_items), 2)
                    line_total = split_total if index < len(normalized_items) - 1 else round(total_amount - allocated_total, 2)
                    unit_price = round(line_total / item['quantity'], 2) if item['quantity'] > 0 else 0
                    allocated_total += line_total
                cur.execute(
                    """
                    INSERT INTO procurements (
                        procurement_date, item_name, specification, quantity, unit_price, unit, total_amount, payment_person, purchase_channel, purchase_batch_no, remarks, procurement_images
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        procurement_date,
                        item['item_name'],
                        item['specification'],
                        item['quantity'],
                        unit_price,
                        item['unit'],
                        line_total,
                        data.get('payment_person', ''),
                        purchase_channel,
                        batch_no,
                        data.get('remarks', ''),
                        _dump_procurement_images(procurement_images),
                    )
                )
                procurement_id = cur.lastrowid
                created_ids.append(procurement_id)
                sync_procurement_create(
                    conn,
                    procurement_id,
                    procurement_date,
                    item['item_name'],
                    item['specification'],
                    item['quantity'],
                    unit_price,
                    item['unit'],
                )
            conn.commit()
            return jsonify({'message': 'Procurement created successfully', 'ids': created_ids, 'count': len(created_ids)}), 201
        else:
            required_fields = ['procurement_date', 'item_name', 'quantity']
            for field in required_fields:
                if field not in data:
                    return jsonify({'error': f'Missing required field: {field}'}), 400

            quantity = _to_float(data.get('quantity'), 0)
            unit_price = _to_float(data.get('unit_price'), 0)
            total_amount = _to_float(data.get('total_amount'), 0)
            if unit_price <= 0 and quantity > 0 and total_amount > 0:
                unit_price = total_amount / quantity
            if total_amount <= 0 and quantity > 0 and unit_price > 0:
                total_amount = quantity * unit_price
            batch_no = _next_batch_no(conn, data['procurement_date'], purchase_channel)

            cur.execute(
                """
                INSERT INTO procurements (
                    procurement_date, item_name, specification, quantity, unit_price, unit, total_amount, payment_person, purchase_channel, purchase_batch_no, remarks, procurement_images
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    data['procurement_date'],
                    data['item_name'],
                    data.get('specification', ''),
                    quantity,
                    unit_price,
                    data.get('unit', ''),
                    total_amount,
                    data.get('payment_person', ''),
                    purchase_channel,
                    batch_no,
                    data.get('remarks', ''),
                    _dump_procurement_images(procurement_images),
                )
            )
            procurement_id = cur.lastrowid
            sync_procurement_create(
                conn,
                procurement_id,
                data['procurement_date'],
                data['item_name'],
                data.get('specification', ''),
                quantity,
                unit_price,
                data.get('unit', ''),
            )
            conn.commit()
            return jsonify({'message': 'Procurement created successfully', 'id': procurement_id}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@procurement_bp.route('/api/procurements/<int:id>', methods=['PUT'])
def update_procurement(id):
    """Update an existing procurement record."""
    data = request.json
    
    procurement_images = _extract_procurement_images_from_payload(data)
    quantity = _to_float(data.get('quantity'), 0)
    unit_price = _to_float(data.get('unit_price'), 0)
    total_amount = _to_float(data.get('total_amount'), 0)
    if unit_price <= 0 and quantity > 0 and total_amount > 0:
        unit_price = total_amount / quantity
    if total_amount <= 0 and quantity > 0 and unit_price > 0:
        total_amount = quantity * unit_price

    conn = connect()
    cur = conn.cursor()
    
    try:
        purchase_channel = _normalize_purchase_channel(data.get('purchase_channel'))
        cur.execute(
            """
            SELECT id, procurement_date, item_name, specification, quantity, unit_price, unit, total_amount, remarks, warehouse_item_id, purchase_channel, purchase_batch_no
            FROM procurements
            WHERE id = ?
            """,
            (id,),
        )
        existing = cur.fetchone()
        if not existing:
            return jsonify({'error': 'Procurement not found'}), 404
        batch_no = existing[11] or _next_batch_no(conn, data['procurement_date'], purchase_channel)
        cur.execute(
            """
            UPDATE procurements SET
                procurement_date = ?,
                item_name = ?,
                specification = ?,
                quantity = ?,
                unit_price = ?,
                unit = ?,
                total_amount = ?,
                payment_person = ?,
                purchase_channel = ?,
                purchase_batch_no = ?,
                remarks = ?,
                procurement_images = ?,
                updated_at = DATETIME('now')
            WHERE id = ?
            """,
            (
                data['procurement_date'],
                data['item_name'],
                data.get('specification', ''),
                quantity,
                unit_price,
                data.get('unit', ''),
                total_amount,
                data.get('payment_person', ''),
                purchase_channel,
                batch_no,
                data.get('remarks', ''),
                _dump_procurement_images(procurement_images),
                id
            )
        )
        sync_procurement_update(
            conn,
            existing,
            data['procurement_date'],
            data['item_name'],
            data.get('specification', ''),
            quantity,
            unit_price,
            data.get('unit', ''),
        )
        conn.commit()
        return jsonify({'message': 'Procurement updated successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


@procurement_bp.route('/api/procurements/<int:id>/image', methods=['POST'])
def upload_procurement_image(id):
    if 'file' not in request.files:
        return jsonify({'error': '请上传图片文件（字段名 file）'}), 400
    file = request.files['file']
    if file.filename is None or str(file.filename).strip() == '':
        return jsonify({'error': '文件名无效'}), 400
    filename = str(file.filename)
    ext = os.path.splitext(filename)[1].lower()
    if ext == '':
        ext = '.png'
    if ext not in ('.png', '.jpg', '.jpeg', '.webp', '.avif'):
        return jsonify({'error': '仅支持 png/jpg/jpeg/webp/avif 图片'}), 400

    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT id, procurement_images FROM procurements WHERE id = ?", (id,))
    record = cur.fetchone()
    if not record:
        conn.close()
        return jsonify({'error': 'Procurement not found'}), 404

    upload_dir = _ensure_procurement_upload_dir()
    unique_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{id}_{uuid.uuid4().hex[:8]}{ext}"
    save_path = os.path.join(upload_dir, unique_name)
    file.save(save_path)
    relative_url = f"/static/uploads/procurements/{unique_name}"
    current_images = _parse_procurement_images(record[1] if len(record) > 1 else "")
    if len(current_images) >= MAX_PROCUREMENT_IMAGES:
        if os.path.exists(save_path):
            os.remove(save_path)
        conn.close()
        return jsonify({'error': f'最多仅支持上传 {MAX_PROCUREMENT_IMAGES} 张图片'}), 400
    current_images.append(relative_url)

    try:
        cur.execute("UPDATE procurements SET procurement_images = ? WHERE id = ?", (_dump_procurement_images(current_images), id))
        conn.commit()
        conn.close()
        return jsonify({
            'message': '上传成功',
            'procurement_images': current_images,
            'procurement_image': current_images[0] if len(current_images) > 0 else '',
        })
    except Exception as e:
        conn.close()
        return jsonify({'error': str(e)}), 500


@procurement_bp.route('/api/procurements/<int:id>/images', methods=['PUT'])
def update_procurement_images(id):
    data = request.json if isinstance(request.json, dict) else {}
    procurement_images = _extract_procurement_images_from_payload(data)

    conn = connect()
    cur = conn.cursor()

    try:
        cur.execute("SELECT id FROM procurements WHERE id = ?", (id,))
        record = cur.fetchone()
        if not record:
            return jsonify({'error': 'Procurement not found'}), 404

        cur.execute(
            """
            UPDATE procurements
            SET procurement_images = ?, updated_at = DATETIME('now')
            WHERE id = ?
            """,
            (_dump_procurement_images(procurement_images), id),
        )
        conn.commit()
        return jsonify({
            'message': 'Procurement images updated successfully',
            'procurement_images': procurement_images,
            'procurement_image': procurement_images[0] if len(procurement_images) > 0 else '',
        })
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@procurement_bp.route('/api/procurements/<int:id>', methods=['DELETE'])
def delete_procurement(id):
    """Delete a procurement record."""
    conn = connect()
    cur = conn.cursor()
    
    try:
        cur.execute(
            """
            SELECT id, procurement_date, item_name, specification, quantity, unit_price, unit, total_amount, remarks, warehouse_item_id
            FROM procurements
            WHERE id = ?
            """,
            (id,),
        )
        existing = cur.fetchone()
        if not existing:
            return jsonify({'error': 'Procurement not found'}), 404
        sync_procurement_delete(conn, existing)
        cur.execute("DELETE FROM procurements WHERE id = ?", (id,))
        conn.commit()
        return jsonify({'message': 'Procurement deleted successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()
