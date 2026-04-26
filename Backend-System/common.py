# 该文件负责提供后端通用配置、数据库连接与分页字段处理等共享工具。
import os
import sqlite3
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Base directory for resolving paths
BASE_DIR = os.path.dirname(__file__)

# Shared database path (moved into sql folder)
DB_NAME = os.path.join(BASE_DIR, "sql", "hotel.db")


def connect():
    """Create a SQLite connection with foreign keys enabled."""
    # Ensure the sql directory exists before connecting
    os.makedirs(os.path.dirname(DB_NAME), exist_ok=True)
    conn = sqlite3.connect(DB_NAME)
    # Enable foreign keys, WAL mode and a reasonable busy timeout to reduce 'database is locked'
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA busy_timeout = 5000")  # wait up to 5s when DB is busy
    except Exception:
        # Some PRAGMA may fail on certain environments; ignore silently
        pass
    return conn


def _safe_int(value, default_value):
    try:
        parsed = int(value)
        return parsed
    except Exception:
        return default_value


def parse_pagination_args(args, default_page=1, default_page_size=20, max_page_size=200):
    """
    Parse `page` and `page_size` from query args.

    Returns:
        (page, page_size, enabled)
        - enabled is True only when either page or page_size is explicitly provided.
    """
    has_page = args.get('page') is not None
    has_page_size = args.get('page_size') is not None
    enabled = has_page or has_page_size

    page = _safe_int(args.get('page', default_page), default_page)
    page_size = _safe_int(args.get('page_size', default_page_size), default_page_size)

    if page < 1:
        page = 1
    if page_size < 1:
        page_size = default_page_size
    if max_page_size > 0:
        page_size = min(page_size, max_page_size)

    return page, page_size, enabled


def paginate_list(items, page, page_size):
    total = len(items)
    if page_size <= 0:
        page_size = 1
    total_pages = max(1, (total + page_size - 1) // page_size)
    if page > total_pages:
        page = total_pages
    start = (page - 1) * page_size
    end = start + page_size
    return items[start:end], {
        'page': page,
        'page_size': page_size,
        'total': total,
        'total_pages': total_pages,
    }


def parse_fields_arg(args, allowed_fields):
    """
    Parse `fields` query arg (comma-separated) and return a validated set.
    Returns None when not provided or empty.
    """
    raw = str(args.get('fields') or '').strip()
    if raw == '':
        return None
    allowed = set(allowed_fields or [])
    selected = []
    for token in raw.split(','):
        key = token.strip()
        if key and key in allowed and key not in selected:
            selected.append(key)
    if not selected:
        return None
    return set(selected)


def project_fields(items, selected_fields, always_include=None):
    if not selected_fields:
        return items
    must_have = set(always_include or [])
    allowed = set(selected_fields) | must_have
    projected = []
    for item in items:
        projected.append({k: v for k, v in item.items() if k in allowed})
    return projected


# Authentication constants (keep consistent with existing modules)
SECRET_KEY = os.getenv('SECRET_KEY', 'homes_rental_secret_key')
JWT_EXPIRATION_DELTA = int(os.getenv('JWT_EXPIRATION_DELTA', 30)) * 60  # minutes to seconds
