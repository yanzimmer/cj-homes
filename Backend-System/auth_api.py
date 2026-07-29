import hashlib
import json
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
    revoke_other_sessions,
    save_session_settings,
    touch_session,
)
from totp_service import (
    build_totp_uri,
    dump_recovery_code_hashes,
    generate_recovery_codes,
    generate_totp_secret,
    parse_recovery_code_hashes,
    verify_recovery_code,
    verify_totp,
)


auth_bp = Blueprint('auth', __name__, url_prefix='/api')
TOTP_MAX_FAILED_ATTEMPTS = 5
TOTP_LOCK_MINUTES = 15


def ensure_totp_schema():
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(admins)")
    cols = {row[1] for row in cursor.fetchall()}
    additions = {
        'totp_secret': "TEXT",
        'totp_pending_secret': "TEXT",
        'totp_enabled': "INTEGER NOT NULL DEFAULT 0",
        'totp_recovery_codes': "TEXT",
        'totp_failed_attempts': "INTEGER NOT NULL DEFAULT 0",
        'totp_locked_until': "TEXT",
    }
    for column, definition in additions.items():
        if column not in cols:
            cursor.execute(f"ALTER TABLE admins ADD COLUMN {column} {definition}")
    conn.commit()
    conn.close()


def _password_hash(value):
    return hashlib.sha256(str(value or '').encode('utf-8')).hexdigest()


def _verify_totp_or_recovery(secret, recovery_codes_json, code):
    if verify_totp(secret, code):
        return True, False, parse_recovery_code_hashes(recovery_codes_json)
    stored_hashes = parse_recovery_code_hashes(recovery_codes_json)
    valid_recovery, remaining = verify_recovery_code(code, stored_hashes)
    return valid_recovery, valid_recovery, remaining


