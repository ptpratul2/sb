# Copyright (c) 2025, ptpratul2@gmail.com and contributors
# For license information, please see license.txt
import frappe
from frappe.model.document import Document
import math
import json
from frappe.utils.background_jobs import enqueue
from frappe.utils import now

class FGRawMaterialSelector(Document):
    def validate(self):
        # Instead of processing directly, enqueue the processing
        frappe.enqueue(
            'sb.sb.doctype.fg_raw_material_selector.fg_raw_material_selector.process_fg_codes_background',
            queue='long',
            timeout=3600,  # 1 hour timeout
            docname=self.name
        )
        frappe.msgprint("Processing of FG codes has been queued. You will be notified once completed.")

    def process_fg_codes(self):
        try:
            # Log only serializable PDU names
            pdu_names = [row.get("project_design_upload") for row in self.project_design_upload if row.get("project_design_upload")]
            frappe.log_error(message=f"Processing PDUs: {json.dumps(pdu_names, indent=2)}", title="FG Process Debug")
            if not self.project_design_upload or not isinstance(self.project_design_upload, list):
                frappe.throw("No Project Design Uploads selected or invalid format.")

            output = []
            valid_fg_codes = (
                ["B", "CP", "CPP", "CPPP", "D", "K", "PC", "PH", "PLB", "SB", "T", "TS", "W", "WR", "WRB", "WS", "WX", "WXS"] +  # ch_straight
                ["BC", "BCE", "KC", "KCE"] +  # ch_corner
                ["CC", "CCL", "CCR", "IC", "ICB", "ICT", "ICX", "LS", "LSL", "LSR", "LSW", "SL", "SLR"] +  # ic_straight
                ["SC", "SCE", "SCY", "SCZ", "LSC", "LSCE"] +  # ic_corner
                ["JL", "JLB", "JLT", "JLX", "JR", "JRB", "JRT", "JRX", "SX"] +  # j_straight
                ["SXC", "SXCE"] +  # j_corner
                ["PCE", "SBE", "TSE", "WRBSE", "WRSE", "WSE", "WXSE"] +  # t_straight
                ["DP", "EB", "MB", "EC", "ECH", "ECT", "ECX", "ECB", "RK"]  # misc_straight
            )

            # Batch processing setup
            batch_size = 100  # Process 100 FG codes at a time
            fg_codes_all = []
            for pdu_entry in self.project_design_upload:
                pdu_name = pdu_entry.get("project_design_upload")
                if not pdu_name or not isinstance(pdu_name, str):
                    frappe.log_error(message=f"Invalid Project Design Upload name: {pdu_name}", title="FG Raw Material Error")
                    continue

                try:
                    project_design = frappe.get_doc("Project Design Upload", pdu_name)
                except frappe.DoesNotExistError:
                    frappe.log_error(message=f"Project Design Upload {pdu_name} not found", title="FG Raw Material Error")
                    continue

                pdu_project = project_design.get("project")
                fg_codes = project_design.get("items", [])
                fg_codes_serializable = [
                    {
                        "fg_code": fg.get("fg_code"),
                        "quantity": fg.get("quantity"),
                        "uom": fg.get("uom"),
                        "ipo_name": fg.get("ipo_name")
                    } for fg in fg_codes
                ]
                frappe.log_error(message=f"FG Codes for PDU {pdu_name}: {json.dumps(fg_codes_serializable, indent=2)}", title="FG Process Debug")
                if not fg_codes:
                    frappe.msgprint(f"No FG Components found for Project Design Upload: {pdu_name}")
                    frappe.log_error(message=f"No FG Components found for Project Design Upload: {pdu_name}", title="FG Raw Material Error")
                    continue

                fg_codes_all.extend([(fg_component, pdu_project, pdu_name) for fg_component in fg_codes])

            # Clear existing raw materials
            self.raw_materials = []

            # Process FG codes in batches
            for i in range(0, len(fg_codes_all), batch_size):
                batch = fg_codes_all[i:i + batch_size]
                for fg_component, pdu_project, pdu_name in batch:
                    fg_code = fg_component.get("fg_code")
                    component_quantity = fg_component.get("quantity", 1)
                    component_uom = fg_component.get("uom")
                    ipo_name = fg_component.get("ipo_name")

                    if not fg_code or not isinstance(fg_code, str):
                        frappe.log_error(message=f"Invalid FG Code in PDU: {pdu_name}, FG Code: {fg_code}", title="FG Raw Material Error")
                        continue

                    parts = fg_code.split('|')
                    if len(parts) != 5 or parts[2] not in valid_fg_codes:
                        frappe.log_error(message=f"Skipping invalid FG Code: {fg_code} in PDU: {pdu_name}", title="FG Raw Material Error")
                        continue

                    try:
                        raw_materials = self.process_single_fg_code(fg_code)
                        if not isinstance(raw_materials, list):
                            frappe.log_error(message=f"Invalid data for FG Code '{fg_code}': {raw_materials}", title="FG Raw Material Error")
                            continue
                    except Exception as e:
                        frappe.log_error(message=f"Error processing FG Code '{fg_code}' in PDU {pdu_name}: {str(e)}", title="FG Raw Material Error")
                        continue

                    rm_table = []
                    for rm in raw_materials:
                        if not isinstance(rm, dict):
                            frappe.log_error(message=f"Invalid raw material for FG Code '{fg_code}': {rm}", title="FG Raw Material Error")
                            continue
                        rm_quantity = rm.get("quantity", 1) * component_quantity
                        rm_entry = {
                            "fg_code": fg_code,
                            "raw_material_code": rm.get("code"),
                            "item_code": rm.get("code"),
                            "dimension": rm.get("dimension"),
                            "remark": rm.get("remark"),
                            "quantity": rm_quantity,
                            "project": pdu_project,
                            "ipo_name": ipo_name,
                            "project_design_upload": pdu_name,
                            "status": rm.get("status"),
                            "warehouse": rm.get("warehouse")
                        }
                        if component_uom:
                            rm_entry["uom"] = component_uom

                        rm_table.append(rm_entry)
                        try:
                            self.append("raw_materials", rm_entry)
                        except Exception as e:
                            frappe.log_error(message=f"Error appending raw material for FG Code '{fg_code}': {str(e)}", title="FG Raw Material Error")
                            continue

                    output.append({
                        "fg_code": fg_code,
                        "project_design_upload": pdu_name,
                        "raw_materials": rm_table
                    })

            if output:
                frappe.log_error(message=json.dumps(output, indent=2), title="FG Raw Material Output")
            else:
                frappe.msgprint("No valid FG codes processed. Check the Error Log for details.")
                frappe.log_error(message="No valid FG codes processed.", title="FG Raw Material Error")

            # Save the document after processing
            self.save()

            # Notify user of completion
            frappe.publish_realtime(
                event='msgprint',
                message='FG Raw Material processing completed successfully.',
                user=frappe.session.user
            )

        except Exception as e:
            frappe.log_error(message=f"Error in process_fg_codes: {str(e)}", title="FG Raw Material Error")
            frappe.publish_realtime(
                event='msgprint',
                message=f'Error processing FG codes: {str(e)}',
                user=frappe.session.user
            )

    def process_single_fg_code(self, fg_code):
        def safe_int(val, default=0):
            try:
                return int(val)
            except (ValueError, TypeError):
                return default

        try:
            frappe.log_error(message=f"Raw FG Code: {fg_code}", title="FG Raw Material Input")
            parts = fg_code.split('|')
            if len(parts) != 5:
                frappe.log_error(message=f"Invalid FG Code format. Expected 5 parts, got {len(parts)}: {fg_code}", title="FG Raw Material Error")
                return []

            frappe.log_error(message=f"Server-Side Parts: {parts}", title="FG Raw Material Parts")

            a = safe_int(parts[0])
            b = safe_int(parts[1]) if parts[1] else 0
            fg_code_part = parts[2]
            l1 = safe_int(parts[3])
            l2 = safe_int(parts[4]) if parts[4] else 0

            frappe.log_error(message=f"Parsed: A={a}, B={b}, FG_CODE={fg_code_part}, L1={l1}, L2={l2}", title="FG Raw Material Parsed")

        except Exception as e:
            frappe.log_error(message=f"Error parsing FG Code: {str(e)}", title="FG Raw Material Error")
            return []

        # Define FG groups
        ch_straight = ["B", "CP", "CPP", "CPPP", "D", "K", "PC", "PH", "PLB", "SB", "T", "TS", "W", "WR", "WRB", "WS", "WX", "WXS"]
        ch_corner = ["BC", "BCE", "KC", "KCE"]
        ic_straight = ["CC", "CCL", "CCR", "IC", "ICB", "ICT", "ICX", "LS", "LSL", "LSR", "LSW", "SL", "SLR"]
        ic_corner = ["SC", "SCE", "SCY", "SCZ", "LSC", "LSCE"]
        j_straight = ["JL", "JLB", "JLT", "JLX", "JR", "JRB", "JRT", "JRX", "SX"]
        j_corner = ["SXC", "SXCE"]
        t_straight = ["PCE", "SBE", "TSE", "WRBSE", "WRSE", "WSE", "WXSE"]
        misc_straight = ["DP", "EB", "MB", "EC", "ECH", "ECT", "ECX", "ECB", "RK"]
        wall_types = ["T", "TS", "W", "WR", "WRB", "WS", "WX", "WXS"]
        cp_like_types = ["CP", "CPP", "CPPP", "PH"]

        # Channel section mappings
        ch_sections = {
            50: "50 CH", 75: "75 CH", 100: "100 CH", 125: "125 CH",
            150: "150 CH", 175: "175 CH", 200: "200 CH", 250: "250 CH",
            300: "300 CH"
        }

        # IC section mappings for exact matches
        ic_sections = {
            (100, 100): ("100 IC", "-", "IC SECTION"),
            (125, 100, "SL"): ("125 IC", "-", "IC SECTION"),
            (125, 100, "CC"): ("125 SL", "-", "IC SECTION"),
            (125, 100): ("125 IC", "-", "IC SECTION"),
            (150, 100): ("150 IC", "-", "IC SECTION")
        }

        # L-section mappings for IC straight and corner
        ic_l_sections = {
            (50, 125): ("130 L", "130 L", "L SECTION"),
            (126, 150): ("155 L", "155 L", "L SECTION"),
            (151, 175): ("180 L", "180 L", "L SECTION"),
            (176, 200): ("205 L", "205 L", "L SECTION"),
            (201, 225): ("230 L", "230 L", "L SECTION"),
            (226, 250): ("255 L", "255 L", "L SECTION"),
            (251, 275): ("280 L", "280 L", "L SECTION"),
            (276, 300): ("305 L", "305 L", "L SECTION")
        }

        # L-section mappings for CH straight
        ch_l_sections_straight = {
            (51, 125): ("130 L", "MAIN FRAME", "L SECTION"),
            (126, 149): ("155 L", "MAIN FRAME", "L SECTION"),
            (151, 174): ("180 L", "MAIN FRAME", "L SECTION"),
            (176, 199): ("205 L", "MAIN FRAME", "L SECTION"),
            (201, 225): ("230 L", "MAIN FRAME", "L SECTION"),
            (226, 249): ("255 L", "MAIN FRAME", "L SECTION"),
            (251, 275): ("280 L", "MAIN FRAME", "L SECTION"),
            (276, 300): ("305 L", "MAIN FRAME", "L SECTION"),
            (301, 325): ("180 L", "155 L", "L SECTION"),
            (326, 350): ("180 L", "180 L", "L SECTION"),
            (351, 375): ("205 L", "180 L", "L SECTION"),
            (376, 400): ("205 L", "205 L", "L SECTION"),
            (401, 425): ("230 L", "205 L", "L SECTION"),
            (426, 450): ("230 L", "230 L", "L SECTION"),
            (451, 475): ("255 L", "230 L", "L SECTION"),
            (476, 500): ("255 L", "255 L", "L SECTION"),
            (501, 525): ("280 L", "255 L", "L SECTION"),
            (526, 550): ("280 L", "280 L", "L SECTION"),
            (551, 575): ("305 L", "280 L", "L SECTION"),
            (576, 600): ("305 L", "305 L", "L SECTION")
        }

        # L-section mappings for CH corner
        ch_l_sections_corner = {
            (51, 124): ("125 L", "MAIN FRAME", "L SECTION"),
            (126, 149): ("150 L", "MAIN FRAME", "L SECTION"),
            (151, 174): ("175 L", "MAIN FRAME", "L SECTION"),
            (176, 199): ("200 L", "MAIN FRAME", "L SECTION"),
            (201, 224): ("225 L", "MAIN FRAME", "L SECTION"),
            (226, 249): ("250 L", "MAIN FRAME", "L SECTION"),
            (251, 275): ("275 L", "MAIN FRAME", "L SECTION"),
            (276, 300): ("300 L", "MAIN FRAME", "L SECTION"),
            (301, 325): ("175 L", "150 L", "L SECTION"),
            (326, 350): ("175 L", "175 L", "L SECTION"),
            (351, 375): ("200 L", "175 L", "L SECTION"),
            (376, 400): ("200 L", "200 L", "L SECTION"),
            (401, 425): ("225 L", "200 L", "L SECTION"),
            (426, 450): ("225 L", "225 L", "L SECTION"),
            (451, 475): ("250 L", "225 L", "L SECTION"),
            (476, 500): ("250 L", "250 L", "L SECTION"),
            (501, 525): ("275 L", "250 L", "L SECTION"),
            (526, 550): ("275 L", "275 L", "L SECTION"),
            (551, 575): ("300 L", "275 L", "L SECTION"),
            (576, 600): ("300 L", "300 L", "L SECTION")
        }

        # J section mappings
        j_sections = {
            (25, 50): ("J SEC", "-", "J SECTION"),
            (51, 115): ("115 T", "-", "J SECTION"),
            (116, 250): ("AL SHEET", "-", "J SECTION")
        }

        j_l_sections = {
            (50, 125): ("130 L", "L SECTION"),
            (126, 150): ("155 L", "L SECTION"),
            (151, 175): ("180 L", "L SECTION"),
            (176, 200): ("205 L", "L SECTION"),
            (201, 225): ("230 L", "L SECTION"),
            (226, 250): ("255 L", "L SECTION"),
            (251, 275): ("280 L", "L SECTION"),
            (276, 300): ("305 L", "L SECTION")
        }

        # T section mappings
        t_sections = {
            (230,): ("100 T", "-", "-", "T SECTION"),
            (231, 360): ("115 T", "115 T", "-", "T SECTION"),
            (380,): ("250 CH", "EC", "-", "T SECTION"),
            (430,): ("300 CH", "EC", "-", "T SECTION"),
            (361, 380): ("255 L", "MAIN FRAME", "EC", "T SECTION"),
            (381, 405): ("280 L", "MAIN FRAME", "EC", "T SECTION"),
            (406, 430): ("305 L", "MAIN FRAME", "EC", "T SECTION"),
            (431, 455): ("180 L", "155 L", "EC", "T SECTION"),
            (456, 480): ("180 L", "180 L", "EC", "T SECTION")
        }

        # Misc section mappings
        misc_sections = {
            (100, "EB"): ("EB MB 100", "-", "SOLDIER WT LIP"),
            (150, "EB"): ("EB MB 150", "-", "SOLDIER WT LIP"),
            (100, "MB"): ("EB MB 100", "-", "SOLDIER WT LIP"),
            (150, "MB"): ("EB MB 150", "-", "SOLDIER WT LIP"),
            (100, "DP"): ("DP 100", "-", "SOLDIER W/O LIP"),
            (150, "DP"): ("DP 150", "-", "SOLDIER W/O LIP"),
            (130,): ("EXTERNAL CORNER", "-", "EXTERNAL CORNER"),
            (50, "RK"): ("RK-50", "-", "RK")
        }

        raw_materials = []
        child_parts = []
        degree_cutting = getattr(self, 'degree_cutting', False)

        if fg_code_part in ch_straight or fg_code_part in ch_corner:
            is_corner = fg_code_part in ch_corner
            section_map = ch_l_sections_corner if is_corner else ch_l_sections_straight
            cut_dim1, cut_dim2 = str(l1), str(l2) if l2 else "-"
            if is_corner:
                if fg_code_part in ["BCE", "KCE"]:
                    cut_dim1, cut_dim2 = f"{l1+65}", f"{l2+65}"
                else:
                    cut_dim1, cut_dim2 = str(l1), str(l2) if l2 else "-"
            if a < 300 and a % 25 == 0 and a in ch_sections:
                rm_code = ch_sections[a]
                cut_dim = f"{cut_dim1},{cut_dim2}" if is_corner else cut_dim1
                raw_materials.append({"code": rm_code, "dimension": cut_dim, "remark": "CHANNEL SECTION", "quantity": 1})
                frappe.log_error(message=f"CH {'Corner' if is_corner else 'Straight'}: A={a} is multiple of 25, using RM1={rm_code}, Cut={cut_dim}", title="CH Section Logic")
            else:
                for (min_a, max_a), (rm1, rm2, remark) in section_map.items():
                    if min_a <= a <= max_a:
                        cut_dim = f"{cut_dim1},{cut_dim2}" if is_corner else cut_dim1
                        if a >= 301:
                            raw_materials.append({"code": rm1, "dimension": cut_dim, "remark": remark, "quantity": 1})
                            raw_materials.append({"code": rm2, "dimension": cut_dim, "remark": remark, "quantity": 1})
                            frappe.log_error(message=f"CH {'Corner' if is_corner else 'Straight'}: A={a} in range {min_a}-{max_a}, using RM1={rm1}, RM2={rm2}, Cut={cut_dim}, QTY=2", title="CH Section Logic")
                        else:
                            raw_materials.append({"code": rm1, "dimension": cut_dim, "remark": remark, "quantity": 1})
                            if rm2 != "MAIN FRAME":
                                raw_materials.append({"code": rm2, "dimension": cut_dim, "remark": remark, "quantity": 1})
                            else:
                                raw_materials.append({"code": "MAIN FRAME", "dimension": cut_dim, "remark": remark, "quantity": 1})
                            frappe.log_error(message=f"CH {'Corner' if is_corner else 'Straight'}: A={a} in range {min_a}-{max_a}, using RM1={rm1}, RM2={rm2}, Cut={cut_dim}", title="CH Section Logic")
                        break
            
        if fg_code_part != "PLB":
            side_rail_qty = 1 if degree_cutting and fg_code_part in ["WR", "WRB"] else 2
            child_parts.append({"code": "SIDE RAIL", "dimension": f"{a-16}", "remark": "CHILD PART", "quantity": side_rail_qty})
            raw_materials.append({"code": "SIDE RAIL", "dimension": f"{a-16}", "remark": "CHILD PART", "quantity": side_rail_qty})
        if fg_code_part == "K" and l1 >= 1800:
            child_parts.append({"code": "STIFF PLATE", "dimension": f"{a-16}X61X4", "remark": "CHILD PART", "quantity": 4})
            raw_materials.append({"code": "STIFF PLATE", "dimension": f"{a-16}X61X4", "remark": "CHILD PART", "quantity": 4})
        if fg_code_part in cp_like_types:
            pipe_qty = {"CP": 1, "CPP": 2, "CPPP": 3, "PH": 1}.get(fg_code_part, 1)
            child_parts.append({"code": "ROUND PIPE", "dimension": "146", "remark": "CHILD PART", "quantity": pipe_qty})
            raw_materials.append({"code": "ROUND PIPE", "dimension": "146", "remark": "CHILD PART", "quantity": pipe_qty})
            child_parts.append({"code": "SQUARE PIPE", "dimension": "80", "remark": "CHILD PART", "quantity": pipe_qty})
            raw_materials.append({"code": "SQUARE PIPE", "dimension": "80", "remark": "CHILD PART", "quantity": pipe_qty})
        if fg_code_part in ["WR", "WRB"] and not degree_cutting:
            child_parts.append({"code": "RK-50", "dimension": f"{a}", "remark": "CHILD PART", "quantity": 1})
            raw_materials.append({"code": "RK-50", "dimension": f"{a}", "remark": "CHILD PART", "quantity": 1})
        if fg_code_part in wall_types:
            u_stiff_qty = 8 if fg_code_part in ["W", "WR", "WRB", "WS", "WX", "WXS"] else 3
            child_parts.append({"code": "U STIFF", "dimension": f"{a-16}", "remark": "CHILD PART", "quantity": u_stiff_qty})
            raw_materials.append({"code": "U STIFF", "dimension": f"{a-16}", "remark": "CHILD PART", "quantity": u_stiff_qty})
            if fg_code_part in ["W", "WR", "WRB", "WS", "WX", "WXS"]:
                child_parts.append({"code": "H STIFF", "dimension": f"{a-16}", "remark": "CHILD PART", "quantity": 2})
                raw_materials.append({"code": "H STIFF", "dimension": f"{a-16}", "remark": "CHILD PART", "quantity": 2})
        if fg_code_part in ["D", "SB", "PC", "B"]:
            i_stiff_qty = 4 if fg_code_part in ["D", "SB"] else 5
            child_parts.append({"code": "I STIFF", "dimension": f"{a-16}", "remark": "CHILD PART", "quantity": i_stiff_qty})
            raw_materials.append({"code": "I STIFF", "dimension": f"{a-16}", "remark": "CHILD PART", "quantity": i_stiff_qty})
        if fg_code_part in ["BC", "BCE", "KC", "KCE"] and a < 301:
            child_parts.append({"code": "STIFF PLATE", "dimension": f"{a-16}X61X4", "remark": "CHILD PART", "quantity": 2})
            raw_materials.append({"code": "STIFF PLATE", "dimension": f"{a-16}X61X4", "remark": "CHILD PART", "quantity": 2})
        if fg_code_part == "B" and l1 == 2775:
            child_parts.append({"code": "STIFF PLATE", "dimension": "61X109X4", "remark": "RAW", "quantity": 3})
            raw_materials.append({"code": "STIFF raw_material", "dimension": "61X109X4", "raw_material": "RAW", "quantity": 3})    


        elif fg_code_part in ic_straight or fg_code_part in ic_corner:
            is_corner = fg_code_part in ic_corner
            key = (a, b, "") if fg_code_part in ["SL", "CC"] else (a, b)
            cut_dim1, cut_dim2 = str(l1), str(l2) if l2 else "-"
            if fg_code_part in ["IC", "ICB"]:
                cut_dim1 = f"{l1-4}"
            elif fg_code_part in ["ICT", "ICX"]:
                cut_dim1 = f"{l1-8}"
            elif fg_code_part == "SCE":
                cut_dim1, cut_dim2 = f"{l1+b}", f"{l2+b}"
            elif fg_code_part == "SCY":
                cut_dim1, cut_dim2 = f"{l1}", f"{l2+96}"
            elif fg_code_part == "SCZ":
                cut_dim1, cut_dim2 = f"{l1-4}", f"{l2}"
            elif fg_code_part == "LSCE":
                cut_dim1, cut_dim2 = f"{l1+b}", f"{l2+b}"
            if key in ic_sections:
                rm1, rm2, remark = ic_sections[key]
                cut_dim = f"{cut_dim1},{cut_dim2}" if is_corner else cut_dim1
                raw_materials.append({"code": rm1, "dimension": cut_dim, "remark": remark, "quantity": 1})
                frappe.log_error(message=f"IC {'Corner' if is_corner else 'Straight'}: A={a}, B={b}, FG={fg_code_part}, using RM1={rm1}, Cut={cut_dim}", title="IC Section Logic")
                if rm2 != "-":
                    raw_materials.append({"code": rm2, "dimension": cut_dim, "remark": remark, "quantity": 1})
            else:
                if a < 150 and a % 25 == 0:
                    cut_dim = f"{cut_dim1},{cut_dim2}" if is_corner else cut_dim1
                    raw_materials.append({"code": f"{a} IC", "dimension": cut_dim, "remark": "IC SECTION", "quantity": 1})
                    frappe.log_error(message=f"IC {'Corner' if is_corner else 'Straight'}: A={a} < 150 and multiple of 25, using RM1={a} IC, Cut={cut_dim}", title="IC Section Logic")
                else:
                    for (min_val, max_val), (rm1, rm2, remark) in ic_l_sections.items():
                        if min_val <= a <= max_val:
                            cut_dim = f"{cut_dim1},{cut_dim2}" if is_corner else cut_dim1
                            raw_materials.append({"code": rm1, "dimension": cut_dim, "remark": remark, "quantity": 2 if not is_corner else 1})
                            frappe.log_error(message=f"IC {'Corner' if is_corner else 'Straight'}: A={a} in range {min_val}-{max_val}, using RM1={rm1}, Cut={cut_dim}, QTY={2 if not is_corner else 1}", title="IC Section Logic")
                            if min_val <= b <= max_val and rm2 != rm1:
                                cut_dim_b = f"{cut_dim1},{cut_dim2}" if is_corner else cut_dim1
                                raw_materials.append({"code": rm2, "dimension": cut_dim_b, "remark": remark, "quantity": 2 if not is_corner else 1})
                                frappe.log_error(message=f"IC {'Corner' if is_corner else 'Straight'}: B={b} in range {min_val}-{max_val}, using RM2={rm2}, Cut={cut_dim_b}", title="IC Section Logic")
                            break
            side_rail_qty = 1 if fg_code_part in ["SCY", "SCZ"] else 2
            side_rail_dim = f"{a-15}" if any(rm["code"].endswith("IC") or rm["code"].endswith("SL") for rm in raw_materials) else f"{a-12}"
            if fg_code_part not in ["IC", "ICB", "ICT", "ICX"]:
                child_parts.append({"code": "SIDE RAIL", "dimension": side_rail_dim, "remark": "CHILD PART", "quantity": side_rail_qty})
                raw_materials.append({"code": "SIDE RAIL", "dimension": side_rail_dim, "remark": "CHILD PART", "quantity": side_rail_qty})
            stiff_qty = 8 if fg_code_part in ["CC", "CCL", "CCR", "IC", "ICB", "LS", "LSL", "LSR", "LSW", "SL", "SLR"] else 5 if fg_code_part in ["ICT", "ICX"] else 4
            stiff_dim = f"{a-15}X{b-15}X4" if any(rm["code"].endswith("IC") or rm["code"].endswith("SL") for rm in raw_materials) else f"{a-12}X{b-12}X4"
            child_parts.append({"code": "STIFF PLATE", "dimension": stiff_dim, "remark": "CHILD PART", "quantity": stiff_qty})
            raw_materials.append({"code": "STIFF PLATE", "dimension": stiff_dim, "remark": "CHILD PART", "quantity": stiff_qty})
            if fg_code_part in ["IC", "ICB"]:
                child_parts.append({"code": "OUTER CAP", "dimension": f"{a}X{b}X4", "remark": "CHILD PART", "quantity": 1})
                raw_materials.append({"code": "OUTER CAP", "dimension": f"{a}X{b}X4", "remark": "CHILD PART", "quantity": 1})
            elif fg_code_part in ["ICT", "ICX"]:
                child_parts.append({"code": "OUTER CAP", "dimension": f"{a}X{b}X4", "remark": "CHILD PART", "quantity": 2})
                raw_materials.append({"code": "OUTER CAP", "dimension": f"{a}X{b}X4", "remark": "CHILD PART", "quantity": 2})
            elif fg_code_part in ["SCY", "SCZ"]:
                outer_cap_dim = f"{b/math.sin(math.radians(45))}X{a}X4"
                child_parts.append({"code": "OUTER CAP", "dimension": outer_cap_dim, "remark": "CHILD PART", "quantity": 1})
                raw_materials.append({"code": "OUTER CAP", "dimension": outer_cap_dim, "remark": "CHILD PART", "quantity": 1})

        elif fg_code_part in j_straight or fg_code_part in j_corner:
            is_corner = fg_code_part in j_corner
            cut_dim1, cut_dim2 = str(l1), str(l2) if l2 else "-"
            if fg_code_part in ["JLT", "JRT", "JLX", "JRX"]:
                cut_dim1 = f"{l1-8}"
            elif fg_code_part in ["JL", "JLB", "JLT", "JLX", "JR", "JRB", "JRT", "JRX"]:
                cut_dim1 = f"{l1-4}"
            for (min_a, max_a), (rm1, rm2, remark) in j_sections.items():
                if min_a <= a <= max_a:
                    cut_dim = f"{cut_dim1},{cut_dim2}" if is_corner else cut_dim1
                    if rm1 == "AL SHEET" and not is_corner:
                        cut_dim = f"{a+65}X{l1}X4"
                    elif rm1 == "AL SHEET" and is_corner:
                        cut_dim = f"{a+65}X{l1}X4,{a+65}X{l2}X4"
                    raw_materials.append({"code": rm1, "dimension": cut_dim, "remark": remark, "quantity": 1})
                    frappe.log_error(message=f"J {'Corner' if is_corner else 'Straight'}: A={a} in range {min_a}-{max_a}, using RM1={rm1}, Cut={cut_dim}", title="J Section Logic")
                    break
            if a >= 51:
                for (min_b, max_b), (rm2, remark) in j_l_sections.items():
                    if min_b <= b <= max_b:
                        cut_dim = f"{cut_dim1},{cut_dim2}" if is_corner else cut_dim1
                        raw_materials.append({"code": rm2, "dimension": cut_dim, "remark": remark, "quantity": 1})
                        frappe.log_error(message=f"J {'Corner' if is_corner else 'Straight'}: B={b} in range {min_b}-{max_b}, using RM2={rm2}, Cut={cut_dim}", title="J Section Logic")
                        break
            if fg_code_part in ["SX", "SXC", "SXCE"]:
                side_rail_dim = f"{b-16}" if any(rm["code"] == "J SEC" for rm in raw_materials) else f"{b-12}"
                stiff_qty = 5 if fg_code_part == "SX" else 2
                child_parts.append({"code": "SIDE RAIL", "dimension": side_rail_dim, "remark": "CHILD PART", "quantity": 2})
                raw_materials.append({"code": "SIDE RAIL", "dimension": side_rail_dim, "remark": "CHILD PART", "quantity": 2})
                stiff_dim = f"{a-16}X{b-16}X4" if any(rm["code"] == "J SEC" for rm in raw_materials) else f"{a-12}X{b-12}X4"
                child_parts.append({"code": "STIFF PLATE", "dimension": stiff_dim, "remark": "CHILD PART", "quantity": stiff_qty})
                raw_materials.append({"code": "STIFF PLATE", "dimension": stiff_dim, "remark": "CHILD PART", "quantity": stiff_qty})
            if fg_code_part in ["JL", "JLB", "JLT", "JLX", "JR", "JRB", "JRT", "JRX"]:
                outer_cap_qty = 2 if fg_code_part in ["JLT", "JRT", "JLX", "JRX"] else 1
                stiff_qty = 2 if fg_code_part in ["JLT", "JRT", "JLX", "JRX"] else 6
                stiff_dim = f"{a-16}X{b-16}X4" if any(rm["code"] == "J SEC" for rm in raw_materials) else f"{a-12}X{b-12}X4"
                child_parts.append({"code": "OUTER CAP", "dimension": f"{a}X{b}X4", "remark": "CHILD PART", "quantity": outer_cap_qty})
                raw_materials.append({"code": "OUTER CAP", "dimension": f"{a}X{b}X4", "remark": "CHILD PART", "quantity": outer_cap_qty})
                child_parts.append({"code": "STIFF PLATE", "dimension": stiff_dim, "remark": "CHILD PART", "quantity": stiff_qty})
                raw_materials.append({"code": "STIFF PLATE", "dimension": stiff_dim, "remark": "CHILD PART", "quantity": stiff_qty})

        elif fg_code_part in t_straight:
            cut_dim = str(l1)
            if fg_code_part in ["WRBSE", "WRSE"] and not degree_cutting:
                cut_dim = f"{l1-50}"
            for key, (rm1, rm2, rm3, remark) in t_sections.items():
                if isinstance(key, tuple) and len(key) == 2:
                    if key[0] <= a <= key[1]:
                        raw_materials.append({"code": rm1, "dimension": cut_dim, "remark": remark, "quantity": 2 if rm1 == "115 T" else 1})
                        frappe.log_error(message=f"T Straight: A={a} in range {key[0]}-{key[1]}, using RM1={rm1}, Cut={cut_dim}, QTY={2 if rm1 == '115 T' else 1}", title="T Section Logic")
                        if rm2 != "-":
                            raw_materials.append({"code": rm2, "dimension": cut_dim, "remark": remark, "quantity": 1})
                        if rm3 != "-":
                            raw_materials.append({"code": rm3, "dimension": cut_dim, "remark": remark, "quantity": 2 if rm3 == "EC" else 1})
                        break
                elif isinstance(key, tuple) and len(key) == 1:
                    if a == key[0]:
                        raw_materials.append({"code": rm1, "dimension": cut_dim, "remark": remark, "quantity": 1})
                        frappe.log_error(message=f"T Straight: A={a} exact match, using RM1={rm1}, Cut={cut_dim}", title="T Section Logic")
                        if rm2 != "-":
                            raw_materials.append({"code": rm2, "dimension": cut_dim, "remark": remark, "quantity": 2 if rm2 == "EC" else 1})
                        if rm3 != "-":
                            raw_materials.append({"code": rm3, "dimension": cut_dim, "remark": remark, "quantity": 2 if rm3 == "EC" else 1})
                        break
            side_rail_qty = 1 if degree_cutting and fg_code_part in ["WRBSE", "WRSE"] else 2
            side_rail_dim = f"{a-1}" if any(rm["code"].endswith("T") for rm in raw_materials) else f"{a-16}"
            if fg_code_part in ["TSE", "WRBSE", "WRSE"]:
                side_rail_dim = f"{a-146}" if any(rm["code"].endswith("T") or rm["code"].endswith("CH") for rm in raw_materials) else f"{a-146}"
            child_parts.append({"code": "SIDE RAIL", "dimension": side_rail_dim, "remark": "CHILD PART", "quantity": side_rail_qty})
            raw_materials.append({"code": "SIDE RAIL", "dimension": side_rail_dim, "remark": "CHILD PART", "quantity": side_rail_qty})
            if fg_code_part in ["WRBSE", "WRSE"] and not degree_cutting:
                child_parts.append({"code": "RK-50", "dimension": f"{a-130}", "remark": "CHILD PART", "quantity": 1})
                raw_materials.append({"code": "RK-50", "dimension": f"{a-130}", "remark": "CHILD PART", "quantity": 1})
            if fg_code_part in ["TSE", "WRBSE", "WRSE", "WSE", "WXSE"]:
                stiff_dim = side_rail_dim
                u_stiff_qty = 5 if fg_code_part == "TSE" else 8
                child_parts.append({"code": "U STIFFNER", "dimension": stiff_dim, "remark": "CHILD PART", "quantity": u_stiff_qty})
                raw_materials.append({"code": "U STIFFNER", "dimension": stiff_dim, "remark": "CHILD PART", "quantity": u_stiff_qty})
            if fg_code_part in ["WRBSE", "WRSE", "WSE", "WXSE"]:
                child_parts.append({"code": "H STIFFNER", "dimension": side_rail_dim, "remark": "CHILD PART", "quantity": 2})
                raw_materials.append({"code": "H STIFFNER", "dimension": side_rail_dim, "remark": "CHILD PART", "quantity": 2})
            if fg_code_part in ["PCE", "SBE"]:
                child_parts.append({"code": "I STIFFNER", "dimension": side_rail_dim, "remark": "CHILD PART", "quantity": 8})
                raw_materials.append({"code": "I STIFFNER", "dimension": side_rail_dim, "remark": "CHILD PART", "quantity": 8})

        elif fg_code_part in misc_straight:
            key = (a, fg_code_part) if fg_code_part in ["EB", "MB", "DP", "RK"] else (a,)
            cut_dim = f"{l1+100}" if fg_code_part == "MB" else str(l1)
            if key in misc_sections:
                rm1, rm2, remark = misc_sections[key]
                raw_materials.append({"code": rm1, "dimension": cut_dim, "remark": remark, "quantity": 1})
                frappe.log_error(message=f"Misc Straight: A={a}, FG={fg_code_part}, using RM1={rm1}, Cut={cut_dim}", title="Misc Section Logic")
                if rm2 != "-":
                    raw_materials.append({"code": rm2, "dimension": cut_dim, "remark": remark, "quantity": 1})
            elif fg_code_part == "RK" and a != 50:
                for (min_a, max_a), (rm1, rm2, remark) in ic_l_sections.items():
                    if min_a <= a <= max_a:
                        raw_materials.append({"code": rm1, "dimension": cut_dim, "remark": "L SECTION FOR RK ODD SIZE", "quantity": 1})
                        frappe.log_error(message=f"Misc Straight: RK with A={a} not 50, using RM1={rm1}, Cut={cut_dim}", title="Misc Section Logic")
                        break
            if fg_code_part == "DP":
                child_parts.append({"code": "ROUND PIPE", "dimension": "196", "remark": "CHILD PART", "quantity": 1})
                raw_materials.append({"code": "ROUND PIPE", "dimension": "196", "remark": "CHILD PART", "quantity": 1})
                if a == 150:
                    child_parts.append({"code": "SQUARE PLATE", "dimension": "150X150X4", "remark": "CHILD PART", "quantity": 1})
                    raw_materials.append({"code": "SQUARE PLATE", "dimension": "150X150X4", "remark": "CHILD PART", "quantity": 1})
            if fg_code_part in ["EB", "MB"] and a == 150:
                child_parts.append({"code": "SUPPORT PIPE", "dimension": "105", "remark": "CHILD PART", "quantity": 1})
                raw_materials.append({"code": "SUPPORT PIPE", "dimension": "105", "remark": "CHILD PART", "quantity": 1})

        else:
            frappe.log_error(message=f"Skipping invalid FG Code: {fg_code_part}, Full Code: {fg_code}", title="FG Raw Material Error")
            return []

        frappe.log_error(message=f"Child Parts for FG Code {fg_code_part}: {json.dumps(child_parts, indent=2)}", title="Child Parts Debug")

        return raw_materials

