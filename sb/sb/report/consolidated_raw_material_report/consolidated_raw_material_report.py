import frappe
from frappe.utils import flt

def execute(filters=None):
    if not filters or not filters.get("fg_raw_material_selector"):
        frappe.throw("Please select FG Raw Material Selector")

    doc = frappe.get_doc("FG Raw Material Selector", filters["fg_raw_material_selector"])
    raw_materials = doc.raw_materials or []

    fg_components = frappe.call(
        "sb.sb.doctype.fg_raw_material_selector.fg_raw_material_selector.get_fg_components_for_merge",
        project_design_upload=doc.project_design_upload
    )

    fg_lookup = {comp["fg_code"]: comp for comp in fg_components}

    consolidated = {}

    # Define all known child parts
    known_child_parts = ["b_side", "round_pipe", "inner_cap", "outer_cap", "stiffener_plate"]

    for item in raw_materials:
        fg_code = item.get("fg_code")
        fg = fg_lookup.get(fg_code, {})

        fg_key = f"{fg.get('a')}|||{fg.get('b')}|||{fg.get('code')}|||{fg.get('l1')}|||{fg.get('l2')}|||{fg.get('dwg_no')}|||{fg.get('client_area')}|||{fg.get('room_no')}|||{fg.get('flat_no')}|||{fg.get('u_area')}|||{fg.get('sb_area')}"

        if fg_key not in consolidated:
            consolidated[fg_key] = {
                "a": fg.get("a"),
                "b": fg.get("b"),
                "code": fg.get("code"),
                "l1": fg.get("l1"),
                "l2": fg.get("l2"),
                "dwg_no": fg.get("dwg_no"),
                "client_area": fg.get("client_area"),
                "room_no": fg.get("room_no"),
                "flat_no": fg.get("flat_no"),
                "u_area": fg.get("u_area"),
                "sb_area": fg.get("sb_area"),
                "total_quantity": 0,
                "rm1": {},
                "rm2": {},
                "rm3": {}
            }
            for part in known_child_parts:
                consolidated[fg_key][part] = {}

        row = consolidated[fg_key]
        row["total_quantity"] += flt(item.get("quantity"))

        remark = (item.remark or "").upper()
        item_code = (item.item_code or "").upper()
        dimension = item.dimension
        quantity = flt(item.quantity)

        # Raw Materials logic
        if any(x in remark for x in ["CHANNEL SECTION", "L SECTION", "IC SECTION", "J SECTION", "T SECTION", "SOLDIER", "EXTERNAL CORNER", "RK"]):
            if not row["rm1"]:
                row["rm1"] = {"code": item_code, "length": dimension, "qty": quantity}
            elif not row["rm2"] and item_code != row["rm1"].get("code"):
                row["rm2"] = {"code": item_code, "length": dimension, "qty": quantity}
            elif not row["rm3"] and item_code not in [row["rm1"].get("code"), row["rm2"].get("code")]:
                row["rm3"] = {"code": item_code, "length": dimension, "qty": quantity}

        # Child Parts logic
        elif "SIDE RAIL" in item_code:
            row["b_side"] = {"length": dimension, "qty": quantity}
        elif "ROUND PIPE" in item_code or "SQUARE PIPE" in item_code:
            row["round_pipe"] = {"length": dimension, "qty": quantity}
        elif "INNER CAP" in item_code:
            row["inner_cap"] = {"length": dimension, "qty": quantity}
        elif "OUTER CAP" in item_code:
            row["outer_cap"] = {"length": dimension, "qty": quantity}
        elif "STIFFENER PLATE" in item_code or "STIFF PLATE" in item_code:
            row["stiffener_plate"] = {"length": dimension, "qty": quantity}

    # Columns
    columns = [
        {"label": "Sr No", "fieldname": "sr_no", "fieldtype": "Int"},
        {"label": "A", "fieldname": "a", "fieldtype": "Data"},
        {"label": "B", "fieldname": "b", "fieldtype": "Data"},
        {"label": "FG Code", "fieldname": "code", "fieldtype": "Data"},
        {"label": "L1", "fieldname": "l1", "fieldtype": "Data"},
        {"label": "L2", "fieldname": "l2", "fieldtype": "Data"},
        {"label": "Drawing No", "fieldname": "dwg_no", "fieldtype": "Data"},
        {"label": "Total Qty", "fieldname": "total_quantity", "fieldtype": "Float"},
        {"label": "U Area", "fieldname": "u_area", "fieldtype": "Data"},
        {"label": "RM1 Code", "fieldname": "rm1_code", "fieldtype": "Data"},
        {"label": "RM1 Length", "fieldname": "rm1_length", "fieldtype": "Data"},
        {"label": "RM1 Qty", "fieldname": "rm1_qty", "fieldtype": "Float"},
        {"label": "RM2 Code", "fieldname": "rm2_code", "fieldtype": "Data"},
        {"label": "RM2 Length", "fieldname": "rm2_length", "fieldtype": "Data"},
        {"label": "RM2 Qty", "fieldname": "rm2_qty", "fieldtype": "Float"},
        {"label": "RM3 Code", "fieldname": "rm3_code", "fieldtype": "Data"},
        {"label": "RM3 Length", "fieldname": "rm3_length", "fieldtype": "Data"},
        {"label": "RM3 Qty", "fieldname": "rm3_qty", "fieldtype": "Float"},
    ]

    for part in known_child_parts:
        part_label = part.replace("_", " ").upper()
        columns.append({"label": f"{part_label} Length", "fieldname": f"{part}_length", "fieldtype": "Data"})
        columns.append({"label": f"{part_label} Qty", "fieldname": f"{part}_qty", "fieldtype": "Float"})

    # Data
    data = []
    for idx, row in enumerate(consolidated.values(), start=1):
        data_row = {
            "sr_no": idx,
            "a": row["a"],
            "b": row["b"],
            "code": row["code"],
            "l1": row["l1"],
            "l2": row["l2"],
            "dwg_no": row["dwg_no"],
            "total_quantity": row["total_quantity"],
            "u_area": row["u_area"],
            "rm1_code": row["rm1"].get("code", ""),
            "rm1_length": row["rm1"].get("length", ""),
            "rm1_qty": row["rm1"].get("qty", 0),
            "rm2_code": row["rm2"].get("code", ""),
            "rm2_length": row["rm2"].get("length", ""),
            "rm2_qty": row["rm2"].get("qty", 0),
            "rm3_code": row["rm3"].get("code", ""),
            "rm3_length": row["rm3"].get("length", ""),
            "rm3_qty": row["rm3"].get("qty", 0),
        }

        for part in known_child_parts:
            part_data = row.get(part, {})
            data_row[f"{part}_length"] = part_data.get("length", "")
            data_row[f"{part}_qty"] = part_data.get("qty", 0)

        data.append(data_row)

    return columns, data
