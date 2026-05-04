import json

from common import connect


def ensure_inventory_sync_schema():
    conn = connect()
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(procurements)")
    procurement_cols = {row[1] for row in cur.fetchall()}
    if "warehouse_item_id" not in procurement_cols:
        cur.execute("ALTER TABLE procurements ADD COLUMN warehouse_item_id INTEGER")

    cur.execute("PRAGMA table_info(repair_records)")
    repair_cols = {row[1] for row in cur.fetchall()}
    if "inventory_usages" not in repair_cols:
        cur.execute("ALTER TABLE repair_records ADD COLUMN inventory_usages TEXT")
    conn.commit()
    conn.close()


def _to_float(value, default=0.0):
    try:
        if value is None or str(value).strip() == "":
            return float(default)
        return float(value)
    except Exception:
        return float(default)


def _parse_inventory_usages(value):
    text = str(value or "").strip()
    if not text:
        return []
    try:
        data = json.loads(text)
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    result = []
    for item in data:
        if not isinstance(item, dict):
            continue
        warehouse_item_id = item.get("warehouse_item_id")
        try:
            warehouse_item_id = int(warehouse_item_id)
        except Exception:
            continue
        quantity = _to_float(item.get("quantity"), 0)
        if quantity <= 0:
            continue
        result.append(
            {
                "warehouse_item_id": warehouse_item_id,
                "item_name": str(item.get("item_name") or "").strip(),
                "specification": str(item.get("specification") or "").strip(),
                "unit": str(item.get("unit") or "").strip(),
                "location": str(item.get("location") or "").strip(),
                "quantity": quantity,
            }
        )
    return result


def dump_inventory_usages(items):
    payload = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        try:
            warehouse_item_id = int(item.get("warehouse_item_id"))
        except Exception:
            continue
        quantity = _to_float(item.get("quantity"), 0)
        if quantity <= 0:
            continue
        payload.append(
            {
                "warehouse_item_id": warehouse_item_id,
                "item_name": str(item.get("item_name") or "").strip(),
                "specification": str(item.get("specification") or "").strip(),
                "unit": str(item.get("unit") or "").strip(),
                "location": str(item.get("location") or "").strip(),
                "quantity": quantity,
            }
        )
    return json.dumps(payload, ensure_ascii=False)


def list_warehouse_stock_options():
    ensure_inventory_sync_schema()
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, item_name, specification, quantity, unit, location
        FROM warehouse_items
        ORDER BY item_name ASC, specification ASC, id DESC
        """
    )
    rows = cur.fetchall()
    conn.close()
    return [
        {
            "id": row[0],
            "item_name": row[1] or "",
            "specification": row[2] or "",
            "quantity": _to_float(row[3], 0),
            "unit": row[4] or "",
            "location": row[5] or "",
        }
        for row in rows
    ]


def _get_warehouse_item(conn, item_id):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, item_name, specification, quantity, unit, location, procurement_date
        FROM warehouse_items
        WHERE id = ?
        LIMIT 1
        """,
        (item_id,),
    )
    return cur.fetchone()


def _find_matching_warehouse_item(conn, item_name, specification, unit):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, item_name, specification, quantity, unit, location, procurement_date
        FROM warehouse_items
        WHERE item_name = ? AND COALESCE(specification, '') = ? AND COALESCE(unit, '') = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (item_name, specification or "", unit or ""),
    )
    return cur.fetchone()


