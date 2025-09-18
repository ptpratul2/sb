# fg_raw_material_selector.py
# Copyright (c) 2025
# For license information, see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
import json
from frappe.utils.background_jobs import enqueue
from frappe.utils import flt
import math
from collections import defaultdict

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
        
        fg_section_map = {
            'B': 'CH SECTION', 'CP': 'CH SECTION', 'CPP': 'CH SECTION', 'CPPP': 'CH SECTION',
            'D': 'CH SECTION', 'K': 'CH SECTION', 'PC': 'CH SECTION', 'PH': 'CH SECTION',
            'PLB': 'CH SECTION', 'SB': 'CH SECTION', 'T': 'CH SECTION', 'TS': 'CH SECTION',
            'W': 'CH SECTION', 'WR': 'CH SECTION', 'WRB': 'CH SECTION', 'WRS': 'CH SECTION',
            'WS': 'CH SECTION', 'WX': 'CH SECTION', 'WXS': 'CH SECTION',
            'BC': 'CH SECTION CORNER', 'BCE': 'CH SECTION CORNER', 'KC': 'CH SECTION CORNER',
            'KCE': 'CH SECTION CORNER', 'BCY': 'CH SECTION CORNER', 'BCZ': 'CH SECTION CORNER',
            'KCY': 'CH SECTION CORNER', 'KCZ': 'CH SECTION CORNER',
            'CC': 'IC SECTION', 'CCL': 'IC SECTION', 'CCR': 'IC SECTION', 'IC': 'IC SECTION',
            'ICB': 'IC SECTION', 'ICT': 'IC SECTION', 'ICX': 'IC SECTION', 'ICXB': 'IC SECTION',
            'LS': 'IC SECTION', 'LSK': 'IC SECTION', 'LSL': 'IC SECTION', 'LSR': 'IC SECTION',
            'LSW': 'IC SECTION', 'SL': 'IC SECTION', 'SLR': 'IC SECTION',
            'SC': 'IC SECTION CORNER', 'SCE': 'IC SECTION CORNER', 'SCY': 'IC SECTION CORNER',
            'SCZ': 'IC SECTION CORNER', 'LSC': 'IC SECTION CORNER', 'LSCE': 'IC SECTION CORNER',
            'LSCK': 'IC SECTION CORNER', 'LSCEK': 'IC SECTION CORNER', 'LSCY': 'IC SECTION CORNER',
            'LSCZ': 'IC SECTION CORNER',
            'JL': 'J SECTION', 'JLB': 'J SECTION', 'JLT': 'J SECTION', 'JLX': 'J SECTION',
            'JR': 'J SECTION', 'JRB': 'J SECTION', 'JRT': 'J SECTION', 'JRX': 'J SECTION',
            'SX': 'J SECTION', 'LSX': 'J SECTION', 'LSXK': 'J SECTION',
            'SXC': 'J SECTION CORNER', 'SXCE': 'J SECTION CORNER', 'SXCY': 'J SECTION CORNER',
            'SXCZ': 'J SECTION CORNER', 'LSXC': 'J SECTION CORNER', 'LSXCK': 'J SECTION CORNER',
            'LSXCE': 'J SECTION CORNER', 'LSXCEK': 'J SECTION CORNER',
            'PCE': 'T SECTION', 'SBE': 'T SECTION', 'TSE': 'T SECTION', 'WRBSE': 'T SECTION',
            'WRSE': 'T SECTION', 'WSE': 'T SECTION', 'WXSE': 'T SECTION',
            'DP': 'MISC SECTION', 'EB': 'MISC SECTION', 'MB': 'MISC SECTION',
            'EC': 'MISC SECTION', 'ECH': 'MISC SECTION', 'ECT': 'MISC SECTION',
            'ECX': 'MISC SECTION', 'ECB': 'MISC SECTION', 'ECK': 'MISC SECTION', 'RK': 'MISC SECTION'
        }
        
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
        ic_straight = ["CC", "CCL", "CCR", "IC", "ICB", "ICT", "ICX", "ICXB", "LSK", "LS", "LSL", "LSR", "LSW", "SL", "SLR"]
        ic_corner = ["SC", "SCE", "SCY", "SCZ", "LSC", "LSCE", "LSCK", "LSCEK", "LSCY", "LSCZ"]
        j_straight = ["JL", "JLB", "JLT", "JLX", "JR", "JRB", "JRT", "JRX", "SX", "LSX", "LSXK"]
        j_corner = ["SXC", "SXCE", "SXCY", "SXCZ", "LSXC", "LSXCE", "LSXCK", "LSXCEK"]
        t_straight = ["PCE", "SBE", "TSE", "WRBSE", "WRSE", "WSE", "WXSE"]
        misc_straight = ["DP", "EB", "MB", "EC", "ECH", "ECT", "ECX", "ECK", "ECB", "RK"]

        # Channel section mappings
        ch_sections = {
            50: "50 CH", 75: "75 CH", 100: "100 CH", 125: "125 CH",
            150: "150 CH", 175: "175 CH", 200: "200 CH", 250: "250 CH",
            300: "300 CH", 350: "350 CH", 400: "400 CH", 600: "600 CH"
        }

        # IC section mappings for exact matches
        ic_sections = {
            (100, 100): ("100 IC", "-"),
            (125, 100, "SL"): ("125 SL", "-"),
            (100, 125, "SL"): ("125 SL", "-"),
            (125, 100, "CC"): ("125 SL", "-"),
            (100, 125, "CC"): ("125 SL", "-"),
            (125, 100, "CCR"): ("125 SL", "-"),
            (125, 100, "CCL"): ("125 SL", "-"),
            (125, 100): ("125 IC", "-"),
            (150, 100): ("150 IC", "-"),
            (100, 150): ("150 IC", "-")
        }

        # L-section mappings for IC straight and corner
        ic_l_sections = {
            (50, 125): ("130 L", "130 L"),
            (126, 150): ("155 L", "155 L"),
            (151, 175): ("180 L", "180 L"),
            (176, 200): ("205 L", "205 L"),
            (201, 225): ("230 L", "230 L"),
            (226, 250): ("255 L", "255 L"),
            (251, 275): ("280 L", "280 L"),
            (276, 300): ("305 L", "305 L"),
            (301, 600): ("AL SHEET", "155 L")
        }

        # L-section mappings for CH straight
        ch_l_sections_straight = {
            (51, 125): ("130 L", "MAIN FRAME"),
            (126, 149): ("155 L", "MAIN FRAME"),
            (151, 174): ("180 L", "MAIN FRAME"),
            (176, 199): ("205 L", "MAIN FRAME"),
            (201, 225): ("230 L", "MAIN FRAME"),
            (226, 249): ("255 L", "MAIN FRAME"),
            (251, 275): ("280 L", "MAIN FRAME"),
            (276, 300): ("305 L", "MAIN FRAME"),
            (301, 325): ("180 L", "155 L"),
            (326, 350): ("180 L", "180 L"),
            (351, 375): ("205 L", "180 L"),
            (376, 400): ("205 L", "205 L"),
            (401, 425): ("230 L", "205 L"),
            (426, 450): ("230 L", "230 L"),
            (451, 475): ("255 L", "230 L"),
            (476, 500): ("255 L", "255 L"),
            (501, 525): ("280 L", "255 L"),
            (526, 550): ("280 L", "280 L"),
            (551, 575): ("305 L", "280 L"),
            (576, 600): ("305 L", "305 L")
        }

        # L-section mappings for CH corner
        ch_l_sections_corner = {
            (51, 125): ("130 L", "MAIN FRAME"),
            (126, 149): ("155 L", "MAIN FRAME"),
            (151, 174): ("180 L", "MAIN FRAME"),
            (176, 199): ("205 L", "MAIN FRAME"),
            (201, 225): ("230 L", "MAIN FRAME"),
            (226, 249): ("255 L", "MAIN FRAME"),
            (251, 275): ("280 L", "MAIN FRAME"),
            (276, 300): ("305 L", "MAIN FRAME"),
            (301, 325): ("180 L", "155 L"),
            (326, 350): ("180 L", "180 L"),
            (351, 375): ("205 L", "180 L"),
            (376, 400): ("205 L", "205 L"),
            (401, 425): ("230 L", "205 L"),
            (426, 450): ("230 L", "230 L"),
            (451, 475): ("255 L", "230 L"),
            (476, 500): ("255 L", "255 L"),
            (501, 525): ("280 L", "255 L"),
            (526, 550): ("280 L", "280 L"),
            (551, 575): ("305 L", "280 L"),
            (576, 600): ("305 L", "305 L")
        }

        # J section mappings
        j_sections = {
            (25, 50): ("J SEC", "-"),
            (25, 115): ("115 T", "-"),
            (116, 250): ("AL SHEET", "-")
        }

        j_l_sections = {
            (50, 125): ("130 L"),
            (126, 150): ("155 L"),
            (151, 175): ("180 L"),
            (176, 200): ("205 L"),
            (201, 225): ("230 L"),
            (226, 250): ("255 L"),
            (251, 275): ("280 L"),
            (276, 300): ("305 L")
        }

        # T section mappings
        t_sections = {
            (230,): ("100 T", "-", "-"),
            (231, 360): ("115 T", "115 T", "-"),
            (380,): ("250 CH", "EC", "-"),
            (430,): ("300 CH", "EC", "-"),
            (361, 380): ("255 L", "MAIN FRAME", "EC"),
            (381, 405): ("280 L", "MAIN FRAME", "EC"),
            (406, 430): ("305 L", "MAIN FRAME", "EC"),
            (431, 455): ("180 L", "155 L", "EC"),
            (456, 480): ("180 L", "180 L", "EC")
        }

        # Misc section mappings
        misc_sections = {
            (100, "EB"): ("EB MB 100", "-"),
            (150, "EB"): ("EB MB 150", "-"),
            (100, "MB"): ("EB MB 100", "-"),
            (150, "MB"): ("EB MB 150", "-"),
            (100, "DP"): ("DP 100", "-"),
            (150, "DP"): ("DP 150", "-"),
            (130,): ("EXTERNAL CORNER", "-"),
            (50, "RK"): ("RK-50", "-")
        }

        raw_materials = []
        child_parts = []
        degree_cutting = getattr(self, 'degree_cutting', False)
        
        # Apply 5mm cutting tolerance to initial lengths
        l1 = l1 + 0 if l1 else 0
        l2 = l2 + 0 if l2 else 0

        if fg_code_part in ch_straight or fg_code_part in ch_corner:
            is_corner = fg_code_part in ch_corner
            section_map = ch_l_sections_corner if is_corner else ch_l_sections_straight
            cut_dim1, cut_dim2 = str(l1), str(l2) if l2 else "-"
            if fg_code_part in ["WR", "WRS"]:
                cut_dim1, cut_dim2 = f"{l1-50+5}", f"{l2-50+5}" if l2 else "-"
            if is_corner:
                if fg_code_part in ["BCE", "KCE"]:
                    cut_dim1, cut_dim2 = f"{l1+65+10+5}", f"{l2+65+10+5}" if l2 else "-"
                elif fg_code_part in ["BCY", "KCY"]:
                    cut_dim1, cut_dim2 = f"{l1+65+10+5}", f"{l2+10+5}" if l2 else "-"
                elif fg_code_part in ["BC", "KC", "BCZ", "KCZ"]:
                    cut_dim1, cut_dim2 = f"{l1+10+5}", f"{l2+10+5}" if l2 else "-"
            
            if a <= 300 and a % 25 == 0 and a in ch_sections:
                rm_code = ch_sections[a]
                cut_dim = f"{cut_dim1},{cut_dim2}" if is_corner else cut_dim1
                raw_materials.append({"code": rm_code, "dimension": cut_dim, "remark": fg_section_map[fg_code_part], "quantity": 1})
                frappe.log_error(message=f"CH {'Corner' if is_corner else 'Straight'}: A={a}, using RM1={rm_code}, Cut={cut_dim}", title="CH Section Logic")
            elif a in [350, 400, 600] and a in ch_sections:
                rm_code = ch_sections[a]
                cut_dim = f"{cut_dim1},{cut_dim2}" if is_corner else cut_dim1
                raw_materials.append({"code": rm_code, "dimension": cut_dim, "remark": fg_section_map[fg_code_part], "quantity": 1})
                frappe.log_error(message=f"CH {'Corner' if is_corner else 'Straight'}: A={a}, using RM1={rm_code}, Cut={cut_dim}", title="CH Section Logic")
            else:
                for (min_a, max_a), (rm1, rm2) in section_map.items():
                    if min_a <= a <= max_a:
                        cut_dim = f"{cut_dim1},{cut_dim2}" if is_corner else cut_dim1
                        raw_materials.append({"code": rm1, "dimension": cut_dim, "remark": fg_section_map[fg_code_part], "quantity": 1})
                        if rm2 != "MAIN FRAME":
                            raw_materials.append({"code": rm2, "dimension": cut_dim, "remark": fg_section_map[fg_code_part], "quantity": 1})
                        else:
                            raw_materials.append({"code": "MAIN FRAME", "dimension": cut_dim, "remark": fg_section_map[fg_code_part], "quantity": 1})
                        frappe.log_error(message=f"CH {'Corner' if is_corner else 'Straight'}: A={a} in range {min_a}-{max_a}, using RM1={rm1}, RM2={rm2}, Cut={cut_dim}", title="CH Section Logic")
                        break
            
            if fg_code_part != "PLB":
                side_rail_qty = 1 if degree_cutting and fg_code_part in ["WR", "WRB", "WRS"] else 2
                child_parts.append({"code": "SIDE RAIL", "dimension": f"{a-16+5}", "remark": "CHILD PART", "quantity": side_rail_qty})
                raw_materials.append({"code": "SIDE RAIL", "dimension": f"{a-16+5}", "remark": "CHILD PART", "quantity": side_rail_qty})
            
            if fg_code_part == "K" and l1 >= 1800:
                child_parts.append({"code": "STIFF PLATE", "dimension": f"{a-4}X{l1-12+5}X4", "remark": "CHILD PART", "quantity": 5})
                raw_materials.append({"code": "STIFF PLATE", "dimension": f"{a-4}X{l1-12+5}X4", "remark": "CHILD PART", "quantity": 5})

        elif fg_code_part in ic_straight or fg_code_part in ic_corner:
            is_corner = fg_code_part in ic_corner
            cut_dim1, cut_dim2 = str(l1), str(l2) if l2 else "-"
            length1, length2 = l1, l2 if l2 else 0
            if fg_code_part in ["ICXB", "ICB"]:
                cut_dim1 = f"{l1-8+5}"
                length1 = l1 - 8 + 5
            elif fg_code_part in ["ICT", "ICX"]:
                cut_dim1 = f"{l1-4+5}"
                length1 = l1 - 4 + 5
            elif fg_code_part in ["SCE", "LSCE", "LSCEK"]:
                cut_dim1, cut_dim2 = f"{l1+b+10+5}", f"{l2+b+10+5}" if l2 else "-"
                length1, length2 = l1 + b + 10 + 5, l2 + b + 10 + 5 if l2 else 0
            elif fg_code_part in ["SCY", "LSCY"]:
                cut_dim1, cut_dim2 = f"{l1+65+10+5}", f"{l2+10+5}" if l2 else "-"
                length1, length2 = l1 + 65 + 10 + 5, l2 + 10 + 5 if l2 else 0
            elif fg_code_part in ["SCZ", "LSCZ"]:
                cut_dim1, cut_dim2 = f"{l1+10+5}", f"{l2+65+10+5}" if l2 else "-"
                length1, length2 = l1 + 10 + 5, l2 + 65 + 10 + 5 if l2 else 0
            elif fg_code_part in ["SC", "SCE", "SCY", "SCZ", "LSC", "LSCE", "LSCK", "LSCEK", "LSCY", "LSCZ"]:
                cut_dim1, cut_dim2 = f"{l1+10+5}", f"{l2+10+5}" if l2 else "-"
                length1, length2 = l1 + 10 + 5, l2 + 10 + 5 if l2 else 0
            
            cut_dim = f"{cut_dim1},{cut_dim2}" if is_corner else cut_dim1
            matched = False
            for key in ic_sections:
                if isinstance(key, tuple) and len(key) == 3:
                    if (a, b, fg_code_part) == key or (b, a, fg_code_part) == key:
                        rm1, rm2 = ic_sections[key]
                        raw_materials.append({"code": rm1, "dimension": cut_dim, "remark": fg_section_map[fg_code_part], "quantity": 1, "length": cut_dim1 if not is_corner else f"{length1},{length2}"})
                        if rm2 != "-":
                            raw_materials.append({"code": rm2, "dimension": cut_dim, "remark": fg_section_map[fg_code_part], "quantity": 1, "length": cut_dim1 if not is_corner else f"{length1},{length2}"})
                        matched = True
                        frappe.log_error(message=f"IC {'Corner' if is_corner else 'Straight'}: A={a}, B={b}, FG={fg_code_part}, using RM1={rm1}, RM2={rm2}, Cut={cut_dim}", title="IC Section Logic")
                        break
                elif isinstance(key, tuple) and len(key) == 2:
                    if (a, b) == key or (b, a) == key:
                        rm1, rm2 = ic_sections[key]
                        raw_materials.append({"code": rm1, "dimension": cut_dim, "remark": fg_section_map[fg_code_part], "quantity": 1, "length": cut_dim1 if not is_corner else f"{length1},{length2}"})
                        if rm2 != "-":
                            raw_materials.append({"code": rm2, "dimension": cut_dim, "remark": fg_section_map[fg_code_part], "quantity": 1, "length": cut_dim1 if not is_corner else f"{length1},{length2}"})
                        matched = True
                        frappe.log_error(message=f"IC {'Corner' if is_corner else 'Straight'}: A={a}, B={b}, using RM1={rm1}, RM2={rm2}, Cut={cut_dim}", title="IC Section Logic")
                        break
            
            if not matched:
                for (min_a, max_a), (rm1, rm2) in ic_l_sections.items():
                    if min_a <= a <= max_a:
                        remark = "L SECTION" if rm1.endswith("L") or rm2.endswith("L") else fg_section_map[fg_code_part]
                        raw_materials.append({"code": rm1, "dimension": cut_dim, "remark": remark, "quantity": 1, "length": cut_dim1 if not is_corner else f"{length1},{length2}"})
                        if rm2 != "-":
                            raw_materials.append({"code": rm2, "dimension": cut_dim, "remark": remark, "quantity": 1, "length": cut_dim1 if not is_corner else f"{length1},{length2}"})
                        frappe.log_error(message=f"IC {'Corner' if is_corner else 'Straight'}: A={a} in range {min_a}-{max_a}, using RM1={rm1}, RM2={rm2}, Cut={cut_dim}, Remark={remark}", title="IC Section Logic")
                        break
            
            if fg_code_part in ["IC", "ICT", "ICX", "ICB", "ICXB"]:
                side_rail_qty = 2
                child_parts.append({"code": "SIDE RAIL", "dimension": f"{a-16+5}", "remark": "CHILD PART", "quantity": side_rail_qty, "length": f"{a-16+5}"})
                raw_materials.append({"code": "SIDE RAIL", "dimension": f"{a-16+5}", "remark": "CHILD PART", "quantity": side_rail_qty, "length": f"{a-16+5}"})
            
            if fg_code_part in ["SC", "SCE", "LSC", "LSCE", "LSCK", "LSCEK"]:
                outer_cap_dim = f"{a+65+5}X{l1}X4,{a+65+5}X{l2}X4" if is_corner else f"{a+65+5}X{l1}X4"
                child_parts.append({"code": "OUTER CAP", "dimension": outer_cap_dim, "remark": "CHILD PART", "quantity": 1, "length": outer_cap_dim})
                raw_materials.append({"code": "OUTER CAP", "dimension": outer_cap_dim, "remark": "CHILD PART", "quantity": 1, "length": outer_cap_dim})
            elif fg_code_part in ["SCY", "SCZ"]:
                outer_cap_dim = f"{b/math.sin(math.radians(45))+5}X{a}X4"
                child_parts.append({"code": "OUTER CAP", "dimension": outer_cap_dim, "remark": "CHILD PART", "quantity": 1, "length": outer_cap_dim})
                raw_materials.append({"code": "OUTER CAP", "dimension": outer_cap_dim, "remark": "CHILD PART", "quantity": 1, "length": outer_cap_dim})

        elif fg_code_part in j_straight or fg_code_part in j_corner:
            is_corner = fg_code_part in j_corner
            cut_dim1, cut_dim2 = str(l1), str(l2) if l2 else "-"
            length1, length2 = l1, l2 if l2 else 0
            if fg_code_part in ["JLT", "JRT", "JLX", "JRX"]:
                cut_dim1 = f"{l1-8+5}"
                length1 = l1 - 8 + 5
            elif fg_code_part in ["LSX"]:
                cut_dim1 = f"{l1+5}"
                length1 = l1 + 5
            elif fg_code_part in ["JL", "JLB", "JLT", "JLX", "JR", "JRB", "JRT", "JRX"]:
                cut_dim1 = f"{l1-4+5}"
                length1 = l1 - 4 + 5
            elif fg_code_part in ["SXC", "SXCE", "SXCZ", "LSXC", "LSXCK", "LSXCE", "LSXCEK"]:
                cut_dim1 = f"{l1+10+5}" if fg_code_part in ["SXC", "SXCZ", "LSXCK"] else f"{l1+b+10+5}"
                cut_dim2 = f"{l2+10+5}" if fg_code_part in ["SXC", "SXCZ", "LSXCK"] else f"{l2+b+10+5}" if l2 else "-"
                length1 = l1 + 10 + 5 if fg_code_part in ["SXC", "SXCZ", "LSXCK"] else l1 + b + 10 + 5
                length2 = l2 + 10 + 5 if fg_code_part in ["SXC", "SXCZ", "LSXCK"] else l2 + b + 10 + 5 if l2 else 0
            elif fg_code_part in ["SXCY"]:
                cut_dim1 = f"{l1+10+5}"
                cut_dim2 = f"{l2+10+5}" if l2 else "-"
                length1, length2 = l1 + 10 + 5, l2 + 10 + 5 if l2 else 0
            
            cut_dim = f"{cut_dim1},{cut_dim2}" if is_corner else cut_dim1
            length = f"{length1},{length2}" if is_corner else cut_dim1
            
            if (a <= 50 and b == 100) or (b <= 50 and a == 100):
                raw_materials.append({"code": "J SEC", "dimension": cut_dim, "remark": fg_section_map[fg_code_part], "quantity": 1, "length": length})
                frappe.log_error(message=f"J {'Corner' if is_corner else 'Straight'}: A={a}, B={b}, using J SEC, Cut={cut_dim}", title="J Section Logic")
            else:
                for (min_a, max_a), (rm1, rm2) in j_sections.items():
                    if min_a <= a <= max_a:
                        rm_dim = f"{a+65+5}X{l1}X4,{a+65+5}X{l2}X4" if is_corner and rm1 == "AL SHEET" else f"{a+65+5}X{l1}X4" if rm1 == "AL SHEET" else cut_dim
                        length = f"{a+65+5}X{l1}X4,{a+65+5}X{l2}X4" if is_corner and rm1 == "AL SHEET" else f"{a+65+5}X{l1}X4" if rm1 == "AL SHEET" else length
                        raw_materials.append({"code": rm1, "dimension": rm_dim, "remark": fg_section_map[fg_code_part], "quantity": 1, "length": length})
                        frappe.log_error(message=f"J {'Corner' if is_corner else 'Straight'}: A={a}, using RM1={rm1}, Cut={rm_dim}", title="J Section Logic")
                        if rm2 != "-" and not ((25 <= a <= 50 and b == 100) or (25 <= b <= 50 and a == 100)):
                            for (min_b, max_b), rm2 in j_l_sections.items():
                                if min_b <= b <= max_b:
                                    raw_materials.append({"code": rm2, "dimension": cut_dim, "remark": "J SECTION", "quantity": 1, "length": length})
                                    frappe.log_error(message=f"J {'Corner' if is_corner else 'Straight'}: B={b}, using RM2={rm2}, Cut={cut_dim}", title="J Section Logic")
                                    break
                        break
            
            if fg_code_part in ["SX", "SXC", "SXCE", "LSX", "LSXC", "SXCZ", "SXCY", "LSXCK", "LSXCE", "LSXCEK"]:
                side_rail_dim = f"{b-16+5}" if any(rm["code"] == "J SEC" for rm in raw_materials) else f"{b-12+5}"
                stiff_qty = 5 if fg_code_part == "SX" else 2
                child_parts.append({"code": "SIDE RAIL", "dimension": side_rail_dim, "remark": "CHILD PART", "quantity": 2, "length": side_rail_dim})
                raw_materials.append({"code": "SIDE RAIL", "dimension": side_rail_dim, "remark": "CHILD PART", "quantity": 2, "length": side_rail_dim})
                stiff_dim = f"{a-4}X{b-12+5}X4" if any(rm["code"] == "J SEC" for rm in raw_materials) else f"{a-4}X{b-12+5}X4"
                child_parts.append({"code": "STIFF PLATE", "dimension": stiff_dim, "remark": "CHILD PART", "quantity": stiff_qty, "length": stiff_dim})
                raw_materials.append({"code": "STIFF PLATE", "dimension": stiff_dim, "remark": "CHILD PART", "quantity": stiff_qty, "length": stiff_dim})

        elif fg_code_part in t_straight:
            cut_dim = str(l1)
            length = str(l1)
            if fg_code_part in ["WRBSE", "WRSE"] and not degree_cutting:
                cut_dim = f"{l1-50+5}"
                length = f"{l1-50+5}"
            
            for key, (rm1, rm2, rm3) in t_sections.items():
                if isinstance(key, tuple) and len(key) == 2:
                    if key[0] <= a <= key[1]:
                        raw_materials.append({"code": rm1, "dimension": cut_dim, "remark": fg_section_map[fg_code_part], "quantity": 1, "length": length})
                        if rm2 != "-":
                            raw_materials.append({"code": rm2, "dimension": cut_dim, "remark": fg_section_map[fg_code_part], "quantity": 1, "length": length})
                        if rm3 != "-":
                            raw_materials.append({"code": rm3, "dimension": cut_dim, "remark": fg_section_map[fg_code_part], "quantity": 2 if rm3 == "EC" else 1, "length": length})
                        frappe.log_error(message=f"T Straight: A={a}, using RM1={rm1}, RM2={rm2}, RM3={rm3}, Cut={cut_dim}", title="T Section Logic")
                        break
                elif isinstance(key, tuple) and len(key) == 1:
                    if a == key[0]:
                        raw_materials.append({"code": rm1, "dimension": cut_dim, "remark": fg_section_map[fg_code_part], "quantity": 1, "length": length})
                        if rm2 != "-":
                            raw_materials.append({"code": rm2, "dimension": cut_dim, "remark": fg_section_map[fg_code_part], "quantity": 2 if rm2 == "EC" else 1, "length": length})
                        if rm3 != "-":
                            raw_materials.append({"code": rm3, "dimension": cut_dim, "remark": fg_section_map[fg_code_part], "quantity": 2 if rm3 == "EC" else 1, "length": length})
                        frappe.log_error(message=f"T Straight: A={a}, using RM1={rm1}, RM2={rm2}, RM3={rm3}, Cut={cut_dim}", title="T Section Logic")
                        break
            
            side_rail_qty = 1 if degree_cutting and fg_code_part in ["WRBSE", "WRSE"] else 2
            side_rail_dim = f"{a-131+5}" if any(rm["code"].endswith("T") for rm in raw_materials) else f"{a-146+5}"
            if fg_code_part in ["TSE", "WRBSE", "WRSE"]:
                side_rail_dim = f"{a-146+5}" if any(rm["code"].endswith("T") or rm["code"].endswith("CH") for rm in raw_materials) else f"{a-146+5}"
            
            child_parts.append({"code": "SIDE RAIL", "dimension": side_rail_dim, "remark": "CHILD PART", "quantity": side_rail_qty, "length": side_rail_dim})
            raw_materials.append({"code": "SIDE RAIL", "dimension": side_rail_dim, "remark": "CHILD PART", "quantity": side_rail_qty, "length": side_rail_dim})
            
            if fg_code_part in ["WRBSE", "WRSE"] and not degree_cutting:
                child_parts.append({"code": "RK-50", "dimension": f"{a-130+5}", "remark": "CHILD PART", "quantity": 1, "length": f"{a-130+5}"})
                raw_materials.append({"code": "RK-50", "dimension": f"{a-130+5}", "remark": "CHILD PART", "quantity": 1, "length": f"{a-130+5}"})
            
            if fg_code_part in ["TSE", "WRBSE", "WRSE", "WSE", "WXSE"]:
                stiff_dim = side_rail_dim
                u_stiff_qty = 5 if fg_code_part == "TSE" else 8
                child_parts.append({"code": "U STIFFNER", "dimension": stiff_dim, "remark": "CHILD PART", "quantity": u_stiff_qty, "length": stiff_dim})
                raw_materials.append({"code": "U STIFFNER", "dimension": stiff_dim, "remark": "CHILD PART", "quantity": u_stiff_qty, "length": stiff_dim})
            
            if fg_code_part in ["WRBSE", "WRSE", "WSE", "WXSE"]:
                child_parts.append({"code": "H STIFFNER", "dimension": side_rail_dim, "remark": "CHILD PART", "quantity": 2, "length": side_rail_dim})
                raw_materials.append({"code": "H STIFFNER", "dimension": side_rail_dim, "remark": "CHILD PART", "quantity": 2, "length": side_rail_dim})
            
            if fg_code_part in ["PCE", "SBE"]:
                child_parts.append({"code": "I STIFFNER", "dimension": side_rail_dim, "remark": "CHILD PART", "quantity": 8, "length": side_rail_dim})
                raw_materials.append({"code": "I STIFFNER", "dimension": side_rail_dim, "remark": "CHILD PART", "quantity": 8, "length": side_rail_dim})

        elif fg_code_part in misc_straight:
            cut_dim = str(l1 + 150 + 5) if fg_code_part == "MB" and a == 150 else str(l1 + 100 + 5) if fg_code_part == "MB" and a == 100 else str(l1)
            length = cut_dim
            key = (a, fg_code_part) if fg_code_part in ["EB", "MB", "DP", "RK"] else (a,)
            if key in misc_sections:
                rm1, rm2 = misc_sections[key]
                raw_materials.append({"code": rm1, "dimension": cut_dim, "remark": fg_section_map[fg_code_part], "quantity": 1, "length": length})
                if rm2 != "-":
                    raw_materials.append({"code": rm2, "dimension": cut_dim, "remark": fg_section_map[fg_code_part], "quantity": 1, "length": length})
                frappe.log_error(message=f"Misc Straight: A={a}, FG={fg_code_part}, using RM1={rm1}, Cut={cut_dim}", title="Misc Section Logic")
            elif fg_code_part == "RK" and a != 50:
                for (min_a, max_a), (rm1, rm2) in ic_l_sections.items():
                    if min_a <= a <= max_a:
                        raw_materials.append({"code": rm1, "dimension": cut_dim, "remark": "MISC SECTION", "quantity": 1, "length": length})
                        frappe.log_error(message=f"Misc Straight: RK with A={a}, using RM1={rm1}, Cut={cut_dim}, Remark=MISC SECTION", title="Misc Section Logic")
                        break
            
            if fg_code_part == "DP":
                child_parts.append({"code": "ROUND PIPE", "dimension": "196", "remark": "CHILD PART", "quantity": 1, "length": "196"})
                raw_materials.append({"code": "ROUND PIPE", "dimension": "196", "remark": "CHILD PART", "quantity": 1, "length": "196"})
            
            if a == 150:
                child_parts.append({"code": "SQUARE PLATE", "dimension": "150X150X4", "remark": "CHILD PART", "quantity": 1, "length": "150X150X4"})
                raw_materials.append({"code": "SQUARE PLATE", "dimension": "150X150X4", "remark": "CHILD PART", "quantity": 1, "length": "150X150X4"})
            
            if fg_code_part in ["EB", "MB"] and a == 150:
                child_parts.append({"code": "SUPPORT PIPE", "dimension": "105", "remark": "CHILD PART", "quantity": 1, "length": "105"})
                raw_materials.append({"code": "SUPPORT PIPE", "dimension": "105", "remark": "CHILD PART", "quantity": 1, "length": "105"})
        
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


