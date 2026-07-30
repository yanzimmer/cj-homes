from flask import Blueprint, request, jsonify
import json
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from auth_api import token_required
import expiry_notification_config as notify_config
from email.mime.text import MIMEText
from email.header import Header
import smtplib


notify_bp = Blueprint('notify', __name__, url_prefix='/api')


@notify_bp.route('/notification-config', methods=['GET'])
@token_required
def get_notification_config(current_user):
    """获取租期到期通知配置"""
    config = notify_config.get_config()
    return jsonify(config)


@notify_bp.route('/notification-config', methods=['PUT'])
@token_required
def update_notification_config(current_user):
    """更新租期到期通知配置"""
    data = request.json
    if not data:
        return jsonify({'error': '请提供配置数据'}), 400

    valid, message = notify_config.validate_config(data)
    if not valid:
        return jsonify({'error': message}), 400

    success, result = notify_config.update_config(data)
    if success:
        return jsonify(result)
    else:
        return jsonify({'error': f'更新配置失败: {result}'}), 500


@notify_bp.route('/test-email', methods=['POST'])
@token_required
def api_test_email(current_user):
    data = request.json or {}

    cfg = notify_config.get_runtime_config() or {}
    smtp_config = data.get('smtp_config') or cfg.get('smtp_config') or {}
    if isinstance(data.get('smtp_config'), dict):
        merged_smtp = dict(cfg.get('smtp_config') or {})
        merged_smtp.update({k: v for k, v in data.get('smtp_config', {}).items() if v != notify_config.MASKED_VALUE})
        smtp_config = merged_smtp
    recipient = data.get('recipient') or smtp_config.get('username')
    sender = data.get('sender') or smtp_config.get('username') or 'system@example.com'
    subject = data.get('subject') or '测试邮件'
    content = data.get('content') or '这是一封测试邮件，用于验证SMTP配置是否正常。'

    required_keys = ['server', 'port', 'username', 'password', 'use_tls']
    if not smtp_config or any(k not in smtp_config for k in required_keys):
        return jsonify({'error': '请提供完整的 smtp_config: server, port, username, password, use_tls'}), 400
    if not recipient:
        return jsonify({'error': '缺少收件人 recipient'}), 400

    try:
        msg = MIMEText(content, 'plain', 'utf-8')
        msg['From'] = sender or smtp_config['username']
        msg['To'] = recipient
        msg['Subject'] = Header(subject, 'utf-8')

        port = int(smtp_config.get('port', 587))
        use_tls = bool(smtp_config.get('use_tls', True))
        use_ssl = bool(data.get('use_ssl')) or port == 465

        if use_ssl:
            server = smtplib.SMTP_SSL(smtp_config['server'], port, timeout=10)
        else:
            server = smtplib.SMTP(smtp_config['server'], port, timeout=10)
            server.ehlo()
            if use_tls:
                server.starttls()
                server.ehlo()

        server.login(smtp_config['username'], smtp_config['password'])
        envelope_from = smtp_config['username']
        server.sendmail(envelope_from, [recipient], msg.as_string())
        server.quit()
        return jsonify({'success': True, 'message': '测试邮件发送成功'})
    except Exception as e:
        return jsonify({'success': False, 'error': f'测试邮件发送失败: {str(e)}'}), 502


@notify_bp.route('/test-sms', methods=['POST'])
@token_required
def api_test_sms(current_user):
    """
    测试短信发送 (模拟)
    ---
    tags:
      - Notification
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        schema:
          type: object
          properties:
            sms_config:
              type: object
    responses:
      200:
        description: 校验通过
      400:
        description: 参数缺失
    """
    data = request.json or {}
    runtime_cfg = notify_config.get_runtime_config() or {}
    sms_config = data.get('sms_config') or runtime_cfg.get('sms_config') or {}
    if isinstance(data.get('sms_config'), dict):
        merged_sms = dict(runtime_cfg.get('sms_config') or {})
        merged_sms.update({k: v for k, v in data.get('sms_config', {}).items() if v != notify_config.MASKED_VALUE})
        sms_config = merged_sms

    required_keys = [
        'secret_id', 'secret_key', 'app_id', 'sign_name',
        'tenant_template_id', 'landlord_template_id'
    ]
    missing = [k for k in required_keys if k not in sms_config]
    if missing:
        return jsonify({'error': f"缺少必要参数: {', '.join(missing)}"}), 400

    template_id = data.get('template_id', sms_config.get('tenant_template_id'))
    template_params = data.get('template_params', {
        'name': '张三',
        'room_no': '1-101',
        'check_out_date': '2025-01-01',
    })

    return jsonify({
        'success': True,
        'message': '短信发送配置校验完成（模拟）。若要真实发送，请集成短信平台SDK。',
        'payload': {
            'template_id': template_id,
            'template_params': template_params,
            'sign_name': sms_config.get('sign_name'),
            'app_id': sms_config.get('app_id'),
        },
    })


def _clean_text(value, max_length=2000):
    return str(value or "").strip()[:max_length]


def _build_bark_request_url(endpoint, bark_config, title, content):
    base_url = endpoint["bark_url"].rstrip("/")
    path = f"/{quote(title, safe='')}/{quote(content, safe='')}"
    query = {
        key: _clean_text(bark_config.get(key), 500)
        for key in ["group", "sound", "icon"]
        if _clean_text(bark_config.get(key), 500)
    }
    return f"{base_url}{path}{'?' + urlencode(query) if query else ''}"