@frappe.whitelist()
def process_fg_codes_background(docname):
    doc = frappe.get_doc("FG Raw Material Selector", docname)
    doc.process_fg_codes()


@frappe.whitelist()
def get_raw_materials(project_design_upload=None):
    try:
        if not project_design_upload:
            frappe.throw(_("No Project Design Uploads provided."))

        pdu_list = []

        # Step 1: Parse input from string or list
        if isinstance(project_design_upload, str):
            try:
                pdu_data = json.loads(project_design_upload)
                if isinstance(pdu_data, list):
                    # Handle list of dicts or strings
                    for entry in pdu_data:
                        if isinstance(entry, dict):
                            value = entry.get("project_design_upload") or entry.get("value") or entry.get("name")
                            if value:
                                pdu_list.append(value)
                        elif isinstance(entry, str):
                            pdu_list.append(entry)
                elif isinstance(pdu_data, dict):
                    value = pdu_data.get("project_design_upload") or pdu_data.get("value") or pdu_data.get("name")
                    if value:
                        pdu_list.append(value)
                elif isinstance(pdu_data, str):
                    pdu_list = [pdu_data]
                else:
                    frappe.throw(_("Invalid Project Design Upload format."))
            except json.JSONDecodeError:
                # If not valid JSON, treat as single raw name
                pdu_list = [project_design_upload]
        elif isinstance(project_design_upload, list):
            for pdu in project_design_upload:
                if isinstance(pdu, str):
                    pdu_list.append(pdu)
        else:
            frappe.throw(_("Invalid Project Design Upload format."))

        # Step 2: Ensure clean list of names
        pdu_list = [pdu for pdu in pdu_list if pdu]
        if not pdu_list:
            frappe.throw(_("No valid Project Design Uploads found."))

        # Step 3: Create new document
        doc = frappe.new_doc("FG Raw Material Selector")

        # ✅ Correctly append to child table field
        doc.set("project_design_upload", [])
        for pdu in pdu_list:
            doc.append("project_design_upload", {"project_design_upload": pdu})

        # Save the doc (triggers .is_new() safely)
        doc.save()

        # Step 4: Enqueue background processing
        job_id = frappe.enqueue(
            'sb.sb.doctype.fg_raw_material_selector.fg_raw_material_selector.process_fg_codes_background',
            queue='long',
            timeout=3600,
            docname=doc.name
        )

        # Step 5: Notify user
        frappe.msgprint(_("Raw material processing has been queued (Job ID: {0}). You will be notified once completed.").format(job_id))
        return []

    except Exception as e:
        frappe.log_error(message=f"Error in get_raw_materials: {str(e)}", title="FG Raw Material Error")
        frappe.throw(_("Failed to fetch raw materials: {0}").format(str(e)))