@frappe.whitelist()
def create_stock_entry_client(items, project=None):
    if isinstance(items, str):
        items = json.loads(items)

    if not items:
        frappe.throw("No items provided for Stock Entry")

    se = frappe.new_doc("Stock Entry")
    se.stock_entry_type = "Material Transfer"
    se.from_warehouse = "Raw Material - VD"
    se.to_warehouse = "Reserved Stock - VD"
    se.company = "Vidhi (Demo)"
    se.purpose = "Material Transfer"
    se.project = project

    # Default warehouses
    source_wh_default = "Raw Material - VD"
    target_wh_default = "Reserved Stock - VD"

    for idx, item in enumerate(items, start=1):
        source_wh = (item.get("s_warehouse") or source_wh_default).strip()
        target_wh = (item.get("t_warehouse") or target_wh_default).strip()

        if not frappe.db.exists("Warehouse", source_wh):
            frappe.throw(f"Invalid Source Warehouse '{source_wh}' for row {idx}")
        if not frappe.db.exists("Warehouse", target_wh):
            frappe.throw(f"Invalid Target Warehouse '{target_wh}' for row {idx}")

        se.append("items", {
            "item_code": item.get("item_code"),
            "qty": flt(item.get("qty")),
            "uom": item.get("uom") or "Nos",
            "stock_uom": item.get("uom") or "Nos",
            "s_warehouse": source_wh,
            "t_warehouse": target_wh,
            "basic_rate": flt(item.get("basic_rate")),
            "valuation_rate": flt(item.get("valuation_rate")),
            "allow_zero_valuation_rate": 0,
            "cost_center": "Main - VD",
            "project": project
        })

    frappe.logger().info(f"Final Stock Entry: {se.as_dict()}")
    se.insert(ignore_permissions=True)
    frappe.db.commit()

    return se.name


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

