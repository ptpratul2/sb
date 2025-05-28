# Copyright (c) 2025, ptpratul2@gmail.com and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class ProjectDesignUpload(Document):
	pass


import frappe
import pandas as pd
from frappe.utils.file_manager import get_file_path

@frappe.whitelist()
def import_from_excel_on_submit(docname):
    doc = frappe.get_doc("Project Design Upload", docname)

    # Step 1: Locate attached Excel file
    file_path = None
    for file in frappe.get_all("File", filters={
        "attached_to_doctype": "Project Design Upload",
        "attached_to_name": doc.name
    }, fields=["file_url"]):
        path = get_file_path(file.file_url)
        if path.endswith((".xls", ".xlsx")):
            file_path = path
            break

    if not file_path:
        frappe.throw("No Excel file (.xls or .xlsx) is attached to this Project BOM.")

    # Step 2: Read Excel with header normalization
    df = pd.read_excel(file_path)
    
    # Normalize column names (remove spaces/special chars, make lowercase)
    df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_')
    df = df.where(pd.notnull(df), None)
    
    # Debug: Show what columns were found
    frappe.logger().debug(f"Excel columns after normalization: {list(df.columns)}")

    # Step 3: Get valid fields
    child_table_fieldname = "items"
    child_doctype = "FG Components"
    valid_fields = [f.fieldname for f in frappe.get_meta(child_doctype).fields]
    
    # Debug: Show field mapping
    frappe.logger().debug(f"Valid fields in {child_doctype}: {valid_fields}")

    # Step 4: Clear existing items
    doc.set(child_table_fieldname, [])

    # Step 5: Append rows with case-insensitive matching
    for _, row in df.iterrows():
        row_data = {}
        for col in row.index:
            # Case-insensitive match to fieldnames
            matched_field = next((f for f in valid_fields if f.lower() == col.lower()), None)
            if matched_field:
                row_data[matched_field] = row[col]
            else:
                frappe.logger().debug(f"Ignoring column '{col}' - no matching field in {child_doctype}")
        
        if row_data:  # Only append if we found matching fields
            frappe.logger().debug(f"Adding row with data: {row_data}")
            doc.append(child_table_fieldname, row_data)
        else:
            frappe.logger().debug(f"Skipping empty row: {dict(row)}")

    # Step 6: Save
    try:
        doc.save()
        frappe.msgprint(f"Successfully imported {len(df)} rows to {child_table_fieldname}")
        return {"status": "success", "rows": len(df)}
    except Exception as e:
        frappe.log_error(f"Error importing Excel data: {str(e)}")
        frappe.throw("Failed to import data. Please check error logs.")