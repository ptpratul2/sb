# Copyright (c) 2025, ptpratul2@gmail.com and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
    columns = [
        {"label": "WIDTH", "fieldname": "width", "fieldtype": "Float", "width": 100},
        {"label": "ITEM", "fieldname": "item", "fieldtype": "Data", "width": 100},
        {"label": "LENGTH", "fieldname": "length", "fieldtype": "Float", "width": 100},
        {"label": "DRAWING", "fieldname": "drawing", "fieldtype": "Data", "width": 120},
        {"label": "QTY", "fieldname": "qty", "fieldtype": "Int", "width": 80},
        {"label": "AREA", "fieldname": "area", "fieldtype": "Float", "width": 100},
        {"label": "RM1", "fieldname": "rm1", "fieldtype": "Data", "width": 100},
        {"label": "RM1 Length", "fieldname": "rm1_length", "fieldtype": "Float", "width": 100},
        {"label": "RM1 QTY", "fieldname": "rm1_qty", "fieldtype": "Int", "width": 80},
        {"label": "B-Side Rail Length", "fieldname": "b_side_rail_length", "fieldtype": "Float", "width": 120},
        {"label": "B-Side Rail QTY", "fieldname": "b_side_rail_qty", "fieldtype": "Int", "width": 100},
        {"label": "Plate Dimension", "fieldname": "plate_dimension", "fieldtype": "Data", "width": 120},
        {"label": "Plate QTY", "fieldname": "plate_qty", "fieldtype": "Int", "width": 80}
    ]

    data = frappe.db.get_all(
        "Cut Logic Details",
        filters={"parent": filters.get("fg_selector_name") or "2nnau2fijd"},
        fields=["width", "item", "length", "drawing", "qty", "area", "rm1", "rm1_length", "rm1_qty", "b_side_rail_length", "b_side_rail_qty", "plate_dimension", "plate_qty"],
        order_by="item"
    )

    return columns, data