@frappe.whitelist()
def create_material_request(fg_selector_name):
    try:
        doc = frappe.get_doc("FG Raw Material Selector", fg_selector_name)

        groups = defaultdict(list)
        for row in doc.raw_materials:
            if row.status == "NIS":
                groups[row.item_code].append(row)

        if not groups:
            frappe.throw("No NIS items to create Material Request for.")

        mr = frappe.new_doc("Material Request")
        mr.material_request_type = "Purchase"
        mr.transaction_date = frappe.utils.nowdate()

        for item_code, group_rows in groups.items():
            total_length = 0.0
            total_piece_qty = 0.0
            uom = group_rows[0].uom if group_rows[0].uom else "Nos"

            for row in group_rows:
                dims = []
                if row.dimension:
                    dims += [flt(v.strip()) for v in row.dimension.split(',') if v.strip()]
                if dims:
                    total_length += sum(dims) * flt(row.quantity)
                else:
                    total_piece_qty += flt(row.quantity)

            if total_length > 0:
                required = math.ceil(total_length / 4820)
            else:
                required = math.ceil(total_piece_qty)

            available = group_rows[0].available_quantity

            shortfall = required - available if available < required else 0

            if shortfall > 0:
                mr.append("items", {
                    "item_code": item_code,
                    "qty": shortfall,
                    "uom": uom,
                    "schedule_date": frappe.utils.nowdate(),
                    "description": f"Consolidated shortfall for NIS item {item_code} from FG Raw Material Selector {fg_selector_name}. Linked reserve tags: {', '.join([str(row.name) for row in group_rows])}",
                })

        if mr.items:
            mr.insert(ignore_permissions=True)
            frappe.db.commit()
            return mr.name
        else:
            return "No shortfalls to request."

    except Exception as e:
        frappe.log_error(message=f"Error creating Material Request: {str(e)}", title="FG Raw Material Error")
        

