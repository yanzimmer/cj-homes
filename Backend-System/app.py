import base64
import json
import logging
import os
import re
import subprocess
import time
from flask import Flask, jsonify, request
from flask_cors import CORS
from flasgger import Swagger

from common import BASE_DIR, SECRET_KEY, JWT_EXPIRATION_DELTA, connect
from contract_templates_api import templates_bp, ensure_contract_templates_schema
from contracts_api import contracts_bp, ensure_contracts_schema
from auth_api import auth_bp
from dashboard_api import dashboard_bp
from notify_api import notify_bp
from rooms_api import rooms_bp, ensure_rooms_schema
from self_checkin_api import self_checkin_bp, ensure_self_checkin_schema
from rent_collection_api import rent_collection_bp, ensure_rent_collection_schema
from tenants_api import tenants_bp
from moves_api import moves_bp
from repair_records_api import repair_bp, ensure_repair_records_schema
from system_api import system_bp
from procurement_api import procurement_bp, ensure_procurement_schema
from public_entry_links_api import public_entry_bp, ensure_public_entry_schema
from rent_ledger_api import rent_ledger_bp, ensure_rent_ledger_schema
from utility_bills_api import utility_bills_bp, ensure_utility_bills_schema
from warehouse_api import warehouse_bp, ensure_warehouse_schema
from upload_api import upload_bp
import forgot_password as fp
from log_config import configure_logging
from session_manager import ensure_session_schema


app = Flask(__name__)
# 鍏佽璺ㄥ煙骞舵樉寮忓０鏄庢柟娉曚笌璇锋眰澶达紝纭繚甯?Authorization 鐨勯妫€閫氳繃
CORS(
    app,
    resources={
        r"/api/*": {
            "origins": "*",
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"],
            # 鏆撮湶鍒锋柊浠ょ墝鐩稿叧鍝嶅簲澶达紝渚夸簬鍓嶇璇诲彇
            "expose_headers": ["Content-Type", "X-Refreshed-Token", "X-Token-Expires"],
        }
    },
    supports_credentials=True,
)

# 搴旂敤鍩虹閰嶇疆锛堥泦涓湪 common.py锛?
app.config['SECRET_KEY'] = SECRET_KEY
app.config['JWT_EXPIRATION_DELTA'] = JWT_EXPIRATION_DELTA

# 閰嶇疆 Swagger
app.config['SWAGGER'] = {
    'title': 'Homes Rental Management API',
    'uiversion': 3,
    'version': '1.1.3',
    'description': 'API documentation for Homes Rental Management System',
    'securityDefinitions': {
        'Bearer': {
            'type': 'apiKey',
            'name': 'Authorization',
            'in': 'header',
            'description': 'JWT Authorization header using the Bearer scheme. Example: "Bearer {token}"'
        }
    },
    'security': [
        {'Bearer': []}
    ]
}
swagger = Swagger(app)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log_paths = configure_logging(app)
app.logger.info(f"后端文件日志目录: {log_paths['log_dir']}")
APP_STARTED_AT = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
BACKEND_APP_VERSION = os.getenv("BACKEND_APP_VERSION", "1.1.3")
REPO_ROOT = os.path.dirname(BASE_DIR)


def _resolve_git_commit():
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=3,
        )
        commit = (result.stdout or "").strip()
        return commit or "unknown"
    except Exception:
        return "unknown"


BACKEND_GIT_COMMIT = _resolve_git_commit()


def drop_legacy_audit_logs_table():
    try:
        conn = connect()
        cur = conn.cursor()
        cur.execute("DROP TABLE IF EXISTS audit_logs")
        conn.commit()
        conn.close()
    except Exception as e:
        app.logger.warning(f"清理旧数据库操作日志表失败: {e}")


drop_legacy_audit_logs_table()


SENSITIVE_LOG_KEYS = {
    "access_key_secret",
    "api_key",
    "answer",
    "authorization",
    "id_card_image",
    "image",
    "new_password",
    "old_password",
    "password",
    "security_answer",
    "secret",
    "token",
}


def _client_ip():
    return request.headers.get("X-Forwarded-For", request.remote_addr or "").split(",")[0].strip()


