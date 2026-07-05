import json
import hashlib
import os
import re
import uuid
from datetime import datetime

from common import BASE_DIR, JWT_EXPIRATION_DELTA, connect


SESSION_SETTINGS_FILE = os.path.join(BASE_DIR, "config", "session_settings.json")
DEFAULT_SESSION_SETTINGS = {
    "login_mode": "multi",
    "token_ttl_minutes": max(1, int(JWT_EXPIRATION_DELTA // 60)),
}


def _now_text():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _normalize_login_mode(value):
    return "single" if str(value or "").strip().lower() == "single" else "multi"


def _normalize_token_ttl_minutes(value):
    try:
        minutes = int(value)
    except Exception:
        minutes = DEFAULT_SESSION_SETTINGS["token_ttl_minutes"]
    return max(5, min(minutes, 7 * 24 * 60))


def _trim_text(value, max_length=240):
    text = str(value or "").strip()
    if len(text) > max_length:
        return f"{text[:max_length]}..."
    return text


def _device_fingerprint(username, ip_address, user_agent):
    raw = "|".join([
        str(username or "").strip().lower(),
        str(ip_address or "").strip(),
        str(user_agent or "").strip().lower(),
    ])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _guess_device_label(user_agent):
    ua = str(user_agent or "").strip()
    if not ua:
        return "未知设备"

    browser = "浏览器"
    browser_rules = [
        (r"Edg/", "Edge"),
        (r"Chrome/", "Chrome"),
        (r"Firefox/", "Firefox"),
        (r"Safari/", "Safari"),
        (r"MicroMessenger/", "微信"),
    ]
    for pattern, label in browser_rules:
        if re.search(pattern, ua, re.IGNORECASE):
            browser = label
            break

    platform = "桌面端"
    platform_rules = [
        (r"iPhone|iPad|iPod", "iPhone/iPad"),
        (r"Android", "Android"),
        (r"Windows", "Windows"),
        (r"Macintosh|Mac OS X", "Mac"),
        (r"Linux", "Linux"),
    ]
    for pattern, label in platform_rules:
        if re.search(pattern, ua, re.IGNORECASE):
            platform = label
            break

    return f"{platform} / {browser}"


def load_session_settings():
    data = {}
    if os.path.exists(SESSION_SETTINGS_FILE):
        try:
            with open(SESSION_SETTINGS_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    data.update(loaded)
        except Exception:
            data = {}

    merged = dict(DEFAULT_SESSION_SETTINGS)
    merged.update(data)
    merged["login_mode"] = _normalize_login_mode(merged.get("login_mode"))
    merged["token_ttl_minutes"] = _normalize_token_ttl_minutes(merged.get("token_ttl_minutes"))
    return merged


def save_session_settings(data):
    current = load_session_settings()
    if isinstance(data, dict) and "login_mode" in data:
        current["login_mode"] = _normalize_login_mode(data.get("login_mode"))
    if isinstance(data, dict) and "token_ttl_minutes" in data:
        current["token_ttl_minutes"] = _normalize_token_ttl_minutes(data.get("token_ttl_minutes"))

    os.makedirs(os.path.dirname(SESSION_SETTINGS_FILE), exist_ok=True)
    with open(SESSION_SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(current, f, ensure_ascii=False, indent=2)
    return current


def ensure_session_schema():
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS admin_sessions (
            session_id TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            full_name TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            login_mode TEXT NOT NULL DEFAULT 'multi',
            ip_address TEXT,
            user_agent TEXT,
            device_label TEXT,
            device_fingerprint TEXT,
            created_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            expires_at TEXT,
            revoked_at TEXT,
            revoked_reason TEXT
        )
        """
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_admin_sessions_username_status ON admin_sessions (username, status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_admin_sessions_last_seen ON admin_sessions (last_seen_at DESC)")
    cursor.execute("PRAGMA table_info(admin_sessions)")
    session_columns = {row[1] for row in cursor.fetchall()}
    if "device_fingerprint" not in session_columns:
        cursor.execute("ALTER TABLE admin_sessions ADD COLUMN device_fingerprint TEXT")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_admin_sessions_device_fingerprint ON admin_sessions (username, device_fingerprint)")
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS admin_session_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            username TEXT NOT NULL,
            event_type TEXT NOT NULL,
            title TEXT NOT NULL,
            message TEXT,
            actor_username TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_admin_session_events_created ON admin_session_events (id DESC)")
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS admin_login_restrictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            device_fingerprint TEXT NOT NULL,
            device_label TEXT,
            ip_address TEXT,
            user_agent TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            restricted_at TEXT NOT NULL,
            restricted_by TEXT,
            reason TEXT,
            released_at TEXT,
            released_by TEXT
        )
        """
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_admin_login_restrictions_active ON admin_login_restrictions (username, device_fingerprint, status)")
    conn.commit()
    conn.close()


def _row_to_session(row):
    if not row:
        return None
    return {
        "session_id": row[0],
        "username": row[1],
        "full_name": row[2],
        "status": row[3],
        "login_mode": row[4],
        "ip_address": row[5] or "",
        "user_agent": row[6] or "",
        "device_label": row[7] or "未知设备",
        "device_fingerprint": row[8] or "",
        "created_at": row[9] or "",
        "last_seen_at": row[10] or "",
        "expires_at": row[11] or "",
        "revoked_at": row[12] or "",
        "revoked_reason": row[13] or "",
    }


def _row_to_event(row):
    if not row:
        return None
    return {
        "id": row[0],
        "session_id": row[1] or "",
        "username": row[2],
        "event_type": row[3],
        "title": row[4],
        "message": row[5] or "",
        "actor_username": row[6] or "",
        "created_at": row[7] or "",
    }


def get_session_invalid_payload(session):
    if not session:
        return {
            "error": "当前登录已失效，请重新登录",
            "code": "AUTH_SESSION_INVALID",
        }
    status = str(session.get("status") or "").strip().lower()
    reason = str(session.get("revoked_reason") or "").strip()
    if status == "revoked":
        if "管理员" in reason and "限制登录" in reason:
            return {
                "error": "你已被管理员手动下线，请联系管理。",
                "code": "AUTH_SESSION_REVOKED",
            }
        if "管理员" in reason:
            return {
                "error": "你已被管理员手动下线，请联系管理。",
                "code": "AUTH_SESSION_REVOKED",
            }
        if "新设备" in reason or "其他设备" in reason or "新的登录" in reason or "旧设备已自动下线" in reason:
            return {
                "error": "你的登录已在其他设备上失效，请重新登录",
                "code": "AUTH_SESSION_REPLACED",
            }
        return {
            "error": reason or "当前登录已失效，请重新登录",
            "code": "AUTH_SESSION_REVOKED",
        }
    if status == "expired":
        return {
            "error": "登录状态已过期，请重新登录",
            "code": "AUTH_TOKEN_EXPIRED",
        }
    return {
        "error": "当前登录已失效，请重新登录",
        "code": "AUTH_SESSION_INVALID",
    }


def _row_to_restriction(row):
    if not row:
        return None
    return {
        "id": row[0],
        "username": row[1],
        "device_fingerprint": row[2] or "",
        "device_label": row[3] or "未知设备",
        "ip_address": row[4] or "",
        "user_agent": row[5] or "",
        "status": row[6] or "active",
        "restricted_at": row[7] or "",
        "restricted_by": row[8] or "",
        "reason": row[9] or "",
        "released_at": row[10] or "",
        "released_by": row[11] or "",
    }


def get_login_restriction(username, ip_address="", user_agent="", device_fingerprint=""):
    ensure_session_schema()
    fingerprint = str(device_fingerprint or "").strip() or _device_fingerprint(username, ip_address, user_agent)
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, username, device_fingerprint, device_label, ip_address, user_agent, status,
               restricted_at, restricted_by, reason, released_at, released_by
        FROM admin_login_restrictions
        WHERE username = ? AND device_fingerprint = ? AND status = 'active'
        ORDER BY id DESC
        LIMIT 1
        """,
        (str(username or "").strip(), fingerprint),
    )
    row = cursor.fetchone()
    conn.close()
    return _row_to_restriction(row)


def list_active_login_restrictions():
    ensure_session_schema()
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, username, device_fingerprint, device_label, ip_address, user_agent, status,
               restricted_at, restricted_by, reason, released_at, released_by
        FROM admin_login_restrictions
        WHERE status = 'active'
        ORDER BY restricted_at DESC, id DESC
        """
    )
    rows = cursor.fetchall()
    conn.close()
    return [_row_to_restriction(row) for row in rows]


def restrict_device_login(username, device_fingerprint, device_label="", ip_address="", user_agent="", actor_username="", reason="管理员已限制该设备登录"):
    ensure_session_schema()
    existing = get_login_restriction(username, device_fingerprint=device_fingerprint)
    if existing:
        return existing
    now_text = _now_text()
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO admin_login_restrictions (
            username, device_fingerprint, device_label, ip_address, user_agent, status,
            restricted_at, restricted_by, reason, released_at, released_by
        )
        VALUES (?, ?, ?, ?, ?, 'active', ?, ?, ?, '', '')
        """,
        (
            str(username or "").strip(),
            str(device_fingerprint or "").strip(),
            _trim_text(device_label, 80),
            _trim_text(ip_address, 60),
            _trim_text(user_agent, 500),
            now_text,
            str(actor_username or "").strip(),
            _trim_text(reason, 240),
        ),
    )
    conn.commit()
    conn.close()
    return get_login_restriction(username, device_fingerprint=device_fingerprint)


def release_device_login_restriction(username, device_fingerprint, actor_username=""):
    ensure_session_schema()
    current = get_login_restriction(username, device_fingerprint=device_fingerprint)
    if not current:
        return False, "该设备当前没有登录限制"
    now_text = _now_text()
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE admin_login_restrictions
        SET status = 'released', released_at = ?, released_by = ?
        WHERE username = ? AND device_fingerprint = ? AND status = 'active'
        """,
        (
            now_text,
            str(actor_username or "").strip(),
            str(username or "").strip(),
            str(device_fingerprint or "").strip(),
        ),
    )
    conn.commit()
    conn.close()
    return True, "已解除该设备的登录限制"


def record_session_event(session_id, username, event_type, title, message="", actor_username=""):
    ensure_session_schema()
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO admin_session_events (session_id, username, event_type, title, message, actor_username, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(session_id or "").strip(),
            str(username or "").strip(),
            str(event_type or "").strip() or "info",
            _trim_text(title, 80) or "会话事件",
            _trim_text(message, 240),
            str(actor_username or "").strip(),
            _now_text(),
        ),
    )
    conn.commit()
    conn.close()


def _mark_expired_sessions(conn=None):
    owns_conn = conn is None
    if owns_conn:
        conn = connect()
    cursor = conn.cursor()
    now_text = _now_text()
    cursor.execute(
        """
        SELECT session_id, username, device_label
        FROM admin_sessions
        WHERE status = 'active' AND expires_at IS NOT NULL AND expires_at != '' AND expires_at < ?
        """,
        (now_text,),
    )
    rows = cursor.fetchall()
    if rows:
        cursor.execute(
            """
            UPDATE admin_sessions
            SET status = 'expired', revoked_at = ?, revoked_reason = ?
            WHERE status = 'active' AND expires_at IS NOT NULL AND expires_at != '' AND expires_at < ?
            """,
            (now_text, "登录超时自动下线", now_text),
        )
        for session_id, username, device_label in rows:
            cursor.execute(
                """
                INSERT INTO admin_session_events (session_id, username, event_type, title, message, actor_username, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    username,
                    "expired",
                    f"{username} 会话已过期",
                    f"{device_label or '设备'} 长时间无活动，系统已自动下线",
                    "",
                    now_text,
                ),
            )
    if owns_conn:
        conn.commit()
        conn.close()


def get_session(session_id):
    ensure_session_schema()
    conn = connect()
    _mark_expired_sessions(conn)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT session_id, username, full_name, status, login_mode, ip_address, user_agent,
               device_label, device_fingerprint, created_at, last_seen_at, expires_at, revoked_at, revoked_reason
        FROM admin_sessions
        WHERE session_id = ?
        LIMIT 1
        """,
        (session_id,),
    )
    row = cursor.fetchone()
    conn.commit()
    conn.close()
    return _row_to_session(row)


def touch_session(session_id, expires_at=""):
    ensure_session_schema()
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE admin_sessions
        SET last_seen_at = ?, expires_at = ?
        WHERE session_id = ? AND status = 'active'
        """,
        (_now_text(), str(expires_at or "").strip(), session_id),
    )
    conn.commit()
    conn.close()


def expire_session(session_id, reason="认证令牌已过期"):
    ensure_session_schema()
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT session_id, username, device_label, status
        FROM admin_sessions
        WHERE session_id = ?
        LIMIT 1
        """,
        (session_id,),
    )
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False

    if row[3] != "active":
        conn.close()
        return False

    now_text = _now_text()
    cursor.execute(
        """
        UPDATE admin_sessions
        SET status = 'expired', revoked_at = ?, revoked_reason = ?
        WHERE session_id = ?
        """,
        (now_text, reason, session_id),
    )
    cursor.execute(
        """
        INSERT INTO admin_session_events (session_id, username, event_type, title, message, actor_username, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            row[0],
            row[1],
            "expired",
            f"{row[1]} 会话已过期",
            f"{row[2] or '设备'} 登录状态已过期，需要重新登录",
            "",
            now_text,
        ),
    )
    conn.commit()
    conn.close()
    return True


def revoke_session(session_id, actor_username="", reason="管理员手动下线", event_type="revoked"):
    ensure_session_schema()
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT session_id, username, device_label, status
        FROM admin_sessions
        WHERE session_id = ?
        LIMIT 1
        """,
        (session_id,),
    )
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False, "会话不存在"

    if row[3] != "active":
        conn.close()
        return False, "该会话已经离线"

    now_text = _now_text()
    cursor.execute(
        """
        UPDATE admin_sessions
        SET status = 'revoked', revoked_at = ?, revoked_reason = ?
        WHERE session_id = ?
        """,
        (now_text, reason, session_id),
    )
    actor_text = str(actor_username or "").strip()
    message = f"{row[2] or '设备'} 已下线"
    if actor_text and actor_text != row[1]:
        message = f"{message}，操作人：{actor_text}"
    cursor.execute(
        """
        INSERT INTO admin_session_events (session_id, username, event_type, title, message, actor_username, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            row[0],
            row[1],
            event_type,
            f"{row[1]} 已下线",
            _trim_text(f"{reason}。{message}", 240),
            actor_text,
            now_text,
        ),
    )
    conn.commit()
    conn.close()
    return True, "会话已下线"


def logout_session(session_id, actor_username=""):
    return revoke_session(session_id, actor_username=actor_username, reason="用户主动退出登录", event_type="logout")


def restrict_session_login(session_id, actor_username="", reason="管理员手动下线并限制该设备登录"):
    ensure_session_schema()
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT session_id, username, full_name, status, login_mode, ip_address, user_agent,
               device_label, device_fingerprint, created_at, last_seen_at, expires_at, revoked_at, revoked_reason
        FROM admin_sessions
        WHERE session_id = ?
        LIMIT 1
        """,
        (session_id,),
    )
    row = cursor.fetchone()
    conn.close()
    session = _row_to_session(row)
    if not session:
        return False, "会话不存在"

    fingerprint = session.get("device_fingerprint") or _device_fingerprint(
        session.get("username"),
        session.get("ip_address"),
        session.get("user_agent"),
    )
    restrict_device_login(
        session.get("username"),
        fingerprint,
        device_label=session.get("device_label"),
        ip_address=session.get("ip_address"),
        user_agent=session.get("user_agent"),
        actor_username=actor_username,
        reason="管理员已限制该设备再次登录",
    )
    revoke_session(
        session_id,
        actor_username=actor_username,
        reason=reason,
        event_type="restricted",
    )
    return True, "已下线该设备，并限制再次登录"


