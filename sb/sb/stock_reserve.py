import frappe
from frappe.utils import flt

@frappe.whitelist()
def reserve_stock_physically(fg_selector_name):
    doc = frappe.get_doc("FG Raw Material Selector", fg_selector_name)
    reserved_warehouse = "Reserved Stock - VD"

    entry = frappe.new_doc("Stock Entry")
    entry.stock_entry_type = "Material Transfer"
    entry.purpose = "Material Transfer"
    entry.set_posting_time = 1
    entry.fg_raw_material_selector = fg_selector_name

    for row in doc.raw_materials:
        if row.reserve_tag and row.status == "IS" and row.warehouse:
            entry.append("items", {
                "item_code": row.item_code,
                "qty": flt(row.quantity),
                "uom": row.uom,
                "stock_uom": row.uom,
                "s_warehouse": row.warehouse,
                "t_warehouse": reserved_warehouse
            })
            row.warehouse = reserved_warehouse
            row.stock_entry = entry.name  # Store Stock Entry reference

    if not entry.items:
        return {"status": "fail", "message": "No eligible items to reserve."}

    entry.save()
    entry.submit()
    doc.save()  # ✅ Save the updated child table with warehouse + stock_entry fields

    return {
        "status": "success",
        "message": f"Stock reserved successfully via Stock Entry {entry.name}",
        "stock_entry": entry.name
    }




@frappe.whitelist()
def return_unconsumed_reserved_stock(fg_selector_name):
    """Return unconsumed stock from Reserved warehouse back to default."""
    doc = frappe.get_doc("FG Raw Material Selector", fg_selector_name)
    source_warehouse = "Reserved Stock - VD"
    default_warehouse = "Raw Material - VD"

    entry = frappe.new_doc("Stock Entry")
    entry.stock_entry_type = "Material Transfer"
    entry.purpose = "Material Transfer"
    entry.set_posting_time = 1
    entry.fg_raw_material_selector = fg_selector_name  # Optional: track origin

    for row in doc.raw_materials:
        if row.reserve_tag and row.status == "IS" and row.warehouse == source_warehouse:
            entry.append("items", {
                "item_code": row.item_code,
                "qty": flt(row.quantity),
                "uom": row.uom,
                "stock_uom": row.uom,
                "s_warehouse": source_warehouse,
                "t_warehouse": default_warehouse
            })
            row.warehouse = default_warehouse
            row.reserve_tag = 0
            row.status = "NIS"

    if not entry.items:
        return {"status": "fail", "message": "No reserved items to return."}

    entry.save()
    entry.submit()
    doc.save()

    return {"status": "success", "message": "Unconsumed stock returned to Raw Material - VD."}


@frappe.whitelist()
def get_available_qty(item_code, uom):
    """Return quantity of item excluding reserved warehouses."""
    warehouses_to_exclude = ["Reserved Stock - VD"]
    warehouses = frappe.get_all("Warehouse", filters={"is_group": 0}, pluck="name")

    total = 0
    for wh in warehouses:
        if wh in warehouses_to_exclude:
            continue
        actual_qty = frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": wh}, "actual_qty")
        total += flt(actual_qty or 0)

    return total



from frappe.utils import flt
@frappe.whitelist()
def get_stock_for_items(items):
    import json
    items = json.loads(items)

    warehouses_to_check = ["Off-Cut - VD", "Raw Material - VD"]  # Use your full warehouse names

    for item in items:
        item_code = item.get("item_code")
        uom = item.get("uom")
        item["available_quantity"] = 0
        item["warehouse"] = ""

        for wh in warehouses_to_check:
            qty = get_actual_qty(item_code, wh, uom)
            if qty > 0:
                item["available_quantity"] = qty
                item["warehouse"] = wh
                break  # found in this warehouse

    return items


def get_actual_qty(item_code, warehouse, uom):
    bin = frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": warehouse}, ["actual_qty"], as_dict=True)
    if not bin:
        return 0
    stock_uom = frappe.db.get_value("Item", item_code, "stock_uom")
    conversion_factor = 1
    if stock_uom != uom:
        from erpnext.stock.doctype.item.item import get_uom_conv_factor as get_uom_conversion_factor
        try:
            conversion_factor = get_uom_conversion_factor(item_code, uom)
        except:
            conversion_factor = 0
    return flt(bin.actual_qty) / flt(conversion_factor or 1)