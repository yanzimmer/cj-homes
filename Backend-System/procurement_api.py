from flask import Blueprint, request, jsonify
from common import connect, parse_fields_arg, parse_pagination_args, project_fields
import sqlite3
import os
import uuid
import json
from datetime import datetime

procurement_bp = Blueprint('procurement_api', __name__)
MAX_PROCUREMENT_IMAGES = 20


def _to_float(value, default=0.0):
    try:
        if value is None or str(value).strip() == '':
            return float(default)
        return float(value)
    except Exception:
        return float(default)


def ensure_procurement_schema():
    conn = connect()
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(procurements)")
    cols = {row[1] for row in cur.fetchall()}
    if "procurement_images" not in cols:
        cur.execute("ALTER TABLE procurements ADD COLUMN procurement_images TEXT")
    if "unit_price" not in cols:
        cur.execute("ALTER TABLE procurements ADD COLUMN unit_price REAL DEFAULT 0")
    conn.commit()
    conn.close()


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

    conn = connect()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    try:
        query_base = "FROM procurements WHERE 1=1"
        params = []

        if search:
            query_base += " AND (item_name LIKE ? OR remarks LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])

        cur.execute(f"SELECT COUNT(*) {query_base}", params)
        total = cur.fetchone()[0]

        total_pages = max(1, (total + page_size - 1) // page_size) if page_size > 0 else 1
        page = max(1, min(page, total_pages))
        offset = (page - 1) * page_size

        query = f"SELECT * {query_base} ORDER BY procurement_date DESC, id DESC LIMIT ? OFFSET ?"
        query_params = params + [page_size, offset]

        cur.execute(query, query_params)
        rows = cur.fetchall()
        procurements = []
        for row in rows:
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
            procurements.append(item)

        allowed_fields = [
            'id', 'procurement_date', 'item_name', 'specification', 'quantity',
            'unit_price', 'unit', 'total_amount', 'remarks',
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
    required_fields = ['procurement_date', 'item_name', 'quantity']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Missing required field: {field}'}), 400
            
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
        cur.execute(
            """
            INSERT INTO procurements (
                procurement_date, item_name, specification, quantity, unit_price, unit, total_amount, remarks, procurement_images
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data['procurement_date'],
                data['item_name'],
                data.get('specification', ''),
                quantity,
                unit_price,
                data.get('unit', ''),
                total_amount,
                data.get('remarks', ''),
                _dump_procurement_images(procurement_images),
            )
        )
        conn.commit()
        return jsonify({'message': 'Procurement created successfully', 'id': cur.lastrowid}), 201
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
                data.get('remarks', ''),
                _dump_procurement_images(procurement_images),
                id
            )
        )
        conn.commit()
        if cur.rowcount == 0:
            return jsonify({'error': 'Procurement not found'}), 404
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

@procurement_bp.route('/api/procurements/<int:id>', methods=['DELETE'])
def delete_procurement(id):
    """Delete a procurement record."""
    conn = connect()
    cur = conn.cursor()
    
    try:
        cur.execute("DELETE FROM procurements WHERE id = ?", (id,))
        conn.commit()
        if cur.rowcount == 0:
            return jsonify({'error': 'Procurement not found'}), 404
        return jsonify({'message': 'Procurement deleted successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()