import frappe
import json
from frappe import _

@frappe.whitelist()
def get_raw_materials(project_design_upload=None):
    try:
        if not project_design_upload:
            frappe.throw(_("No Project Design Uploads provided."))

        pdu_list = []

        # Step 1: Parse input from string or list
        if isinstance(project_design_upload, str):
            try:
                pdu_data = json.loads(project_design_upload)
                if isinstance(pdu_data, list):
                    # Handle list of dicts or strings
                    for entry in pdu_data:
                        if isinstance(entry, dict):
                            value = entry.get("project_design_upload") or entry.get("value") or entry.get("name")
                            if value:
                                pdu_list.append(value)
                        elif isinstance(entry, str):
                            pdu_list.append(entry)
                elif isinstance(pdu_data, dict):
                    value = pdu_data.get("project_design_upload") or pdu_data.get("value") or pdu_data.get("name")
                    if value:
                        pdu_list.append(value)
                elif isinstance(pdu_data, str):
                    pdu_list = [pdu_data]
                else:
                    frappe.throw(_("Invalid Project Design Upload format."))
            except json.JSONDecodeError:
                # If not valid JSON, treat as single raw name
                pdu_list = [project_design_upload]
        elif isinstance(project_design_upload, list):
            for pdu in project_design_upload:
                if isinstance(pdu, str):
                    pdu_list.append(pdu)
        else:
            frappe.throw(_("Invalid Project Design Upload format."))

        # Step 2: Ensure clean list of names
        pdu_list = [pdu for pdu in pdu_list if pdu]
        if not pdu_list:
            frappe.throw(_("No valid Project Design Uploads found."))

        # Step 3: Create new document
        doc = frappe.new_doc("FG Raw Material Selector")

        # ✅ Correctly append to child table field
        doc.set("project_design_upload", [])
        for pdu in pdu_list:
            doc.append("project_design_upload", {"project_design_upload": pdu})

        # Save the doc (triggers .is_new() safely)
        doc.save()

        # Step 4: Enqueue background processing
        job_id = frappe.enqueue(
            'sb.sb.doctype.fg_raw_material_selector.fg_raw_material_selector.process_fg_codes_background',
            queue='long',
            timeout=3600,
            docname=doc.name
        )

        # Step 5: Notify user
        frappe.msgprint(_("Raw material processing has been queued (Job ID: {0}). You will be notified once completed.").format(job_id))
        return []

    except Exception as e:
        frappe.log_error(message=f"Error in get_raw_materials: {str(e)}", title="FG Raw Material Error")
        frappe.throw(_("Failed to fetch raw materials: {0}").format(str(e)))