@frappe.whitelist()
def create_offcut_stock_entry(fg_selector_name, item_code, remaining_length, rate=0, is_fresh=True):
    try:
        if remaining_length <= 0:
            frappe.throw("No valid offcut length to create entry for.")

        doc = frappe.get_doc("FG Raw Material Selector", fg_selector_name)
        # Validate item_code exists in raw_materials
        if not any(row.item_code == item_code for row in doc.raw_materials):
            frappe.throw(f"Item {item_code} not found in FG Selector {fg_selector_name}.")

        se = frappe.new_doc("Stock Entry")
        se.stock_entry_type = "Material Receipt"
        se.to_warehouse = "Off-Cut - VD"
        se.company = "Vidhi (Demo)"
        se.append("items", {
            "item_code": item_code,
            "qty": 1,  # Quantity is always 1 for a single offcut piece
            "uom": "Nos",
            "basic_rate": flt(rate),
            "valuation_rate": flt(rate),
            "custom_length": flt(remaining_length),  # Set the remaining length here (assumes custom field exists)
            "allow_zero_valuation_rate": 0,
            "cost_center": "Main - VD"
        })
        se.insert(ignore_permissions=True)
        frappe.db.commit()

        frappe.log_error(message=f"Offcut stock entry created for {item_code} with length {remaining_length}.", title="FG Offcut Debug")
        return se.name
    except Exception as e:
        frappe.log_error(message=f"Error creating offcut stock entry: {str(e)}", title="FG Raw Material Error")
        raise

