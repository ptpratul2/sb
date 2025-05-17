# Copyright (c) 2025, ptpratul2@gmail.com and contributors
# For license information, please see license.txt
import frappe
from frappe.model.document import Document

class FGRawMaterialSelector(Document):
    def validate(self):
        if self.fg_code:
            self.raw_materials = []  # Clear existing raw materials
            self.process_fg_code()

    def process_fg_code(self):
        def safe_int(val, default=0):
            try:
                return int(val)
            except (ValueError, TypeError):
                return default

        try:
            # Log raw input
            frappe.log_error(message=f"Raw FG Code: {self.fg_code}", title="FG Raw Material Input")
            
            # Handle mixed delimiters
            parts = self.fg_code.replace("|-|", "|").split("|")
            frappe.log_error(message=f"Server-Side Parts: {parts}", title="FG Raw Material Parts")

            if len(parts) != 4:
                frappe.throw(f"Invalid FG Code format. Expected 4 parts (A|B|L1|L2), got {len(parts)}: {parts}")

            a = safe_int(parts[0])
            b = parts[1]
            l1 = safe_int(parts[2])
            l2 = safe_int(parts[3])

            frappe.log_error(message=f"Parsed: A={a}, B={b}, L1={l1}, L2={l2}", title="FG Raw Material Parsed")

        except Exception as e:
            frappe.throw(f"Error parsing FG Code: {str(e)}")

        # Define FG groups
        ch_straight = ["B", "CP", "CPP", "CPPP", "D", "K", "PC", "PH", "PLB", "SB", "T", "TS", "W", "WR", "WRB", "WS", "WX", "WXS"]
        ch_corner = ["BC", "BCE", "KC", "KCE"]
        wall_types = ["T", "TS", "W", "WR", "WRB", "WS", "WX", "WXS"]
        cp_like_types = ["CP", "CPP", "CPPP", "PH", "BC", "BCE"]  # Includes BC, BCE for pipes

        # Channel section mappings
        ch_sections = {
            50: "50-CHANNEL", 75: "75-CHANNEL", 100: "100-CHANNEL", 125: "125-CHANNEL",
            150: "150-CHANNEL", 175: "175-CHANNEL", 200: "200-CHANNEL", 250: "250-CHANNEL",
            300: "300-CHANNEL"
        }

        l_sections_straight = {
            (51, 125): ("130 L", "MAIN FRAME"), (126, 149): ("155 L", "MAIN FRAME"),
            (151, 174): ("180 L", "MAIN FRAME"), (176, 199): ("205 L", "MAIN FRAME"),
            (201, 225): ("230 L", "MAIN FRAME"), (226, 249): ("255 L", "MAIN FRAME"),
            (251, 275): ("280 L", "MAIN FRAME"), (276, 300): ("305 L", "MAIN FRAME"),
            (301, 325): ("180 L", "155 L"), (326, 350): ("180 L", "180 L"),
            (351, 375): ("205 L", "180 L"), (376, 400): ("205 L", "205 L"),
            (401, 425): ("230 L", "205 L"), (426, 450): ("230 L", "230 L"),
            (451, 475): ("255 L", "230 L"), (476, 500): ("255 L", "255 L"),
            (501, 525): ("280 L", "255 L"), (526, 550): ("280 L", "280 L"),
            (551, 575): ("305 L", "280 L"), (576, 600): ("305 L", "305 L")
        }

        l_sections_corner = {
            (51, 124): ("125L", "MAIN FRAME"), (126, 149): ("150L", "MAIN FRAME"),
            (151, 174): ("175L", "MAIN FRAME"), (176, 199): ("200L", "MAIN FRAME"),
            (201, 224): ("225L", "MAIN FRAME"), (226, 249): ("250L", "MAIN FRAME"),
            (251, 275): ("275L", "MAIN FRAME"), (276, 300): ("300L", "MAIN FRAME"),
            (301, 325): ("175L", "150L"), (326, 350): ("175L", "175L"),
            (351, 375): ("200L", "175L"), (376, 400): ("200L", "200L"),
            (401, 425): ("225L", "200L"), (426, 450): ("225L", "225L"),
            (451, 475): ("250L", "225L"), (476, 500): ("250L", "250L"),
            (501, 525): ("275L", "250L"), (526, 550): ("275L", "275L"),
            (551, 575): ("300L", "275L"), (576, 600): ("300L", "300L")
        }

        raw_materials = []

        # Determine RM group
        if b in ch_straight:
            section_map = l_sections_straight
        elif b in ch_corner:
            section_map = l_sections_corner
        else:
            frappe.throw(f"Invalid FG Type: {b}")

        # Determine Channel or L-section
        if a < 300 and a in ch_sections and a % 25 == 0:
            raw_materials.append({"code": ch_sections[a], "dimension": "-", "remark": "CHANNEL SECTION"})
        else:
            for (min_a, max_a), (rm1, rm2) in section_map.items():
                if min_a <= a <= max_a:
                    raw_materials.append({"code": rm1, "dimension": "-", "remark": "L SECTION 1"})
                    if rm2 != "MAIN FRAME":
                        raw_materials.append({"code": rm2, "dimension": "-", "remark": "L SECTION 2"})
                    break

        # Add child parts
        if b != "PLB":
            raw_materials.append({"code": "B SIDE RAIL", "dimension": "-16MM", "remark": "FOR ALL CH ITEMS EXCEPT PLB"})
        
        if b == "K" and l1 >= 1800:
            raw_materials.append({"code": "STIFFNER PLATE", "dimension": "-16X61X4 MM", "remark": "FOR K IF LENGTH 1800MM+ AND CORNER MADE WITH L SEC"})
        
        if b in cp_like_types:
            raw_materials.append({"code": "ROUND PIPE", "dimension": "146 MM", "remark": "FOR CP, CPP, CPPP, PH, BC, BCE"})
            raw_materials.append({"code": "SQUARE PIPE", "dimension": "80 MM", "remark": "FOR CP, CPP, CPPP, PH, BC, BCE"})
        
        if b == "WR":
            raw_materials.append({"code": "ROCKER", "dimension": "RK-50", "remark": "FOR WR"})
        
        if b in wall_types:
            raw_materials.append({"code": "STIFFNER U", "dimension": "-16MM", "remark": "FOR WALL"})
            raw_materials.append({"code": "STIFFNER H", "dimension": "-16MM", "remark": "FOR WALL"})
        
        if b in ["D", "SB", "PC", "B"]:
            raw_materials.append({"code": "STIFFNER I", "dimension": "-16MM", "remark": "FOR D, SB, PC, B"})

        # Log raw materials
        frappe.log_error(message=f"Raw Materials: {raw_materials}", title="FG Raw Material Output")

        # Populate child table
        for rm in raw_materials:
            self.append("raw_materials", {
                "raw_material_code": rm["code"],
                "item_code": rm["code"],  # Links to Item master
                "dimension": rm["dimension"],
                "remark": rm["remark"],
                "quantity": 1
            })

@frappe.whitelist()
def create_bom_from_fg_selector(fg_selector_name):
    fg_doc = frappe.get_doc("FG Raw Material Selector", fg_selector_name)
    bom = frappe.new_doc("BOM")
    bom.item = fg_doc.fg_code  # Assumes FG code is a valid Item
    for rm in fg_doc.raw_materials:
        bom.append("items", {
            "item_code": rm.item_code,
            "qty": rm.quantity
        })
    bom.save()
    return bom.name