import frappe
import json
from frappe import _

@frappe.whitelist()
def get_raw_materials(project_design_upload=None):
    try:
        if not project_design_upload:
            frappe.throw(_("No Project Design Uploads provided."))

        pdu_list = []

        # Step 1: Parse input from string or list
        if isinstance(project_design_upload, str):
            try:
                pdu_data = json.loads(project_design_upload)
                if isinstance(pdu_data, list):
                    # Handle list of dicts or strings
                    for entry in pdu_data:
                        if isinstance(entry, dict):
                            value = entry.get("project_design_upload") or entry.get("value") or entry.get("name")
                            if value:
                                pdu_list.append(value)
                        elif isinstance(entry, str):
                            pdu_list.append(entry)
                elif isinstance(pdu_data, dict):
                    value = pdu_data.get("project_design_upload") or pdu_data.get("value") or pdu_data.get("name")
                    if value:
                        pdu_list.append(value)
                elif isinstance(pdu_data, str):
                    pdu_list = [pdu_data]
                else:
                    frappe.throw(_("Invalid Project Design Upload format."))
            except json.JSONDecodeError:
                # If not valid JSON, treat as single raw name
                pdu_list = [project_design_upload]
        elif isinstance(project_design_upload, list):
            for pdu in project_design_upload:
                if isinstance(pdu, str):
                    pdu_list.append(pdu)
        else:
            frappe.throw(_("Invalid Project Design Upload format."))

        # Step 2: Ensure clean list of names
        pdu_list = [pdu for pdu in pdu_list if pdu]
        if not pdu_list:
            frappe.throw(_("No valid Project Design Uploads found."))

        # Step 3: Create new document
        doc = frappe.new_doc("FG Raw Material Selector")

        # ✅ Correctly append to child table field
        doc.set("project_design_upload", [])
        for pdu in pdu_list:
            doc.append("project_design_upload", {"project_design_upload": pdu})

        # Save the doc (triggers .is_new() safely)
        doc.save()

        # Step 4: Enqueue background processing
        job_id = frappe.enqueue(
            'sb.sb.doctype.fg_raw_material_selector.fg_raw_material_selector.process_fg_codes_background',
            queue='long',
            timeout=3600,
            docname=doc.name
        )

        # Step 5: Notify user
        frappe.msgprint(_("Raw material processing has been queued (Job ID: {0}). You will be notified once completed.").format(job_id))
        return []

    except Exception as e:
        frappe.log_error(message=f"Error in get_raw_materials: {str(e)}", title="FG Raw Material Error")
        frappe.throw(_("Failed to fetch raw materials: {0}").format(str(e)))
