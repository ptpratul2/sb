# Copyright (c) 2025, ptpratul2@gmail.com and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
    columns = [
        {"label": _("FG Code"), "fieldname": "fg_code", "fieldtype": "Data", "width": 150},
        {"label": _("Raw Material Code"), "fieldname": "raw_material_code", "fieldtype": "Data", "width": 150},
        {"label": _("Dimension"), "fieldname": "dimension", "fieldtype": "Data", "width": 100},
        {"label": _("Remark"), "fieldname": "remark", "fieldtype": "Data", "width": 200},
        {"label": _("Quantity"), "fieldname": "quantity", "fieldtype": "Int", "width": 80}
    ]

    data = []
    fg_docs = frappe.get_all("FG Raw Material Selector", filters=filters, fields=["fg_code"])

    for fg in fg_docs:
        doc = frappe.get_doc("FG Raw Material Selector", fg.fg_code)
        for rm in doc.raw_materials:
            data.append({
                "fg_code": fg.fg_code,
                "raw_material_code": rm.raw_material_code,
                "dimension": rm.dimension,
                "remark": rm.remark,
                "quantity": rm.quantity
            })

    return columns, data