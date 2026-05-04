import sqlite3
import os
import uuid
import json
from datetime import datetime

from flask import Blueprint, request, jsonify

from auth_api import token_required
from common import connect, parse_fields_arg, parse_pagination_args, paginate_list, project_fields
from room_feature_config import get_room_feature_options


rooms_bp = Blueprint('rooms', __name__, url_prefix='/api')


def _get_rooms_table_columns(conn):
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(rooms)")
    return {row[1] for row in cursor.fetchall()}


def ensure_rooms_schema():
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS rooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            building TEXT,
            floor INTEGER,
            room_no TEXT UNIQUE NOT NULL,
            room_type TEXT,
            price REAL,
            deposit REAL DEFAULT 0,
            status TEXT DEFAULT '空闲',
            description TEXT,
            features_json TEXT DEFAULT '[]',
            water_meter_imgs TEXT DEFAULT '[]',
            water_meter_img TEXT,
            electricity_meter_img TEXT
        )
        """
    )
    room_columns = _get_rooms_table_columns(conn)
    if 'deposit' not in room_columns:
        cursor.execute("ALTER TABLE rooms ADD COLUMN deposit REAL DEFAULT 0")
    if 'features_json' not in room_columns:
        cursor.execute("ALTER TABLE rooms ADD COLUMN features_json TEXT DEFAULT '[]'")
    if 'water_meter_imgs' not in room_columns:
        cursor.execute("ALTER TABLE rooms ADD COLUMN water_meter_imgs TEXT DEFAULT '[]'")
    cursor.execute(
        """
        UPDATE rooms
        SET water_meter_imgs = CASE
            WHEN COALESCE(TRIM(water_meter_imgs), '') = '' AND COALESCE(TRIM(water_meter_img), '') <> ''
            THEN json_array(water_meter_img)
            WHEN COALESCE(TRIM(water_meter_imgs), '') = '' THEN '[]'
            ELSE water_meter_imgs
        END
        """
    )
    conn.commit()
    conn.close()


def _parse_room_features(value):
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    raw = str(value or "").strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return [str(v).strip() for v in data if str(v).strip()]
    except Exception:
        pass
    return [raw]


def _dump_room_features(values):
    return json.dumps(_parse_room_features(values), ensure_ascii=False)


def _parse_room_meter_images(value):
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    raw = str(value or '').strip()
    if not raw:
        return []
    if raw.startswith('['):
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return [str(v).strip() for v in data if str(v).strip()]
        except Exception:
            pass
    return [raw]


def _dump_room_meter_images(values):
    return json.dumps(_parse_room_meter_images(values), ensure_ascii=False)


@rooms_bp.route('/rooms/feature-options', methods=['GET'])
@token_required
def api_get_room_feature_options(current_user):
    return jsonify({'options': get_room_feature_options()})


def _ensure_room_meter_upload_dir():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    upload_dir = os.path.join(base_dir, 'static', 'uploads', 'room_meters')
    os.makedirs(upload_dir, exist_ok=True)
    return upload_dir


def _normalize_building_code(value):
    if value is None:
        return ''
    text = str(value).strip().upper().replace(' ', '')
    if text.endswith('栋') or text.endswith('座'):
        text = text[:-1]
    return text


def _extract_room_number(room_no, building):
    text = '' if room_no is None else str(room_no).strip().upper().replace(' ', '')
    if text == '':
        return ''
    if '-' in text:
        parts = [p for p in text.split('-') if p != '']
        if len(parts) >= 2:
            return parts[-1]
    building_code = _normalize_building_code(building)
    if building_code != '' and text.startswith(building_code):
        suffix = text[len(building_code):].lstrip('-_')
        if suffix != '':
            return suffix
    return text


def _compose_room_no(building, room_no):
    building_code = _normalize_building_code(building)
    number = _extract_room_number(room_no, building_code)
    if building_code != '' and number != '':
        return f'{building_code}-{number}'
    if number != '':
        return number
    return building_code


def _derive_floor(room_no):
    number = ''.join(ch for ch in str(room_no or '') if ch.isdigit())
    if len(number) >= 3:
        try:
            return int(number[:-2])
        except ValueError:
            return 0
    return 0


def _find_room_by_no(conn, room_no_input):
    cursor = conn.cursor()
    text = '' if room_no_input is None else str(room_no_input).strip().upper()
    if text == '':
        return None
    cursor.execute("SELECT id, room_no FROM rooms WHERE UPPER(room_no) = ?", (text,))
    exact = cursor.fetchone()
    if exact:
        return exact
    cursor.execute("SELECT id, room_no FROM rooms WHERE UPPER(room_no) LIKE ?", (f'%-{text}',))
    rows = cursor.fetchall()
    if len(rows) == 1:
        return rows[0]
    return None


def _find_room_matches_by_no(conn, room_no_input):
    cursor = conn.cursor()
    text = '' if room_no_input is None else str(room_no_input).strip().upper()
    if text == '':
        return []
    cursor.execute("SELECT id, room_no FROM rooms WHERE UPPER(room_no) = ?", (text,))
    exact = cursor.fetchall()
    if exact:
        return exact
    cursor.execute("SELECT id, room_no FROM rooms WHERE UPPER(room_no) LIKE ? ORDER BY room_no", (f'%-{text}',))
    return cursor.fetchall()


@rooms_bp.route('/rooms', methods=['GET'])
@token_required
def api_list_rooms(current_user):
    """
    获取房间列表
    ---
    tags:
      - Rooms
    security:
      - Bearer: []
    responses:
      200:
        description: 成功获取房间列表
        schema:
          type: object
          properties:
            rooms:
              type: array
              items:
                type: object
                properties:
                  id:
                    type: integer
                  room_no:
                    type: string
                    description: 纯房号数字部分，如 101
                  room_display:
                    type: string
                    description: 楼栋-房号格式，如 A-101
                  building:
                    type: string
                  room_type:
                    type: string
                  price:
                    type: number
                  status:
                    type: string
                    description: 房间状态 (已入住/空闲)
                  tenant_count:
                    type: integer
    """
    conn = connect()
    room_columns = _get_rooms_table_columns(conn)
    has_description = 'description' in room_columns
    has_deposit = 'deposit' in room_columns
    has_features = 'features_json' in room_columns
    has_water_meter_imgs = 'water_meter_imgs' in room_columns
    has_water_meter_img = 'water_meter_img' in room_columns
    has_electricity_meter_img = 'electricity_meter_img' in room_columns
    cursor = conn.cursor()
    cursor.execute(
        f"""
    SELECT
        r.id,
        r.room_no,
        r.building,
        r.room_type,
        r.price,
        {"COALESCE(r.deposit, 0)" if has_deposit else "0"} AS deposit,
        {"r.description" if has_description else "''"} AS description,
        {"COALESCE(r.features_json, '[]')" if has_features else "'[]'"} AS features_json,
        {"COALESCE(r.water_meter_imgs, '[]')" if has_water_meter_imgs else "'[]'"} AS water_meter_imgs,
        {"COALESCE(r.water_meter_img, '')" if has_water_meter_img else "''"} AS water_meter_img,
        {"COALESCE(r.electricity_meter_img, '')" if has_electricity_meter_img else "''"} AS electricity_meter_img,
        CASE
            WHEN EXISTS (
                SELECT 1 FROM tenants t
                WHERE t.room_id = r.id
                  AND t.status = '在住'
                  AND DATE('now','localtime') BETWEEN t.check_in_date AND t.check_out_date
            ) THEN '已入住'
            ELSE '空闲'
        END AS current_status,
        (SELECT COUNT(*) FROM tenants t
         WHERE t.room_id = r.id
           AND t.status = '在住'
           AND DATE('now','localtime') BETWEEN t.check_in_date AND t.check_out_date) AS tenant_count,
        {"CASE WHEN COALESCE(r.water_meter_imgs, '') <> '[]' OR COALESCE(r.water_meter_img, '') <> '' THEN 1 ELSE 0 END" if has_water_meter_imgs or has_water_meter_img else "0"} AS has_water_meter_img,
        {"CASE WHEN COALESCE(r.electricity_meter_img, '') <> '' THEN 1 ELSE 0 END" if has_electricity_meter_img else "0"} AS has_electricity_meter_img
    FROM rooms r
    ORDER BY r.room_no
    """
    )
    rows = cursor.fetchall()
    conn.close()

    rooms = []
    for row in rows:
        water_meter_imgs = _parse_room_meter_images(row[8])
        if not water_meter_imgs and row[9]:
          water_meter_imgs = _parse_room_meter_images(row[9])
        rooms.append({
            'id': row[0],
            'room_no': _extract_room_number(row[1], row[2]),
            'room_display': _compose_room_no(row[2], row[1]),
            'building': _normalize_building_code(row[2]),
            'room_type': row[3],
            'price': row[4],
            'deposit': row[5],
            'description': row[6],
            'features': _parse_room_features(row[7]),
            'water_meter_imgs': water_meter_imgs,
            'water_meter_img': water_meter_imgs[0] if water_meter_imgs else '',
            'electricity_meter_img': row[10] or '',
            'status': row[11],
            'tenant_count': row[12],
            'has_water_meter_img': bool(row[13]),
            'has_electricity_meter_img': bool(row[14]),
        })

    q = (request.args.get('q') or request.args.get('search') or '').strip().lower()
    status_filter = (request.args.get('status') or '').strip()
    room_type_filter = (request.args.get('room_type') or '').strip()
    sort_by = (request.args.get('sort_by') or '').strip()
    sort_order = (request.args.get('sort_order') or 'asc').strip().lower()

    if q:
        rooms = [
            item
            for item in rooms
            if q in str(item.get('room_no', '')).lower()
            or q in str(item.get('room_display', '')).lower()
            or q in str(item.get('building', '')).lower()
            or q in str(item.get('room_type', '')).lower()
            or q in str(item.get('description', '')).lower()
        ]

    if status_filter:
        rooms = [item for item in rooms if str(item.get('status') or '') == status_filter]

    if room_type_filter:
        rooms = [item for item in rooms if str(item.get('room_type') or '') == room_type_filter]

    if sort_by in ('room_no', 'room_display', 'building', 'room_type', 'price', 'status', 'tenant_count'):
        reverse = sort_order == 'desc'
        rooms.sort(key=lambda x: x.get(sort_by), reverse=reverse)

    total = len(rooms)

    page, page_size, paging_enabled = parse_pagination_args(
        request.args,
        default_page=1,
        default_page_size=20,
        max_page_size=200,
    )
    if paging_enabled:
        rooms, pagination = paginate_list(rooms, page, page_size)
    else:
        pagination = {
            'page': 1,
            'page_size': total if total > 0 else 0,
            'total': total,
            'total_pages': 1,
        }

    allowed_fields = [
        'id',
        'room_no',
        'room_display',
        'building',
        'room_type',
        'price',
        'deposit',
        'description',
        'features',
        'status',
        'tenant_count',
        'water_meter_imgs',
        'water_meter_img',
        'electricity_meter_img',
        'has_water_meter_img',
        'has_electricity_meter_img',
    ]
    selected_fields = parse_fields_arg(request.args, allowed_fields)
    rooms = project_fields(rooms, selected_fields, always_include=['id'])

    return jsonify({'rooms': rooms, 'total': total, 'pagination': pagination})


@rooms_bp.route('/rooms/<int:room_id>', methods=['GET'])
@token_required
def api_get_room(current_user, room_id):
    conn = connect()
    room_columns = _get_rooms_table_columns(conn)
    has_description = 'description' in room_columns
    has_deposit = 'deposit' in room_columns
    has_features = 'features_json' in room_columns
    has_water_meter_imgs = 'water_meter_imgs' in room_columns
    has_water_meter_img = 'water_meter_img' in room_columns
    has_electricity_meter_img = 'electricity_meter_img' in room_columns
    cursor = conn.cursor()
    cursor.execute(
        f"""
        SELECT id, room_no, building, room_type, price,
               {"COALESCE(deposit, 0)" if has_deposit else "0"} AS deposit,
               {"description" if has_description else "''"} AS description,
               {"COALESCE(features_json, '[]')" if has_features else "'[]'"} AS features_json,
               {"COALESCE(water_meter_imgs, '[]')" if has_water_meter_imgs else "'[]'"} AS water_meter_imgs,
               {"water_meter_img" if has_water_meter_img else "''"} AS water_meter_img,
               {"electricity_meter_img" if has_electricity_meter_img else "''"} AS electricity_meter_img
        FROM rooms
        WHERE id = ?
        """,
        (room_id,),
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        return jsonify({'error': f'房间ID {room_id} 不存在'}), 404
    water_meter_imgs = _parse_room_meter_images(row[8])
    if not water_meter_imgs and row[9]:
        water_meter_imgs = _parse_room_meter_images(row[9])
    return jsonify({
        'room': {
            'id': row[0],
            'room_no': _extract_room_number(row[1], row[2]),
            'room_display': _compose_room_no(row[2], row[1]),
            'building': _normalize_building_code(row[2]),
            'room_type': row[3],
            'price': row[4],
            'deposit': row[5],
            'description': row[6],
            'features': _parse_room_features(row[7]),
            'water_meter_imgs': water_meter_imgs,
            'water_meter_img': water_meter_imgs[0] if water_meter_imgs else '',
            'electricity_meter_img': row[10] or '',
            'has_water_meter_img': bool(water_meter_imgs),
            'has_electricity_meter_img': bool(row[10]),
        }
    })


@rooms_bp.route('/rooms/<int:room_id>/meter-image', methods=['GET'])
@token_required
def api_get_room_meter_image(current_user, room_id):
    meter_type = (request.args.get('type') or '').strip().lower()
    if meter_type not in ('water', 'electricity'):
        return jsonify({'error': 'type 参数必须为 water 或 electricity'}), 400
    conn = connect()
    room_columns = _get_rooms_table_columns(conn)
    if meter_type == 'water':
        has_water_meter_imgs = 'water_meter_imgs' in room_columns
        has_water_meter_img = 'water_meter_img' in room_columns
        if not has_water_meter_imgs and not has_water_meter_img:
            conn.close()
            return jsonify({'error': '当前数据库未启用二维码字段'}), 400
    else:
        if 'electricity_meter_img' not in room_columns:
            conn.close()
            return jsonify({'error': '当前数据库未启用二维码字段'}), 400
    cursor = conn.cursor()
    if meter_type == 'water':
        cursor.execute(
            f"SELECT {'water_meter_imgs' if 'water_meter_imgs' in room_columns else '\'[]\''}, {'water_meter_img' if 'water_meter_img' in room_columns else '\'\'\''} FROM rooms WHERE id = ?",
            (room_id,),
        )
    else:
        cursor.execute("SELECT electricity_meter_img FROM rooms WHERE id = ?", (room_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return jsonify({'error': f'房间ID {room_id} 不存在'}), 404
    if meter_type == 'water':
        images = _parse_room_meter_images(row[0])
        if not images and row[1]:
            images = _parse_room_meter_images(row[1])
        if not images:
            return jsonify({'error': '该房间未上传二维码'}), 404
        return jsonify({'images': images, 'image': images[0]})
    image = row[0] or ''
    if not image:
        return jsonify({'error': '该房间未上传二维码'}), 404
    return jsonify({'image': image})


@rooms_bp.route('/rooms/<int:room_id>/meter-image', methods=['POST'])
@token_required
def api_upload_room_meter_image(current_user, room_id):
    meter_type = (request.form.get('type') or '').strip().lower()
    if meter_type not in ('water', 'electricity'):
        return jsonify({'error': 'type 参数必须为 water 或 electricity'}), 400
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
    room_columns = _get_rooms_table_columns(conn)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM rooms WHERE id = ?", (room_id,))
    room = cursor.fetchone()
    if not room:
        conn.close()
        return jsonify({'error': f'房间ID {room_id} 不存在'}), 404

    upload_dir = _ensure_room_meter_upload_dir()
    unique_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{meter_type}_{uuid.uuid4().hex[:8]}{ext}"
    save_path = os.path.join(upload_dir, unique_name)
    file.save(save_path)
    relative_url = f"/static/uploads/room_meters/{unique_name}"
    try:
        if meter_type == 'water':
            existing_images = []
            if 'water_meter_imgs' in room_columns:
                cursor.execute("SELECT water_meter_imgs FROM rooms WHERE id = ?", (room_id,))
                existing_row = cursor.fetchone()
                existing_images = _parse_room_meter_images(existing_row[0] if existing_row else '')
            elif 'water_meter_img' in room_columns:
                cursor.execute("SELECT water_meter_img FROM rooms WHERE id = ?", (room_id,))
                existing_row = cursor.fetchone()
                existing_images = _parse_room_meter_images(existing_row[0] if existing_row else '')
            existing_images.append(relative_url)
            cursor.execute(
                "UPDATE rooms SET water_meter_imgs = ?, water_meter_img = ? WHERE id = ?",
                (_dump_room_meter_images(existing_images), existing_images[0] if existing_images else '', room_id),
            )
        else:
            cursor.execute("UPDATE rooms SET electricity_meter_img = ? WHERE id = ?", (relative_url, room_id))
        conn.commit()
        conn.close()
        if meter_type == 'water':
            return jsonify({'message': '上传成功', 'image': relative_url, 'images': existing_images})
        return jsonify({'message': '上传成功', 'image': relative_url})
    except sqlite3.Error as e:
        conn.close()
        return jsonify({'error': str(e)}), 500


@rooms_bp.route('/rooms/<room_no>/tenants', methods=['GET'])
@token_required
def api_get_room_tenants(current_user, room_no):
    conn = connect()
    room = _find_room_by_no(conn, room_no)
    if not room:
        matches = _find_room_matches_by_no(conn, room_no)
        conn.close()
        if len(matches) > 1:
            options = '、'.join(row[1] for row in matches)
            return jsonify({'error': f'房间 {room_no} 对应多个房间：{options}，请指定完整房间号'}), 400
        return jsonify({'error': f'房间 {room_no} 不存在'}), 404

    room_id = room[0]
    room_no = room[1]
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, name, id_card, phone, gender, check_in_date, check_out_date, status
        FROM tenants
        WHERE room_id = ?
        ORDER BY CASE WHEN status = '在住' THEN 0 ELSE 1 END, check_in_date DESC, id DESC
        """,
        (room_id,),
    )
    tenants_data = cursor.fetchall()
    conn.close()

    tenants = []
    for tenant in tenants_data:
        tenants.append({
            'id': tenant[0],
            'name': tenant[1],
            'id_card': tenant[2],
            'phone': tenant[3],
            'gender': tenant[4],
            'check_in_date': tenant[5],
            'check_out_date': tenant[6],
            'status': tenant[7],
        })

    return jsonify({'tenants': tenants})


