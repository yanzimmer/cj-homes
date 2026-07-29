import base64
import hashlib
import hmac
import json
import secrets
import struct
import time
from urllib.parse import quote, urlencode


TOTP_DIGITS = 6
TOTP_PERIOD_SECONDS = 30
TOTP_ISSUER = "从江房屋登记系统"


def generate_totp_secret():
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def build_totp_uri(secret, account_name, issuer=TOTP_ISSUER):
    label = quote(f"{issuer}:{account_name}", safe="")
    query = urlencode(
        {
            "secret": secret,
            "issuer": issuer,
            "algorithm": "SHA1",
            "digits": TOTP_DIGITS,
            "period": TOTP_PERIOD_SECONDS,
        }
    )
    return f"otpauth://totp/{label}?{query}"


def totp_code(secret, for_time=None, digits=TOTP_DIGITS, period=TOTP_PERIOD_SECONDS):
    timestamp = time.time() if for_time is None else float(for_time)
    counter = int(timestamp // period)
    padded_secret = str(secret or "").strip().upper()
    padded_secret += "=" * ((8 - len(padded_secret) % 8) % 8)
    key = base64.b32decode(padded_secret, casefold=True)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(value % (10 ** digits)).zfill(digits)


def verify_totp(secret, code, for_time=None, valid_window=1):
    normalized = str(code or "").strip().replace(" ", "")
    if len(normalized) != TOTP_DIGITS or not normalized.isdigit():
        return False
    timestamp = time.time() if for_time is None else float(for_time)
    for offset in range(-valid_window, valid_window + 1):
        candidate = totp_code(secret, timestamp + offset * TOTP_PERIOD_SECONDS)
        if hmac.compare_digest(candidate, normalized):
            return True
    return False


def normalize_recovery_code(value):
    return "".join(ch for ch in str(value or "").upper() if ch.isalnum())


def hash_recovery_code(value):
    normalized = normalize_recovery_code(value)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def generate_recovery_codes(count=10):
    return [f"{secrets.token_hex(3).upper()}-{secrets.token_hex(3).upper()}" for _ in range(count)]


def dump_recovery_code_hashes(codes):
    return json.dumps([hash_recovery_code(code) for code in codes], ensure_ascii=True)


def parse_recovery_code_hashes(value):
    try:
        data = json.loads(str(value or "[]"))
    except Exception:
        return []
    return [str(item) for item in data if str(item).strip()] if isinstance(data, list) else []


def verify_recovery_code(value, stored_hashes):
    candidate = hash_recovery_code(value)
    for index, stored_hash in enumerate(stored_hashes):
        if hmac.compare_digest(candidate, stored_hash):
            return True, stored_hashes[:index] + stored_hashes[index + 1:]
    return False, stored_hashes
