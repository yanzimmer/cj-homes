import sqlite3
from datetime import datetime

from flask import Blueprint, request, jsonify

from auth_api import token_required
from common import connect


repair_bp = Blueprint('repair_records', __name__, url_prefix='/api')


@repair_bp.route('/repair-records', methods=['GET'])
@token_required
def api_list_repair_records(current_user):
    """
    获取维修记录列表
    ---
    tags:
      - Repair Records
    security:
      - Bearer: []
    responses:
      200:
        description: 成功获取维修记录
        schema:
          type: object
          properties:
            repair_records:
              type: array
              items:
                type: object
                properties:
                  id:
                    type: integer
                  building:
                    type: string
                  room_no:
                    type: string
                  repair_type:
                    type: string
                  description:
                    type: string
                  report_date:
                    type: string
                  report_by:
                    type: string
                  status:
                    type: string
                  repair_date:
                    type: string
                  repair_cost:
                    type: number
                  repair_person:
                    type: string
                  remarks:
                    type: string
    """
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT 
            id, building, room_no, repair_type, description, 
            report_date, report_by, status,
            repair_date, repair_cost, repair_person, remarks
        FROM repair_records
        ORDER BY report_date DESC
        """
    )
    rows = cursor.fetchall()
    conn.close()

    records = []
    for row in rows:
        records.append({
            'id': row[0],
            'building': row[1],
            'room_no': row[2],
            'repair_type': row[3],
            'description': row[4],
            'report_date': row[5],
            'report_by': row[6],
            'status': row[7],
            'repair_date': row[8],
            'repair_cost': row[9],
            'repair_person': row[10],
            'remarks': row[11],
        })

    return jsonify({'repair_records': records})


@repair_bp.route('/repair-records/<int:record_id>', methods=['GET'])
@token_required
def api_get_repair_record(current_user, record_id):
    """
    获取单条维修记录
    ---
    tags:
      - Repair Records
    security:
      - Bearer: []
    parameters:
      - in: path
        name: record_id
        type: integer
        required: true
        description: 维修记录ID
    responses:
      200:
        description: 成功获取记录
      404:
        description: 记录不存在
    """
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT 
            id, building, room_no, repair_type, description, 
            report_date, report_by, status,
            repair_date, repair_cost, repair_person, remarks
        FROM repair_records
        WHERE id = ?
        """,
        (record_id,),
    )
    row = cursor.fetchone()
    conn.close()

    if not row:
        return jsonify({'error': f'维修记录 {record_id} 不存在'}), 404

    record = {
        'id': row[0],
        'building': row[1],
        'room_no': row[2],
        'repair_type': row[3],
        'description': row[4],
        'report_date': row[5],
        'report_by': row[6],
        'status': row[7],
        'repair_date': row[8],
        'repair_cost': row[9],
        'repair_person': row[10],
        'remarks': row[11],
    }

    return jsonify({'repair_record': record})