@rooms_bp.route('/rooms/<room_no>/checkout', methods=['POST'])
@token_required
def api_checkout_room(current_user, room_no):
    """
    房间一键退租
    ---
    tags:
      - Rooms
    security:
      - Bearer: []
    parameters:
      - in: path
        name: room_no
        type: string
        required: true
        description: 房间号
    responses:
      200:
        description: 退租成功
        schema:
          type: object
          properties:
            message:
              type: string
            tenants:
              type: array
              items:
                type: string
                description: 已退租的租户姓名
      400:
        description: 房间没有在住租户
      404:
        description: 房间不存在
    """
    conn = connect()
    data = request.get_json(silent=True) or {}
    building = data.get('building') or request.args.get('building') or ''
    lookup_room_no = _compose_room_no(building, room_no) if building else room_no
    room = _find_room_by_no(conn, lookup_room_no)
    if not room:
        matches = _find_room_matches_by_no(conn, lookup_room_no)
        conn.close()
        if len(matches) > 1:
            options = '、'.join(row[1] for row in matches)
            return jsonify({'error': f'房间 {room_no} 对应多个房间：{options}，请指定完整房间号'}), 400
        return jsonify({'error': f'房间 {room_no} 不存在'}), 404

    room_id = room[0]
    room_no = room[1]
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM tenants WHERE room_id = ? AND status = '在住'", (room_id,))
    tenants = cursor.fetchall()
    if not tenants:
        conn.close()
        return jsonify({'error': f'房间 {room_no} 没有在住租户'}), 400

    today = datetime.now().strftime('%Y-%m-%d')
    tenant_names = []
    for tenant in tenants:
        tenant_id, tenant_name = tenant
        cursor.execute("UPDATE tenants SET status = '已退租' WHERE id = ?", (tenant_id,))
        tenant_names.append(tenant_name)

    cursor.execute(
        """
    UPDATE rooms
        SET status = CASE
            WHEN EXISTS (
                SELECT 1 FROM tenants t
                WHERE t.room_id = rooms.id
                  AND t.status = '在住'
                  AND DATE('now','localtime') BETWEEN t.check_in_date AND t.check_out_date
            ) THEN '已入住'
            ELSE '空闲'
        END
    WHERE id = ?
    """,
        (room_id,),
    )
    conn.commit()
    conn.close()

    return jsonify({'message': f'房间 {room_no} 已成功退租', 'tenants': tenant_names})


