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
    Consolidate multiple Project Design Upload documents into Planning BOM
    """
    doc = frappe.get_doc("Planning BOM", docname)
    
    if not doc.project_design_upload:
        frappe.throw("Please select at least one Project Design Upload document")
    
    # Clear existing items
    doc.set("items", [])
    
    # Dictionary to store consolidated items
    consolidated_items = {}
    
    # Process each selected Project Design Upload
    for row in doc.project_design_upload:
        design_upload_name = row.project_design_upload
        
        # Get the Project Design Upload document
        design_upload_doc = frappe.get_doc("Project Design Upload", design_upload_name)
        
        # Process each item in the design upload
        for item in design_upload_doc.items:
            # Create a unique key for consolidation
            # You can modify this key based on your consolidation logic
            key = f"{item.get('fg_code')}_{item.get('item_code')}_{item.get('dimension')}"
            
            if key in consolidated_items:
                # If item already exists, add quantities
                consolidated_items[key]['quantity'] = flt(consolidated_items[key].get('quantity', 0)) + flt(item.get('quantity', 0))
            else:
                # Create new consolidated item
                consolidated_items[key] = {
                    'fg_code': item.get('fg_code'),
                    'item_code': item.get('item_code'),
                    'dimension': item.get('dimension'),
                    'quantity': flt(item.get('quantity', 0)),
                    'remark': item.get('remark'),
                    'project': item.get('project'),
                    'ipo_name': item.get('ipo_name'),
                    # Add other fields as needed
                    'a': item.get('a'),
                    'b': item.get('b'),
                    'code': item.get('code'),
                    'l1': item.get('l1'),
                    'l2': item.get('l2'),
                    'dwg_no': item.get('dwg_no'),
                    'u_area': item.get('u_area'),
                    'source_document': design_upload_name  # Track source
                }
    
    # Add consolidated items to Planning BOM
    for item_data in consolidated_items.values():
        doc.append("items", item_data)
    
    # Save the document
    doc.save()
    
    return {
        "status": "success", 
        "message": f"Successfully consolidated {len(consolidated_items)} unique items from {len(doc.project_design_upload)} Project Design Upload documents"
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
        design_upload_doc = frappe.get_doc("Project Design Upload", row.project_design_upload)
        item_count = len(design_upload_doc.items)
        total_items += item_count
        
        summary.append({
            "name": row.project_design_upload,
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


@frappe.whitelist()
def get_consolidation_preview(docname):
    """
    Preview consolidation results without saving
    """
    doc = frappe.get_doc("Planning BOM", docname)
    
    if not doc.project_design_upload:
        return {"preview": []}
    
    consolidated_items = {}
    
    for row in doc.project_design_upload:
        design_upload_doc = frappe.get_doc("Project Design Upload", row.project_design_upload)
        
        for item in design_upload_doc.items:
            key = f"{item.get('fg_code')}_{item.get('item_code')}_{item.get('dimension')}"
            
            if key in consolidated_items:
                consolidated_items[key]['quantity'] += flt(item.get('quantity', 0))
                consolidated_items[key]['source_count'] += 1
                consolidated_items[key]['sources'].append(row.project_design_upload)
            else:
                consolidated_items[key] = {
                    'fg_code': item.get('fg_code'),
                    'item_code': item.get('item_code'),
                    'dimension': item.get('dimension'),
                    'quantity': flt(item.get('quantity', 0)),
                    'remark': item.get('remark'),
                    'project': item.get('project'),
                    'source_count': 1,
                    'sources': [row.project_design_upload]
                }
    
    preview = list(consolidated_items.values())
    
    return {
        "preview": preview,
        "total_unique_items": len(preview),
        "total_quantity": sum(item['quantity'] for item in preview)
    }