# fg_raw_material_selector.py
# Copyright (c) 2025
# For license information, see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
import json
from frappe.utils.background_jobs import enqueue
from frappe.utils import flt

class FGRawMaterialSelector(Document):
    def validate(self):
        frappe.log_error(
            message=f"Validating FG Raw Material Selector: {self.name}",
            title="FG Validation Debug"
        )
        pass

    def process_fg_codes(self):
        try:
            frappe.log_error(
                message=f"Starting process_fg_codes for document: {self.name}",
                title="FG Process Debug"
            )

            # Collect Planning BOM names from planning_bom child table
            pbom_names = [row.get("planning_bom") for row in self.planning_bom if row.get("planning_bom")]
            frappe.log_error(
                message=f"Processing Planning BOMs: {json.dumps(pbom_names, indent=2)}",
                title="FG Process Debug"
            )

            # if not self.planning_bom or not isinstance(self.planning_bom, list):
            #     frappe.log_error(
            #         message="No Planning BOMs selected or invalid format.",
            #         title="FG Raw Material Error"
            #     )
            #     frappe.throw("No Planning BOMs selected or invalid format.")

            output = []

            valid_fg_codes = (
                ["B", "CP", "CPP", "CPPP", "D", "K", "PC", "PH", "PLB", "SB",
                 "T", "TS", "W", "WR", "WRB", "WRS", "WS", "WX", "WXS"] +
                ["BC", "BCE", "KC", "KCE", "BCY", "KCY", "BCZ", "KCZ"] +
                ["CC", "CCL", "CCR", "IC", "ICB", "ICXB", "ICT", "ICX",
                 "LS", "LSK", "LSL", "LSR", "LSW", "SL", "SLR"] +
                ["SC", "SCE", "SCY", "SCZ", "LSC", "LSCE", "LSCK", "LSCEK", "LSCY", "LSCZ"] +
                ["JL", "JLB", "JLT", "JLX", "JR", "JRB", "JRT", "JRX",
                 "SX", "LSX", "LSXK"] +
                ["SXC", "SXCE", "SXCY", "SXCZ", "LSXC", "LSXCE", "LSXCK", "LSXCEK"] +
                ["PCE", "SBE", "TSE", "WRBSE", "WRSE", "WSE", "WXSE"] +
                ["DP", "EB", "MB", "EC", "ECH", "ECT", "ECX", "ECB",
                 "ECK", "RK"]
            )

            batch_size = 100
            fg_codes_all = []

            for pbom_entry in self.planning_bom:
                pbom_name = pbom_entry.get("planning_bom")
                if not pbom_name or not isinstance(pbom_name, str):
                    frappe.log_error(
                        message=f"Invalid Planning BOM name: {pbom_name}",
                        title="FG Raw Material Error"
                    )
                    continue

                try:
                    pbom_doc = frappe.get_doc("Planning BOM", pbom_name)
                    frappe.log_error(
                        message=f"Fetched Planning BOM: {pbom_name}",
                        title="FG Process Debug"
                    )
                except frappe.DoesNotExistError:
                    frappe.log_error(
                        message=f"Planning BOM {pbom_name} not found",
                        title="FG Raw Material Error"
                    )
                    continue

                pbom_project = pbom_doc.get("project")
                pbom_items = pbom_doc.get("items", [])

                pbom_items_serializable = [
                    {
                        "fg_code": fg.get("fg_code"),
                        "quantity": fg.get("quantity"),
                        "uom": fg.get("uom"),
                        "ipo_name": fg.get("ipo_name"),
                        "a": fg.get("a"),
                        "b": fg.get("b"),
                        "code": fg.get("code"),
                        "l1": fg.get("l1"),
                        "l2": fg.get("l2"),
                        "u_area": fg.get("u_area")
                    } for fg in pbom_items
                ]
                frappe.log_error(
                    message=f"FG Codes for PBOM {pbom_name}: {json.dumps(pbom_items_serializable, indent=2)}",
                    title="FG Process Debug"
                )

                if not pbom_items:
                    frappe.msgprint(f"No FG Components found for Planning BOM: {pbom_name}")
                    frappe.log_error(
                        message=f"No FG Components found for Planning BOM: {pbom_name}",
                        title="FG Raw Material Error"
                    )
                    continue

                fg_codes_all.extend([(fg_component, pbom_project, pbom_name) for fg_component in pbom_items])

            if fg_codes_all:
                self.raw_materials = []
                frappe.log_error(
                    message="Cleared existing raw_materials table.",
                    title="FG Process Debug"
                )
            else:
                frappe.log_error(
                    message="No FG codes to process. Skipping raw_materials clear.",
                    title="FG Process Debug"
                )

            # Process in batches
            for i in range(0, len(fg_codes_all), batch_size):
                batch = fg_codes_all[i:i + batch_size]
                for fg_component, pbom_project, pbom_name in batch:
                    fg_code = fg_component.get("fg_code")
                    component_quantity = fg_component.get("quantity", 1)
                    component_uom = fg_component.get("uom")
                    ipo_name = fg_component.get("ipo_name")
                    a = fg_component.get("a", 0)
                    b = fg_component.get("b", 0)
                    sec_code = fg_component.get("code", "")
                    l1 = fg_component.get("l1", 0)
                    l2 = fg_component.get("l2", 0)
                    bom_qty = fg_component.get("quantity", 0)
                    planning_bom_item_reference = fg_component.get("name")

                    if not fg_code or not isinstance(fg_code, str):
                        frappe.log_error(
                            message=f"Invalid FG Code in PBOM: {pbom_name}, FG Code: {fg_code}",
                            title="FG Raw Material Error"
                        )
                        continue

                    parts = fg_code.split('|')
                    if len(parts) != 5 or parts[2] not in valid_fg_codes:
                        frappe.log_error(
                            message=f"Skipping invalid FG Code: {fg_code} in PBOM: {pbom_name}",
                            title="FG Raw Material Error"
                        )
                        continue

                    try:
                        raw_materials = self.process_single_fg_code(fg_code)
                        frappe.log_error(
                            message=f"Processed FG Code {fg_code}: {json.dumps(raw_materials, indent=2)}",
                            title="FG Process Debug"
                        )
                        if not isinstance(raw_materials, list):
                            frappe.log_error(
                                message=f"Invalid data for FG Code '{fg_code}': {raw_materials}",
                                title="FG Raw Material Error"
                            )
                            continue
                    except Exception as e:
                        frappe.log_error(
                            message=f"Error processing FG Code '{fg_code}' in PBOM {pbom_name}: {str(e)}",
                            title="FG Raw Material Error"
                        )
                        continue

                    rm_table = []
                    for rm in raw_materials:
                        if not isinstance(rm, dict):
                            frappe.log_error(
                                message=f"Invalid raw material for FG Code '{fg_code}': {rm}",
                                title="FG Raw Material Error"
                            )
                            continue

                        rm_quantity = rm.get("quantity", 1) * component_quantity
                        rm_entry = {
                            "fg_code": fg_code,
                            "raw_material_code": rm.get("code"),
                            "item_code": rm.get("code"),
                            "a": a,
                            "b": b,
                            "code": sec_code,
                            "l1": l1,
                            "l2": l2,
                            "bom_qty": bom_qty,
                            "dimension": rm.get("dimension"),
                            "remark": rm.get("remark"),
                            "quantity": rm_quantity,
                            "project": pbom_project,
                            "ipo_name": ipo_name,
                            "planning_bom": pbom_name,
                            "status": rm.get("status"),
                            "warehouse": rm.get("warehouse"),
                            "planning_bom_item_reference": planning_bom_item_reference
                        }
                        if component_uom:
                            rm_entry["uom"] = component_uom

                        rm_table.append(rm_entry)

                        try:
                            self.append("raw_materials", rm_entry)
                            frappe.log_error(
                                message=f"Appended raw material for FG Code '{fg_code}': {json.dumps(rm_entry, indent=2)}",
                                title="FG Process Debug"
                            )
                        except Exception as e:
                            frappe.log_error(
                                message=f"Error appending raw material for FG Code '{fg_code}': {str(e)}",
                                title="FG Raw Material Error"
                            )
                            continue

                    output.append({
                        "fg_code": fg_code,
                        "planning_bom": pbom_name,
                        "raw_materials": rm_table
                    })

            if output:
                frappe.log_error(
                    message=f"Processing output: {json.dumps(output, indent=2)}",
                    title="FG Raw Material Output"
                )
            else:
                frappe.msgprint("No valid FG codes processed. Check the Error Log for details.")
                frappe.log_error(
                    message="No valid FG codes processed.",
                    title="FG Raw Material Error"
                )

            self.save()

            frappe.publish_realtime(
                event='fg_materials_done',
                message='FG Raw Material processing completed successfully.',
                user=frappe.session.user,
                docname=self.name
            )

        except Exception as e:
            frappe.log_error(
                message=f"Error in process_fg_codes: {str(e)}",
                title="FG Raw Material Error"
            )
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
            frappe.log_error(message=f"Processing FG Code: {fg_code}", title="FG Single Code Debug")
            parts = fg_code.split('|')
            if len(parts) != 5:
                frappe.log_error(message=f"Invalid FG Code format. Expected 5 parts, got {len(parts)}: {fg_code}", title="FG Raw Material Error")
                return []

            frappe.log_error(message=f"Server-Side Parts: {parts}", title="FG Single Code Debug")

            a = safe_int(parts[0])
            b = safe_int(parts[1]) if parts[1] else 0
            fg_code_part = parts[2]
            l1 = safe_int(parts[3])
            l2 = safe_int(parts[4]) if parts[4] else 0

            frappe.log_error(message=f"Parsed: A={a}, B={b}, FG_CODE={fg_code_part}, L1={l1}, L2={l2}", title="FG Single Code Debug")

        except Exception as e:
            frappe.log_error(message=f"Error parsing FG Code: {str(e)}", title="FG Raw Material Error")
            return []

        # Define FG groups
        ch_straight = ["B", "CP", "CPP", "CPPP", "D", "K", "PC", "PH", "PLB", "SB", "T", "TS", "W", "WR", "WRS", "WRB", "WS", "WX", "WXS"]
        ch_corner = ["BC", "BCE", "BCY", "KC", "KCE", "BCZ", "KCY", "KCZ"]
        ic_straight = ["CC", "CCL", "CCR", "IC", "ICB", "ICT", "ICX","ICXB","LSK", "LS", "LSL", "LSR", "LSW", "SL", "SLR"]
        ic_corner = ["SC", "SCE", "SCY", "SCZ", "LSC", "LSCE", "LSCK", "LSCEK", "LSCY", "LSCZ"]
        j_straight = ["JL", "JLB", "JLT", "JLX", "JR", "JRB", "JRT", "JRX", "SX", "LSX", "LSXK"]
        j_corner = ["SXC", "SXCE", "SXCY", "SXCZ", "LSXC", "LSXCE", "LSXCK", "LSXCEK"]
        t_straight = ["PCE", "SBE", "TSE", "WRBSE", "WRSE", "WSE", "WXSE"]
        misc_straight = ["DP", "EB", "MB", "EC", "ECH", "ECT", "ECX", "ECK", "ECB", "RK"]
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
            (125, 100, "SL"): ("125 SL", "-", "IC SECTION"),
            (100, 125, "SL"): ("125 SL", "-", "IC SECTION"),
            (125, 100, "CC"): ("125 SL", "-", "IC SECTION"),
            (100, 125, "CC"): ("125 SL", "-", "IC SECTION"),
            (125, 100, "CCR"): ("125 SL", "-", "IC SECTION"),
            (125, 100, "CCL"): ("125 SL", "-", "IC SECTION"),
            (125, 100): ("125 IC", "-", "IC SECTION"),
            (150, 100): ("150 IC", "-", "IC SECTION"),
            (100, 150): ("150 IC", "-", "IC SECTION") 
        }

        # L-section mappings for IC straight and corner
        ic_l_sections = {
            (50, 125): ("130 L", "130 L", "CH SECTION"),
            (126, 150): ("155 L", "155 L", "CH SECTION"),
            (151, 175): ("180 L", "180 L", "CH SECTION"),
            (176, 200): ("205 L", "205 L", "CH SECTION"),
            (201, 225): ("230 L", "230 L", "CH SECTION"),
            (226, 250): ("255 L", "255 L", "CH SECTION"),
            (251, 275): ("280 L", "280 L", "CH SECTION"),
            (276, 300): ("305 L", "305 L", "CH SECTION"),
            (301, 600): ("AL SHEET", "130 L", "IC SECTION"),
            (301, 600): ("AL SHEET", "155 L", "IC SECTION")
        }

        # L-section mappings for CH straight
        ch_l_sections_straight = {
            (51, 125): ("130 L", "MAIN FRAME", "CH SECTION"),
            (126, 149): ("155 L", "MAIN FRAME", "CH SECTION"),
            (151, 174): ("180 L", "MAIN FRAME", "CH SECTION"),
            (176, 199): ("205 L", "MAIN FRAME", "CH SECTION"),
            (201, 225): ("230 L", "MAIN FRAME", "CH SECTION"),
            (226, 249): ("255 L", "MAIN FRAME", "CH SECTION"),
            (251, 275): ("280 L", "MAIN FRAME", "CH SECTION"),
            (276, 300): ("305 L", "MAIN FRAME", "CH SECTION"),
            (301, 325): ("180 L", "155 L", "CH SECTION"),
            (326, 350): ("180 L", "180 L", "CH SECTION"),
            (351, 375): ("205 L", "180 L", "CH SECTION"),
            (376, 400): ("205 L", "205 L", "CH SECTION"),
            (401, 425): ("230 L", "205 L", "CH SECTION"),
            (426, 450): ("230 L", "230 L", "CH SECTION"),
            (451, 475): ("255 L", "230 L", "CH SECTION"),
            (476, 500): ("255 L", "255 L", "CH SECTION"),
            (501, 525): ("280 L", "255 L", "CH SECTION"),
            (526, 550): ("280 L", "280 L", "CH SECTION"),
            (551, 575): ("305 L", "280 L", "CH SECTION"),
            (576, 600): ("305 L", "305 L", "CH SECTION")
        }

        # L-section mappings for CH corner
        ch_l_sections_corner = {
            (51, 125): ("130 L", "MAIN FRAME", "CH SECTION CORNER"),
            (126, 149): ("155 L", "MAIN FRAME", "CH SECTION CORNER"),
            (151, 174): ("180 L", "MAIN FRAME", "CH SECTION CORNER"),
            (176, 199): ("205 L", "MAIN FRAME", "CH SECTION CORNER"),
            (201, 225): ("230 L", "MAIN FRAME", "CH SECTION CORNER"),
            (226, 249): ("255 L", "MAIN FRAME", "CH SECTION CORNER"),
            (251, 275): ("280 L", "MAIN FRAME", "CH SECTION CORNER"),
            (276, 300): ("305 L", "MAIN FRAME", "CH SECTION CORNER"),
            (301, 325): ("180 L", "155 L", "CH SECTION CORNER"),
            (326, 350): ("180 L", "180 L", "CH SECTION CORNER"),
            (351, 375): ("205 L", "180 L", "CH SECTION CORNER"),
            (376, 400): ("205 L", "205 L", "CH SECTION CORNER"),
            (401, 425): ("230 L", "205 L", "CH SECTION CORNER"),
            (426, 450): ("230 L", "230 L", "CH SECTION CORNER"),
            (451, 475): ("255 L", "230 L", "CH SECTION CORNER"),
            (476, 500): ("255 L", "255 L", "CH SECTION CORNER"),
            (501, 525): ("280 L", "255 L", "CH SECTION CORNER"),
            (526, 550): ("280 L", "280 L", "CH SECTION CORNER"),
            (551, 575): ("305 L", "280 L", "CH SECTION CORNER"),
            (576, 600): ("305 L", "305 L", "CH SECTION CORNER")
        }

        # J section mappings
        j_sections = {
            (25, 50): ("J SEC", "-", "J SECTION"),
            (25, 115): ("115 T", "-", "J SECTION"),
            (116, 250): ("AL SHEET", "-", "J SECTION")
        }

        j_l_sections = {
            (50, 125): ("130 L", "J SECTION"),
            (126, 150): ("155 L", "J SECTION"),
            (151, 175): ("180 L", "J SECTION"),
            (176, 200): ("205 L", "J SECTION"),
            (201, 225): ("230 L", "J SECTION"),
            (226, 250): ("255 L", "J SECTION"),
            (251, 275): ("280 L", "J SECTION"),
            (276, 300): ("305 L", "J SECTION")
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
            (100, "EB"): ("EB MB 100", "-", "MISC SECTION"),
            (150, "EB"): ("EB MB 150", "-", "MISC SECTION"),
            (100, "MB"): ("EB MB 100", "-", "MISC SECTION"),
            (150, "MB"): ("EB MB 150", "-", "MISC SECTION"),
            (100, "DP"): ("DP 100", "-", "MISC SECTION"),
            (150, "DP"): ("DP 150", "-", "MISC SECTION"),
            (130,): ("EXTERNAL CORNER", "-", "MISC SECTION"),
            (50, "RK"): ("RK-50", "-", "MISC SECTION")
        }

        raw_materials = []
        child_parts = []
        degree_cutting = getattr(self, 'degree_cutting', False)

        if fg_code_part in ch_straight or fg_code_part in ch_corner:
            is_corner = fg_code_part in ch_corner
            section_map = ch_l_sections_corner if is_corner else ch_l_sections_straight
            cut_dim1, cut_dim2 = str(l1), str(l2) if l2 else "-"
            if ch_straight:
                if fg_code_part in ["WR","WRS",]:
                    cut_dim1, cut_dim2 = f"{l1-50}", f"{l2-50}"
            if is_corner:
                if fg_code_part in ["BCE", "KCE"]:
                    cut_dim1, cut_dim2 = f"{l1+65+10}", f"{l2+65+10}"
                elif fg_code_part in ["BCY", "KCY"]:
                    cut_dim1, cut_dim2 = f"{l1+65+10}", f"{l2+10}"
                elif fg_code_part in ["BC", "KC", "BCZ", "KCZ"]:
                    cut_dim1, cut_dim2 = f"{l1+10}", f"{l2+10}"
                else:
                    cut_dim1, cut_dim2 = str(l1), str(l2) if l2 else "-"
            if a <= 300 and a % 25 == 0 and a in ch_sections:
                rm_code = ch_sections[a]
                cut_dim = f"{cut_dim1},{cut_dim2}" if is_corner else cut_dim1
                raw_materials.append({"code": rm_code, "dimension": cut_dim, "remark": "CH SECTION", "quantity": 1})
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
                side_rail_qty = 1 if degree_cutting and fg_code_part in ["WR", "WRB", "WRS"] else 2
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
            if fg_code_part in ["WR", "WRB", "WRS"] and not degree_cutting:
                child_parts.append({"code": "RK-50", "dimension": f"{a}", "remark": "CHILD PART", "quantity": 1})
                raw_materials.append({"code": "RK-50", "dimension": f"{a}", "remark": "CHILD PART", "quantity": 1})
            if fg_code_part in wall_types:
                u_stiff_qty = 8 if fg_code_part in ["W", "WR", "WRB", "WRS", "WS", "WX", "WXS"] else 3
                child_parts.append({"code": "U STIFFNER", "dimension": f"{a-16}", "remark": "CHILD PART", "quantity": u_stiff_qty})
                raw_materials.append({"code": "U STIFFNER", "dimension": f"{a-16}", "remark": "CHILD PART", "quantity": u_stiff_qty})
                if fg_code_part in ["W", "WR", "WRB", "WS", "WRS", "WX", "WXS"]:
                    child_parts.append({"code": "H STIFFNER", "dimension": f"{a-16}", "remark": "CHILD PART", "quantity": 2})
                    raw_materials.append({"code": "H STIFFNER", "dimension": f"{a-16}", "remark": "CHILD PART", "quantity": 2})
            if fg_code_part in ["D", "SB", "PC", "B"]:
                i_stiff_qty = 4 if fg_code_part in ["D", "SB"] else 5
                child_parts.append({"code": "I STIFFNER", "dimension": f"{a-16}", "remark": "CHILD PART", "quantity": i_stiff_qty})
                raw_materials.append({"code": "I STIFFNER", "dimension": f"{a-16}", "remark": "CHILD PART", "quantity": i_stiff_qty})
            if fg_code_part in ["BC", "BCE", "KC", "KCE"] and a < 301:
                child_parts.append({"code": "STIFF PLATE", "dimension": f"{a-16}X61X4", "remark": "CHILD PART", "quantity": 2})
                raw_materials.append({"code": "STIFF PLATE", "dimension": f"{a-16}X61X4", "remark": "CHILD PART", "quantity": 2})
            if fg_code_part == "B" and l1 == 2775:
                child_parts.append({"code": "STIFF PLATE", "dimension": "61X109X4", "remark": "RAW", "quantity": 3})
                raw_materials.append({"code": "STIFF raw_material", "dimension": "61X109X4", "remark": "RAW", "quantity": 3})

        elif fg_code_part in ic_straight or fg_code_part in ic_corner:
            is_corner = fg_code_part in ic_corner
            key = (a, b, "") if fg_code_part in ["SL", "CC","CCL","CCR"] else (a, b)
            cut_dim1, cut_dim2 = str(l1), str(l2) if l2 else "-"
            if fg_code_part in ["IC", "ICB", "ICXB"]:
                cut_dim1 = f"{l1-4}"
            elif fg_code_part in ["ICT", "ICX"]:
                cut_dim1 = f"{l1-8}"
            if fg_code_part in ["SC", "LSC","LSCK"]:
                cut_dim1, cut_dim2 = f"{l1+10}" if l1 else "-", f"{l2+10}" if l2 else "-"
            elif fg_code_part == "SCE":
                cut_dim1, cut_dim2 = f"{l1+b+10}", f"{l2+b+10}"
            elif fg_code_part == "SCY":
                cut_dim1, cut_dim2 = f"{l1+10}", f"{l2+96+10}"
            elif fg_code_part == "LSCY":
                cut_dim1, cut_dim2 = f"{l1+10}", f"{l2+(b-4)+10}"
            elif fg_code_part in ["SCZ","LSCZ"]:
                cut_dim1, cut_dim2 = f"{(l1-4)+10}", f"{l2+10}"
            elif fg_code_part in ["LSCE","LSCEK"]:
                cut_dim1, cut_dim2 = f"{l1+b+10}", f"{l2+b+10}"
            cut_dim = f"{cut_dim1},{cut_dim2}" if is_corner else cut_dim1

            # Check for exact IC section matches
            if key in ic_sections:
                rm1, rm2, remark = ic_sections[key]
                raw_materials.append({"code": rm1, "dimension": cut_dim, "remark": remark, "quantity": 1})
                frappe.log_error(message=f"IC {'Corner' if is_corner else 'Straight'}: A={a}, B={b}, FG={fg_code_part}, Exact match, using RM1={rm1}, Cut={cut_dim}", title="IC Section Logic")
                if rm2 != "-":
                    raw_materials.append({"code": rm2, "dimension": cut_dim, "remark": remark, "quantity": 1})
                    frappe.log_error(message=f"IC {'Corner' if is_corner else 'Straight'}: Using RM2={rm2}, Cut={cut_dim}", title="IC Section Logic")
            else:
                # Check special IC conditions
                valid_ics = ["100 IC", "125 IC", "125 SL", "150 IC"]
                if (a==125 and b == 100) and fg_code_part in ["SL", "CC","CCL","CCR"]:
                    rm1 = "125 SL"
                    raw_materials.append({"code": rm1, "dimension": cut_dim, "remark": "IC SECTION", "quantity": 1})
                    frappe.log_error(message=f"IC {'Corner' if is_corner else 'Straight'}: A={a}, B={b}, FG={fg_code_part}, special condition (A=125 and B=100), using RM1={rm1}, Cut={cut_dim}", title="IC Section Logic")

                elif (100 < a < 150 and a % 25 == 0 and b == 100) or (a == 100 and 100 < b < 150 and b % 25 == 0):
                    rm1 = "125 IC"  # Default to 125 IC; adjust if specific mapping provided
                    raw_materials.append({"code": rm1, "dimension": cut_dim, "remark": "IC SECTION", "quantity": 1})
                    frappe.log_error(message=f"IC {'Corner' if is_corner else 'Straight'}: A={a}, B={b}, FG={fg_code_part}, special condition (100<A<150 or 100<B<150, multiple of 25), using RM1={rm1}, Cut={cut_dim}", title="IC Section Logic")
                else:
                    # Process A against ic_l_sections
                    for (min_val, max_val), (rm1, rm2, remark) in ic_l_sections.items():
                        if min_val <= a <= max_val:
                            raw_materials.append({"code": rm1, "dimension": cut_dim, "remark": remark, "quantity": 1})
                            frappe.log_error(message=f"IC {'Corner' if is_corner else 'Straight'}: A={a} in range {min_val}-{max_val}, using RM1={rm1}, Cut={cut_dim}, QTY=1", title="IC Section Logic")
                            break
                    # Process B against ic_l_sections if B is provided
                    if b and b > 0:
                        for (min_val, max_val), (rm1, rm2, remark) in ic_l_sections.items():
                            if min_val <= b <= max_val:
                                raw_materials.append({"code": rm2, "dimension": cut_dim, "remark": remark, "quantity": 1})
                                frappe.log_error(message=f"IC {'Corner' if is_corner else 'Straight'}: B={b} in range {min_val}-{max_val}, using RM2={rm2}, Cut={cut_dim}, QTY=1", title="IC Section Logic")
                                break

            side_rail_qty = 1 if fg_code_part in ["SCY", "SCZ"] else 2
            side_rail_dim = f"{a-15}" if any(rm["code"].endswith("IC") or rm["code"].endswith("SL") for rm in raw_materials) else f"{a-12}"
            if fg_code_part not in ["IC", "ICB", "ICT", "ICX"]:
                child_parts.append({"code": "SIDE RAIL", "dimension": side_rail_dim, "remark": "CHILD PART", "quantity": side_rail_qty})
                raw_materials.append({"code": "SIDE RAIL", "dimension": side_rail_dim, "remark": "CHILD PART", "quantity": side_rail_qty})
            stiff_qty = 8 if fg_code_part in ["CC", "CCL", "CCR", "IC", "ICB","ICXB", "LS", "LSL","LSK", "LSR", "LSW", "SL", "SLR"] else 5 if fg_code_part in ["ICT", "ICX"] else 4
            stiff_dim = f"{a-15}X{b-15}X4" if any(rm["code"].endswith("IC") or rm["code"].endswith("SL") for rm in raw_materials) else f"{a-12}X{b-12}X4"
            child_parts.append({"code": "STIFF PLATE", "dimension": stiff_dim, "remark": "CHILD PART", "quantity": stiff_qty})
            raw_materials.append({"code": "STIFF PLATE", "dimension": stiff_dim, "remark": "CHILD PART", "quantity": stiff_qty})
            if fg_code_part in ["IC", "ICB", "ICXB"]:
                child_parts.append({"code": "OUTER CAP", "dimension": f"{a}X{b}X4", "remark": "CHILD PART", "quantity": 1})
                raw_materials.append({"code": "OUTER CAP", "dimension": f"{a}X{b}X4", "remark": "CHILD PART", "quantity": 1})
            elif fg_code_part in ["ICT", "ICX"]:
                child_parts.append({"code": "OUTER CAP", "dimension": f"{a}X{b}X4", "remark": "CHILD PART", "quantity": 2})
                raw_materials.append({"code": "OUTER CAP", "dimension": f"{a}X{b}X4", "remark": "CHILD PART", "quantity": 2})
            elif fg_code_part in ["SCY", "SCZ"]:
                outer_cap_dim = f"{b/math.sin(math.radians(45))}X{a}X4"
                child_parts.append({"code": "OUTER CAP", "dimension": outer_cap_dim, "remark": "CHILD PART", "quantity": 1})
                raw_materials.append({"code": "OUTER CAP", "dimension": outer_cap_dim, "remark": "CHILD PART", "quantity": 1})
        ## J Section Logic
        elif fg_code_part in j_straight or fg_code_part in j_corner:
            is_corner = fg_code_part in j_corner
            cut_dim1, cut_dim2 = str(l1), str(l2) if l2 else "-"
            if fg_code_part in ["JLT", "JRT", "JLX", "JRX"]:
                cut_dim1 = f"{l1-8}"
            elif fg_code_part in ["LSX"]:
                cut_dim1 = f"{l1}"
            elif fg_code_part in ["JL", "JLB", "JLT", "JLX", "JR", "JRB", "JRT", "JRX"]:
                cut_dim1 = f"{l1-4}"
            elif fg_code_part in ["SXC", "SXCE", "SXCZ", "LSXC","LSXCK","LSXCE","LSXCEK"]:
                cut_dim1 = f"{l1+10}" if fg_code_part in ["SXC","SXCZ","LSXCK"] else f"{l1+b+10}"
                cut_dim2 = f"{l2+10}" if fg_code_part in ["SXC","SXCZ","LSXCK"] else f"{l2+b+10}"
            elif fg_code_part in ["SXCY"]:
                cut_dim1 = f"{l1+10}"
                cut_dim2 = f"{l2+96+10}" if any(rm["code"] == "J SEC" for rm in raw_materials) else f"{l2+10}"
            cut_dim = f"{cut_dim1},{cut_dim2}" if is_corner else cut_dim1
            if (a <= 50 and b == 100) or (b <= 50 and a == 100):
                raw_materials.append({"code": "J SEC", "dimension": cut_dim, "remark": "J SECTION", "quantity": 1})
                frappe.log_error(message=f"J {'Corner' if is_corner else 'Straight'}: A={a}, B={b}, FG={fg_code_part}, Using J SEC due to A<=50 and B=100 or B<=50 and A=100, Cut={cut_dim}", title="J Section Logic")
            else:
                for (min_a, max_a), (rm1, rm2, remark) in j_sections.items():
                    if min_a <= a <= max_a:
                        cut_dim = f"{cut_dim1},{cut_dim2}" if is_corner else cut_dim1
                        if rm1 == "AL SHEET" and not is_corner:
                            cut_dim = f"{a+65}X{l1}X4"
                        elif rm1 == "AL SHEET" and is_corner:
                            cut_dim = f"{a+65}X{l1}X4,{a+65}X{l2}X4"
                        raw_materials.append({"code": rm1, "dimension": cut_dim, "remark": remark, "quantity": 1})
                        frappe.log_error(message=f"J {'Corner' if is_corner else 'Straight'}: A={a} in range {min_a}-{max_a}, using RM1={rm1}, Cut={cut_dim}", title="J Section Logic")
                        # Check for A in 25-50 and B = 100 to skip RM2
                        if not (25 <= a <= 50 and b == 100) or (25 <= b <= 50 and a == 100):
                            # Only add RM2 if A >= 51 or if A is outside 25-50
                            for (min_b, max_b), (rm2, remark) in j_l_sections.items():
                                if min_b <= b <= max_b:
                                    cut_dim = f"{cut_dim1},{cut_dim2}" if is_corner else cut_dim1
                                    raw_materials.append({"code": rm2, "dimension": cut_dim, "remark": remark, "quantity": 1})
                                    frappe.log_error(message=f"J {'Corner' if is_corner else 'Straight'}: B={b} in range {min_b}-{max_b}, using RM2={rm2}, Cut={cut_dim}", title="J Section Logic")
                                    break
                        else:
                            frappe.log_error(message=f"J {'Corner' if is_corner else 'Straight'}: A={a} in 25-50 and B={b} == 100, skipping RM2 as per logic", title="J Section Logic")
                        break
            # Child parts logic
            if fg_code_part in ["SX", "SXC", "SXCE", "LSX", "LSXC", "SXCZ", "SXCY", "LSXCK", "LSXCE", "LSXCEK"]:
                side_rail_dim = f"{b-16}" if any(rm["code"] == "J SEC" for rm in raw_materials) else f"{b-12}"
                stiff_qty = 5 if fg_code_part == "SX" else 2
                child_parts.append({"code": "SIDE RAIL", "dimension": side_rail_dim, "remark": "CHILD PART", "quantity": 2})
                raw_materials.append({"code": "SIDE RAIL", "dimension": side_rail_dim, "remark": "CHILD PART", "quantity": 2})
                stiff_dim = f"{a-4}X{b-12}X4" if any(rm["code"] == "J SEC" for rm in raw_materials) else f"{a-4}X{b-12}X4"
                child_parts.append({"code": "STIFF PLATE", "dimension": stiff_dim, "remark": "CHILD PART", "quantity": stiff_qty})
                raw_materials.append({"code": "STIFF PLATE", "dimension": stiff_dim, "remark": "CHILD PART", "quantity": stiff_qty})
            if fg_code_part in ["JL", "JLB", "JLT", "JLX", "JR", "JRB", "JRT", "JRX"]:
                outer_cap_qty = 2 if fg_code_part in ["JLT", "JRT", "JLX", "JRX"] else 1
                stiff_qty = 2 if fg_code_part in ["JLT", "JRT", "JLX", "JRX"] else 6
                stiff_dim = f"{a-4}X{b-16}X4" if any(rm["code"] == "J SEC" for rm in raw_materials) else f"{a-4}X{b-12}X4"
                child_parts.append({"code": "OUTER CAP", "dimension": f"{a+65}X{b}X4", "remark": "CHILD PART", "quantity": outer_cap_qty})
                raw_materials.append({"code": "OUTER CAP", "dimension": f"{a+65}X{b}X4", "remark": "CHILD PART", "quantity": outer_cap_qty})
                child_parts.append({"code": "STIFF PLATE", "dimension": stiff_dim, "remark": "CHILD PART", "quantity": stiff_qty})
                raw_materials.append({"code": "STIFF PLATE", "dimension": stiff_dim, "remark": "CHILD PART", "quantity": stiff_qty})
        # T section logic
        elif fg_code_part in t_straight:
            cut_dim = str(l1)
            if fg_code_part in ["WRBSE", "WRSE"] and not degree_cutting:
                cut_dim = f"{l1-50}"
            for key, (rm1, rm2, rm3, remark) in t_sections.items():
                if isinstance(key, tuple) and len(key) == 2:
                    if key[0] <= a <= key[1]:
                        raw_materials.append({"code": rm1, "dimension": cut_dim, "remark": remark, "quantity": 1 if rm1 == "115 T" else 1})
                        frappe.log_error(message=f"T Straight: A={a} in range {key[0]}-{key[1]}, using RM1={rm1}, Cut={cut_dim}, QTY={1 if rm1 == '115 T' else 1}", title="T Section Logic")
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
            side_rail_dim = f"{a-131}" if any(rm["code"].endswith("T") for rm in raw_materials) else f"{a-146}"
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
            cut_dim = str(l1 + 150) if fg_code_part == "MB" and a == 150 else str(l1 + 100) if fg_code_part == "MB" and a == 100 else str(l1)

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
        frappe.log_error(message=f"Returning raw_materials for FG Code {fg_code}: {json.dumps(raw_materials, indent=2)}", title="FG Single Code Debug")

        return raw_materials
