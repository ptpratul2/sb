# Copyright (c) 2025, ptpratul2@gmail.com and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class OffCutEntry(Document):
	pass
@frappe.whitelist()
def create_offcut_item(data):
	from frappe.model.naming import make_autoname

	# Create new item
	item = frappe.new_doc("Item") 
	item.item_code = data['generated_item_code'] 
	item.item_name = data['generated_item_code'] 
	item.item_group = "Raw Material" 
	item.is_stock_item = 1
	item.disabled = 0
	item.is_off_cut = 1
	item.original_length = data['original_length'] 
	item.original_rm_code = data['original_rm_code'] 
	item.design_code = data['design_code'] 
	item.barcode = data['barcode'] 
	item.insert(ignore_permissions=True)

	# Create Stock Entry to add 1 qty of this off-cut 
	stock_entry = frappe.new_doc("Stock Entry") 
	stock_entry.stock_entry_type = "Material Receipt" 
	stock_entry.append("items", {
	"item_code": item.item_code, "qty": 1,
	"t_warehouse": frappe.get_value("Item", item.item_code, "default_warehouse") or "Stores - WH"})
	stock_entry.insert(ignore_permissions=True) 
	stock_entry.submit()

	return "success"