def _mask_value(key, value):
    lower_key = str(key).lower()
    if value is None:
        return None
    if "id_card" in lower_key:
        text = str(value)
        return f"****{text[-4:]}" if len(text) > 4 else "****"
    if "phone" in lower_key or lower_key in {"mobile", "tel"}:
        text = str(value)
        return f"{text[:3]}****{text[-4:]}" if len(text) >= 7 else "****"
    if lower_key in SENSITIVE_LOG_KEYS or "password" in lower_key or "secret" in lower_key or "token" in lower_key:
        return "***"
    return value


def _clean_log_value(value, key=""):
    if isinstance(value, dict):
        return {item_key: _clean_log_value(item_value, item_key) for item_key, item_value in value.items()}
    if isinstance(value, list):
        limit = 5
        cleaned = [_clean_log_value(item, key) for item in value[:limit]]
        if len(value) > limit:
            cleaned.append(f"...共{len(value)}项")
        return cleaned
    return _mask_value(key, value)


def _trim_text(value, max_length=220):
    text = str(value).strip()
    if len(text) > max_length:
        return f"{text[:max_length]}..."
    return text


def _safe_payload():
    payload = {}
    if request.is_json:
        payload = request.get_json(silent=True) or {}
    elif request.form:
        payload = request.form.to_dict(flat=True)
    elif request.args:
        payload = request.args.to_dict(flat=True)

    if request.files:
        payload = dict(payload)
        payload["files"] = {
            key: {
                "filename": file.filename,
                "content_type": file.content_type,
            }
            for key, file in request.files.items()
        }

    return _clean_log_value(payload)


def _response_json(response):
    if not response.is_json:
        return None
    try:
        return response.get_json(silent=True)
    except Exception:
        return None


def _response_message(response_data):
    if not isinstance(response_data, dict):
        return ""
    return response_data.get("message") or response_data.get("error") or response_data.get("msg") or ""


def _jwt_payload_unverified(token):
    try:
        parts = token.split(".")
        if len(parts) < 2:
            return {}
        payload = parts[1] + "=" * (-len(parts[1]) % 4)
        raw = base64.urlsafe_b64decode(payload.encode("utf-8")).decode("utf-8")
        return json.loads(raw)
    except Exception:
        return {}


def _current_operator(payload):
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "", 1).strip() if auth_header.startswith("Bearer ") else ""
    if token:
        decoded = _jwt_payload_unverified(token)
        return decoded.get("username") or decoded.get("user") or decoded.get("sub") or "已登录用户"
    if request.path == "/api/login":
        return payload.get("username") or "未登录用户"
    return "未登录用户"


def _payload_preview(payload):
    if not payload:
        return ""
    try:
        return _trim_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), 360)
    except Exception:
        return _trim_text(payload, 360)


def _field(payload, *names):
    if not isinstance(payload, dict):
        return ""
    for name in names:
        value = payload.get(name)
        if value not in (None, ""):
            return value
    return ""


def _room_label(payload, response_data=None):
    response_data = response_data if isinstance(response_data, dict) else {}
    room = _field(response_data, "room_display", "room_no") or _field(payload, "room_display", "room_no")
    building = _field(response_data, "building") or _field(payload, "building")
    if building and room and not str(room).upper().startswith(f"{str(building).upper()}-"):
        return f"{building}-{room}"
    return str(room or "")


def _changed_fields(payload):
    if not isinstance(payload, dict):
        return ""
    ignored = {"files", "image", "id_card_image"}
    fields = [key for key, value in payload.items() if key not in ignored and value not in (None, "")]
    return "、".join(fields[:12])


def _procurement_label(payload):
    items = payload.get("items") if isinstance(payload, dict) else None
    if isinstance(items, list) and items:
        total = _field(payload, "total_price", "total_amount", "amount")
        total_text = f"，总金额{total}" if total not in (None, "") else ""
        return f"采购单{len(items)}项{total_text}"
    name = _field(payload, "item_name", "name", "title", "material_name")
    qty = _field(payload, "quantity", "count", "amount")
    return f"{name} 数量{qty}".strip() if qty else str(name or "")