def release_session_login_restriction(session_id, actor_username=""):
    ensure_session_schema()
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT session_id, username, full_name, status, login_mode, ip_address, user_agent,
               device_label, device_fingerprint, created_at, last_seen_at, expires_at, revoked_at, revoked_reason
        FROM admin_sessions
        WHERE session_id = ?
        LIMIT 1
        """,
        (session_id,),
    )
    row = cursor.fetchone()
    conn.close()
    session = _row_to_session(row)
    if not session:
        return False, "会话不存在"
    fingerprint = session.get("device_fingerprint") or _device_fingerprint(
        session.get("username"),
        session.get("ip_address"),
        session.get("user_agent"),
    )
    return release_device_login_restriction(session.get("username"), fingerprint, actor_username=actor_username)


def revoke_other_sessions(username, except_session_id="", actor_username="", reason="新设备登录，旧设备已自动下线"):
    ensure_session_schema()
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT session_id
        FROM admin_sessions
        WHERE username = ? AND status = 'active' AND session_id != ?
        """,
        (username, except_session_id or ""),
    )
    rows = cursor.fetchall()
    conn.close()

    count = 0
    for (session_id,) in rows:
        ok, _ = revoke_session(
            session_id,
            actor_username=actor_username or username,
            reason=reason,
            event_type="replaced",
        )
        if ok:
            count += 1
    return count


