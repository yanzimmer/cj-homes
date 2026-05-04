import json
import sqlite3
from datetime import datetime

import jwt
from flask import request

from common import SECRET_KEY, connect


SENSITIVE_KEYS = {
    "password",
    "old_password",
    "new_password",
    "access_key_secret",
    "secret",
    "token",
    "authorization",
}


def ensure_audit_logs_schema():
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            username TEXT,
            user_id INTEGER,
            method TEXT NOT NULL,
            path TEXT NOT NULL,
            action TEXT,
            module TEXT,
            status_code INTEGER,
            ip_address TEXT,
            user_agent TEXT,
            request_summary TEXT,
            error TEXT
        )
        """
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_audit_logs_username ON audit_logs(username)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_audit_logs_module ON audit_logs(module)")
    conn.commit()
    conn.close()


def _mask_payload(value):
    if isinstance(value, dict):
        masked = {}
        for key, item in value.items():
            lower_key = str(key or "").lower()
            if lower_key in SENSITIVE_KEYS or "password" in lower_key or "secret" in lower_key:
                masked[key] = "***"
            else:
                masked[key] = _mask_payload(item)
        return masked
    if isinstance(value, list):
        return [_mask_payload(item) for item in value[:20]]
    return value


def _request_summary():
    try:
        if request.is_json:
            return json.dumps(_mask_payload(request.get_json(silent=True) or {}), ensure_ascii=False)[:3000]
        if request.files:
            files = []
            for name, storage in request.files.items():
                files.append({
                    "field": name,
                    "filename": storage.filename,
                    "content_type": storage.content_type,
                })
            return json.dumps({"files": files, "form": _mask_payload(request.form.to_dict())}, ensure_ascii=False)[:3000]
        if request.form:
            return json.dumps(_mask_payload(request.form.to_dict()), ensure_ascii=False)[:3000]
        if request.args:
            return json.dumps({"query": _mask_payload(request.args.to_dict())}, ensure_ascii=False)[:3000]
    except Exception:
        return ""
    return ""


def _current_user_from_token():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        if request.path.endswith("/login") and request.is_json:
            data = request.get_json(silent=True) or {}
            return str(data.get("username") or ""), None
        return "", None
    token = auth_header.split(" ", 1)[1]
    try:
        data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"], options={"verify_exp": False})
        username = data.get("username") or ""
        conn = connect()
        cur = conn.cursor()
        cur.execute("SELECT id FROM admins WHERE username = ? LIMIT 1", (username,))
        row = cur.fetchone()
        conn.close()
        return username, row[0] if row else None
    except Exception:
        return "", None


def module_from_path(path):
    text = str(path or "").strip("/")
    parts = text.split("/")
    if len(parts) >= 2 and parts[0] == "api":
        return parts[1]
    return parts[0] if parts else ""


def action_from_request(method, path):
    normalized = str(path or "")
    method = str(method or "").upper()
    if normalized.endswith("/login"):
        return "登录"
    if normalized.endswith("/export"):
        return "导出"
    if normalized.endswith("/import"):
        return "导入"
    if normalized.endswith("/reset"):
        return "重置"
    if normalized.endswith("/seed"):
        return "生成演示数据"
    if method == "POST":
        return "新增/提交"
    if method == "PUT":
        return "修改"
    if method == "DELETE":
        return "删除"
    return method


def should_audit_request(method, path):
    method = str(method or "").upper()
    path = str(path or "")
    if not path.startswith("/api/"):
        return False
    if path.startswith("/api/system/logs"):
        return False
    if path.startswith("/api/uploads/chunk/") and not path.endswith("/complete"):
        return False
    if method in ("POST", "PUT", "DELETE"):
        return True
    if method == "GET" and path.endswith("/export"):
        return True
    return False


def record_audit_log(response=None, error=""):
    try:
        ensure_audit_logs_schema()
        username, user_id = _current_user_from_token()
        conn = connect()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO audit_logs (
                created_at, username, user_id, method, path, action, module,
                status_code, ip_address, user_agent, request_summary, error
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                username,
                user_id,
                request.method,
                request.path,
                action_from_request(request.method, request.path),
                module_from_path(request.path),
                getattr(response, "status_code", None),
                request.headers.get("X-Forwarded-For", request.remote_addr or "").split(",")[0].strip(),
                (request.headers.get("User-Agent") or "")[:500],
                _request_summary(),
                str(error or "")[:1000],
            ),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass
