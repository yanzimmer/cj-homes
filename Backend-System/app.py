import logging
import os
from flask import Flask, jsonify, request
from flask_cors import CORS
from flasgger import Swagger

from common import SECRET_KEY, JWT_EXPIRATION_DELTA
from contract_templates_api import templates_bp, ensure_contract_templates_schema
from contracts_api import contracts_bp, ensure_contracts_schema
from auth_api import auth_bp
from dashboard_api import dashboard_bp
from notify_api import notify_bp
from rooms_api import rooms_bp, ensure_rooms_schema
from self_checkin_api import self_checkin_bp, ensure_self_checkin_schema
from tenants_api import tenants_bp
from moves_api import moves_bp
from repair_records_api import repair_bp, ensure_repair_records_schema
from system_api import system_bp
from procurement_api import procurement_bp, ensure_procurement_schema
from public_entry_links_api import public_entry_bp, ensure_public_entry_schema
from warehouse_api import warehouse_bp, ensure_warehouse_schema
from upload_api import upload_bp
import forgot_password as fp
from audit_logs import ensure_audit_logs_schema, record_audit_log, should_audit_request
from log_config import configure_logging


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
    'version': '1.0.0',
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
ensure_audit_logs_schema()


@app.after_request
def write_audit_log(response):
    if should_audit_request(request.method, request.path):
        record_audit_log(response=response)
        app.logger.info(
            "操作日志: %s %s -> %s",
            request.method,
            request.path,
            response.status_code,
        )
    return response


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
ensure_rooms_schema()
ensure_self_checkin_schema()
app.register_blueprint(rooms_bp)
app.register_blueprint(self_checkin_bp)
app.register_blueprint(tenants_bp)
app.register_blueprint(moves_bp)
ensure_repair_records_schema()
app.register_blueprint(repair_bp)
app.register_blueprint(system_bp)
ensure_procurement_schema()
app.register_blueprint(procurement_bp)
ensure_public_entry_schema()
app.register_blueprint(public_entry_bp)
try:
    ensure_warehouse_schema()
    app.register_blueprint(warehouse_bp)
except Exception as e:
    app.logger.warning(f"娉ㄥ唽搴撴埧妯″潡澶辫触: {e}")


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