def create_session(username, full_name, ip_address="", user_agent="", expires_at=""):
    ensure_session_schema()
    settings = load_session_settings()
    login_mode = settings.get("login_mode", "multi")
    if login_mode == "single":
        revoke_other_sessions(
            username=username,
            except_session_id="",
            actor_username=username,
            reason="检测到新的登录，旧设备已自动下线",
        )

    session_id = str(uuid.uuid4())
    now_text = _now_text()
    device_label = _guess_device_label(user_agent)
    device_fingerprint = _device_fingerprint(username, ip_address, user_agent)
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO admin_sessions (
            session_id, username, full_name, status, login_mode, ip_address, user_agent,
            device_label, device_fingerprint, created_at, last_seen_at, expires_at, revoked_at, revoked_reason
        )
        VALUES (?, ?, ?, 'active', ?, ?, ?, ?, ?, ?, ?, ?, '', '')
        """,
        (
            session_id,
            username,
            full_name,
            login_mode,
            _trim_text(ip_address, 60),
            _trim_text(user_agent, 500),
            device_label,
            device_fingerprint,
            now_text,
            now_text,
            str(expires_at or "").strip(),
        ),
    )
    cursor.execute(
        """
        INSERT INTO admin_session_events (session_id, username, event_type, title, message, actor_username, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            session_id,
            username,
            "login",
            f"{username} 已上线",
            _trim_text(f"{device_label} 登录成功，IP：{ip_address or '未知'}", 240),
            username,
            now_text,
        ),
    )
    conn.commit()
    conn.close()
    return {
        "session_id": session_id,
        "device_label": device_label,
        "device_fingerprint": device_fingerprint,
        "login_mode": login_mode,
    }