def _current_password_valid(username, current_password):
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM admins WHERE username = ? AND password_hash = ?",
        (username, _password_hash(current_password)),
    )
    valid = cursor.fetchone() is not None
    conn.close()
    return valid


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
    password_hash = _password_hash(password)

    ensure_totp_schema()
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, username, full_name, totp_enabled, totp_secret,
               totp_recovery_codes, totp_failed_attempts, totp_locked_until
        FROM admins
        WHERE username = ? AND password_hash = ?
        """,
        (username, password_hash),
    )
    user = cursor.fetchone()

    if not user:
        conn.close()
        return jsonify({'error': '用户名或密码错误'}), 401

    recovery_code_used = False
    recovery_codes_remaining = None
    if bool(user[3]):
        secret = str(user[4] or '').strip()
        if not secret:
            conn.close()
            return jsonify({'error': '两步验证配置异常，请使用服务器端密码重置工具处理'}), 500

        now = datetime.now()
        locked_until = None
        if user[7]:
            try:
                locked_until = datetime.strptime(str(user[7]), "%Y-%m-%d %H:%M:%S")
            except ValueError:
                locked_until = None
        if locked_until and locked_until > now:
            conn.close()
            return jsonify(
                {
                    'error': f'动态验证码尝试次数过多，请于 {user[7]} 后重试',
                    'code': 'AUTH_TOTP_LOCKED',
                }
            ), 429

        totp_code = str(data.get('totp_code') or '').strip()
        if not totp_code:
            if locked_until:
                cursor.execute(
                    "UPDATE admins SET totp_failed_attempts = 0, totp_locked_until = NULL WHERE id = ?",
                    (user[0],),
                )
                conn.commit()
            conn.close()
            return jsonify(
                {
                    'error': '请输入身份验证器动态码或恢复码',
                    'code': 'AUTH_TOTP_REQUIRED',
                    'totp_required': True,
                }
            ), 401

        valid_factor, recovery_code_used, remaining_hashes = _verify_totp_or_recovery(
            secret,
            user[5],
            totp_code,
        )
        if not valid_factor:
            failed_attempts = int(user[6] or 0) + 1
            next_locked_until = None
            if failed_attempts >= TOTP_MAX_FAILED_ATTEMPTS:
                next_locked_until = (now + timedelta(minutes=TOTP_LOCK_MINUTES)).strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute(
                """
                UPDATE admins
                SET totp_failed_attempts = ?, totp_locked_until = ?
                WHERE id = ?
                """,
                (failed_attempts, next_locked_until, user[0]),
            )
            conn.commit()
            conn.close()
            if next_locked_until:
                return jsonify(
                    {
                        'error': f'连续验证失败 {TOTP_MAX_FAILED_ATTEMPTS} 次，请于 {next_locked_until} 后重试',
                        'code': 'AUTH_TOTP_LOCKED',
                    }
                ), 429
            return jsonify(
                {
                    'error': '动态验证码或恢复码不正确',
                    'code': 'AUTH_TOTP_INVALID',
                    'remaining_attempts': TOTP_MAX_FAILED_ATTEMPTS - failed_attempts,
                }
            ), 401

        recovery_codes_remaining = len(remaining_hashes)
        cursor.execute(
            """
            UPDATE admins
            SET totp_recovery_codes = ?, totp_failed_attempts = 0, totp_locked_until = NULL
            WHERE id = ?
            """,
            (json.dumps(remaining_hashes), user[0]),
        )
        conn.commit()
    conn.close()

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
        'recovery_code_used': recovery_code_used,
        'recovery_codes_remaining': recovery_codes_remaining,
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
    if len(str(new_password)) < 6:
        return jsonify({'error': '新密码长度不能少于 6 个字符'}), 400

    ok, msg = fp.verify_and_reset_password(username, answer, new_password)
    if ok:
        revoked_count = revoke_other_sessions(
            username=username,
            except_session_id='',
            actor_username=username,
            reason='密码已通过安全口令重置，旧会话已失效',
        )
        return jsonify({'message': msg, 'revoked_sessions': revoked_count})
    else:
        status_code = 429 if '后重试' in msg else 400
        return jsonify({'error': msg}), status_code


@auth_bp.route('/recovery-settings', methods=['GET'])
@token_required
def get_recovery_settings(current_user):
    status = fp.get_recovery_status(current_user['username']) or {}
    return jsonify({
        'configured': bool(status.get('configured')),
        'updated_at': status.get('updated_at') or '',
    })


@auth_bp.route('/recovery-settings', methods=['PUT'])
@token_required
def update_recovery_settings(current_user):
    data = request.json or {}
    current_password = str(data.get('current_password') or '')
    security_answer = str(data.get('security_answer') or '').strip()
    if not current_password or not security_answer:
        return jsonify({'error': '请提供当前密码和新的安全口令'}), 400
    if len(security_answer) < 6:
        return jsonify({'error': '安全口令长度不能少于 6 个字符'}), 400
    if security_answer == current_password:
        return jsonify({'error': '安全口令不能与登录密码相同'}), 400

    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM admins WHERE username = ? AND password_hash = ?",
        (current_user['username'], hashlib.sha256(current_password.encode('utf-8')).hexdigest()),
    )
    valid_password = cursor.fetchone()
    conn.close()
    if not valid_password:
        return jsonify({'error': '当前密码不正确'}), 401

    ok, message = fp.set_recovery_info(
        current_user['username'],
        security_answer=security_answer,
    )
    if not ok:
        return jsonify({'error': message}), 400
    return jsonify({'message': '安全口令已设置', 'configured': True})


@auth_bp.route('/totp/settings', methods=['GET'])
@token_required
def get_totp_settings(current_user):
    ensure_totp_schema()
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT totp_enabled, totp_pending_secret, totp_recovery_codes FROM admins WHERE username = ?",
        (current_user['username'],),
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        return jsonify({'error': '用户不存在'}), 404
    recovery_codes = parse_recovery_code_hashes(row[2])
    return jsonify(
        {
            'enabled': bool(row[0]),
            'setup_pending': bool(row[1]) and not bool(row[0]),
            'recovery_codes_remaining': len(recovery_codes) if row[0] else 0,
        }
    )


@auth_bp.route('/totp/setup', methods=['POST'])
@token_required
def setup_totp(current_user):
    data = request.json or {}
    current_password = str(data.get('current_password') or '')
    if not current_password:
        return jsonify({'error': '请输入当前登录密码'}), 400
    if not _current_password_valid(current_user['username'], current_password):
        return jsonify({'error': '当前密码不正确'}), 401

    ensure_totp_schema()
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT totp_enabled FROM admins WHERE username = ?",
        (current_user['username'],),
    )
    row = cursor.fetchone()
    if not row:
        conn.close()
        return jsonify({'error': '用户不存在'}), 404
    if bool(row[0]):
        conn.close()
        return jsonify({'error': '两步验证已启用，请先关闭后再重新绑定'}), 400

    secret = generate_totp_secret()
    cursor.execute(
        "UPDATE admins SET totp_pending_secret = ? WHERE username = ?",
        (secret, current_user['username']),
    )
    conn.commit()
    conn.close()
    return jsonify(
        {
            'secret': secret,
            'otpauth_uri': build_totp_uri(secret, current_user['username']),
        }
    )


@auth_bp.route('/totp/enable', methods=['POST'])
@token_required
def enable_totp(current_user):
    data = request.json or {}
    current_password = str(data.get('current_password') or '')
    code = str(data.get('code') or '').strip()
    if not current_password or not code:
        return jsonify({'error': '请输入当前密码和动态验证码'}), 400
    if not _current_password_valid(current_user['username'], current_password):
        return jsonify({'error': '当前密码不正确'}), 401

    ensure_totp_schema()
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT totp_enabled, totp_pending_secret FROM admins WHERE username = ?",
        (current_user['username'],),
    )
    row = cursor.fetchone()
    if not row or bool(row[0]):
        conn.close()
        return jsonify({'error': '当前状态不能启用两步验证'}), 400
    pending_secret = str(row[1] or '').strip()
    if not pending_secret:
        conn.close()
        return jsonify({'error': '请先生成绑定二维码'}), 400
    if not verify_totp(pending_secret, code):
        conn.close()
        return jsonify({'error': '动态验证码不正确，请确认手机时间准确'}), 400

    recovery_codes = generate_recovery_codes()
    cursor.execute(
        """
        UPDATE admins
        SET totp_secret = ?, totp_pending_secret = NULL, totp_enabled = 1,
            totp_recovery_codes = ?, totp_failed_attempts = 0, totp_locked_until = NULL
        WHERE username = ?
        """,
        (
            pending_secret,
            dump_recovery_code_hashes(recovery_codes),
            current_user['username'],
        ),
    )
    conn.commit()
    conn.close()
    revoked_count = revoke_other_sessions(
        username=current_user['username'],
        except_session_id=current_user['session_id'],
        actor_username=current_user['username'],
        reason='账号已启用两步验证，其他设备需要重新登录',
    )
    return jsonify(
        {
            'message': '两步验证已启用',
            'enabled': True,
            'recovery_codes': recovery_codes,
            'revoked_sessions': revoked_count,
        }
    )


@auth_bp.route('/totp/disable', methods=['POST'])
@token_required
def disable_totp(current_user):
    data = request.json or {}
    current_password = str(data.get('current_password') or '')
    code = str(data.get('code') or '').strip()
    if not current_password or not code:
        return jsonify({'error': '请输入当前密码和动态验证码或恢复码'}), 400
    if not _current_password_valid(current_user['username'], current_password):
        return jsonify({'error': '当前密码不正确'}), 401

    ensure_totp_schema()
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT totp_enabled, totp_secret, totp_recovery_codes FROM admins WHERE username = ?",
        (current_user['username'],),
    )
    row = cursor.fetchone()
    if not row or not bool(row[0]):
        conn.close()
        return jsonify({'error': '两步验证尚未启用'}), 400
    valid_factor, _, _ = _verify_totp_or_recovery(row[1], row[2], code)
    if not valid_factor:
        conn.close()
        return jsonify({'error': '动态验证码或恢复码不正确'}), 400

    cursor.execute(
        """
        UPDATE admins
        SET totp_secret = NULL, totp_pending_secret = NULL, totp_enabled = 0,
            totp_recovery_codes = NULL, totp_failed_attempts = 0, totp_locked_until = NULL
        WHERE username = ?
        """,
        (current_user['username'],),
    )
    conn.commit()
    conn.close()
    revoked_count = revoke_other_sessions(
        username=current_user['username'],
        except_session_id=current_user['session_id'],
        actor_username=current_user['username'],
        reason='账号已关闭两步验证，其他设备需要重新登录',
    )
    return jsonify(
        {
            'message': '两步验证已关闭',
            'enabled': False,
            'revoked_sessions': revoked_count,
        }
    )


@auth_bp.route('/totp/recovery-codes', methods=['POST'])
@token_required
def regenerate_totp_recovery_codes(current_user):
    data = request.json or {}
    current_password = str(data.get('current_password') or '')
    code = str(data.get('code') or '').strip()
    if not current_password or not code:
        return jsonify({'error': '请输入当前密码和动态验证码或恢复码'}), 400
    if not _current_password_valid(current_user['username'], current_password):
        return jsonify({'error': '当前密码不正确'}), 401

    ensure_totp_schema()
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT totp_enabled, totp_secret, totp_recovery_codes FROM admins WHERE username = ?",
        (current_user['username'],),
    )
    row = cursor.fetchone()
    if not row or not bool(row[0]):
        conn.close()
        return jsonify({'error': '两步验证尚未启用'}), 400
    valid_factor, _, _ = _verify_totp_or_recovery(row[1], row[2], code)
    if not valid_factor:
        conn.close()
        return jsonify({'error': '动态验证码或恢复码不正确'}), 400

    recovery_codes = generate_recovery_codes()
    cursor.execute(
        "UPDATE admins SET totp_recovery_codes = ? WHERE username = ?",
        (dump_recovery_code_hashes(recovery_codes), current_user['username']),
    )
    conn.commit()
    conn.close()
    return jsonify(
        {
            'message': '恢复码已重新生成，旧恢复码已失效',
            'recovery_codes': recovery_codes,
        }
    )


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
    if len(str(new_password)) < 6:
        return jsonify({'error': '新密码长度不能少于 6 个字符'}), 400
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

    revoked_count = revoke_other_sessions(
        username=current_user['username'],
        except_session_id=current_user['session_id'],
        actor_username=current_user['username'],
        reason='账号密码已修改，其他设备需要重新登录',
    )
    return jsonify({'message': '密码修改成功', 'revoked_sessions': revoked_count})