@frappe.whitelist()
def get_raw_materials(docname=None, planning_bom=None):
    try:
        frappe.log_error(
            message=f"get_raw_materials called with docname: {docname}, planning_bom: {planning_bom}",
            title="FG Get Raw Materials Debug"
        )
        if not docname:
            frappe.throw(_("No FG Raw Material Selector document specified."))
        if not planning_bom:
            frappe.throw(_("No Planning BOMs provided."))

        pbom_list = []
        if isinstance(planning_bom, str):
            try:
                pbom_data = json.loads(planning_bom)
                if isinstance(pbom_data, list):
                    for entry in pbom_data:
                        if isinstance(entry, dict):
                            value = entry.get("planning_bom") or entry.get("value") or entry.get("name")
                            if value:
                                pbom_list.append(value)
                        elif isinstance(entry, str):
                            pbom_list.append(entry)
                elif isinstance(pbom_data, str):
                    pbom_list = [pbom_data]
                elif isinstance(pbom_data, dict):
                    value = pbom_data.get("planning_bom") or pbom_data.get("value") or pbom_data.get("name")
                    if value:
                        pbom_list.append(value)
            except json.JSONDecodeError:
                pbom_list = [planning_bom]
        elif isinstance(planning_bom, list):
            for pb in planning_bom:
                if isinstance(pb, str):
                    pbom_list.append(pb)

        pbom_list = [p for p in pbom_list if p]
        if not pbom_list:
            frappe.throw(_("No valid Planning BOMs found."))

        doc = frappe.get_doc("FG Raw Material Selector", docname)

        existing = {row.planning_bom for row in doc.planning_bom}
        for pb in pbom_list:
            if pb not in existing:
                doc.append("raw_materials", {"planning_bom": pb})

        doc.save()

        job_id = frappe.enqueue(
            'sb.sb.doctype.fg_raw_material_selector.fg_raw_material_selector.process_fg_codes_background',
            queue='long',
            timeout=3600,
            docname=doc.name
        )

        frappe.msgprint(
            _("Raw material processing has been queued (Job ID: {0}).").format(job_id)
        )
        return []

    except Exception as e:
        frappe.throw(_("Failed to fetch raw materials: {0}").format(str(e)))
