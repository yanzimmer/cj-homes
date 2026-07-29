import argparse
import getpass
import sys

import forgot_password as recovery
from common import connect
from session_manager import revoke_other_sessions


def reset_admin_password(username, new_password, disable_totp=False):
    username = str(username or "").strip()
    if not username:
        raise ValueError("管理员账号不能为空")
    if len(new_password) < 6:
        raise ValueError("新密码长度不能少于 6 个字符")

    recovery.ensure_schema()
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM admins WHERE username = ?", (username,))
    if not cursor.fetchone():
        conn.close()
        raise ValueError(f"管理员账号 {username} 不存在")
    if disable_totp:
        cursor.execute("PRAGMA table_info(admins)")
        columns = {row[1] for row in cursor.fetchall()}
        if "totp_enabled" in columns:
            cursor.execute(
                """
                UPDATE admins
                SET password_hash = ?, recovery_failed_attempts = 0, recovery_locked_until = NULL,
                    totp_secret = NULL, totp_pending_secret = NULL, totp_enabled = 0,
                    totp_recovery_codes = NULL, totp_failed_attempts = 0, totp_locked_until = NULL
                WHERE username = ?
                """,
                (recovery.sha256(new_password), username),
            )
        else:
            cursor.execute(
                """
                UPDATE admins
                SET password_hash = ?, recovery_failed_attempts = 0, recovery_locked_until = NULL
                WHERE username = ?
                """,
                (recovery.sha256(new_password), username),
            )
    else:
        cursor.execute(
            """
            UPDATE admins
            SET password_hash = ?, recovery_failed_attempts = 0, recovery_locked_until = NULL
            WHERE username = ?
            """,
            (recovery.sha256(new_password), username),
        )
    conn.commit()
    conn.close()

    return revoke_other_sessions(
        username=username,
        except_session_id="",
        actor_username=username,
        reason="管理员通过服务器命令重置密码，旧会话已失效",
    )


def main():
    parser = argparse.ArgumentParser(description="从服务器终端重置 Homes 管理员密码")
    parser.add_argument("--username", default="admin", help="管理员账号，默认 admin")
    parser.add_argument(
        "--disable-totp",
        action="store_true",
        help="同时停用两步验证（仅在身份验证器和恢复码均丢失时使用）",
    )
    args = parser.parse_args()

    password = getpass.getpass("请输入新密码: ")
    confirmation = getpass.getpass("请再次输入新密码: ")
    if password != confirmation:
        print("两次输入的密码不一致", file=sys.stderr)
        return 1

    try:
        revoked_count = reset_admin_password(args.username, password, disable_totp=args.disable_totp)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    totp_message = "，两步验证已停用" if args.disable_totp else ""
    print(f"管理员 {args.username} 的密码已重置{totp_message}，已注销 {revoked_count} 个旧会话。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
