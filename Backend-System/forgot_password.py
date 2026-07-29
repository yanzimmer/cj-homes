import hashlib
from datetime import datetime, timedelta

from common import connect


MAX_RECOVERY_ATTEMPTS = 5
RECOVERY_LOCK_MINUTES = 15
LEGACY_DEFAULT_ANSWER_HASH = "1c6c0a7f01c9bf04faf4e2dc460874875094608f3632bdd6ea0ee11222c83186"


def _now_text(value=None):
    return (value or datetime.now()).strftime("%Y-%m-%d %H:%M:%S")


def ensure_schema():
    """Ensure admins table exists and has recovery fields for forgot password."""
    conn = connect()
    cursor = conn.cursor()

    # Ensure base admins table exists
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT,
            created_at DATE DEFAULT (DATE('now'))
        )
        """
    )

    # Inspect existing columns
    cursor.execute("PRAGMA table_info(admins)")
    cols = {row[1] for row in cursor.fetchall()}

    is_lockout_migration = 'recovery_failed_attempts' not in cols

    # Add recovery phrase hash column
    if 'recovery_phrase_hash' not in cols:
        cursor.execute("ALTER TABLE admins ADD COLUMN recovery_phrase_hash TEXT")
    # Add security question text column
    if 'security_question' not in cols:
        cursor.execute("ALTER TABLE admins ADD COLUMN security_question TEXT")
    # Add security answer hash column
    if 'security_answer_hash' not in cols:
        cursor.execute("ALTER TABLE admins ADD COLUMN security_answer_hash TEXT")
    if 'recovery_failed_attempts' not in cols:
        cursor.execute("ALTER TABLE admins ADD COLUMN recovery_failed_attempts INTEGER NOT NULL DEFAULT 0")
    if 'recovery_locked_until' not in cols:
        cursor.execute("ALTER TABLE admins ADD COLUMN recovery_locked_until TEXT")
    if 'recovery_updated_at' not in cols:
        cursor.execute("ALTER TABLE admins ADD COLUMN recovery_updated_at TEXT")

    # Previous versions rewrote this known answer on every startup. Invalidate it
    # once while adding the lockout columns so upgraded installations are safe.
    if is_lockout_migration:
        cursor.execute(
            """
            UPDATE admins
            SET security_answer_hash = NULL,
                recovery_failed_attempts = 0,
                recovery_locked_until = NULL,
                recovery_updated_at = NULL
            WHERE security_answer_hash = ?
            """,
            (LEGACY_DEFAULT_ANSWER_HASH,),
        )

    conn.commit()
    conn.close()

def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def get_recovery_status(username: str):
    ensure_schema()
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT security_answer_hash, recovery_locked_until, recovery_updated_at
        FROM admins
        WHERE username = ?
        """,
        (str(username or '').strip(),),
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    return {
        'configured': bool(row[0]),
        'locked_until': row[1] or '',
        'updated_at': row[2] or '',
    }


def verify_and_reset_password(username: str, answer: str, new_password: str):
    """仅通过安全问题答案找回并重置密码。"""
    ensure_schema()
    conn = connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, security_question, security_answer_hash,
               recovery_failed_attempts, recovery_locked_until
        FROM admins
        WHERE username = ?
        """,
        (username,)
    )
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False, "用户不存在"

    admin_id, _, sec_ans_hash, failed_attempts, locked_until = row

    if not sec_ans_hash:
        conn.close()
        return False, "未设置安全口令，无法找回"
    now = datetime.now()
    if locked_until:
        try:
            locked_until_dt = datetime.strptime(locked_until, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            locked_until_dt = None
        if locked_until_dt and locked_until_dt > now:
            conn.close()
            return False, f"尝试次数过多，请于 {locked_until} 后重试"
        cursor.execute(
            "UPDATE admins SET recovery_failed_attempts = 0, recovery_locked_until = NULL WHERE id = ?",
            (admin_id,),
        )
        failed_attempts = 0

    if sha256(answer) != sec_ans_hash:
        failed_attempts = int(failed_attempts or 0) + 1
        if failed_attempts >= MAX_RECOVERY_ATTEMPTS:
            next_allowed_at = _now_text(now + timedelta(minutes=RECOVERY_LOCK_MINUTES))
            cursor.execute(
                """
                UPDATE admins
                SET recovery_failed_attempts = ?, recovery_locked_until = ?
                WHERE id = ?
                """,
                (failed_attempts, next_allowed_at, admin_id),
            )
            conn.commit()
            conn.close()
            return False, f"连续验证失败 {MAX_RECOVERY_ATTEMPTS} 次，请于 {next_allowed_at} 后重试"
        cursor.execute(
            "UPDATE admins SET recovery_failed_attempts = ? WHERE id = ?",
            (failed_attempts, admin_id),
        )
        conn.commit()
        conn.close()
        remaining = MAX_RECOVERY_ATTEMPTS - failed_attempts
        return False, f"安全口令不正确，还可尝试 {remaining} 次"

    # 更新密码
    new_hash = sha256(new_password)
    cursor.execute(
        """
        UPDATE admins
        SET password_hash = ?, recovery_failed_attempts = 0, recovery_locked_until = NULL
        WHERE id = ?
        """,
        (new_hash, admin_id),
    )
    conn.commit()
    conn.close()
    return True, "密码重置成功"


def set_recovery_info(username: str, recovery_phrase: str | None = None, security_question: str | None = None, security_answer: str | None = None):
    """Helper to set recovery phrase and/or security question/answer for a user."""
    ensure_schema()
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM admins WHERE username = ?", (username,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False, "用户不存在"
    admin_id = row[0]

    updates = []
    params = []
    if recovery_phrase is not None:
        updates.append("recovery_phrase_hash = ?")
        params.append(sha256(recovery_phrase))
    if security_question is not None:
        updates.append("security_question = ?")
        params.append(security_question)
    if security_answer is not None:
        updates.append("security_answer_hash = ?")
        params.append(sha256(security_answer))
        updates.extend([
            "recovery_failed_attempts = 0",
            "recovery_locked_until = NULL",
            "recovery_updated_at = ?",
        ])
        params.append(_now_text())

    if not updates:
        conn.close()
        return False, "无更新内容"

    params.append(admin_id)
    cursor.execute(f"UPDATE admins SET {', '.join(updates)} WHERE id = ?", params)
    conn.commit()
    conn.close()
    return True, "找回信息已更新"
