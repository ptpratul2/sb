import frappe
from frappe.utils import flt
import re
import json

def parse_dimension(dimension):
    if not dimension:
        return "", ""
    dimension = dimension.strip("()")
    parts = dimension.split(",")
    l1 = parts[0].strip() if parts else ""
    l2 = parts[1].strip() if len(parts) > 1 else "-"
    frappe.log_error(
        message=f"Parsing dimension: {dimension} -> L1={l1}, L2={l2}",
        title="Dimension Parse Debug"
    )
    return l1, l2

def normalize_fieldname(name):
    name = name.lower()
    name = re.sub(r"[^a-z0-9]", "_", name)
    return name

def execute(filters=None):
    if not filters or not filters.get("fg_raw_material_selector"):
        frappe.throw("Please select FG Raw Material Selector")

    # Get the FG Raw Material Selector document
    doc = frappe.get_doc("FG Raw Material Selector", filters["fg_raw_material_selector"])
    
    # Get FG Components directly from Project Design Upload items
    project_design_uploads = [row.project_design_upload for row in doc.project_design_upload]
    fg_components = []
    for pdu in project_design_uploads:
        pdu_doc = frappe.get_doc("Project Design Upload", pdu)
        for item in pdu_doc.items:
            fg_components.append({
                "fg_code": item.fg_code,
                "quantity": item.quantity,
                "a": item.a,
                "b": item.b,
                "code": item.code,
                "l1": item.l1,
                "l2": item.l2,
                "dwg_no": item.dwg_no,
                "u_area": item.u_area,
                "ipo_name": item.ipo_name,
                "project": pdu_doc.project,
                "section": "",  # Section will be populated from raw_materials
            })

    # Apply filters to FG Components
    filtered_fg_components = []
    project = filters.get("project")
    ipo_name = (filters.get("ipo_name") or "").upper()
    code = (filters.get("code") or "").upper()

    for item in fg_components:
        item_ipo_name = (item["ipo_name"] or "").upper()
        item_project = item["project"]
        item_code = (item["code"] or "").upper()
        fg_code = (item["fg_code"] or "").upper()

        if project and item_project != project:
            continue
        if ipo_name and item_ipo_name != ipo_name:  # Exact match
            continue
        if code and item_code != code:  # Exact match
            continue

        filtered_fg_components.append(item)

    if not filtered_fg_components:
        frappe.msgprint("No FG components match the provided filters.")
        return [], []

    # Consolidate FG Components by fg_code
    consolidated = {}
    for item in filtered_fg_components:
        fg_code = item["fg_code"]
        if fg_code not in consolidated:
            consolidated[fg_code] = {
                "a": item["a"],
                "b": item["b"],
                "code": item["code"],
                "l1": item["l1"],
                "l2": item["l2"],
                "dwg_no": item["dwg_no"],
                "u_area": item["u_area"],
                "quantity": 0,
                "ipo_name": set(),
                "project": set(),
                "section": set(),
                "total_quantity": 0,
                "rm1_code": "",
                "rm1_l1": "",
                "rm1_l2": "",
                "rm1_qty": 0,
                "rm2_code": "",
                "rm2_l1": "",
                "rm2_l2": "",
                "rm2_qty": 0,
                "rm3_code": "",
                "rm3_l1": "",
                "rm3_l2": "",
                "rm3_qty": 0,
                "b_side_rail_l1": "",
                "b_side_rail_l2": "",
                "b_side_rail_qty": 0,
                "outer_cap_l1": "",
                "outer_cap_l2": "",
                "outer_cap_qty": 0,
                "rocker_l1": "",
                "rocker_l2": "",
                "rocker_qty": 0,
                "round_pipe_l1": "",
                "round_pipe_l2": "",
                "round_pipe_qty": 0,
                "square_pipe_l1": "",
                "square_pipe_l2": "",
                "square_pipe_qty": 0,
                "stiffner_h_l1": "",
                "stiffner_h_l2": "",
                "stiffner_h_qty": 0,
                "stiffner_i_l1": "",
                "stiffner_i_l2": "",
                "stiffner_i_qty": 0,
                "stiffner_plate_l1": "",
                "stiffner_plate_l2": "",
                "stiffner_plate_qty": 0,
                "stiffner_u_l1": "",
                "stiffner_u_l2": "",
                "stiffner_u_qty": 0,
            }
        consolidated[fg_code]["total_quantity"] += flt(item["quantity"])
        consolidated[fg_code]["ipo_name"].add(item["ipo_name"])
        consolidated[fg_code]["project"].add(item["project"])

    # Process raw materials for child parts and sections
    raw_materials = doc.raw_materials or []
    raw_material_sections = ["CH SECTION", "CH SECTION CORNER", "L SECTION", "IC SECTION", "J SECTION", "T SECTION", "SOLDIER", "MISC SECTION"]
    predefined_child_parts = {
        "B SIDE RAIL": "b_side_rail",
        "SIDE RAIL": "b_side_rail",
        "STIFFNER PLATE": "stiffner_plate",
        "STIFF PLATE": "stiffner_plate",
        "STIFFENER PLATE": "stiffner_plate",
        "PLATE STIFFNER": "stiffner_plate",
        "ROUND PIPE": "round_pipe",
        "SQUARE PIPE": "square_pipe",
        "ROCKER": "rocker",
        "RK-50": "rocker",
        "U STIFFNER": "stiffner_u",
        "H STIFFNER": "stiffner_h",
        "I STIFFNER": "stiffner_i",
        "OUTER CAP": "outer_cap"
    }

    # Apply filters to raw materials for section and child parts
    for item in raw_materials:
        remark = (item.remark or "").upper()
        item_code = (item.item_code or "").upper()
        fg_code = (item.fg_code or "").upper()
        item_ipo_name = (item.ipo_name or "").upper()
        item_project = item.project
        l1, l2 = parse_dimension(item.dimension)
        quantity = flt(item.quantity)
        total_fg_quantity = consolidated.get(fg_code, {}).get("total_quantity", 0)

        if project and item_project != project:
            continue
        if ipo_name and item_ipo_name != ipo_name:  # Exact match
            continue
        if code and code != item_code:  # Exact match
            continue
        if fg_code not in consolidated:
            continue

        # Add section information only if remark is in raw_material_sections
        if remark in raw_material_sections:
            consolidated[fg_code]["section"].add(remark)

        # Handle raw materials (RM1, RM2, RM3)
        if remark in raw_material_sections:
            # Check if the item_code is already used in any RM slot for this FG
            rm_codes_used = [
                consolidated[fg_code]["rm1_code"],
                consolidated[fg_code]["rm2_code"],
                consolidated[fg_code]["rm3_code"]
            ]

            if item_code not in rm_codes_used:
                for rm_slot in ["rm1", "rm2", "rm3"]:
                    if not consolidated[fg_code][f"{rm_slot}_code"]:
                        consolidated[fg_code][f"{rm_slot}_code"] = item_code
                        consolidated[fg_code][f"{rm_slot}_l1"] = l1
                        consolidated[fg_code][f"{rm_slot}_l2"] = l2
                        consolidated[fg_code][f"{rm_slot}_qty"] =  quantity* total_fg_quantity  # Scale by total FG quantity
                        break


        # Handle child parts
        elif item_code in predefined_child_parts:
            part_fieldname = predefined_child_parts[item_code]
            if not consolidated[fg_code][f"{part_fieldname}_l1"] or (
                consolidated[fg_code][f"{part_fieldname}_l1"] == l1 and
                consolidated[fg_code][f"{part_fieldname}_l2"] == l2):
                consolidated[fg_code][f"{part_fieldname}_l1"] = l1
                consolidated[fg_code][f"{part_fieldname}_l2"] = l2
                consolidated[fg_code][f"{part_fieldname}_qty"] += quantity  # Scale by total FG quantity

    # Define columns
    columns = [
        {"label": "Sr No", "fieldname": "sr_no", "fieldtype": "Int"},
        {"label": "Project", "fieldname": "project", "fieldtype": "Data"},
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
        {"label": "Total Area", "fieldname": "total_area", "fieldtype": "Float"},
        {"label": "RM1 Code", "fieldname": "rm1_code", "fieldtype": "Data"},
        {"label": "RM1 L1", "fieldname": "rm1_l1", "fieldtype": "Data"},
        {"label": "RM1 L2", "fieldname": "rm1_l2", "fieldtype": "Data"},
        {"label": "RM1 Qty", "fieldname": "rm1_qty", "fieldtype": "Float"},
        {"label": "RM2 Code", "fieldname": "rm2_code", "fieldtype": "Data"},
        {"label": "RM2 L1", "fieldname": "rm2_l1", "fieldtype": "Data"},
        {"label": "RM2 L2", "fieldname": "rm2_l2", "fieldtype": "Data"},
        {"label": "RM2 Qty", "fieldname": "rm2_qty", "fieldtype": "Float"},
        {"label": "RM3 Code", "fieldname": "rm3_code", "fieldtype": "Data"},
        {"label": "RM3 L1", "fieldname": "rm3_l1", "fieldtype": "Data"},
        {"label": "RM3 L2", "fieldname": "rm3_l2", "fieldtype": "Data"},
        {"label": "RM3 Qty", "fieldname": "rm3_qty", "fieldtype": "Float"},
        {"label": "B Side Rail L1", "fieldname": "b_side_rail_l1", "fieldtype": "Data"},
        {"label": "B Side Rail L2", "fieldname": "b_side_rail_l2", "fieldtype": "Data"},
        {"label": "B Side Rail Qty", "fieldname": "b_side_rail_qty", "fieldtype": "Float"},
        {"label": "Outer Cap L1", "fieldname": "outer_cap_l1", "fieldtype": "Data"},
        {"label": "Outer Cap L2", "fieldname": "outer_cap_l2", "fieldtype": "Data"},
        {"label": "Outer Cap Qty", "fieldname": "outer_cap_qty", "fieldtype": "Float"},
        {"label": "Rocker L1", "fieldname": "rocker_l1", "fieldtype": "Data"},
        {"label": "Rocker L2", "fieldname": "rocker_l2", "fieldtype": "Data"},
        {"label": "Rocker Qty", "fieldname": "rocker_qty", "fieldtype": "Float"},
        {"label": "Round Pipe L1", "fieldname": "round_pipe_l1", "fieldtype": "Data"},
        {"label": "Round Pipe L2", "fieldname": "round_pipe_l2", "fieldtype": "Data"},
        {"label": "Round Pipe Qty", "fieldname": "round_pipe_qty", "fieldtype": "Float"},
        {"label": "Square Pipe L1", "fieldname": "square_pipe_l1", "fieldtype": "Data"},
        {"label": "Square Pipe L2", "fieldname": "square_pipe_l2", "fieldtype": "Data"},
        {"label": "Square Pipe Qty", "fieldname": "square_pipe_qty", "fieldtype": "Float"},
        {"label": "Stiffner H L1", "fieldname": "stiffner_h_l1", "fieldtype": "Data"},
        {"label": "Stiffner H L2", "fieldname": "stiffner_h_l2", "fieldtype": "Data"},
        {"label": "Stiffner H Qty", "fieldname": "stiffner_h_qty", "fieldtype": "Float"},
        {"label": "Stiffner I L1", "fieldname": "stiffner_i_l1", "fieldtype": "Data"},
        {"label": "Stiffner I L2", "fieldname": "stiffner_i_l2", "fieldtype": "Data"},
        {"label": "Stiffner I Qty", "fieldname": "stiffner_i_qty", "fieldtype": "Float"},
        {"label": "Stiffner Plate L1", "fieldname": "stiffner_plate_l1", "fieldtype": "Data"},
        {"label": "Stiffner Plate L2", "fieldname": "stiffner_plate_l2", "fieldtype": "Data"},
        {"label": "Stiffner Plate Qty", "fieldname": "stiffner_plate_qty", "fieldtype": "Float"},
        {"label": "Stiffner U L1", "fieldname": "stiffner_u_l1", "fieldtype": "Data"},
        {"label": "Stiffner U L2", "fieldname": "stiffner_u_l2", "fieldtype": "Data"},
        {"label": "Stiffner U Qty", "fieldname": "stiffner_u_qty", "fieldtype": "Float"},
    ]

    # Prepare data for report
    data = []
    for idx, row in enumerate(consolidated.values(), start=1):
        a = flt(row.get("a") or 0)
        b = flt(row.get("b") or 0)
        l1 = flt(row.get("l1") or 0)
        l2 = flt(row.get("l2") or 0)
        total_quantity = flt(row.get("total_quantity") or 0)
        u_area = flt(row.get("u_area") or 0)
        total_area = total_quantity * u_area

        data_row = {
            "sr_no": idx,
            "project": ", ".join(row["project"]),
            "ipo_name": ", ".join(row["ipo_name"]),
            "section": ", ".join(row["section"]),
            "a": row["a"],
            "b": row["b"],
            "code": row["code"],
            "l1": row["l1"],
            "l2": row["l2"],
            "dwg_no": row["dwg_no"],
            "total_quantity": total_quantity,
            "u_area": row["u_area"],
            "total_area": total_area,
            "rm1_code": row["rm1_code"],
            "rm1_l1": row["rm1_l1"],
            "rm1_l2": row["rm1_l2"],
            "rm1_qty": row["rm1_qty"],
            "rm2_code": row["rm2_code"],
            "rm2_l1": row["rm2_l1"],
            "rm2_l2": row["rm2_l2"],
            "rm2_qty": row["rm2_qty"],
            "rm3_code": row["rm3_code"],
            "rm3_l1": row["rm3_l1"],
            "rm3_l2": row["rm3_l2"],
            "rm3_qty": row["rm3_qty"],
            "b_side_rail_l1": row["b_side_rail_l1"],
            "b_side_rail_l2": row["b_side_rail_l2"],
            "b_side_rail_qty": row["b_side_rail_qty"],
            "outer_cap_l1": row["outer_cap_l1"],
            "outer_cap_l2": row["outer_cap_l2"],
            "outer_cap_qty": row["outer_cap_qty"],
            "rocker_l1": row["rocker_l1"],
            "rocker_l2": row["rocker_l2"],
            "rocker_qty": row["rocker_qty"],
            "round_pipe_l1": row["round_pipe_l1"],
            "round_pipe_l2": row["round_pipe_l2"],
            "round_pipe_qty": row["round_pipe_qty"],
            "square_pipe_l1": row["square_pipe_l1"],
            "square_pipe_l2": row["square_pipe_l2"],
            "square_pipe_qty": row["square_pipe_qty"],
            "stiffner_h_l1": row["stiffner_h_l1"],
            "stiffner_h_l2": row["stiffner_h_l2"],
            "stiffner_h_qty": row["stiffner_h_qty"],
            "stiffner_i_l1": row["stiffner_i_l1"],
            "stiffner_i_l2": row["stiffner_i_l2"],
            "stiffner_i_qty": row["stiffner_i_qty"],
            "stiffner_plate_l1": row["stiffner_plate_l1"],
            "stiffner_plate_l2": row["stiffner_plate_l2"],
            "stiffner_plate_qty": row["stiffner_plate_qty"],
            "stiffner_u_l1": row["stiffner_u_l1"],
            "stiffner_u_l2": row["stiffner_u_l2"],
            "stiffner_u_qty": row["stiffner_u_qty"],
        }
        data.append(data_row)

    return columns, data