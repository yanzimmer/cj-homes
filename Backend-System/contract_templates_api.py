# 该文件负责处理合同模板的增删改查、渲染与表结构初始化。
import sqlite3
from flask import Blueprint, request, jsonify
from auth_api import token_required
from common import connect


DEFAULT_TEMPLATE_NAME = "\u9ed8\u8ba4\u79df\u8d41\u5408\u540c\uff08\u793a\u4f8b\uff09"
DEFAULT_TEMPLATE_DESC = "\u7cfb\u7edf\u81ea\u52a8\u521b\u5efa\u7684\u793a\u4f8b\u5408\u540c\u6a21\u677f\uff0c\u53ef\u6309\u9700\u4fee\u6539\u3002"
DEFAULT_TEMPLATE_HTML = """
<div style="font-family:Arial,'Microsoft YaHei',sans-serif;line-height:1.8;color:#1f2937;">
  <h2 style="text-align:center;margin:0 0 16px;">\u623f\u5c4b\u79df\u8d41\u5408\u540c\uff08\u793a\u4f8b\uff09</h2>
  <p>\u51fa\u79df\u65b9\uff08\u7532\u65b9\uff09\uff1a{{landlord}}</p>
  <p>\u627f\u79df\u65b9\uff08\u4e59\u65b9\uff09\uff1a{{tenant_name}}</p>
  <p>\u8eab\u4efd\u8bc1\u53f7\uff1a{{id_card}}</p>
  <p>\u623f\u95f4\u53f7\uff1a{{room_no}}</p>
  <p>\u79df\u8d41\u671f\u9650\uff1a{{start_date}} \u81f3 {{end_date}}</p>
  <p>\u6708\u79df\u91d1\uff1a{{rent}}\u5143</p>
  <p>\u62bc\u91d1\uff1a{{deposit}}\u5143</p>
  <p style="margin-top:16px;">\u5907\u6ce8\uff1a\u6b64\u6a21\u677f\u4e3a\u7cfb\u7edf\u9ed8\u8ba4\u793a\u4f8b\uff0c\u8bf7\u6309\u5b9e\u9645\u4e1a\u52a1\u9700\u6c42\u8c03\u6574\u6761\u6b3e\u5185\u5bb9\u3002</p>
</div>
""".strip()


def ensure_default_contract_template(cursor):
    cursor.execute("SELECT id FROM contract_templates WHERE name = ? LIMIT 1", (DEFAULT_TEMPLATE_NAME,))
    if cursor.fetchone() is not None:
        return
    cursor.execute(
        "INSERT INTO contract_templates (name, description, content_html, updated_at) VALUES (?, ?, ?, DATETIME('now'))",
        (DEFAULT_TEMPLATE_NAME, DEFAULT_TEMPLATE_DESC, DEFAULT_TEMPLATE_HTML),
    )

