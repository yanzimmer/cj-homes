import sqlite3
from datetime import date

from flask import Blueprint, request, jsonify

from auth_api import token_required
from common import connect, parse_fields_arg, parse_pagination_args, paginate_list, project_fields


tenants_bp = Blueprint('tenants', __name__, url_prefix='/api')


def _refresh_tenant_statuses(conn):
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE tenants
        SET status = CASE
            WHEN check_out_date IS NOT NULL
              AND TRIM(check_out_date) <> ''
              AND DATE('now') >= DATE(check_out_date)
            THEN '已退租'
            ELSE '在住'
        END
        """
    )


def _refresh_room_statuses(conn):
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE rooms
        SET status = CASE
            WHEN EXISTS (
                SELECT 1 FROM tenants t
                WHERE t.room_id = rooms.id
                  AND t.status = '在住'
                  AND DATE('now') BETWEEN t.check_in_date AND t.check_out_date
            ) THEN '已入住'
            ELSE '空闲'
        END
        """
    )


@tenants_bp.route('/tenants', methods=['GET'])
@token_required
def api_list_tenants(current_user):
    """
    获取租户列表
    ---
    tags:
      - Tenants
    security:
      - Bearer: []
    responses:
      200:
        description: 成功获取租户列表
        schema:
          type: object
          properties:
            tenants:
              type: array
              items:
                type: object
                properties:
                  id:
                    type: integer
                  name:
                    type: string
                  gender:
                    type: string
                  nation:
                    type: string
                  birth_date:
                    type: string
                  id_card:
                    type: string
                  address:
                    type: string
                  phone:
                    type: string
                  room_no:
                    type: string
                  status:
                    type: string
                    description: 在住/已退租
                  check_in_date:
                    type: string
                  check_out_date:
                    type: string
    """
    conn = connect()
    cursor = conn.cursor()

    # 尝试进行自动状态更新；若数据库繁忙（锁定），则跳过更新以保证查询可用
    try:
        _refresh_tenant_statuses(conn)
        conn.commit()
    except sqlite3.OperationalError as e:
        if 'locked' in str(e).lower():
            pass
        else:
            conn.close()
            return jsonify({'error': str(e)}), 500

    try:
        _refresh_room_statuses(conn)
        conn.commit()
    except sqlite3.OperationalError as e:
        if 'locked' in str(e).lower():
            pass
        else:
            conn.close()
            return jsonify({'error': str(e)}), 500

    cursor.execute(
        """
        SELECT t.id, t.name, t.gender, t.nation, t.birth_date, t.id_card, 
               t.address, t.issuing_authority, t.valid_from, t.valid_to,
               t.phone, t.emergency_contact_name, t.emergency_contact_phone, 
               t.check_in_date, t.check_out_date, r.room_no, r.building, t.remarks, t.status,
               t.front_img, t.back_img
        FROM tenants t
        LEFT JOIN rooms r ON t.room_id = r.id
        ORDER BY r.room_no, t.name
        """
    )
    rows = cursor.fetchall()
    conn.close()

    tenants = []
    for row in rows:
        tenants.append({
            'id': row[0],
            'name': row[1],
            'gender': row[2],
            'nation': row[3],
            'birth_date': row[4],
            'id_card': row[5],
            'address': row[6],
            'issuing_authority': row[7],
            'valid_from': row[8],
            'valid_to': row[9],
            'phone': row[10],
            'emergency_contact_name': row[11],
            'emergency_contact_phone': row[12],
            'check_in_date': row[13],
            'check_out_date': row[14],
            'room_no': row[15],
            'building': row[16],
            'remarks': row[17],
            'status': row[18],
            'front_img': row[19],
            'back_img': row[20],
        })

    q = (request.args.get('q') or request.args.get('search') or '').strip().lower()
    status_filter = (request.args.get('status') or '').strip()
    building_filter = (request.args.get('building') or '').strip()
    room_no_filter = (request.args.get('room_no') or '').strip()
    sort_by = (request.args.get('sort_by') or '').strip()
    sort_order = (request.args.get('sort_order') or 'asc').strip().lower()

    if q:
        tenants = [
            item
            for item in tenants
            if q in str(item.get('name', '')).lower()
            or q in str(item.get('id_card', '')).lower()
            or q in str(item.get('phone', '')).lower()
            or q in str(item.get('room_no', '')).lower()
        ]

    if status_filter:
        tenants = [item for item in tenants if str(item.get('status') or '') == status_filter]

    if building_filter:
        tenants = [item for item in tenants if str(item.get('building') or '') == building_filter]

    if room_no_filter:
        tenants = [item for item in tenants if str(item.get('room_no') or '') == room_no_filter]

    if sort_by in ('id', 'name', 'gender', 'nation', 'birth_date', 'id_card', 'phone', 'building', 'room_no', 'status', 'check_in_date', 'check_out_date'):
        reverse = sort_order == 'desc'
        tenants.sort(key=lambda x: x.get(sort_by), reverse=reverse)

    total = len(tenants)

    page, page_size, paging_enabled = parse_pagination_args(
        request.args,
        default_page=1,
        default_page_size=20,
        max_page_size=200,
    )
    if paging_enabled:
        tenants, pagination = paginate_list(tenants, page, page_size)
    else:
        pagination = {
            'page': 1,
            'page_size': total if total > 0 else 0,
            'total': total,
            'total_pages': 1,
        }

    allowed_fields = [
        'id', 'name', 'gender', 'nation', 'birth_date', 'id_card', 'address',
        'issuing_authority', 'valid_from', 'valid_to', 'phone',
        'emergency_contact_name', 'emergency_contact_phone',
        'check_in_date', 'check_out_date', 'room_no', 'building',
        'remarks', 'status', 'front_img', 'back_img'
    ]
    selected_fields = parse_fields_arg(request.args, allowed_fields)
    tenants = project_fields(tenants, selected_fields, always_include=['id'])

    return jsonify({'tenants': tenants, 'total': total, 'pagination': pagination})