def _repair_label(payload):
    room = _room_label(payload)
    repair_type = _field(payload, "repair_type", "type", "category")
    reporter = _field(payload, "reporter", "report_by", "tenant_name", "name")
    parts = [item for item in (room, repair_type, reporter) if item]
    return " / ".join(parts)


def _public_business_name(value):
    return {
        "procurement": "采购",
        "repair": "维修",
        "warehouse": "库存",
    }.get(value, value)


def _business_operation(method, path, payload, response_data):
    detail = ""

    if path == "/api/login" and method == "POST":
        detail = f"登录账号 {payload.get('username', '')}".strip()
        return "用户登录", detail

    if path == "/api/forgot-password" and method == "POST":
        return "找回密码", f"账号 {payload.get('username', '')}".strip()
    if path == "/api/change-password" and method == "POST":
        return "修改密码", f"账号 {payload.get('username', '')}".strip()

    if path == "/api/rooms" and method == "POST":
        return "新增房间", _room_label(payload, response_data)
    match = re.fullmatch(r"/api/rooms/(\d+)", path)
    if match and method == "PUT":
        return "修改房间", f"id={match.group(1)} 字段={_changed_fields(payload)}"
    if match and method == "DELETE":
        return "删除房间", f"id={match.group(1)}"
    match = re.fullmatch(r"/api/rooms/([^/]+)/checkout", path)
    if match and method == "POST":
        return "房间退租", f"房间号 {match.group(1)}"
    match = re.fullmatch(r"/api/rooms/(\d+)/meter-image", path)
    if match and method == "POST":
        return "上传房间表读数图片", f"房间id={match.group(1)} 类型={payload.get('meter_type', '')}"

    if path == "/api/tenants" and method == "POST":
        return "新增租户", f"{_field(payload, 'name', 'tenant_name')} 房间={_room_label(payload)}"
    match = re.fullmatch(r"/api/tenants/([^/]+)", path)
    if match and method == "PUT":
        return "修改租户", f"身份证={_mask_value('id_card', match.group(1))} 字段={_changed_fields(payload)}"
    if match and method == "DELETE":
        return "删除租户", f"身份证={_mask_value('id_card', match.group(1))}"
    match = re.fullmatch(r"/api/tenants/by-id/(\d+)", path)
    if match and method == "PUT":
        return "修改租户", f"租户id={match.group(1)} 字段={_changed_fields(payload)}"
    if match and method == "DELETE":
        return "删除租户", f"租户id={match.group(1)}"
    match = re.fullmatch(r"/api/tenants/([^/]+)/checkout", path)
    if match and method == "POST":
        return "租户退租", f"身份证={_mask_value('id_card', match.group(1))}"
    match = re.fullmatch(r"/api/tenants/by-id/(\d+)/checkout", path)
    if match and method == "POST":
        return "租户退租", f"租户id={match.group(1)}"
    if path == "/api/tenants/recognize-id-card" and method == "POST":
        return "租户身份证OCR识别", "图片识别填表"
    if path == "/api/tenants/ai-draft" and method == "POST":
        return "租户AI输入填表", "文本/图片整理"

    if path == "/api/procurements" and method == "POST":
        return "新增采购", _procurement_label(payload)
    match = re.fullmatch(r"/api/procurements/(\d+)", path)
    if match and method == "PUT":
        return "修改采购", f"id={match.group(1)} 字段={_changed_fields(payload)}"
    if match and method == "DELETE":
        return "删除采购", f"id={match.group(1)}"
    match = re.fullmatch(r"/api/procurements/(\d+)/image", path)
    if match and method == "POST":
        return "上传采购图片", f"id={match.group(1)}"
    if path == "/api/procurements/ai-draft" and method == "POST":
        return "采购AI输入填表", "文本/图片整理"

    if path == "/api/repair-records" and method == "POST":
        return "新增维修记录", _repair_label(payload)
    match = re.fullmatch(r"/api/repair-records/(\d+)", path)
    if match and method == "PUT":
        return "修改维修记录", f"id={match.group(1)} 字段={_changed_fields(payload)}"
    if match and method == "DELETE":
        return "删除维修记录", f"id={match.group(1)}"
    match = re.fullmatch(r"/api/repair-records/(\d+)/image", path)
    if match and method == "POST":
        return "上传维修图片", f"id={match.group(1)}"
    if path == "/api/repair-records/ai-draft" and method == "POST":
        return "维修AI输入填表", "文本/图片整理"

    if path == "/api/utility-bills" and method == "POST":
        return "保存水电费账单", f"{_field(payload, 'utility_type')} {_field(payload, 'account', 'subject')} 年月={_field(payload, 'year')}-{_field(payload, 'month')}"
    match = re.fullmatch(r"/api/utility-bills/(\d+)", path)
    if match and method == "PUT":
        return "修改水电费账单", f"id={match.group(1)} 字段={_changed_fields(payload)}"
    if match and method == "DELETE":
        return "删除水电费账单", f"id={match.group(1)}"
    if path == "/api/rent-ledger/sync" and method == "POST":
        return "同步收租台账期次", ""
    match = re.fullmatch(r"/api/rent-ledger/(\d+)", path)
    if match and method == "PUT":
        return "修改收租台账", f"id={match.group(1)} 字段={_changed_fields(payload)}"
    if path == "/api/warehouse-items" and method == "POST":
        return "新增库存物品", f"{_field(payload, 'name', 'item_name')} 数量={_field(payload, 'quantity', 'stock', 'count')}"
    match = re.fullmatch(r"/api/warehouse-items/(\d+)", path)
    if match and method == "PUT":
        return "修改库存物品", f"id={match.group(1)} 字段={_changed_fields(payload)}"
    if match and method == "DELETE":
        return "删除库存物品", f"id={match.group(1)}"

    if path == "/api/moves/tenant" and method == "POST":
        return "租户搬迁", f"{_field(payload, 'tenant_name', 'name')} 从{_field(payload, 'from_room_no', 'old_room_no')}到{_field(payload, 'to_room_no', 'new_room_no')}"
    if path == "/api/moves/room" and method == "POST":
        return "房间搬迁", f"从{_field(payload, 'from_room_no', 'old_room_no')}到{_field(payload, 'to_room_no', 'new_room_no')}"
    match = re.fullmatch(r"/api/moves/(\d+)", path)
    if match and method == "DELETE":
        return "删除搬迁记录", f"id={match.group(1)}"

    if path == "/api/contracts" and method == "POST":
        return "新增合同", f"{_field(payload, 'tenant_name', 'name')} 房间={_room_label(payload)}"
    match = re.fullmatch(r"/api/contracts/(\d+)", path)
    if match and method == "PUT":
        return "修改合同", f"id={match.group(1)} 字段={_changed_fields(payload)}"
    if path == "/api/contract-templates" and method == "POST":
        return "新增合同模板", _field(payload, "name", "title")
    match = re.fullmatch(r"/api/contract-templates/(\d+)", path)
    if match and method == "PUT":
        return "修改合同模板", f"id={match.group(1)} 字段={_changed_fields(payload)}"
    if match and method == "DELETE":
        return "删除合同模板", f"id={match.group(1)}"

    if path == "/api/system/ai-settings" and method == "PUT":
        return "修改AI模型配置", f"模型={_field(payload, 'model')} 启用={_field(payload, 'enabled')} 动作={_field(payload, 'action')}"
    if path == "/api/system/ocr-settings" and method == "PUT":
        return "修改OCR配置", f"启用={_field(payload, 'enabled')} 类型={_field(payload, 'provider')}"
    if path == "/api/system/payment-settings" and method == "PUT":
        return "修改支付配置", f"总开关={_field(payload, 'enabled')} 微信={_field(payload, 'wechat_enabled')} 支付宝={_field(payload, 'alipay_enabled')}"
    if path == "/api/system/room-feature-options" and method == "PUT":
        return "修改房间特色选项", f"字段={_changed_fields(payload)}"
    if path == "/api/system/import" and method == "POST":
        return "恢复系统备份", "上传备份文件"
    if path == "/api/system/export" and method == "GET":
        return "导出系统备份", ""
    if path == "/api/system/reset" and method == "POST":
        return "重置系统数据", ""
    if path == "/api/system/seed" and method == "POST":
        return "生成演示数据", ""

    match = re.fullmatch(r"/api/self-checkin/rooms/(\d+)/links", path)
    if match and method == "POST":
        return "生成自助入住链接", f"房间id={match.group(1)}"
    match = re.fullmatch(r"/api/self-checkin/links/(\d+)/(disable|enable)", path)
    if match and method == "POST":
        return ("停用自助入住链接" if match.group(2) == "disable" else "启用自助入住链接"), f"链接id={match.group(1)}"
    match = re.fullmatch(r"/api/self-checkin/links/(\d+)", path)
    if match and method == "DELETE":
        return "删除自助入住链接", f"链接id={match.group(1)}"
    match = re.fullmatch(r"/api/self-checkin/submissions/(\d+)/(approve|reject)", path)
    if match and method == "POST":
        return ("通过自助入住申请" if match.group(2) == "approve" else "拒绝自助入住申请"), f"申请id={match.group(1)}"
    match = re.fullmatch(r"/api/public/self-checkin/([^/]+)/recognize-id-card", path)
    if match and method == "POST":
        return "公开自助入住身份证OCR识别", "图片识别填表"
    match = re.fullmatch(r"/api/public/self-checkin/([^/]+)/ai-draft", path)
    if match and method == "POST":
        return "公开自助入住AI识别填表", "文本/图片整理"
    match = re.fullmatch(r"/api/public/self-checkin/([^/]+)/submit", path)
    if match and method == "POST":
        return "提交自助入住申请", f"{_field(payload, 'name', 'tenant_name')} 房间={_room_label(payload)}"

    match = re.fullmatch(r"/api/rent-collection/rooms/(\d+)/links", path)
    if match and method == "POST":
        return "生成房间缴租链接", f"房间id={match.group(1)}"
    match = re.fullmatch(r"/api/rent-collection/links/(\d+)/(disable|enable)", path)
    if match and method == "POST":
        return ("停用房间缴租链接" if match.group(2) == "disable" else "启用房间缴租链接"), f"链接id={match.group(1)}"
    match = re.fullmatch(r"/api/rent-collection/links/(\d+)", path)
    if match and method == "DELETE":
        return "删除房间缴租链接", f"链接id={match.group(1)}"
    match = re.fullmatch(r"/api/public/rent-collection/([^/]+)/orders", path)
    if match and method == "POST":
        return "创建房租支付订单", f"支付方式={_field(payload, 'provider')} 金额={_field(payload, 'amount')}"
    if path == "/api/payment-callbacks/wechat" and method == "POST":
        return "微信支付回调", ""
    if path == "/api/payment-callbacks/alipay" and method == "POST":
        return "支付宝支付回调", ""

    match = re.fullmatch(r"/api/public-entry-links/([^/]+)", path)
    if match and method == "POST":
        return "生成公开填写链接", _public_business_name(match.group(1))
    match = re.fullmatch(r"/api/public-entry-links/(\d+)/(disable|enable)", path)
    if match and method == "POST":
        return ("停用公开填写链接" if match.group(2) == "disable" else "启用公开填写链接"), f"链接id={match.group(1)}"
    match = re.fullmatch(r"/api/public-entry-links/(\d+)", path)
    if match and method == "DELETE":
        return "删除公开填写链接", f"链接id={match.group(1)}"
    match = re.fullmatch(r"/api/public-entry/([^/]+)/([^/]+)/submit", path)
    if match and method == "POST":
        return f"公开提交{_public_business_name(match.group(1))}表单", f"{_field(payload, 'name', 'tenant_name')} 房间={_room_label(payload)}"
    match = re.fullmatch(r"/api/public-entry/([^/]+)/([^/]+)/upload-image", path)
    if match and method == "POST":
        return f"公开上传{_public_business_name(match.group(1))}图片", ""

    if method in {"POST", "PUT", "DELETE"}:
        return f"{method} {path}", ""
    return None, None