def ensure_contract_templates_schema():
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS contract_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            content_html TEXT NOT NULL,
            created_at DATETIME DEFAULT (DATETIME('now')),
            updated_at DATETIME DEFAULT (DATETIME('now'))
        )
        """
    )
    ensure_default_contract_template(cursor)
    conn.commit()
    conn.close()


templates_bp = Blueprint("contract_templates", __name__, url_prefix="/api/contract-templates")


@templates_bp.route("", methods=["GET"])
@token_required
def list_templates(current_user):
    """
    获取合同模板列表
    ---
    tags:
      - Contract Templates
    security:
      - Bearer: []
    responses:
      200:
        description: 成功获取模板列表
        schema:
          type: object
          properties:
            templates:
              type: array
              items:
                type: object
                properties:
                  id:
                    type: integer
                  name:
                    type: string
                  description:
                    type: string
                  created_at:
                    type: string
                  updated_at:
                    type: string
    """
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, description, created_at, updated_at FROM contract_templates ORDER BY updated_at DESC")
    rows = cursor.fetchall()
    conn.close()

    templates = []
    for row in rows:
        templates.append({
            "id": row[0],
            "name": row[1],
            "description": row[2],
            "created_at": row[3],
            "updated_at": row[4],
        })
    return jsonify({"templates": templates})


@templates_bp.route("/<int:tid>", methods=["GET"])
@token_required
def get_template(current_user, tid):
    """
    获取单个合同模板详情
    ---
    tags:
      - Contract Templates
    security:
      - Bearer: []
    parameters:
      - in: path
        name: tid
        type: integer
        required: true
    responses:
      200:
        description: 成功获取模板详情
      404:
        description: 模板不存在
    """
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, description, content_html, created_at, updated_at FROM contract_templates WHERE id = ?", (tid,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return jsonify({"error": "模板不存在"}), 404
    tpl = {
        "id": row[0],
        "name": row[1],
        "description": row[2],
        "content_html": row[3],
        "created_at": row[4],
        "updated_at": row[5],
    }
    return jsonify({"template": tpl})


@templates_bp.route("", methods=["POST"])
@token_required
def add_template(current_user):
    """
    添加合同模板
    ---
    tags:
      - Contract Templates
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        schema:
          type: object
          required:
            - name
            - content_html
          properties:
            name:
              type: string
            content_html:
              type: string
            description:
              type: string
    responses:
      200:
        description: 模板已创建
      400:
        description: 缺少必填字段
    """
    data = request.json or {}
    name = data.get("name")
    content_html = data.get("content_html")
    description = data.get("description", "")
    if not name or not content_html:
        return jsonify({"error": "缺少必填字段 name 或 content_html"}), 400
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO contract_templates (name, description, content_html, updated_at) VALUES (?, ?, ?, DATETIME('now'))",
        (name, description, content_html),
    )
    tid = cursor.lastrowid
    conn.commit()
    conn.close()
    return jsonify({"message": "模板已创建", "id": tid})


@templates_bp.route("/<int:tid>", methods=["PUT"])
@token_required
def update_template(current_user, tid: int):
    data = request.json or {}
    allowed = {"name", "description", "content_html"}
    updates = {k: v for k, v in data.items() if k in allowed}
    if not updates:
        return jsonify({"error": "没有有效的更新字段"}), 400
    conn = connect()
    cursor = conn.cursor()
    for k, v in updates.items():
        cursor.execute(f"UPDATE contract_templates SET {k} = ?, updated_at = DATETIME('now') WHERE id = ?", (v, tid))
    if cursor.rowcount == 0:
        conn.close()
        return jsonify({"error": "模板不存在"}), 404
    conn.commit()
    conn.close()
    return jsonify({"message": "模板已更新"})


@templates_bp.route("/<int:tid>", methods=["DELETE"])
@token_required
def delete_template(current_user, tid: int):
    """删除模板时总是连同删除关联合同。"""
    conn = connect()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM contract_templates WHERE id = ?", (tid,))
        if not cursor.fetchone():
            conn.close()
            return jsonify({"error": "模板不存在"}), 404

        cursor.execute("SELECT COUNT(*) FROM contracts WHERE template_id = ?", (tid,))
        linked_count = cursor.fetchone()[0] or 0
        cursor.execute("DELETE FROM contracts WHERE template_id = ?", (tid,))

        cursor.execute("DELETE FROM contract_templates WHERE id = ?", (tid,))
        conn.commit()
        conn.close()

        return jsonify({
            "message": f"模板已删除，并删除了 {linked_count} 条关联合同",
            "contracts_deleted": linked_count
        })
    except sqlite3.OperationalError as e:
        try:
            conn.rollback()
        except Exception:
            pass
        conn.close()
        return jsonify({"error": f"数据库繁忙或不可用：{e}"}), 503
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        conn.close()
        return jsonify({"error": f"删除失败：{e}"}), 500


@templates_bp.route("/<int:tid>/render", methods=["POST"])
@token_required
def render_template(current_user, tid: int):
    """
    渲染模板预览
    ---
    tags:
      - Contract Templates
    security:
      - Bearer: []
    parameters:
      - in: path
        name: tid
        type: integer
        required: true
      - in: body
        name: body
        schema:
          type: object
          properties:
            vars:
              type: object
              description: 模板变量
    responses:
      200:
        description: 渲染成功
      404:
        description: 模板不存在
    """
    data = request.json or {}
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT content_html FROM contract_templates WHERE id = ?", (tid,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return jsonify({"error": "模板不存在"}), 404
    html = row[0] or ""
    try:
        for k, v in (data.get("vars") or {}).items():
            placeholder = f"{{{{{k}}}}}"
            html = html.replace(placeholder, str(v))
        return jsonify({"rendered_html": html})
    except Exception as e:
        return jsonify({"error": f"渲染失败: {e}"}), 500
