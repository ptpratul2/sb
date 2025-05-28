// Copyright (c) 2025, ptpratul2@gmail.com and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Project Design Upload", {
// 	refresh(frm) {

// 	},
// });


frappe.ui.form.on("Project Design Upload", {
    refresh(frm) {
        if (!frm.is_new()) {
            frm.add_custom_button("Submit", function () {
                frappe.call({
                    method: "sb.sb.doctype.project_design_upload.project_design_upload.import_from_excel_on_submit",
                    args: { docname: frm.doc.name },
                    callback(r) {
                        if (!r.exc) {
                            frappe.msgprint(`Imported ${r.message.rows} rows from Excel.`);
                            frm.reload_doc();
                        }
                    }
                });
            });
        }
    }
});

