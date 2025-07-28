import frappe
from frappe.utils import flt
import re
import json


def parse_dimension(dimension):
    if not dimension: 
        return "", ""
    dimension = str(dimension).strip("()")
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
    try:
        # Validate required filters
        if not filters or not filters.get("fg_raw_material_selector"):
            frappe.throw("Please select FG Raw Material Selector")

        # Get the FG Raw Material Selector document
        try:
            doc = frappe.get_doc("FG Raw Material Selector", filters["fg_raw_material_selector"])
        except frappe.DoesNotExistError:
            frappe.throw(f"FG Raw Material Selector '{filters['fg_raw_material_selector']}' does not exist")
        
        # Check if project_design_upload exists and has data
        if not hasattr(doc, 'project_design_upload') or not doc.project_design_upload:
            frappe.msgprint("No Project Design Upload data found in the selected FG Raw Material Selector.")
            return [], []

        # Get FG Components directly from Project Design Upload items
        project_design_uploads = [row.project_design_upload for row in doc.project_design_upload if row.project_design_upload]
        
        if not project_design_uploads:
            frappe.msgprint("No valid Project Design Upload references found.")
            return [], []

        fg_components = []
        for pdu in project_design_uploads:
            try:
                pdu_doc = frappe.get_doc("Project Design Upload", pdu)
                
                # Check if items exist
                if not hasattr(pdu_doc, 'items') or not pdu_doc.items:
                    frappe.log_error(
                        message=f"No items found in Project Design Upload: {pdu}",
                        title="Missing Items Debug"
                    )
                    continue
                    
                for item in pdu_doc.items:
                    fg_components.append({
                        "fg_code": item.get("fg_code", ""),
                        "quantity": flt(item.get("quantity", 0)),
                        "a": item.get("a", ""),
                        "b": item.get("b", ""),
                        "code": item.get("code", ""),
                        "l1": item.get("l1", ""),
                        "l2": item.get("l2", ""),
                        "dwg_no": item.get("dwg_no", ""),
                        "u_area": flt(item.get("u_area", 0)),
                        "ipo_name": item.get("ipo_name", ""),
                        "project": pdu_doc.get("project", ""),
                        "section": "",
                        "project_design_item_reference": item.get("project_design_item_reference", "")
                    })
                    frappe.log_error(
                        message=f"FG Component: fg_code={item.get('fg_code')}, ipo_name={item.get('ipo_name')}, project={pdu_doc.get('project')}, quantity={item.get('quantity')}, ref={item.get('project_design_item_reference')}",
                        title="FG Component Debug"
                    )
            except frappe.DoesNotExistError:
                frappe.log_error(
                    message=f"Project Design Upload {pdu} does not exist",
                    title="Missing PDU Debug"
                )
                continue
            except Exception as e:
                frappe.log_error(
                    message=f"Error processing Project Design Upload {pdu}: {str(e)}",
                    title="PDU Processing Error"
                )
                continue

        if not fg_components:
            frappe.msgprint("No FG components found in the selected Project Design Uploads.")
            return [], []

        # Apply filters to FG Components
        filtered_fg_components = []
        project = filters.get("project")
        ipo_name = (filters.get("ipo_name") or "").upper()
        code = (filters.get("code") or "").upper()

        for item in fg_components:
            item_ipo_name = (item["ipo_name"] or "").upper()
            item_project = item["project"] or ""
            item_code = (item["code"] or "").upper()
            fg_code = (item["fg_code"] or "").upper()

            if project and item_project != project:
                continue
            if ipo_name and item_ipo_name != ipo_name:  # Exact match
                continue
            if code and item_code != code:  # Exact match
                continue

            filtered_fg_components.append(item)
            frappe.log_error(
                message=f"Filtered FG Component: fg_code={fg_code}, ipo_name={item_ipo_name}, project={item_project}",
                title="Filtered FG Component Debug"
            )

        if not filtered_fg_components:
            frappe.msgprint("No FG components match the provided filters.")
            return [], []

        # Consolidate FG Components by project_design_item_reference only
        consolidated = {}
        for item in filtered_fg_components:
            consolidation_key = item.get("project_design_item_reference")
            if not consolidation_key:
                # Generate a fallback key if project_design_item_reference is missing
                consolidation_key = f"{item['fg_code']}_{item['ipo_name']}_{item['project']}_{item['code']}"
                frappe.log_error(
                    message=f"Using fallback consolidation key: {consolidation_key} for FG component fg_code={item['fg_code']}, ipo_name={item['ipo_name']}",
                    title="Fallback Consolidation Key"
                )

            if consolidation_key not in consolidated:
                consolidated[consolidation_key] = {
                    "fg_code": item["fg_code"],
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
            consolidated[consolidation_key]["total_quantity"] += flt(item["quantity"])
            consolidated[consolidation_key]["ipo_name"].add(item["ipo_name"] or "")
            consolidated[consolidation_key]["project"].add(item["project"] or "")

        # Process raw materials if they exist
        if hasattr(doc, 'raw_materials') and doc.raw_materials:
            # Aggregate raw material quantities by fg_code, ipo_name, project, and item_code
            raw_materials = doc.raw_materials
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

            # Process raw materials directly without aggregation
            frappe.log_error(
                message=f"Processing {len(raw_materials)} raw materials",
                title="Raw Materials Count"
            )
            
            # Process each raw material individually
            for item in raw_materials:
                remark = (item.get("remark") or "").upper()
                item_code = (item.get("item_code") or "").upper()
                fg_code = (item.get("fg_code") or "").upper()
                item_ipo_name = (item.get("ipo_name") or "").upper()
                item_project = item.get("project", "")
                project_design_item_reference = item.get("project_design_item_reference") or ""
                l1, l2 = parse_dimension(item.get("dimension"))
                quantity = flt(item.get("quantity", 0))

                frappe.log_error(
                    message=f"Processing RM: fg_code={fg_code}, item_code={item_code}, remark={remark}, ipo_name={item_ipo_name}, project={item_project}, qty={quantity}, ref={project_design_item_reference}",
                    title="Raw Material Processing"
                )

                # Find the correct consolidation key - try multiple approaches
                consolidation_key = None
                
                # First try: exact match with project_design_item_reference
                if project_design_item_reference:
                    if project_design_item_reference in consolidated:
                        consolidation_key = project_design_item_reference
                        frappe.log_error(
                            message=f"Found exact match consolidation_key: {consolidation_key} for item_code={item_code}",
                            title="Consolidation Key Match"
                        )
                
                # Second try: find by matching FG component details
                if not consolidation_key:
                    for key, consolidated_item in consolidated.items():
                        # Check if this consolidated item matches the raw material
                        if (consolidated_item["fg_code"].upper() == fg_code and
                            any(ipo.upper() == item_ipo_name for ipo in consolidated_item["ipo_name"]) and
                            any(proj == item_project for proj in consolidated_item["project"])):
                            consolidation_key = key
                            frappe.log_error(
                                message=f"Found FG component match consolidation_key: {consolidation_key} for item_code={item_code}",
                                title="Consolidation Key Match"
                            )
                            break
                
                # Third try: find by partial matching (less strict)
                if not consolidation_key:
                    for key, consolidated_item in consolidated.items():
                        if consolidated_item["fg_code"].upper() == fg_code:
                            consolidation_key = key
                            frappe.log_error(
                                message=f"Using partial match for fg_code={fg_code}, consolidation_key={key} for item_code={item_code}",
                                title="Partial Match Used"
                            )
                            break

                if not consolidation_key:
                    frappe.log_error(
                        message=f"No consolidation key found for fg_code={fg_code}, ipo_name={item_ipo_name}, project={item_project}, item_code={item_code}, ref={project_design_item_reference}",
                        title="Consolidation Key Missing"
                    )
                    continue

                frappe.log_error(
                    message=f"Processing item_code={item_code}, remark={remark} for consolidation_key={consolidation_key}",
                    title="Item Processing Start"
                )

                # Add section information
                if remark in raw_material_sections:
                    consolidated[consolidation_key]["section"].add(remark)

                # Check if this is a child part based on remark/section
                is_child_part_section = remark == "CHILD PART"

                # Handle raw materials (RM1, RM2, RM3) - but exclude CHILD PART items
                is_raw_material = (
                    (remark in raw_material_sections or 
                     item_code == "130 L" or
                     any(section in remark for section in ["SECTION", "ANGLE", "CHANNEL", "BEAM"]) or
                     any(section in item_code for section in ["L", "C", "I", "H", "T"])) and
                    not is_child_part_section  # Exclude CHILD PART items from RM columns
                )
                
                if is_raw_material:
                    # Log current RM slot status before assignment
                    frappe.log_error(
                        message=f"Before assignment - RM1: {consolidated[consolidation_key]['rm1_code']}, RM2: {consolidated[consolidation_key]['rm2_code']}, RM3: {consolidated[consolidation_key]['rm3_code']} for consolidation_key={consolidation_key}",
                        title="RM Slots Before Assignment"
                    )
                    
                    # Always assign to the next available RM slot without checking for existing item_code
                    rm_assigned = False
                    for rm_slot in ["rm1", "rm2", "rm3"]:
                        if not consolidated[consolidation_key][f"{rm_slot}_code"]:
                            consolidated[consolidation_key][f"{rm_slot}_code"] = item_code
                            consolidated[consolidation_key][f"{rm_slot}_l1"] = l1
                            consolidated[consolidation_key][f"{rm_slot}_l2"] = l2
                            consolidated[consolidation_key][f"{rm_slot}_qty"] = quantity
                            rm_assigned = True
                            frappe.log_error(
                                message=f"Assigned {item_code} to {rm_slot} for consolidation_key={consolidation_key}, qty={quantity}, l1={l1}, l2={l2}",
                                title="Raw Material Assignment Debug"
                            )
                            break
                    
                    # Log current RM slot status after assignment
                    frappe.log_error(
                        message=f"After assignment - RM1: {consolidated[consolidation_key]['rm1_code']}, RM2: {consolidated[consolidation_key]['rm2_code']}, RM3: {consolidated[consolidation_key]['rm3_code']} for consolidation_key={consolidation_key}",
                        title="RM Slots After Assignment"
                    )
                    
                    if not rm_assigned:
                        frappe.log_error(
                            message=f"Could not assign {item_code} - all RM slots are full for consolidation_key={consolidation_key}",
                            title="Raw Material Assignment Full"
                        )
                else:
                    frappe.log_error(
                        message=f"Item {item_code} with remark={remark} is NOT classified as raw material",
                        title="Not Raw Material"
                    )

                # Handle child parts - check both item_code and remark, OR if section is CHILD PART
                part_fieldname = None
                if item_code in predefined_child_parts:
                    part_fieldname = predefined_child_parts[item_code]
                elif is_child_part_section:
                    # If section is CHILD PART, try to find matching child part by item_code pattern
                    # or assign to a generic child part field based on item_code
                    for part_name, field_name in predefined_child_parts.items():
                        if part_name in item_code or item_code in part_name:
                            part_fieldname = field_name
                            break
                    # If no specific match found but it's a CHILD PART, log for manual handling
                    if not part_fieldname:
                        frappe.log_error(
                            message=f"CHILD PART item {item_code} could not be mapped to predefined child parts",
                            title="Unmapped Child Part"
                        )
                else:
                    # Check if remark matches any predefined child parts
                    for part_name, field_name in predefined_child_parts.items():
                        if part_name in remark:
                            part_fieldname = field_name
                            break
                
                if part_fieldname:
                    # Always add the quantity without checking for existing dimensions
                    # Set dimensions from the first entry, then just add quantities for subsequent entries
                    if not consolidated[consolidation_key][f"{part_fieldname}_l1"]:
                        consolidated[consolidation_key][f"{part_fieldname}_l1"] = l1
                        consolidated[consolidation_key][f"{part_fieldname}_l2"] = l2
                    
                    consolidated[consolidation_key][f"{part_fieldname}_qty"] += quantity
                    frappe.log_error(
                        message=f"Assigned child part {item_code} to {part_fieldname} for consolidation_key={consolidation_key}, qty={quantity}, total_qty={consolidated[consolidation_key][f'{part_fieldname}_qty']}",
                        title="Child Part Assignment Debug"
                    )



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

            # Log final consolidated data for debugging
            frappe.log_error(
                message=f"Final Row {idx}: fg_code={row['fg_code']}, rm1={row['rm1_code']}, rm2={row['rm2_code']}, rm3={row['rm3_code']}, b_side_rail_qty={row['b_side_rail_qty']}, outer_cap_qty={row['outer_cap_qty']}",
                title="Final Consolidated Data"
            )

            data_row = {
                "sr_no": idx,
                "project": ", ".join(filter(None, row["project"])),
                "ipo_name": ", ".join(filter(None, row["ipo_name"])),
                "section": ", ".join(filter(None, row["section"])),
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

        frappe.log_error(
            message=f"Report generated successfully with {len(data)} rows",
            title="Report Generation Complete"
        )

        return columns, data

    except Exception as e:
        frappe.log_error(
            message=f"Report execution error: {str(e)}\nTraceback: {frappe.get_traceback()}",
            title="Report Execution Error"
        )
        frappe.throw(f"Error generating report: {str(e)}")