def _create_warehouse_item(conn, procurement_date, item_name, specification, unit, unit_price):
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO warehouse_items (
            procurement_date, item_name, specification, category, quantity, unit_price, unit, location, image, remarks, created_at, updated_at
        ) VALUES (?, ?, ?, '', 0, ?, ?, '', '[]', '', DATETIME('now'), DATETIME('now'))
        """,
        (
            procurement_date,
            item_name,
            specification or "",
            _to_float(unit_price, 0),
            unit or "",
        ),
    )
    item_id = cur.lastrowid
    return _get_warehouse_item(conn, item_id)


def _change_warehouse_quantity(conn, item_id, delta_quantity):
    row = _get_warehouse_item(conn, item_id)
    if not row:
        raise ValueError("库存物品不存在")
    current_quantity = _to_float(row[3], 0)
    next_quantity = current_quantity + _to_float(delta_quantity, 0)
    if next_quantity < 0:
        raise ValueError(f"库存不足：{row[1]} 当前仅剩 {current_quantity}")
    cur = conn.cursor()
    cur.execute(
        "UPDATE warehouse_items SET quantity = ?, updated_at = DATETIME('now') WHERE id = ?",
        (next_quantity, item_id),
    )
    return next_quantity


def sync_procurement_create(conn, procurement_id, procurement_date, item_name, specification, quantity, unit_price, unit):
    ensure_inventory_sync_schema()
    target = _find_matching_warehouse_item(conn, item_name, specification, unit)
    if not target:
        target = _create_warehouse_item(conn, procurement_date, item_name, specification, unit, unit_price)
    item_id = target[0]
    _change_warehouse_quantity(conn, item_id, _to_float(quantity, 0))
    cur = conn.cursor()
    cur.execute("UPDATE procurements SET warehouse_item_id = ? WHERE id = ?", (item_id, procurement_id))
    return item_id


def sync_procurement_update(conn, procurement_row, procurement_date, item_name, specification, quantity, unit_price, unit):
    ensure_inventory_sync_schema()
    old_quantity = _to_float(procurement_row[4], 0)
    old_item_id = procurement_row[9]

    target = _find_matching_warehouse_item(conn, item_name, specification, unit)
    if not target:
        target = _create_warehouse_item(conn, procurement_date, item_name, specification, unit, unit_price)
    new_item_id = target[0]

    if old_item_id:
        _change_warehouse_quantity(conn, old_item_id, -old_quantity)
    _change_warehouse_quantity(conn, new_item_id, _to_float(quantity, 0))

    cur = conn.cursor()
    cur.execute("UPDATE procurements SET warehouse_item_id = ? WHERE id = ?", (new_item_id, procurement_row[0]))
    return new_item_id


def sync_procurement_delete(conn, procurement_row):
    ensure_inventory_sync_schema()
    quantity = _to_float(procurement_row[4], 0)
    warehouse_item_id = procurement_row[9]
    if warehouse_item_id:
        row = _get_warehouse_item(conn, warehouse_item_id)
        if row:
            _change_warehouse_quantity(conn, warehouse_item_id, -quantity)


def validate_inventory_usages(conn, inventory_usages):
    normalized = []
    for item in inventory_usages or []:
        if not isinstance(item, dict):
            continue
        try:
            warehouse_item_id = int(item.get("warehouse_item_id"))
        except Exception:
            raise ValueError("领用库存项格式不正确")
        quantity = _to_float(item.get("quantity"), 0)
        if quantity <= 0:
            raise ValueError("领用数量必须大于 0")
        row = _get_warehouse_item(conn, warehouse_item_id)
        if not row:
            raise ValueError("所选库存物品不存在")
        normalized.append(
            {
                "warehouse_item_id": warehouse_item_id,
                "item_name": row[1] or "",
                "specification": row[2] or "",
                "unit": row[4] or "",
                "location": row[5] or "",
                "quantity": quantity,
            }
        )
    return normalized


def apply_inventory_usage(conn, inventory_usages):
    for item in inventory_usages or []:
        _change_warehouse_quantity(conn, item["warehouse_item_id"], -_to_float(item.get("quantity"), 0))


def restore_inventory_usage(conn, inventory_usages):
    for item in inventory_usages or []:
        _change_warehouse_quantity(conn, item["warehouse_item_id"], _to_float(item.get("quantity"), 0))