from frappe import _
from collections import defaultdict

@frappe.whitelist()
def get_offcut_report(fg_selector_name):
    try:
        doc = frappe.get_doc("FG Raw Material Selector", fg_selector_name)
        
        # Group raw materials by item_code and collect all required cut lengths
        rm_groups = defaultdict(list)
        for row in doc.raw_materials:
            if row.dimension and row.quantity > 0:
                dims = [flt(v.strip()) for v in row.dimension.split(',') if v.strip()]
                for _ in range(int(row.quantity)):
                    rm_groups[row.item_code].extend(dims)
        
        report_data = []
        standard_length = 4820.0  # Standard stock length
        
        for item_code, cuts in rm_groups.items():
            if not cuts:
                continue
            
            # Process cuts sequentially
            current_piece_remaining = standard_length
            piece_count = 0
            last_remaining_per_piece = []
            
            for cut in sorted(cuts, reverse=True):  # Sort cuts in descending order
                if cut > standard_length:
                    frappe.log_error(
                        message=f"Cut length {cut} for {item_code} exceeds standard length {standard_length}",
                        title="FG Offcut Report Error"
                    )
                    continue
                
                # If cut doesn't fit in current piece, start a new piece
                if cut > current_piece_remaining:
                    if current_piece_remaining < standard_length:
                        last_remaining_per_piece.append({
                            "rm": item_code,
                            "remaining_length": current_piece_remaining,
                            "quantity": 1
                        })
                    current_piece_remaining = standard_length
                    piece_count += 1
                
                # Apply the cut
                current_piece_remaining -= cut
            
            # Add the last piece's remaining length if it's not fully used
            if current_piece_remaining < standard_length and piece_count > 0:
                last_remaining_per_piece.append({
                    "rm": item_code,
                    "remaining_length": current_piece_remaining,
                    "quantity": 1
                })
            
            # Aggregate quantities for identical remaining lengths
            from collections import Counter
            length_counts = Counter()
            for entry in last_remaining_per_piece:
                length_counts[entry['remaining_length']] += entry['quantity']
            
            # Add to report data
            for length, qty in length_counts.items():
                report_data.append({
                    "rm": item_code,
                    "remaining_length": length,
                    "quantity": qty
                })
        
        if not report_data:
            frappe.msgprint("No offcuts calculated based on current raw materials.")
            return []
        
        # Sort report by rm and then by remaining_length descending
        report_data.sort(key=lambda x: (x['rm'], -x['remaining_length']))
        
        return report_data
    
    except Exception as e:
        frappe.log_error(message=f"Error generating offcut report: {str(e)}", title="FG Offcut Report Error")
        frappe.throw(f"Failed to generate offcut report: {str(e)}")