import frappe
import json
from frappe import _

@frappe.whitelist()
def get_raw_materials(project_design_upload=None):
    try:
        if not project_design_upload:
            frappe.throw(_("No Project Design Uploads provided."))

        pdu_list = []

        # Step 1: Parse input from string or list
        if isinstance(project_design_upload, str):
            try:
                pdu_data = json.loads(project_design_upload)
                if isinstance(pdu_data, list):
                    # Handle list of dicts or strings
                    for entry in pdu_data:
                        if isinstance(entry, dict):
                            value = entry.get("project_design_upload") or entry.get("value") or entry.get("name")
                            if value:
                                pdu_list.append(value)
                        elif isinstance(entry, str):
                            pdu_list.append(entry)
                elif isinstance(pdu_data, dict):
                    value = pdu_data.get("project_design_upload") or pdu_data.get("value") or pdu_data.get("name")
                    if value:
                        pdu_list.append(value)
                elif isinstance(pdu_data, str):
                    pdu_list = [pdu_data]
                else:
                    frappe.throw(_("Invalid Project Design Upload format."))
            except json.JSONDecodeError:
                # If not valid JSON, treat as single raw name
                pdu_list = [project_design_upload]
        elif isinstance(project_design_upload, list):
            for pdu in project_design_upload:
                if isinstance(pdu, str):
                    pdu_list.append(pdu)
        else:
            frappe.throw(_("Invalid Project Design Upload format."))

        # Step 2: Ensure clean list of names
        pdu_list = [pdu for pdu in pdu_list if pdu]
        if not pdu_list:
            frappe.throw(_("No valid Project Design Uploads found."))

        # Step 3: Create new document
        doc = frappe.new_doc("FG Raw Material Selector")

        # ✅ Correctly append to child table field
        doc.set("project_design_upload", [])
        for pdu in pdu_list:
            doc.append("project_design_upload", {"project_design_upload": pdu})

        # Save the doc (triggers .is_new() safely)
        doc.save()

        # Step 4: Enqueue background processing
        job_id = frappe.enqueue(
            'sb.sb.doctype.fg_raw_material_selector.fg_raw_material_selector.process_fg_codes_background',
            queue='long',
            timeout=3600,
            docname=doc.name
        )

        # Step 5: Notify user
        frappe.msgprint(_("Raw material processing has been queued (Job ID: {0}). You will be notified once completed.").format(job_id))
        return []

    except Exception as e:
        frappe.log_error(message=f"Error in get_raw_materials: {str(e)}", title="FG Raw Material Error")
        frappe.throw(_("Failed to fetch raw materials: {0}").format(str(e)))