@app.after_request
def write_request_log(response):
    started_at = getattr(request, "_started_at", None)
    duration_ms = int((time.time() - started_at) * 1000) if started_at else 0
    payload = _safe_payload()
    response_data = _response_json(response)
    operator = _current_operator(payload)
    operation, detail = _business_operation(request.method, request.path, payload, response_data)
    message = _response_message(response_data)
    result = "成功" if response.status_code < 400 else "失败"
    base = (
        f"{request.method} {request.path} -> {response.status_code} "
        f"{duration_ms}ms ip={_client_ip()} 操作人={operator}"
    )
    if operation:
        detail_text = f" 详情={_trim_text(detail)}" if detail else ""
        request_text = f" 请求={_payload_preview(payload)}" if payload and request.method in {"POST", "PUT", "DELETE"} else ""
        message_text = f" 返回={_trim_text(message, 180)}" if message else ""
        app.logger.info(
            "业务操作: %s%s 结果=%s %s%s%s",
            operation,
            detail_text,
            result,
            base,
            request_text,
            message_text,
        )
    else:
        app.logger.info("接口请求: %s", base)
    return response


@app.before_request
def mark_request_start():
    request._started_at = time.time()


# 鍒濆鍖栨壘鍥炲瘑鐮佹ā鍧楋紙濡傚瓨鍦ㄥ垯杩涜鍒濆鍖栵級
try:
    fp.ensure_schema()
    # 璁剧疆涓€涓粯璁ょ殑鎭㈠淇℃伅锛岄伩鍏嶉娆′娇鐢ㄦ椂娌℃湁閰嶇疆
    fp.set_recovery_info('admin', security_answer='15286304124')
