frappe.ui.form.on('FG Raw Material Selector', {
    refresh: function(frm) {
        if (!frm.is_new()) {
            frm.add_custom_button(__('Fetch Raw Materials'), function () {
                if (!frm.doc.project_design_upload || frm.doc.project_design_upload.length === 0) {
                    frappe.msgprint(__('Please select at least one Project Design Upload.'));
                    return;
                }

                const pdu_list = frm.doc.project_design_upload.map(row => row.project_design_upload);
                frappe.show_alert({ message: __('Queuing raw material processing...'), indicator: 'blue' });

                frappe.call({
                    method: 'sb.sb.doctype.fg_raw_material_selector.fg_raw_material_selector.get_raw_materials',
                    args: {
                        docname: frm.doc.name,
                        project_design_upload: pdu_list
                    },
                    callback: function (r) {
                        if (!r.exc) {
                            frappe.show_alert({ message: __('Processing has been queued.'), indicator: 'green' });
                        }
                    }
                });
            }).addClass('btn-primary');
        }

        // Listen for real-time job completion
        frappe.realtime.on('fg_materials_done', function (data) {
            if (frm.doc.name === data.docname) {
                frappe.show_alert({ message: __('FG Raw Material processing is complete.'), indicator: 'green' });
                frm.reload_doc();
            }
        });
    }
});