@frappe.whitelist()
def process_fg_codes_background(docname):
    try:
        frappe.log_error(message=f"Starting background job for FG Raw Material Selector: {docname}", title="FG Background Debug")
        doc = frappe.get_doc("FG Raw Material Selector", docname)
        doc.process_fg_codes()
        frappe.log_error(message=f"Completed background job for FG Raw Material Selector: {docname}", title="FG Background Debug")
    except Exception as e:
        frappe.log_error(message=f"Error in background job for {docname}: {str(e)}", title="FG Raw Material Error")
        raise

@frappe.whitelist()
def create_bom_from_fg_selector(fg_selector_name, fg_code=None, project_design_upload=None):
    try:
        frappe.log_error(message=f"Creating BOM for FG Selector: {fg_selector_name}, FG Code: {fg_code}, PDU: {project_design_upload}", title="FG BOM Debug")
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
        frappe.log_error(message=f"Created BOM: {bom.name}", title="FG BOM Debug")
        return bom.name
    except Exception as e:
        frappe.log_error(message=f"Error creating BOM: {str(e)}", title="FG Raw Material Error")
        frappe.throw(f"Failed to create BOM: {str(e)}")

from frappe.utils import flt

@frappe.whitelist()
def reserve_stock(fg_selector_name):
    try:
        frappe.log_error(message=f"Reserving stock for FG Selector: {fg_selector_name}", title="FG Stock Debug")
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
        frappe.log_error(message="Stock reservation completed.", title="FG Stock Debug")
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
    except Exception as e:
        frappe.log_error(message=f"Error reserving stock: {str(e)}", title="FG Raw Material Error")
        raise