@frappe.whitelist()
def reserve_stock(fg_selector_name):
    try:
        frappe.log_error(message=f"Reserving stock for FG Selector: {fg_selector_name}", title="FG Stock Debug")
        warehouses_to_check = ["Off-Cut - VD", "Raw Material - VD"]
        doc = frappe.get_doc("FG Raw Material Selector", fg_selector_name)

        # Group rows by item_code
        groups = defaultdict(list)
        for row in doc.raw_materials:
            groups[row.item_code].append(row)

        for item_code, group_rows in groups.items():
            total_length = 0.0
            total_piece_qty = 0.0
            uom = group_rows[0].uom if group_rows[0].uom else "Nos"

            # Consolidated length sum for the same item_code
            for row in group_rows:
                dims = []
                # If dimension is a comma-separated string
                if row.dimension:
                    dims += [flt(v.strip()) for v in row.dimension.split(',') if v.strip()]
                # Multiply length sum by row quantity
                if dims:
                    total_length += sum(dims) * flt(row.quantity)
                else:
                    total_piece_qty += flt(row.quantity)

            # Decide required qty based on length or pieces
            if total_length > 0:
                required = math.ceil(total_length / 4820)
                is_length_based = True
            else:
                required = math.ceil(total_piece_qty)
                is_length_based = False

            # Find warehouse with enough stock
            selected_wh = ""
            available = 0
            for wh in warehouses_to_check:
                qty = get_actual_qty(item_code, wh, uom)
                if qty >= required:
                    selected_wh = wh
                    available = qty
                    break
            if not selected_wh:
                available = sum(get_actual_qty(item_code, wh, uom) for wh in warehouses_to_check)

            if selected_wh:
                status = "IS"
                reserve_tag = 1
                warehouse = selected_wh
            else:
                status = "NIS"
                reserve_tag = 0
                warehouse = ""

            # Update all rows for this item_code
            for row in group_rows:
                row.db_set("status", status)
                row.db_set("reserve_tag", reserve_tag)
                row.db_set("warehouse", warehouse)
                row.db_set("available_quantity", available)

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
