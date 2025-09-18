import frappe

def update_length_in_sle(doc, method):
    """
    Copy custom_length and custom_total_length from items into Stock Ledger Entries
    after document is submitted.
    """
    for item in doc.items:
        if not item.custom_length and not item.custom_total_length:
            continue

        sle_list = frappe.get_all(
            "Stock Ledger Entry",
            filters={"voucher_no": doc.name, "voucher_detail_no": item.name},
            fields=["name"]
        )
        for sle in sle_list:
            frappe.db.set_value(
                "Stock Ledger Entry",
                sle.name,
                {
                    "custom_length": item.custom_length,
                    "custom_total_length": item.custom_total_length or (
                        item.custom_length * item.qty if item.custom_length and item.qty else 0
                    )
                }
            )

def clear_length_in_sle(doc, method):
    """
    Reset custom_length and custom_total_length in Stock Ledger Entries
    when document is cancelled.
    """
    sle_list = frappe.get_all(
        "Stock Ledger Entry",
        filters={"voucher_no": doc.name},
        fields=["name"]
    )
    for sle in sle_list:
        frappe.db.set_value(
            "Stock Ledger Entry",
            sle.name,
            {
                "custom_length": 0,
                "custom_total_length": 0
            }
        )
