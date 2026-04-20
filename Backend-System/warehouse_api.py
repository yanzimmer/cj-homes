import sqlite3
import json
from flask import Blueprint, request, jsonify

from auth_api import token_required
from common import connect, parse_fields_arg, parse_pagination_args, project_fields


warehouse_bp = Blueprint('warehouse', __name__, url_prefix='/api')
MAX_WAREHOUSE_IMAGES = 20


def _parse_warehouse_images(value):
    if value is None:
        return []
    text = str(value).strip()
    if text == '':
        return []
    if text.startswith('['):
        try:
            arr = json.loads(text)
            if isinstance(arr, list):
                result = []
                for item in arr:
                    item_text = str(item).strip()
                    if item_text != '':
                        result.append(item_text)
                return result[:MAX_WAREHOUSE_IMAGES]
        except Exception:
            pass
    return [text]


def _dump_warehouse_images(images):
    clean = []
    for item in images:
        text = str(item).strip()
        if text != '':
            clean.append(text)
    return json.dumps(clean[:MAX_WAREHOUSE_IMAGES], ensure_ascii=False)


def _extract_warehouse_images_from_payload(data):
    if data is None:
        return []
    raw = data.get('images')
    if isinstance(raw, list):
        return _parse_warehouse_images(json.dumps(raw, ensure_ascii=False))
    raw_single = data.get('image')
    return _parse_warehouse_images(raw_single)


def ensure_warehouse_schema():
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
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
    conn.commit()
    conn.close()


@warehouse_bp.route('/warehouse-items', methods=['GET'])
@token_required
def list_warehouse_items(current_user):
    q = (request.args.get('q') or '').strip().lower()

    page, page_size, paging_enabled = parse_pagination_args(
        request.args,
        default_page=1,
        default_page_size=20,
        max_page_size=200,
    )

    conn = connect()
    cursor = conn.cursor()

    where_clause = ''
    where_params = []
    if q:
        where_clause = """
            WHERE LOWER(COALESCE(item_name, '')) LIKE ?
               OR LOWER(COALESCE(category, '')) LIKE ?
               OR LOWER(COALESCE(location, '')) LIKE ?
               OR LOWER(COALESCE(remarks, '')) LIKE ?
        """
        where_params = [f'%{q}%', f'%{q}%', f'%{q}%', f'%{q}%']

    cursor.execute("SELECT COUNT(*) FROM warehouse_items")
    total = cursor.fetchone()[0]

    cursor.execute(f"SELECT COUNT(*) FROM warehouse_items {where_clause}", tuple(where_params))
    filtered_total = cursor.fetchone()[0]

    total_pages = max(1, (filtered_total + page_size - 1) // page_size) if page_size > 0 else 1
    page = max(1, min(page, total_pages))

    query = f"""
        SELECT id, item_name, category, quantity, unit, location, image, remarks, created_at, updated_at
        FROM warehouse_items
        {where_clause}
        ORDER BY id DESC
    """
    query_params = list(where_params)
    if paging_enabled:
        offset = (page - 1) * page_size
        query += " LIMIT ? OFFSET ?"
        query_params.extend([page_size, offset])

    cursor.execute(query, tuple(query_params))
    rows = cursor.fetchall()
    conn.close()

    items = [
        (lambda images: {
            'id': row[0],
            'item_name': row[1],
            'category': row[2] or '',
            'quantity': row[3],
            'unit': row[4] or '',
            'location': row[5] or '',
            'image': images[0] if len(images) > 0 else '',
            'images': images,
            'remarks': row[7] or '',
            'created_at': row[8],
            'updated_at': row[9],
            'has_image': len(images) > 0,
        })(_parse_warehouse_images(row[6]))
        for row in rows
    ]

    allowed_fields = [
        'id', 'item_name', 'category', 'quantity', 'unit', 'location',
        'image', 'images', 'remarks', 'created_at', 'updated_at', 'has_image'
    ]
    selected_fields = parse_fields_arg(request.args, allowed_fields)
    items = project_fields(items, selected_fields, always_include=['id'])

    pagination = {
        'page': page,
        'page_size': page_size if paging_enabled else filtered_total,
        'total': filtered_total,
        'total_pages': total_pages if paging_enabled else 1,
    }

    return jsonify({'items': items, 'total': total, 'filtered_total': filtered_total, 'pagination': pagination})


@warehouse_bp.route('/warehouse-items/<int:item_id>', methods=['GET'])
@token_required
def get_warehouse_item(current_user, item_id):
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, item_name, category, quantity, unit, location, image, remarks, created_at, updated_at
        FROM warehouse_items
        WHERE id = ?
        """,
        (item_id,),
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        return jsonify({'error': f'库房物资ID {item_id} 不存在'}), 404
    images = _parse_warehouse_images(row[6])
    return jsonify(
        {
            'item': {
                'id': row[0],
                'item_name': row[1],
                'category': row[2] or '',
                'quantity': row[3],
                'unit': row[4] or '',
                'location': row[5] or '',
                'image': images[0] if len(images) > 0 else '',
                'images': images,
                'remarks': row[7] or '',
                'created_at': row[8],
                'updated_at': row[9],
                'has_image': len(images) > 0,
            }
        }
    )


@warehouse_bp.route('/warehouse-items', methods=['POST'])
@token_required
def create_warehouse_item(current_user):
    data = request.json or {}
    item_name = (data.get('item_name') or '').strip()
    quantity = data.get('quantity', 0)
    if not item_name:
        return jsonify({'error': '物资名称不能为空'}), 400
    try:
        quantity = float(quantity)
    except (TypeError, ValueError):
        return jsonify({'error': '库存数量格式不正确'}), 400
    if quantity < 0:
        return jsonify({'error': '库存数量不能小于0'}), 400
    category = (data.get('category') or '').strip()
    unit = (data.get('unit') or '').strip()
    location = (data.get('location') or '').strip()
    images = _extract_warehouse_images_from_payload(data)
    remarks = (data.get('remarks') or '').strip()

    conn = connect()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO warehouse_items (item_name, category, quantity, unit, location, image, remarks, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, DATETIME('now'), DATETIME('now'))
            """,
            (item_name, category, quantity, unit, location, _dump_warehouse_images(images), remarks),
        )
        item_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return jsonify({'message': '库房物资新增成功', 'id': item_id}), 200
    except sqlite3.Error as e:
        conn.close()
        return jsonify({'error': str(e)}), 500