@repair_bp.route('/repair-records', methods=['POST'])
@token_required
def api_add_repair_record(current_user):
    """
    添加维修记录
    ---
    tags:
      - Repair Records
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        schema:
          type: object
          required:
            - room_no
            - repair_type
            - description
            - report_by
          properties:
            room_no:
              type: string
            repair_type:
              type: string
            description:
              type: string
            report_by:
              type: string
            report_date:
              type: string
            status:
              type: string
            repair_date:
              type: string
            repair_cost:
              type: number
            repair_person:
              type: string
            remarks:
              type: string
    responses:
      200:
        description: 添加成功
      400:
        description: 参数缺失
      404:
        description: 房间不存在
    """
    data = request.json
    required_fields = ['room_no', 'repair_type', 'description', 'report_by']

    if not data or not all(k in data for k in required_fields):
        return jsonify({'error': '缺少必要参数', 'required': required_fields}), 400

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("SELECT building FROM rooms WHERE room_no = ?", (data['room_no'],))
    room = cursor.fetchone()
    if not room:
        conn.close()
        return jsonify({'error': f"房间 {data['room_no']} 不存在"}), 404

    building = room[0]

    report_date = data.get('report_date', datetime.now().strftime('%Y-%m-%d'))
    status = data.get('status', '待处理')
    remarks = data.get('remarks', '')

    try:
        cursor.execute(
            """
            INSERT INTO repair_records (
                building, room_no, repair_type, description, 
                report_date, report_by, status,
                repair_date, repair_cost, repair_person, remarks
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                building,
                data['room_no'],
                data['repair_type'],
                data['description'],
                report_date,
                data['report_by'],
                status,
                data.get('repair_date'),
                data.get('repair_cost'),
                data.get('repair_person'),
                remarks,
            ),
        )

        record_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return jsonify({'message': '维修记录已添加', 'id': record_id, 'room_no': data['room_no']})
    except sqlite3.Error as e:
        conn.close()
        return jsonify({'error': str(e)}), 500


@repair_bp.route('/repair-records/<int:record_id>', methods=['PUT'])
@token_required
def api_update_repair_record(current_user, record_id):
    """
    更新维修记录
    ---
    tags:
      - Repair Records
    security:
      - Bearer: []
    parameters:
      - in: path
        name: record_id
        type: integer
        required: true
        description: 维修记录ID
      - in: body
        name: body
        schema:
          type: object
          properties:
            repair_type:
              type: string
            description:
              type: string
            status:
              type: string
            repair_date:
              type: string
            repair_cost:
              type: number
            repair_person:
              type: string
            remarks:
              type: string
    responses:
      200:
        description: 更新成功
      400:
        description: 参数错误
      404:
        description: 记录不存在
    """
    data = request.json
    if not data:
        return jsonify({'error': '缺少更新数据'}), 400

    allowed_fields = [
        'repair_type',
        'description',
        'status',
        'repair_date',
        'repair_cost',
        'repair_person',
        'remarks',
    ]

    update_data = {k: v for k, v in data.items() if k in allowed_fields}

    if not update_data:
        return jsonify({'error': '没有有效的更新字段'}), 400

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM repair_records WHERE id = ?", (record_id,))
    record = cursor.fetchone()
    if not record:
        conn.close()
        return jsonify({'error': f'维修记录 {record_id} 不存在'}), 404

    try:
        for key, value in update_data.items():
            cursor.execute(
                f"UPDATE repair_records SET {key} = ? WHERE id = ?",
                (value, record_id),
            )

        conn.commit()
        conn.close()
        return jsonify({'message': f'维修记录 {record_id} 已更新'})
    except sqlite3.Error as e:
        conn.close()
        return jsonify({'error': str(e)}), 500


@repair_bp.route('/repair-records/<int:record_id>', methods=['DELETE'])
@token_required
def api_delete_repair_record(current_user, record_id):
    """
    删除维修记录
    ---
    tags:
      - Repair Records
    security:
      - Bearer: []
    parameters:
      - in: path
        name: record_id
        type: integer
        required: true
        description: 维修记录ID
    responses:
      200:
        description: 删除成功
      404:
        description: 记录不存在
    """
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM repair_records WHERE id = ?", (record_id,))
    record = cursor.fetchone()
    if not record:
        conn.close()
        return jsonify({'error': f'维修记录 {record_id} 不存在'}), 404

    try:
        cursor.execute("DELETE FROM repair_records WHERE id = ?", (record_id,))
        conn.commit()
        conn.close()
        return jsonify({'message': f'维修记录 {record_id} 已删除'})
    except sqlite3.Error as e:
        conn.close()
        return jsonify({'error': str(e)}), 500


@repair_bp.route('/repair-records/room/<room_no>', methods=['GET'])
@token_required
def api_get_room_repair_records(current_user, room_no):
    """
    获取指定房间的维修记录
    ---
    tags:
      - Repair Records
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
        description: 成功获取记录列表
      404:
        description: 房间不存在
    """
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM rooms WHERE room_no = ?", (room_no,))
    room = cursor.fetchone()
    if not room:
        conn.close()
        return jsonify({'error': f'房间 {room_no} 不存在'}), 404

    cursor.execute(
        """
        SELECT 
            id, building, room_no, repair_type, description, 
            report_date, report_by, status,
            repair_date, repair_cost, repair_person, remarks
        FROM repair_records
        WHERE room_no = ?
        ORDER BY report_date DESC
        """,
        (room_no,),
    )
    rows = cursor.fetchall()
    conn.close()

    records = []
    for row in rows:
        records.append({
            'id': row[0],
            'building': row[1],
            'room_no': row[2],
            'repair_type': row[3],
            'description': row[4],
            'report_date': row[5],
            'report_by': row[6],
            'status': row[7],
            'repair_date': row[8],
            'repair_cost': row[9],
            'repair_person': row[10],
            'remarks': row[11],
        })

    return jsonify({'repair_records': records})