def get_actual_qty(item_code, warehouse, uom):
    try:
        bin = frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": warehouse}, ["actual_qty"], as_dict=True)
        if not bin:
            frappe.log_error(message=f"No bin found for item {item_code} in warehouse {warehouse}", title="FG Stock Debug")
            return 0
        stock_uom = frappe.db.get_value("Item", item_code, "stock_uom")
        conversion_factor = 1
        if stock_uom != uom:
            from erpnext.stock.doctype.item.item import get_uom_conv_factor as get_uom_conversion_factor
            try:
                conversion_factor = get_uom_conversion_factor(item_code, uom)
            except Exception as e:
                frappe.log_error(message=f"Error getting UOM conversion factor for {item_code}: {str(e)}", title="FG Stock Debug")
                conversion_factor = 0
        qty = flt(bin.actual_qty) / flt(conversion_factor or 1)
        frappe.log_error(message=f"Actual qty for {item_code} in {warehouse}: {qty}", title="FG Stock Debug")
        return qty
    except Exception as e:
        frappe.log_error(message=f"Error in get_actual_qty for {item_code}: {str(e)}", title="FG Raw Material Error")
        return 0

@frappe.whitelist()
def clear_reservation(fg_selector_name):
    try:
        frappe.log_error(message=f"Clearing reservation for FG Selector: {fg_selector_name}", title="FG Stock Debug")
        doc = frappe.get_doc("FG Raw Material Selector", fg_selector_name)
        for row in doc.raw_materials:
            row.db_set("status", "")
            row.db_set("reserve_tag", 0)
            row.db_set("warehouse", "")
            row.db_set("available_quantity", 0)
        frappe.log_error(message=f"Reservation cleared for {fg_selector_name}", title="FG Stock Debug")
        return {
            "status": "success",
            "message": f"Reservation cleared for {fg_selector_name}"
        }
    except Exception as e:
        frappe.log_error(message=f"Error clearing reservation: {str(e)}", title="FG Raw Material Error")
        raise