def _send_bark_endpoint(endpoint, bark_config, title, content, timeout=10):
    request_url = _build_bark_request_url(endpoint, bark_config, title, content)
    bark_request = Request(
        request_url,
        headers={"Accept": "application/json", "User-Agent": "homes-bark-notifier/1.0"},
        method="GET",
    )
    try:
        with urlopen(bark_request, timeout=timeout) as response:
            status = int(getattr(response, "status", 200) or 200)
            raw_body = response.read(4096).decode("utf-8", errors="replace")
        payload = {}
        if raw_body:
            try:
                payload = json.loads(raw_body)
            except json.JSONDecodeError:
                payload = {}
        bark_code = payload.get("code") if isinstance(payload, dict) else None
        if not 200 <= status < 300 or (bark_code is not None and int(bark_code) != 200):
            raise RuntimeError(f"Bark 服务返回异常状态 {bark_code or status}")
        return {
            "id": endpoint["id"],
            "remark": endpoint["remark"],
            "success": True,
            "status": status,
        }
    except HTTPError as error:
        return {
            "id": endpoint["id"],
            "remark": endpoint["remark"],
            "success": False,
            "error": f"Bark 服务返回 HTTP {error.code}",
        }
    except URLError as error:
        reason = _clean_text(getattr(error, "reason", "网络连接失败"), 160)
        return {
            "id": endpoint["id"],
            "remark": endpoint["remark"],
            "success": False,
            "error": f"Bark 服务连接失败: {reason}",
        }
    except Exception as error:
        return {
            "id": endpoint["id"],
            "remark": endpoint["remark"],
            "success": False,
            "error": _clean_text(error, 200) or "Bark 推送失败",
        }


def send_bark_notification(title, content, bark_config=None, endpoint_ids=None, force=False):
    runtime_config = notify_config.get_runtime_config()
    merged_bark = dict(runtime_config.get("bark_config") or {})
    if isinstance(bark_config, dict):
        merged_bark.update({key: value for key, value in bark_config.items() if key != "endpoints"})
        if "endpoints" in bark_config:
            merged_bark["endpoints"] = notify_config.normalize_bark_endpoints(bark_config["endpoints"])

    if not force and not merged_bark.get("enabled", True):
        raise ValueError("Bark 推送已停用")

    normalized_title = _clean_text(title or merged_bark.get("title") or "房屋提醒", 100)
    normalized_content = _clean_text(content, 2000)
    if not normalized_content:
        raise ValueError("Bark 推送内容不能为空")

    selected_ids = {str(item) for item in (endpoint_ids or []) if str(item).strip()}
    endpoints = notify_config.normalize_bark_endpoints(merged_bark.get("endpoints", []))
    endpoints = [
        endpoint for endpoint in endpoints
        if endpoint.get("enabled", True) and (not selected_ids or endpoint["id"] in selected_ids)
    ]
    if not endpoints:
        raise ValueError("没有可用的 Bark 推送地址")

    results = [
        _send_bark_endpoint(endpoint, merged_bark, normalized_title, normalized_content)
        for endpoint in endpoints
    ]
    success_count = sum(1 for result in results if result["success"])
    return {
        "success": success_count == len(results),
        "success_count": success_count,
        "failure_count": len(results) - success_count,
        "results": results,
    }


@notify_bp.route('/test-bark', methods=['POST'])
@token_required
def api_test_bark(current_user):
    data = request.json or {}
    endpoint = data.get("endpoint")
    endpoint_id = _clean_text(data.get("endpoint_id"), 64)
    bark_config = data.get("bark_config") if isinstance(data.get("bark_config"), dict) else {}

    if endpoint is not None:
        bark_config = dict(bark_config)
        bark_config["endpoints"] = [{**endpoint, "enabled": True}] if isinstance(endpoint, dict) else [endpoint]
        endpoint_ids = None
    elif endpoint_id:
        endpoint_ids = [endpoint_id]
    else:
        return jsonify({"error": "请选择要测试的 Bark 地址"}), 400

    try:
        result = send_bark_notification(
            data.get("title") or bark_config.get("title") or "从江房屋登记系统",
            data.get("content") or "Bark 通知配置测试成功。",
            bark_config=bark_config,
            endpoint_ids=endpoint_ids,
            force=True,
        )
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    status = 200 if result["failure_count"] == 0 else 502
    return jsonify(result), status


@notify_bp.route('/notify/send', methods=['POST'])
@token_required
def api_send_notification(current_user):
    data = request.json or {}
    try:
        result = send_bark_notification(
            data.get("title"),
            data.get("content") or data.get("message"),
            endpoint_ids=data.get("endpoint_ids"),
        )
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    if result["failure_count"] == 0:
        status = 200
    elif result["success_count"] > 0:
        status = 207
    else:
        status = 502
    return jsonify(result), status


@notify_bp.route('/notify/run-due', methods=['POST'])
@token_required
def api_run_due_notifications(current_user):
    from notification_service import run_due_bark_notifications

    try:
        result = run_due_bark_notifications(force=True)
    except Exception as error:
        return jsonify({'error': f'自动通知检查失败: {_clean_text(error, 200)}'}), 500
    return jsonify(result)