@warehouse_bp.route('/warehouse-items/<int:item_id>', methods=['PUT'])
@token_required
def update_warehouse_item(current_user, item_id):
    data = request.json or {}
    allowed_fields = ['item_name', 'category', 'quantity', 'unit', 'location', 'image', 'images', 'remarks']
    update_data = {k: data.get(k) for k in allowed_fields if k in data}
    if not update_data:
        return jsonify({'error': '没有可更新的字段'}), 400
    if 'item_name' in update_data:
        update_data['item_name'] = (update_data['item_name'] or '').strip()
        if not update_data['item_name']:
            return jsonify({'error': '物资名称不能为空'}), 400
    if 'quantity' in update_data:
        try:
            update_data['quantity'] = float(update_data['quantity'])
        except (TypeError, ValueError):
            return jsonify({'error': '库存数量格式不正确'}), 400
        if update_data['quantity'] < 0:
            return jsonify({'error': '库存数量不能小于0'}), 400
    for text_field in ('category', 'unit', 'location', 'remarks'):
        if text_field in update_data:
            update_data[text_field] = (update_data[text_field] or '').strip()
    if 'images' in update_data or 'image' in update_data:
        update_data['image'] = _dump_warehouse_images(_extract_warehouse_images_from_payload(data))
        if 'images' in update_data:
            del update_data['images']

    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM warehouse_items WHERE id = ?", (item_id,))
    exists = cursor.fetchone()
    if not exists:
        conn.close()
        return jsonify({'error': f'库房物资ID {item_id} 不存在'}), 404
    try:
        for key, value in update_data.items():
            cursor.execute(f"UPDATE warehouse_items SET {key} = ? WHERE id = ?", (value, item_id))
        cursor.execute("UPDATE warehouse_items SET updated_at = DATETIME('now') WHERE id = ?", (item_id,))
        conn.commit()
        conn.close()
        return jsonify({'message': '库房物资更新成功'})
    except sqlite3.Error as e:
        conn.close()
        return jsonify({'error': str(e)}), 500


@warehouse_bp.route('/warehouse-items/<int:item_id>', methods=['DELETE'])
@token_required
def delete_warehouse_item(current_user, item_id):
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM warehouse_items WHERE id = ?", (item_id,))
    if cursor.rowcount == 0:
        conn.close()
        return jsonify({'error': f'库房物资ID {item_id} 不存在'}), 404
    conn.commit()
    conn.close()
    return jsonify({'message': '库房物资删除成功'})