@tenants_bp.route('/tenants/<id_card>/checkout', methods=['POST'])
@token_required
def api_checkout_tenant(current_user, id_card):
    """
    办理退租
    ---
    tags:
      - Tenants
    security:
      - Bearer: []
    parameters:
      - in: path
        name: id_card
        type: string
        required: true
        description: 身份证号
    responses:
      200:
        description: 退租成功
      404:
        description: 未找到该租户或已退租
    """
    conn = connect()
    cursor = conn.cursor()

    today = date.today().isoformat()
    cursor.execute(
        """
    UPDATE tenants
    SET check_out_date = ?,
        status = '已退租'
    WHERE id_card = ? AND status = '在住'
    """,
        (today, id_card),
    )

    if cursor.rowcount == 0:
        conn.close()
        return jsonify({'error': '未找到该租户或租户已退租'}), 404

    _refresh_tenant_statuses(conn)
    _refresh_room_statuses(conn)
    conn.commit()
    conn.close()

    return jsonify({'message': '租户退租成功', 'checkout_date': today})


@tenants_bp.route('/tenants', methods=['POST'])
@token_required
def api_add_tenant(current_user):
    data = request.json
    required_fields = [
        'name', 'gender', 'id_card', 'phone',
        'emergency_contact_name', 'emergency_contact_phone',
        'check_in_date', 'check_out_date', 'room_no',
    ]

    if not data or not all(k in data for k in required_fields):
        return jsonify({'error': '缺少必要参数', 'required': required_fields}), 400

    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM rooms WHERE room_no = ?", (data['room_no'],))
    room = cursor.fetchone()
    if not room:
        conn.close()
        return jsonify({'error': f"房间 {data['room_no']} 不存在"}), 404

    room_id = room[0]
    remarks = data.get('remarks', '')

    try:
        cursor.execute(
            """
            INSERT INTO tenants (
                name, gender, nation, birth_date, id_card, address, issuing_authority,
                valid_from, valid_to, front_img, back_img,
                phone, emergency_contact_name, emergency_contact_phone,
                check_in_date, check_out_date, room_id, remarks, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '在住')
            """,
            (
                data['name'],
                data['gender'],
                data.get('nation', '汉族'),
                data.get('birth_date', None),
                data['id_card'],
                data.get('address', ''),
                # 前端可能以 issuer 传入，这里兼容映射至 issuing_authority
                data.get('issuing_authority', data.get('issuer', '')),
                # 兼容 valid_start/valid_end 映射至 valid_from/valid_to
                data.get('valid_from', data.get('valid_start', None)),
                data.get('valid_to', data.get('valid_end', None)),
                data.get('front_img', ''),
                data.get('back_img', ''),
                data['phone'],
                data['emergency_contact_name'],
                data['emergency_contact_phone'],
                data['check_in_date'],
                data['check_out_date'],
                room_id,
                remarks,
            ),
        )
        _refresh_tenant_statuses(conn)
        _refresh_room_statuses(conn)
        conn.commit()
        conn.close()

        return jsonify({'message': f"租户 {data['name']} 已添加", 'id_card': data['id_card']})
    except sqlite3.Error as e:
        conn.close()
        return jsonify({'error': str(e)}), 500