@rooms_bp.route('/rooms', methods=['POST'])
@token_required
def api_add_room(current_user):
    """
    添加新房间
    ---
    tags:
      - Rooms
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        schema:
          type: object
          required:
            - room_no
            - room_type
            - price
          properties:
            room_no:
              type: string
            room_type:
              type: string
            price:
              type: number
            deposit:
              type: number
            building:
              type: string
    responses:
      200:
        description: 房间添加成功
      400:
        description: 缺少必要参数
      500:
        description: 数据库错误
    """
    data = request.json
    if not data or not all(k in data for k in ('room_no', 'room_type', 'price')):
        return jsonify({'error': '缺少必要参数'}), 400

    building = _normalize_building_code(data.get('building', ''))
    room_no = _compose_room_no(building, data.get('room_no', ''))
    floor = _derive_floor(room_no)
    room_type = data['room_type']
    price = data['price']
    deposit = data.get('deposit', 0)
    water_meter_img = data.get('water_meter_img', '')
    electricity_meter_img = data.get('electricity_meter_img', '')
    description = data.get('description', '')
    features_json = _dump_room_features(data.get('features', []))

    conn = connect()
    room_columns = _get_rooms_table_columns(conn)
    cursor = conn.cursor()
    try:
        insert_columns = ['room_no', 'floor', 'room_type', 'price', 'building']
        insert_values = [room_no, floor, room_type, price, building]
        if 'deposit' in room_columns:
            insert_columns.append('deposit')
            insert_values.append(deposit)
        if 'description' in room_columns:
            insert_columns.append('description')
            insert_values.append(description)
        if 'features_json' in room_columns:
            insert_columns.append('features_json')
            insert_values.append(features_json)
        if 'water_meter_img' in room_columns:
            insert_columns.append('water_meter_img')
            insert_values.append(water_meter_img)
        if 'electricity_meter_img' in room_columns:
            insert_columns.append('electricity_meter_img')
            insert_values.append(electricity_meter_img)
        columns_sql = ', '.join(insert_columns)
        placeholders = ', '.join(['?'] * len(insert_columns))
        cursor.execute(
            f"INSERT INTO rooms ({columns_sql}) VALUES ({placeholders})",
            tuple(insert_values),
        )
        room_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return jsonify({'message': f'房间 {room_no} 已添加', 'id': room_id, 'room_no': _extract_room_number(room_no, building), 'room_display': room_no})
    except sqlite3.Error as e:
        conn.close()
        return jsonify({'error': str(e)}), 500


