// frappe.ui.form.on('FG Raw Material Selector', {
//     fg_code: function(frm) {
//         let fg_code = (frm.doc.fg_code || "").trim();

//         if (!fg_code) {
//             frappe.msgprint({
//                 title: __("Invalid FG Code"),
//                 message: __("FG Code cannot be empty."),
//                 indicator: "red"
//             });
//             frm.set_value("fg_code", "");
//             return;
//         }

//         const parts = fg_code.split("|");

//         if (parts.length !== 5) {
//             frappe.msgprint({
//                 title: __("Invalid FG Code"),
//                 message: __("FG Code must follow the format: a|b|fg|l1|l2"),
//                 indicator: "red"
//             });
//             frm.set_value("fg_code", "");
//             return;
//         }

//         let [a, b, fg, l1, l2] = parts;

//         if (!/^\d+$/.test(a)) {
//             frappe.msgprint({ title: __("Invalid FG Code"), message: __("First part (a) must be a number."), indicator: "red" });
//             frm.set_value("fg_code", "");
//             return;
//         }

//         if (!(b === "-" || /^\d+$/.test(b))) {
//             frappe.msgprint({ title: __("Invalid FG Code"), message: __("Second part (b) must be '-' or a number."), indicator: "red" });
//             frm.set_value("fg_code", "");
//             return;
//         }

//         if (!/^[A-Z]+$/.test(fg)) {
//             frappe.msgprint({ title: __("Invalid FG Code"), message: __("Third part (fg) must be uppercase letters."), indicator: "red" });
//             frm.set_value("fg_code", "");
//             return;
//         }

//         if (!/^\d+$/.test(l1)) {
//             frappe.msgprint({ title: __("Invalid FG Code"), message: __("Fourth part (l1) must be a number."), indicator: "red" });
//             frm.set_value("fg_code", "");
//             return;
//         }

//         if (!(l2 === "-" || /^\d+$/.test(l2))) {
//             frappe.msgprint({ title: __("Invalid FG Code"), message: __("Fifth part (l2) must be a number or '-'."), indicator: "red" });
//             frm.set_value("fg_code", "");
//             return;
//         }

//         // You may use normalized value internally if needed
//         const normalized_l2 = l2 === "-" ? "" : l2;

//         console.log("FG Code Parts:", {
//             a, b, fg, l1, l2: normalized_l2
//         });

//         // ✅ Do not set back the normalized fg_code on the form!
//         // frm.set_value("fg_code", normalized_fg_code); <-- don't do this

//         // Optionally store cleaned parts into hidden fields if needed:
//         // frm.set_value("parsed_l2", normalized_l2);

//         frm.refresh();
//     }
// });



frappe.ui.form.on('FG Raw Material Selector', {
    project_design_upload: function(frm) {
        frm.refresh();
        // Add a custom button to fetch raw materials
        frm.add_custom_button(__('Fetch Raw Materials'), function() {
            // Get project_design_upload values from the child table
            let pdu_list = frm.doc.project_design_upload.map(row => row.project_design_upload).filter(pdu => pdu);
            if (!pdu_list.length) {
                frappe.msgprint(__('Please select at least one Project Design Upload.'));
                return;
            }
            frappe.call({
                method: 'sb.sb.doctype.fg_raw_material_selector.fg_raw_material_selector.get_raw_materials',
                args: {
                    project_design_upload: JSON.stringify(frm.doc.project_design_upload)
                },
                freeze: true,
                freeze_message: __('Fetching raw materials...'),
                callback: function(r) {
                    if (r.message) {
                        frm.clear_table('raw_materials');
                        r.message.forEach(rm => {
                            let row = frm.add_child('raw_materials');
                            Object.assign(row, rm);
                        });
                        frm.refresh_field('raw_materials');
                        frappe.msgprint(__('Raw materials fetched successfully.'));
                    }
                }
            });
        });

        // Customize raw_materials table display
        frm.fields_dict['raw_materials'].grid.get_field('project').get_query = function() {
            return {
                filters: {
                    "name": ["in", frm.doc.project_design_upload.map(row => frm.doc.project)]
                }
            };
        };
    }
});