except Exception as e:
    app.logger.warning(f"鍒濆鍖栨壘鍥炲瘑鐮佹ā鍧楀け璐? {e}")
app.register_blueprint(upload_bp)


# 娉ㄥ唽鍚勫姛鑳借摑鍥?
try:
    ensure_contract_templates_schema()
    app.register_blueprint(templates_bp)
except Exception as e:
    app.logger.warning(f"娉ㄥ唽鍚堝悓妯℃澘妯″潡澶辫触: {e}")

# 娉ㄥ唽鍚堝悓妗ｆ钃濆浘
try:
    ensure_contracts_schema()
    app.register_blueprint(contracts_bp)
except Exception as e:
    app.logger.warning(f"娉ㄥ唽鍚堝悓妗ｆ妯″潡澶辫触: {e}")

app.register_blueprint(auth_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(notify_bp)
ensure_session_schema()
ensure_rooms_schema()
ensure_self_checkin_schema()
ensure_rent_collection_schema()
app.register_blueprint(rooms_bp)
app.register_blueprint(self_checkin_bp)
app.register_blueprint(rent_collection_bp)
app.register_blueprint(tenants_bp)
app.register_blueprint(moves_bp)
ensure_repair_records_schema()
app.register_blueprint(repair_bp)
app.register_blueprint(system_bp)
ensure_procurement_schema()
app.register_blueprint(procurement_bp)
ensure_utility_bills_schema()
app.register_blueprint(utility_bills_bp)
ensure_rent_ledger_schema()
app.register_blueprint(rent_ledger_bp)
ensure_public_entry_schema()
app.register_blueprint(public_entry_bp)
try:
    ensure_warehouse_schema()
    app.register_blueprint(warehouse_bp)
except Exception as e:
    app.logger.warning(f"娉ㄥ唽搴撴埧妯″潡澶辫触: {e}")


@app.route("/api/version", methods=["GET"])
def get_version_info():
    return jsonify({
        "backend": {
            "name": "homes-backend",
            "version": BACKEND_APP_VERSION,
            "commit": BACKEND_GIT_COMMIT,
            "started_at": APP_STARTED_AT,
            "python": os.sys.version.split(" ")[0],
        }
    })


@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Resource not found"}), 404


@app.errorhandler(500)
def internal_error(error):
    app.logger.error(f"Server Error: {error}")
    return jsonify({"error": "Internal Server Error"}), 500


if __name__ == "__main__":
    app.run(
        debug=True,
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "5000"))
    )