@rooms_bp.route('/rooms/<int:room_id>', methods=['PUT'])
@token_required
def api_update_room(current_user, room_id):
    """
    更新房间信息
    ---
    tags:
      - Rooms
    security:
      - Bearer: []
    parameters:
      - in: path
        name: room_id
        type: integer
        required: true
        description: 房间ID
      - in: body
        name: body
        schema:
          type: object
          properties:
            room_no:
              type: string
            room_type:
              type: string
            price:
              type: number
            deposit:
              type: number
            building:
              type: string
    responses:
      200:
        description: 更新成功
      400:
        description: 参数错误
      404:
        description: 房间不存在
    """
    data = request.json
    if not data:
        return jsonify({'error': '缺少更新数据'}), 400

    conn = connect()
    room_columns = _get_rooms_table_columns(conn)
    allowed_fields = [field for field in ['room_no', 'room_type', 'price', 'deposit', 'building', 'description', 'water_meter_img', 'electricity_meter_img'] if field in room_columns]
    update_data = {k: v for k, v in data.items() if k in allowed_fields}
    if 'features_json' in room_columns and 'features' in data:
        update_data['features_json'] = _dump_room_features(data.get('features', []))

    if not update_data:
        conn.close()
        return jsonify({'error': '没有有效的更新字段'}), 400
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT id FROM rooms WHERE id = ?", (room_id,))
        room = cursor.fetchone()
        if not room:
            conn.close()
            return jsonify({'error': f'房间ID {room_id} 不存在'}), 404

        current_room_no = ''
        current_building = ''
        cursor.execute("SELECT room_no, building FROM rooms WHERE id = ?", (room_id,))
        current_row = cursor.fetchone()
        if current_row:
            current_room_no = current_row[0] or ''
            current_building = current_row[1] or ''

        new_building = _normalize_building_code(update_data.get('building', current_building))
        if 'building' in update_data:
            update_data['building'] = new_building
        if 'room_no' in update_data:
            update_data['room_no'] = _compose_room_no(new_building, update_data.get('room_no'))
        if 'room_no' in update_data and 'floor' in room_columns:
            update_data['floor'] = _derive_floor(update_data['room_no'])
        if (
            'room_no' in update_data
            and str(update_data['room_no']) == str(current_room_no)
            and 'room_no' in update_data
        ):
            update_data.pop('room_no', None)
            if 'floor' in update_data:
                update_data.pop('floor', None)

        if not update_data:
            conn.close()
            return jsonify({'message': '房间信息已更新'})

        for key, value in update_data.items():
            cursor.execute(f"UPDATE rooms SET {key} = ? WHERE id = ?", (value, room_id))

        conn.commit()
        conn.close()
        return jsonify({'message': f'房间信息已更新'})
    except sqlite3.IntegrityError as e:
        conn.close()
        if 'UNIQUE constraint failed: rooms.room_no' in str(e):
            return jsonify({'error': f'房间号已存在'}), 400
        return jsonify({'error': str(e)}), 500
    except sqlite3.Error as e:
        conn.close()
        return jsonify({'error': str(e)}), 500