import frappe
import json
from frappe import _

@frappe.whitelist()
def get_raw_materials(project_design_upload=None):
    try:
        if not project_design_upload:
            frappe.throw(_("No Project Design Uploads provided."))

        pdu_list = []

        # Step 1: Parse input from string or list
        if isinstance(project_design_upload, str):
            try:
                pdu_data = json.loads(project_design_upload)
                if isinstance(pdu_data, list):
                    # Handle list of dicts or strings
                    for entry in pdu_data:
                        if isinstance(entry, dict):
                            value = entry.get("project_design_upload") or entry.get("value") or entry.get("name")
                            if value:
                                pdu_list.append(value)
                        elif isinstance(entry, str):
                            pdu_list.append(entry)
                elif isinstance(pdu_data, dict):
                    value = pdu_data.get("project_design_upload") or pdu_data.get("value") or pdu_data.get("name")
                    if value:
                        pdu_list.append(value)
                elif isinstance(pdu_data, str):
                    pdu_list = [pdu_data]
                else:
                    frappe.throw(_("Invalid Project Design Upload format."))
            except json.JSONDecodeError:
                # If not valid JSON, treat as single raw name
                pdu_list = [project_design_upload]
        elif isinstance(project_design_upload, list):
            for pdu in project_design_upload:
                if isinstance(pdu, str):
                    pdu_list.append(pdu)
        else:
            frappe.throw(_("Invalid Project Design Upload format."))

        # Step 2: Ensure clean list of names
        pdu_list = [pdu for pdu in pdu_list if pdu]
        if not pdu_list:
            frappe.throw(_("No valid Project Design Uploads found."))

        # Step 3: Create new document
        doc = frappe.new_doc("FG Raw Material Selector")

        # ✅ Correctly append to child table field
        doc.set("project_design_upload", [])
        for pdu in pdu_list:
            doc.append("project_design_upload", {"project_design_upload": pdu})

        # Save the doc (triggers .is_new() safely)
        doc.save()

        # Step 4: Enqueue background processing
        job_id = frappe.enqueue(
            'sb.sb.doctype.fg_raw_material_selector.fg_raw_material_selector.process_fg_codes_background',
            queue='long',
            timeout=3600,
            docname=doc.name
        )

        # Step 5: Notify user
        frappe.msgprint(_("Raw material processing has been queued (Job ID: {0}). You will be notified once completed.").format(job_id))
        return []

    except Exception as e:
        frappe.log_error(message=f"Error in get_raw_materials: {str(e)}", title="FG Raw Material Error")
        frappe.throw(_("Failed to fetch raw materials: {0}").format(str(e)))
