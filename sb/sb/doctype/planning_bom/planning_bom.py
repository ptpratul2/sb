# planning_bom.py
# Copyright (c) 2025, ptpratul2@gmail.com and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt


class PlanningBOM(Document):
    pass


@frappe.whitelist()
def consolidate_project_design_uploads(docname):
    """
    Append all items from selected Project Design Upload documents
    into Planning BOM without consolidation (as-is).
    """
    doc = frappe.get_doc("Planning BOM", docname)
    
    if not doc.project_design_upload:
        frappe.throw("Please select at least one Project Design Upload document")
    
    # Clear existing items
    doc.set("items", [])
    
    item_count = 0
    
    # Process each selected Project Design Upload
    for row in doc.project_design_upload:
        design_upload_name = row.project_design
        design_upload_doc = frappe.get_doc("Project Design Upload", design_upload_name)
        
        # Directly append each item without consolidation
        for item in design_upload_doc.items:
            doc.append("items", {
                'project_design_upload': item.get('parent'),
                'project_design_upload_item': item.get('name'),
                'fg_code': item.get('fg_code'),
                'item_code': item.get('item_code'),
                'dimension': item.get('dimension'),
                'quantity': flt(item.get('quantity', 0)),
                'remark': item.get('remark'),
                'project': item.get('project'),
                'ipo_name': item.get('ipo_name'),
                'a': item.get('a'),
                'b': item.get('b'),
                'code': item.get('code'),
                'l1': item.get('l1'),
                'l2': item.get('l2'),
                'dwg_no': item.get('dwg_no'),
                'u_area': item.get('u_area'),
                'source_document': design_upload_name
            })
            item_count += 1
    
    # Save the document
    doc.save()
    
    return {
        "status": "success",
        "message": f"Successfully appended {item_count} items from {len(doc.project_design_upload)} Project Design Upload documents without consolidation"
    }
@frappe.whitelist()
def get_consolidation_preview(docname):
    """
    Preview all items from selected Project Design Upload documents
    without consolidation (as-is).
    """
    doc = frappe.get_doc("Planning BOM", docname)
    
    if not doc.project_design_upload:
        return {"preview": []}
    
    preview = []
    total_qty = 0
    total_unit_area = 0

    for row in doc.project_design_upload:
        design_upload_doc = frappe.get_doc("Project Design Upload", row.project_design)
        
        for item in design_upload_doc.items:
            quantity = flt(item.get('quantity', 0))
            u_area = flt(item.get('u_area', 0))

            preview.append({
                'fg_code': item.get('fg_code'),
                'item_code': item.get('item_code'),
                'dimension': item.get('dimension'),
                'quantity': quantity,
                'u_area': u_area,  # ✅ include u_area in each row
                'project': item.get('project'),
                'source_document': row.project_design
            })

            total_qty += quantity
            total_unit_area += u_area  # ✅ accumulate while iterating
    
    return {
        "preview": preview,
        "total_items": len(preview),
        "total_quantity": total_qty,
        "total_unit_area": total_unit_area
    }

@frappe.whitelist()
def get_project_design_upload_summary(docname):
    """
    Get summary of selected Project Design Upload documents
    """
    doc = frappe.get_doc("Planning BOM", docname)
    
    if not doc.project_design_upload:
        return {"summary": []}
    
    summary = []
    total_items = 0
    
    for row in doc.project_design_upload:
        design_upload_doc = frappe.get_doc("Project Design Upload", row.project_design)
        item_count = len(design_upload_doc.items)
        total_items += item_count
        
        summary.append({
            "name": row.project_design,
            "project": design_upload_doc.project,
            "upload_date": design_upload_doc.upload_date,
            "item_count": item_count,
            "processed_status": design_upload_doc.processed_status
        })
    
    return {
        "summary": summary,
        "total_documents": len(doc.project_design_upload),
        "total_items": total_items
    }