@rooms_bp.route('/rooms/<int:room_id>', methods=['DELETE'])
@token_required
def api_delete_room(current_user, room_id):
    """
    删除房间
    ---
    tags:
      - Rooms
    security:
      - Bearer: []
    parameters:
      - in: path
        name: room_id
        type: integer
        required: true
        description: 房间ID
    responses:
      200:
        description: 删除成功
      400:
        description: 房间有关联数据（如在住租户）无法删除
      404:
        description: 房间不存在
    """
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("SELECT room_no FROM rooms WHERE id=?", (room_id,))
    room = cursor.fetchone()
    if not room:
        conn.close()
        return jsonify({'error': f'房间ID {room_id} 不存在'}), 404

    room_no = room[0]
    # 仅当房间不存在在住租户时允许删除
    cursor.execute(
        """
        SELECT COUNT(*) FROM tenants
        WHERE room_id = ?
          AND status = '在住'
          AND DATE('now','localtime') BETWEEN check_in_date AND check_out_date
        """,
        (room_id,),
    )
    active_count = cursor.fetchone()[0]
    if active_count > 0:
        conn.close()
        return jsonify({'error': f'房间 {room_no} 有 {active_count} 位在住租户，请先办理退租后再删除'}), 400

    # 额外检查其他关联数据：即使没有在住租户，仍可能有退租租户、搬迁记录或维修记录导致外键约束失败
    cursor.execute("SELECT COUNT(*) FROM tenants WHERE room_id = ?", (room_id,))
    total_tenants = cursor.fetchone()[0]
    cursor.execute(
        "SELECT COUNT(*) FROM tenant_moves WHERE old_room_id = ? OR new_room_id = ?",
        (room_id, room_id),
    )
    moves_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM repair_records WHERE room_no = ?", (room_no,))
    repairs_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM self_checkin_links WHERE room_id = ?", (room_id,))
    self_checkin_links_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM self_checkin_submissions WHERE room_id = ?", (room_id,))
    self_checkin_submissions_count = cursor.fetchone()[0]

    if total_tenants > 0 or moves_count > 0 or repairs_count > 0 or self_checkin_links_count > 0 or self_checkin_submissions_count > 0:
        details = []
        if total_tenants > 0:
            details.append(f"租户档案 {total_tenants} 条（含已退租）")
        if moves_count > 0:
            details.append(f"搬迁记录 {moves_count} 条")
        if repairs_count > 0:
            details.append(f"维修记录 {repairs_count} 条")
        if self_checkin_links_count > 0:
            details.append(f"入住链接 {self_checkin_links_count} 条")
        if self_checkin_submissions_count > 0:
            details.append(f"入住提交记录 {self_checkin_submissions_count} 条")
        conn.close()
        return jsonify({'error': f'房间 {room_no} 存在关联数据，无法删除：' + '；'.join(details) + '。请先清理关联数据后再尝试删除。'}), 400

    try:
        cursor.execute("DELETE FROM rooms WHERE id = ?", (room_id,))
        if cursor.rowcount == 0:
            conn.close()
            return jsonify({'error': f'房间ID {room_id} 不存在'}), 404
        conn.commit()
        conn.close()
        return jsonify({'message': f'房间 {room_no} 已删除'})
    except sqlite3.Error as e:
        conn.close()
        return jsonify({'error': str(e)}), 500