@tenants_bp.route('/tenants/<id_card>', methods=['PUT'])
@token_required
def api_update_tenant(current_user, id_card):
    data = request.json
    if not data:
        return jsonify({'error': '缺少更新数据'}), 400

    allowed_fields = [
        'name', 'phone', 'emergency_contact_name', 'emergency_contact_phone',
        'check_in_date', 'check_out_date', 'remarks',
    ]
    update_data = {k: v for k, v in data.items() if k in allowed_fields}

    if 'room_no' in data:
        conn = connect()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM rooms WHERE room_no = ?", (data['room_no'],))
        room = cursor.fetchone()
        if not room:
            conn.close()
            return jsonify({'error': f"房间 {data['room_no']} 不存在"}), 404
        update_data['room_id'] = room[0]
        conn.close()

    if not update_data:
        return jsonify({'error': '没有有效的更新字段'}), 400

    conn = connect()
    cursor = conn.cursor()

    try:
        for key, value in update_data.items():
            cursor.execute(f"UPDATE tenants SET {key} = ? WHERE id_card = ?", (value, id_card))

        if cursor.rowcount == 0:
            conn.close()
            return jsonify({'error': f'租户 {id_card} 不存在'}), 404

        _refresh_tenant_statuses(conn)
        _refresh_room_statuses(conn)
        conn.commit()
        conn.close()

        return jsonify({'message': f'租户 {id_card} 信息已更新'})
    except sqlite3.Error as e:
        conn.close()
        return jsonify({'error': str(e)}), 500


@tenants_bp.route('/tenants/<id_card>', methods=['DELETE'])
@token_required
def api_delete_tenant(current_user, id_card):
    """
    删除租户
    ---
    tags:
      - Tenants
    security:
      - Bearer: []
    parameters:
      - in: path
        name: id_card
        type: string
        required: true
        description: 身份证号
    responses:
      200:
        description: 删除成功
      400:
        description: 在住状态不可删除，或存在关联数据
      404:
        description: 租户不存在
    """
    conn = connect()
    cursor = conn.cursor()

    try:
        # 校验租户存在与状态，并获取 room_id 以便精确更新房间状态
        cursor.execute("SELECT id, status, room_id FROM tenants WHERE id_card = ? LIMIT 1", (id_card,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return jsonify({'error': f'租户 {id_card} 不存在'}), 404
        tenant_id, status, room_id = row[0], row[1], row[2]
        if status != '已退租':
            conn.close()
            return jsonify({'error': '在住状态不可删除，请先办理退租'}), 400
        # 先级联清理关联的搬迁记录，避免外键约束失败
        cursor.execute("DELETE FROM tenant_moves WHERE tenant_id = ?", (tenant_id,))
        moves_deleted = cursor.rowcount

        # 执行删除租户
        cursor.execute("DELETE FROM tenants WHERE id_card = ?", (id_card,))
        if cursor.rowcount == 0:
            conn.close()
            return jsonify({'error': f'租户 {id_card} 不存在'}), 404

        conn.commit()

        # 更新房间状态（如有需要）
        # 仅针对受影响的房间更新状态，降低并发锁竞争
        if room_id is not None:
            cursor.execute(
                """
                UPDATE rooms
                SET status = CASE
                    WHEN EXISTS (
                        SELECT 1 FROM tenants t
                        WHERE t.room_id = rooms.id
                          AND t.status = '在住'
                          AND DATE('now') BETWEEN t.check_in_date AND t.check_out_date
                    ) THEN '已入住'
                    ELSE '空闲'
                END
                WHERE id = ?
                """,
                (room_id,)
            )
        conn.commit()
        conn.close()
        msg = f'租户 {id_card} 已删除'
        if moves_deleted and moves_deleted > 0:
            msg += f'（已清理搬迁记录 {moves_deleted} 条）'
        return jsonify({'message': msg})
    except sqlite3.IntegrityError as e:
        # 针对外键约束失败（例如存在关联的搬迁记录）返回明确的业务错误，避免 500
        try:
            # 尝试提供更明确的失败原因
            conn2 = connect()
            cur2 = conn2.cursor()
            # 查出租户ID
            cur2.execute("SELECT id FROM tenants WHERE id_card = ? LIMIT 1", (id_card,))
            r = cur2.fetchone()
            tenant_id = r[0] if r else None
            moves_count = 0
            if tenant_id is not None:
                cur2.execute("SELECT COUNT(*) FROM tenant_moves WHERE tenant_id = ?", (tenant_id,))
                moves_count = cur2.fetchone()[0]
            conn2.close()
            if moves_count > 0:
                return jsonify({'error': f'租户 {id_card} 存在 {moves_count} 条搬迁记录，无法删除；请先删除或归档相关记录'}), 400
        except Exception:
            # 若补充查询失败，也避免抛出 500
            pass
        return jsonify({'error': '删除失败：存在关联数据约束（如搬迁记录），请先清理关联数据后再尝试'}), 400
    except sqlite3.Error as e:
        conn.close()
        return jsonify({'error': str(e)}), 500