import frappe
import json
from frappe import _

@frappe.whitelist()
def get_raw_materials(project_design_upload=None):
    try:
        if not project_design_upload:
            frappe.throw(_("No Project Design Uploads provided."))

        pdu_list = []

        # Step 1: Parse input from string or list
        if isinstance(project_design_upload, str):
            try:
                pdu_data = json.loads(project_design_upload)
                if isinstance(pdu_data, list):
                    # Handle list of dicts or strings
                    for entry in pdu_data:
                        if isinstance(entry, dict):
                            value = entry.get("project_design_upload") or entry.get("value") or entry.get("name")
                            if value:
                                pdu_list.append(value)
                        elif isinstance(entry, str):
                            pdu_list.append(entry)
                elif isinstance(pdu_data, dict):
                    value = pdu_data.get("project_design_upload") or pdu_data.get("value") or pdu_data.get("name")
                    if value:
                        pdu_list.append(value)
                elif isinstance(pdu_data, str):
                    pdu_list = [pdu_data]
                else:
                    frappe.throw(_("Invalid Project Design Upload format."))
            except json.JSONDecodeError:
                # If not valid JSON, treat as single raw name
                pdu_list = [project_design_upload]
        elif isinstance(project_design_upload, list):
            for pdu in project_design_upload:
                if isinstance(pdu, str):
                    pdu_list.append(pdu)
        else:
            frappe.throw(_("Invalid Project Design Upload format."))

        # Step 2: Ensure clean list of names
        pdu_list = [pdu for pdu in pdu_list if pdu]
        if not pdu_list:
            frappe.throw(_("No valid Project Design Uploads found."))

        # Step 3: Create new document
        doc = frappe.new_doc("FG Raw Material Selector")

        # ✅ Correctly append to child table field
        doc.set("project_design_upload", [])
        for pdu in pdu_list:
            doc.append("project_design_upload", {"project_design_upload": pdu})

        # Save the doc (triggers .is_new() safely)
        doc.save()

        # Step 4: Enqueue background processing
        job_id = frappe.enqueue(
            'sb.sb.doctype.fg_raw_material_selector.fg_raw_material_selector.process_fg_codes_background',
            queue='long',
            timeout=3600,
            docname=doc.name
        )

        # Step 5: Notify user
        frappe.msgprint(_("Raw material processing has been queued (Job ID: {0}). You will be notified once completed.").format(job_id))
        return []

    except Exception as e:
        frappe.log_error(message=f"Error in get_raw_materials: {str(e)}", title="FG Raw Material Error")
        frappe.throw(_("Failed to fetch raw materials: {0}").format(str(e)))

