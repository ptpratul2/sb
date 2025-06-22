import frappe
from frappe.utils import flt

def execute(filters=None):
    if not filters or not filters.get("fg_raw_material_selector"):
        frappe.throw("Please select FG Raw Material Selector")

    doc = frappe.get_doc("FG Raw Material Selector", filters["fg_raw_material_selector"])
    raw_materials = doc.raw_materials or []

    # Apply filters to raw materials
    filtered_raw_materials = []
    project = filters.get("project")
    ipo_name = filters.get("ipo_name", "").upper() if filters.get("ipo_name") else None
    code = filters.get("code", "").upper() if filters.get("code") else None
    section = filters.get("section")

    for item in raw_materials:
        remark = (item.remark or "").upper()
        item_code = (item.item_code or "").upper()
        fg_code = (item.fg_code or "").upper()
        item_ipo_name = (item.ipo_name or "").upper() if item.ipo_name else ""
        item_project = item.project

        # Debug logging
        frappe.log_error(
            message=f"Filtering item: fg_code={fg_code}, project={item_project}, ipo_name={item_ipo_name}, item_code={item_code}, remark={remark}, dimension={item.dimension}, quantity={item.quantity}",
            title="Raw Material Filter Debug"
        )

        # Apply filters
        if project and item_project != project:
            continue
        if ipo_name and ipo_name not in item_ipo_name:
            continue
        if code and code not in fg_code:
            continue
        if section and section not in remark:
            continue

        filtered_raw_materials.append(item)

    if not filtered_raw_materials:
        frappe.msgprint("No raw materials match the provided filters.")
        return [], []

    # Fetch FG components
    fg_codes = list(set(item.fg_code for item in filtered_raw_materials))
    fg_components = frappe.call(
        "sb.sb.doctype.fg_raw_material_selector.fg_raw_material_selector.get_fg_components_for_merge",
        project_design_upload=[row.project_design_upload for row in doc.project_design_upload]
    )

    # Debug FG components
    frappe.log_error(
        message=f"FG Components: {fg_components}",
        title="FG Components Debug"
    )

    fg_lookup = {comp["fg_code"]: comp for comp in fg_components if comp["fg_code"] in fg_codes}

    consolidated = {}

    # Define known child parts
    known_child_parts = ["b_side", "round_pipe", "inner_cap", "outer_cap", "stiffener_plate", "i_stiff"]

    for item in filtered_raw_materials:
        fg_code = item.get("fg_code")
        fg = fg_lookup.get(fg_code, {})
        item_ipo_name = item.ipo_name or ""
        item_project = item.project or ""
        item_section = item.remark or ""

        # Group by fg_code, project, and ipo_name
        fg_key = f"{fg_code}|||{item_ipo_name}|||{item_project}"

        if fg_key not in consolidated:
            consolidated[fg_key] = {
                "a": fg.get("a"),
                "b": fg.get("b"),
                "code": fg.get("code"),
                "l1": fg.get("l1"),
                "l2": fg.get("l2"),
                "dwg_no": fg.get("dwg_no"),
                "u_area": fg.get("u_area"),
                "ipo_name": item_ipo_name,
                "project": item_project,
                "section": item_section,
                "total_quantity": 0,
                "rm1_code": "",
                "rm1_length": "",
                "rm1_qty": 0,
                "rm2_code": "",
                "rm2_length": "",
                "rm2_qty": 0,
                "rm3_code": "",
                "rm3_length": "",
                "rm3_qty": 0,
            }
            for part in known_child_parts:
                consolidated[fg_key][f"{part}_length"] = ""
                consolidated[fg_key][f"{part}_qty"] = 0

        row = consolidated[fg_key]
        remark = (item.remark or "").upper()
        item_code = (item.item_code or "").upper()
        dimension = item.dimension or ""
        quantity = flt(item.get("quantity"))

        row["total_quantity"] += quantity

        # Debug quantity accumulation
        frappe.log_error(
            message=f"Processing item: fg_key={fg_key}, item_code={item_code}, dimension={dimension}, quantity={quantity}, total_quantity={row['total_quantity']}",
            title="Quantity Accumulation Debug"
        )

        # Raw Materials
        if any(x in remark for x in ["CHANNEL SECTION", "L SECTION", "IC SECTION", "J SECTION", "T SECTION", "SOLDIER", "EXTERNAL CORNER", "RK"]):
            for rm_slot in ["rm1", "rm2", "rm3"]:
                if not row[f"{rm_slot}_code"]:
                    row[f"{rm_slot}_code"] = item_code
                    row[f"{rm_slot}_length"] = dimension
                    row[f"{rm_slot}_qty"] = quantity
                    frappe.log_error(
                        message=f"Assigned raw material: {rm_slot}_code={item_code}, {rm_slot}_length={dimension}, {rm_slot}_qty={quantity}",
                        title="Raw Material Assignment Debug"
                    )
                    break
                elif row[f"{rm_slot}_code"] == item_code and row[f"{rm_slot}_length"] == dimension:
                    row[f"{rm_slot}_qty"] += quantity
                    frappe.log_error(
                        message=f"Updated raw material: {rm_slot}_code={item_code}, {rm_slot}_length={dimension}, {rm_slot}_qty={row[f'{rm_slot}_qty']}",
                        title="Raw Material Assignment Debug"
                    )
                    break

        # Child Parts
        elif item_code == "SIDE RAIL":
            if not row["b_side_length"] or row["b_side_length"] == dimension:
                row["b_side_length"] = dimension
                row["b_side_qty"] += quantity
                frappe.log_error(
                    message=f"Updated child part: b_side_length={dimension}, b_side_qty={row['b_side_qty']}",
                    title="Child Part Assignment Debug"
                )
        elif item_code == "I STIFF":
            if not row["i_stiff_length"] or row["i_stiff_length"] == dimension:
                row["i_stiff_length"] = dimension
                row["i_stiff_qty"] += quantity
                frappe.log_error(
                    message=f"Updated child part: i_stiff_length={dimension}, i_stiff_qty={row['i_stiff_qty']}",
                    title="Child Part Assignment Debug"
                )
        elif item_code in ["ROUND PIPE", "SQUARE PIPE"]:
            if not row["round_pipe_length"] or row["round_pipe_length"] == dimension:
                row["round_pipe_length"] = dimension
                row["round_pipe_qty"] += quantity
                frappe.log_error(
                    message=f"Updated child part: round_pipe_length={dimension}, round_pipe_qty={row['round_pipe_qty']}",
                    title="Child Part Assignment Debug"
                )
        elif item_code == "INNER CAP":
            if not row["inner_cap_length"] or row["inner_cap_length"] == dimension:
                row["inner_cap_length"] = dimension
                row["inner_cap_qty"] += quantity
                frappe.log_error(
                    message=f"Updated child part: inner_cap_length={dimension}, inner_cap_qty={row['inner_cap_qty']}",
                    title="Child Part Assignment Debug"
                )
        elif item_code == "OUTER CAP":
            if not row["outer_cap_length"] or row["outer_cap_length"] == dimension:
                row["outer_cap_length"] = dimension
                row["outer_cap_qty"] += quantity
                frappe.log_error(
                    message=f"Updated child part: outer_cap_length={dimension}, outer_cap_qty={row['outer_cap_qty']}",
                    title="Child Part Assignment Debug"
                )
        elif item_code in ["STIFFENER PLATE", "STIFF PLATE"]:
            if not row["stiffener_plate_length"] or row["stiffener_plate_length"] == dimension:
                row["stiffener_plate_length"] = dimension
                row["stiffener_plate_qty"] += quantity
                frappe.log_error(
                    message=f"Updated child part: stiffener_plate_length={dimension}, stiffener_plate_qty={row['stiffener_plate_qty']}",
                    title="Child Part Assignment Debug"
                )

    # Columns
    columns = [
        {"label": "Sr No", "fieldname": "sr_no", "fieldtype": "Int"},
        {"label": "Project", "fieldname": "project", "fieldtype": "Link", "options": "Project"},
        {"label": "IPO Name", "fieldname": "ipo_name", "fieldtype": "Data"},
        {"label": "Section", "fieldname": "section", "fieldtype": "Data"},
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
        part_label = part.replace("_", " ").title()
        columns.append({"label": f"{part_label} Length", "fieldname": f"{part}_length", "fieldtype": "Data"})
        columns.append({"label": f"{part_label} Qty", "fieldname": f"{part}_qty", "fieldtype": "Float"})

    # Data
    data = []
    for idx, row in enumerate(consolidated.values(), start=1):
        data_row = {
            "sr_no": idx,
            "project": row["project"],
            "ipo_name": row["ipo_name"],
            "section": row["section"],
            "a": row["a"],
            "b": row["b"],
            "code": row["code"],
            "l1": row["l1"],
            "l2": row["l2"],
            "dwg_no": row["dwg_no"],
            "total_quantity": row["total_quantity"],
            "u_area": row["u_area"],
            "rm1_code": row["rm1_code"],
            "rm1_length": row["rm1_length"],
            "rm1_qty": row["rm1_qty"],
            "rm2_code": row["rm2_code"],
            "rm2_length": row["rm2_length"],
            "rm2_qty": row["rm2_qty"],
            "rm3_code": row["rm3_code"],
            "rm3_length": row["rm3_length"],
            "rm3_qty": row["rm3_qty"],
        }

        for part in known_child_parts:
            data_row[f"{part}_length"] = row[f"{part}_length"]
            data_row[f"{part}_qty"] = row[f"{part}_qty"]

        data.append(data_row)

    # Debug consolidated data
    frappe.log_error(
        message=f"Consolidated Data: {data}",
        title="Consolidated Data Debug"
    )

    return columns, data