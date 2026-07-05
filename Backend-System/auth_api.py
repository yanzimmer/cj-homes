import hashlib
from datetime import datetime, timedelta
from functools import wraps

import jwt
from flask import Blueprint, request, jsonify, make_response

from common import connect, SECRET_KEY, JWT_EXPIRATION_DELTA
import forgot_password as fp
from session_manager import (
    create_session,
    ensure_session_schema,
    expire_session,
    get_session,
    get_session_invalid_payload,
    get_login_restriction,
    list_session_events,
    list_sessions,
    load_session_settings,
    logout_session,
    revoke_session,
    release_session_login_restriction,
    restrict_session_login,
    save_session_settings,
    touch_session,
)


auth_bp = Blueprint('auth', __name__, url_prefix='/api')


def _build_token(username, full_name, session_id, token_expiry):
    return jwt.encode(
        {
            'username': username,
            'full_name': full_name,
            'sid': session_id,
            'exp': token_expiry,
        },
        SECRET_KEY,
        algorithm="HS256",
    )


def _client_ip():
    return request.headers.get('X-Forwarded-For', request.remote_addr or '').split(',')[0].strip()


def _token_ttl_seconds():
    settings = load_session_settings()
    try:
        minutes = int(settings.get('token_ttl_minutes') or 0)
    except Exception:
        minutes = max(1, int(JWT_EXPIRATION_DELTA // 60))
    return max(5 * 60, minutes * 60)


def _utc_token_expiry():
    return datetime.utcnow() + timedelta(seconds=_token_ttl_seconds())


def _local_session_expiry_text():
    return (datetime.now() + timedelta(seconds=_token_ttl_seconds())).strftime("%Y-%m-%d %H:%M:%S")


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None

        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]

        if not token:
            return jsonify({'error': '缺少认证令牌', 'code': 'AUTH_TOKEN_MISSING'}), 401

        try:
            data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            session_id = str(data.get('sid') or '').strip()
            if not session_id:
                return jsonify({'error': '无效的认证令牌', 'code': 'AUTH_TOKEN_INVALID'}), 401

            session = get_session(session_id)
            if not session or session.get('status') != 'active':
                payload = get_session_invalid_payload(session)
                return jsonify(payload), 401

            conn = connect()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM admins WHERE username = ?", (data['username'],))
            user_data = cursor.fetchone()
            conn.close()

            if not user_data:
                return jsonify({'error': '无效的认证令牌', 'code': 'AUTH_TOKEN_INVALID'}), 401

            current_user = {
                'id': user_data[0],
                'username': user_data[1],
                'full_name': user_data[3],
                'session_id': session_id,
                'session': session,
            }
        except jwt.ExpiredSignatureError:
            try:
                decoded = jwt.decode(token, SECRET_KEY, algorithms=["HS256"], options={"verify_exp": False})
                session_id = str(decoded.get('sid') or '').strip()
                if session_id:
                    expire_session(session_id)
            except Exception:
                pass
            return jsonify({'error': '认证令牌已过期，请重新登录', 'code': 'AUTH_TOKEN_EXPIRED'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': '无效的认证令牌', 'code': 'AUTH_TOKEN_INVALID'}), 401

        # 成功认证后：活动续期——签发一个新的令牌并通过响应头返回
        response = f(current_user=current_user, *args, **kwargs)
        try:
            new_expiry = _utc_token_expiry()
            new_token = _build_token(
                current_user['username'],
                current_user['full_name'],
                current_user['session_id'],
                new_expiry,
            )
            touch_session(
                current_user['session_id'],
                expires_at=_local_session_expiry_text(),
            )
            resp = make_response(response)
            resp.headers['X-Refreshed-Token'] = new_token
            resp.headers['X-Token-Expires'] = new_expiry.isoformat()
            return resp
        except Exception:
            # 如果续期失败，不影响原始响应
            return response

    return decorated


@auth_bp.route('/login', methods=['POST'])
def login():
    """
    用户登录
    ---
    tags:
      - Authentication
    parameters:
      - in: body
        name: body
        schema:
          type: object
          required:
            - username
            - password
          properties:
            username:
              type: string
              example: admin
            password:
              type: string
              example: password123
    responses:
      200:
        description: 登录成功
        schema:
          type: object
          properties:
            token:
              type: string
              description: JWT Token
            username:
              type: string
            full_name:
              type: string
      400:
        description: 缺少参数
      401:
        description: 认证失败
    """
    data = request.json
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({'error': '请提供用户名和密码'}), 400

    username = data.get('username')
    password = data.get('password')
    password_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()

    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, username, full_name FROM admins WHERE username = ? AND password_hash = ?",
        (username, password_hash),
    )
    user = cursor.fetchone()
    conn.close()

    if not user:
        return jsonify({'error': '用户名或密码错误'}), 401

    restriction = get_login_restriction(
        user[1],
        ip_address=_client_ip(),
        user_agent=request.headers.get('User-Agent', ''),
    )
    if restriction:
        return jsonify({
            'error': '当前设备已被限制登录，请联系管理。',
            'code': 'AUTH_LOGIN_RESTRICTED',
        }), 403

    token_expiry = _utc_token_expiry()
    session_info = create_session(
        username=user[1],
        full_name=user[2],
        ip_address=_client_ip(),
        user_agent=request.headers.get('User-Agent', ''),
        expires_at=_local_session_expiry_text(),
    )
    token = _build_token(user[1], user[2], session_info['session_id'], token_expiry)

    return jsonify({
        'token': token,
        'username': user[1],
        'full_name': user[2],
        'expires': token_expiry.isoformat(),
        'session_id': session_info['session_id'],
        'device_label': session_info['device_label'],
        'login_mode': session_info['login_mode'],
    })


@auth_bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    """
    忘记密码（通过安全问题重置）
    ---
    tags:
      - Authentication
    parameters:
      - in: body
        name: body
        schema:
          type: object
          required:
            - username
            - answer
            - new_password
          properties:
            username:
              type: string
              example: admin
            answer:
              type: string
              description: 安全问题答案
              example: 123456
            new_password:
              type: string
              example: newpassword123
    responses:
      200:
        description: 密码重置成功
      400:
        description: 验证失败或参数缺失
    """
    data = request.json or {}
    username = data.get('username')
    answer = data.get('answer')
    new_password = data.get('new_password')

    if not username or not answer or not new_password:
        return jsonify({'error': '请提供用户名、问题答案以及新密码'}), 400

    ok, msg = fp.verify_and_reset_password(username, answer, new_password)
    if ok:
        return jsonify({'message': msg})
    else:
        return jsonify({'error': msg}), 400


@auth_bp.route('/verify-token', methods=['GET'])
@token_required
def verify_token(current_user):
    """
    验证 Token 有效性
    ---
    tags:
      - Authentication
    security:
      - Bearer: []
    responses:
      200:
        description: Token 有效
        schema:
          type: object
          properties:
            message:
              type: string
      401:
        description: Token 无效或已过期
    """
    return jsonify({
        'message': '令牌有效',
        'username': current_user['username'],
        'full_name': current_user['full_name'],
        'session_id': current_user['session_id'],
    })


@auth_bp.route('/logout', methods=['POST'])
@token_required
def logout(current_user):
    logout_session(current_user['session_id'], actor_username=current_user['username'])
    return jsonify({'message': '已退出登录'})


@auth_bp.route('/session-settings', methods=['GET'])
@token_required
def get_session_settings(current_user):
    settings = load_session_settings()
    session_payload = list_sessions(current_session_id=current_user['session_id'], include_history=False)
    return jsonify({
        'login_mode': settings.get('login_mode', 'multi'),
        'token_ttl_minutes': settings.get('token_ttl_minutes'),
        'active_count': session_payload.get('active_count', 0),
    })


@auth_bp.route('/session-settings', methods=['PUT'])
@token_required
def update_session_settings(current_user):
    data = request.json or {}
    if 'login_mode' not in data and 'token_ttl_minutes' not in data:
        return jsonify({'error': '请提供 login_mode 或 token_ttl_minutes'}), 400
    settings = save_session_settings(data)
    return jsonify(settings)


@auth_bp.route('/sessions', methods=['GET'])
@token_required
def get_sessions(current_user):
    include_history = str(request.args.get('include_history', 'true')).lower() != 'false'
    payload = list_sessions(current_session_id=current_user['session_id'], include_history=include_history)
    return jsonify(payload)


@auth_bp.route('/sessions/<session_id>/revoke', methods=['POST'])
@token_required
def revoke_session_api(current_user, session_id):
    ok, message = revoke_session(
        session_id,
        actor_username=current_user['username'],
        reason='管理员手动下线',
        event_type='revoked',
    )
    if not ok:
        return jsonify({'error': message}), 400
    payload = list_sessions(current_session_id=current_user['session_id'], include_history=True)
    payload['message'] = message
    return jsonify(payload)


@auth_bp.route('/sessions/<session_id>/restrict-login', methods=['POST'])
@token_required
def restrict_session_login_api(current_user, session_id):
    ok, message = restrict_session_login(
        session_id,
        actor_username=current_user['username'],
        reason='管理员手动下线并限制该设备登录',
    )
    if not ok:
        return jsonify({'error': message}), 400
    payload = list_sessions(current_session_id=current_user['session_id'], include_history=True)
    payload['message'] = message
    return jsonify(payload)


@auth_bp.route('/sessions/<session_id>/release-login-restriction', methods=['POST'])
@token_required
def release_session_login_restriction_api(current_user, session_id):
    ok, message = release_session_login_restriction(
        session_id,
        actor_username=current_user['username'],
    )
    if not ok:
        return jsonify({'error': message}), 400
    payload = list_sessions(current_session_id=current_user['session_id'], include_history=True)
    payload['message'] = message
    return jsonify(payload)


@auth_bp.route('/session-events', methods=['GET'])
@token_required
def get_session_events_api(current_user):
    raw_limit = request.args.get('limit', 20)
    raw_after_id = request.args.get('after_id')
    try:
        limit = max(1, min(int(raw_limit), 50))
    except Exception:
        limit = 20
    try:
        after_id = int(raw_after_id) if raw_after_id not in (None, '') else None
    except Exception:
        after_id = None
    events = list_session_events(limit=limit, after_id=after_id)
    return jsonify({
        'events': events,
        'latest_event_id': events[-1]['id'] if events else after_id or 0,
    })


@auth_bp.route('/change-password', methods=['POST'])
@token_required
def change_password(current_user):
    """
    修改密码
    ---
    tags:
      - Authentication
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        schema:
          type: object
          required:
            - old_password
            - new_password
          properties:
            old_password:
              type: string
              example: oldpassword123
            new_password:
              type: string
              example: newpassword123
    responses:
      200:
        description: 密码修改成功
      400:
        description: 参数缺失
      401:
        description: 旧密码错误
    """
    data = request.json
    if not data or not data.get('old_password') or not data.get('new_password'):
        return jsonify({'error': '请提供旧密码和新密码'}), 400

    old_password = data.get('old_password')
    new_password = data.get('new_password')
    old_password_hash = hashlib.sha256(old_password.encode("utf-8")).hexdigest()

    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM admins WHERE username = ? AND password_hash = ?",
        (current_user['username'], old_password_hash),
    )
    user = cursor.fetchone()
    if not user:
        conn.close()
        return jsonify({'error': '旧密码不正确', 'code': 'AUTH_OLD_PASSWORD_INCORRECT'}), 401

    new_password_hash = hashlib.sha256(new_password.encode("utf-8")).hexdigest()
    cursor.execute(
        "UPDATE admins SET password_hash = ? WHERE username = ?",
        (new_password_hash, current_user['username']),
    )
    conn.commit()
    conn.close()

    return jsonify({'message': '密码修改成功'})