@frappe.whitelist()
def create_bom_from_fg_selector(fg_selector_name, fg_code=None, project_design_upload=None):
    try:
        fg_doc = frappe.get_doc("FG Raw Material Selector", fg_selector_name)
        bom = frappe.new_doc("BOM")
        bom.item = fg_code.split('|')[2] if fg_code else fg_doc.raw_materials[0].fg_code.split('|')[2] if fg_doc.raw_materials else ""
        for rm in fg_doc.raw_materials:
            if fg_code and rm.fg_code != fg_code:
                continue
            if project_design_upload and rm.project_design_upload != project_design_upload:
                continue
            bom.append("items", {
                "item_code": rm.item_code,
                "qty": rm.quantity,
                "uom": rm.uom if rm.uom else "Nos"
            })
        bom.save()
        return bom.name
    except Exception as e:
        frappe.log_error(message=f"Error creating BOM: {str(e)}", title="FG Raw Material Error")
        frappe.throw(f"Failed to create BOM: {str(e)}")

from frappe.utils import flt

@frappe.whitelist()
def reserve_stock(fg_selector_name):
    warehouses_to_check = ["Off-Cut - VD", "Raw Material - VD"]

    doc = frappe.get_doc("FG Raw Material Selector", fg_selector_name)

    stock_map = {}
    reserved_warehouse = {}

    for row in doc.raw_materials:
        item_code = row.item_code
        uom = row.uom

        if item_code in stock_map:
            continue

        for wh in warehouses_to_check:
            qty = get_actual_qty(item_code, wh, uom)
            if qty > 0:
                stock_map[item_code] = qty
                reserved_warehouse[item_code] = wh
                break
        else:
            stock_map[item_code] = 0
            reserved_warehouse[item_code] = ""

    for row in doc.raw_materials:
        item_code = row.item_code
        required_qty = flt(row.quantity)
        available_qty = flt(stock_map.get(item_code, 0))
        reserved_wh = reserved_warehouse.get(item_code, "")

        row.db_set("available_quantity", available_qty)

        if available_qty >= required_qty:
            stock_map[item_code] -= required_qty
            row.db_set("status", "IS")
            row.db_set("reserve_tag", 1)
            row.db_set("warehouse", reserved_wh)
        else:
            row.db_set("status", "NIS")
            row.db_set("reserve_tag", 0)
            row.db_set("warehouse", "")

    return {
        "status": "success",
        "message": "Stock reserved and warehouse recorded.",
        "data": [
            {
                "item_code": row.item_code,
                "status": row.status,
                "reserve_tag": row.reserve_tag,
                "warehouse": row.warehouse,
                "available_quantity": row.available_quantity
            }
            for row in doc.raw_materials
        ]
    }

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

@frappe.whitelist()
def clear_reservation(fg_selector_name):
    doc = frappe.get_doc("FG Raw Material Selector", fg_selector_name)

    for row in doc.raw_materials:
        row.db_set("status", "")
        row.db_set("reserve_tag", 0)
        row.db_set("warehouse", "")
        row.db_set("available_quantity", 0)

    return {
        "status": "success",
        "message": f"Reservation cleared for {fg_selector_name}"
    }

@frappe.whitelist()
def get_fg_components_for_merge(project_design_upload):
    if not project_design_upload:
        return []

    pdu_list = [project_design_upload] if isinstance(project_design_upload, str) else project_design_upload
    if not pdu_list or not all(isinstance(pdu, str) for pdu in pdu_list):
        frappe.log_error(message=f"Invalid project_design_upload format: {project_design_upload}", title="FG Components Error")
        return []

    return frappe.get_all(
        "FG Components",
        filters={"parent": ["in", pdu_list], "parenttype": "Project Design Upload"},
        fields=[
            "fg_code", "a", "client_area", "room_no", "flat_no", "b", "code",
            "l1", "l2", "u_area", "sb_area", "dwg_no", "quantity", "ipo_name"
        ],
        ignore_permissions=True
    )