def list_sessions(current_session_id="", include_history=True):
    ensure_session_schema()
    conn = connect()
    _mark_expired_sessions(conn)
    cursor = conn.cursor()
    sql = """
        SELECT session_id, username, full_name, status, login_mode, ip_address, user_agent,
               device_label, device_fingerprint, created_at, last_seen_at, expires_at, revoked_at, revoked_reason
        FROM admin_sessions
    """
    if not include_history:
        sql += " WHERE status = 'active'"
    sql += " ORDER BY CASE WHEN status = 'active' THEN 0 ELSE 1 END, last_seen_at DESC, created_at DESC LIMIT 100"
    cursor.execute(sql)
    rows = cursor.fetchall()
    conn.commit()
    conn.close()

    restriction_map = {
        (item["username"], item["device_fingerprint"]): item
        for item in list_active_login_restrictions()
    }
    sessions = []
    active_count = 0
    for row in rows:
        item = _row_to_session(row)
        item["is_current"] = item["session_id"] == current_session_id
        restriction = restriction_map.get((item["username"], item["device_fingerprint"]))
        item["login_restricted"] = bool(restriction)
        item["restriction_reason"] = restriction["reason"] if restriction else ""
        item["restriction_at"] = restriction["restricted_at"] if restriction else ""
        sessions.append(item)
        if item["status"] == "active":
            active_count += 1
    return {
        "sessions": sessions,
        "current_session_id": current_session_id,
        "active_count": active_count,
        "restricted_count": len(restriction_map),
        "settings": load_session_settings(),
    }


def list_session_events(limit=20, after_id=None):
    ensure_session_schema()
    conn = connect()
    _mark_expired_sessions(conn)
    cursor = conn.cursor()
    if after_id is not None:
        cursor.execute(
            """
            SELECT id, session_id, username, event_type, title, message, actor_username, created_at
            FROM admin_session_events
            WHERE id > ?
            ORDER BY id ASC
            LIMIT ?
            """,
            (int(after_id), max(1, min(int(limit or 20), 50))),
        )
        rows = cursor.fetchall()
    else:
        cursor.execute(
            """
            SELECT id, session_id, username, event_type, title, message, actor_username, created_at
            FROM admin_session_events
            ORDER BY id DESC
            LIMIT ?
            """,
            (max(1, min(int(limit or 20), 50)),),
        )
        rows = cursor.fetchall()
        rows = list(reversed(rows))
    conn.commit()
    conn.close()
    return [_row_to_event(row) for row in rows]
