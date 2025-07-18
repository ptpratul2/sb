// Copyright (c) 2025, ptpratul2@gmail.com and contributors
// For license information, please see license.txt

frappe.ui.form.on("Planning BOM", {
    refresh(frm) {
        if (!frm.is_new()) {
            // Add Consolidate button
            frm.add_custom_button("Consolidate Items", function () {
                if (!frm.doc.project_design_upload || frm.doc.project_design_upload.length === 0) {
                    frappe.msgprint("Please select at least one Project Design Upload document");
                    return;
                }
                
                frappe.confirm(
                    "This will replace all existing items with consolidated data from selected Project Design Upload documents. Continue?",
                    function() {
                        frappe.call({
                            method: "sb.sb.doctype.planning_bom.planning_bom.consolidate_project_design_uploads",
                            args: { docname: frm.doc.name },
                            callback(r) {
                                if (!r.exc && r.message) {
                                    frappe.msgprint(r.message.message);
                                    frm.reload_doc();
                                }
                            }
                        });
                    }
                );
            }, "Actions");

            // Add Preview button
            frm.add_custom_button("Preview Consolidation", function () {
                if (!frm.doc.project_design_upload || frm.doc.project_design_upload.length === 0) {
                    frappe.msgprint("Please select at least one Project Design Upload document");
                    return;
                }
                
                frappe.call({
                    method: "sb.sb.doctype.planning_bom.planning_bom.get_consolidation_preview",
                    args: { docname: frm.doc.name },
                    callback(r) {
                        if (!r.exc && r.message) {
                            show_consolidation_preview(r.message);
                        }
                    }
                });
            }, "Actions");

            // Add Summary button
            frm.add_custom_button("Show Summary", function () {
                frappe.call({
                    method: "sb.sb.doctype.planning_bom.planning_bom.get_project_design_upload_summary",
                    args: { docname: frm.doc.name },
                    callback(r) {
                        if (!r.exc && r.message) {
                            show_design_upload_summary(r.message);
                        }
                    }
                });
            }, "View");
        }
    },

    project_design_upload_on_form_rendered(frm) {
        // Auto-refresh summary when project design uploads are changed
        if (frm.doc.project_design_upload && frm.doc.project_design_upload.length > 0) {
            update_summary_section(frm);
        }
    }
});

// Show consolidation preview in a dialog
function show_consolidation_preview(data) {
    let preview_html = `
        <div class="consolidation-preview">
            <h4>Consolidation Preview</h4>
            <p><strong>Total Unique Items:</strong> ${data.total_unique_items}</p>
            <p><strong>Total Quantity:</strong> ${data.total_quantity}</p>
            <table class="table table-bordered">
                <thead>
                    <tr>
                        <th>FG Code</th>
                        <th>Item Code</th>
                        <th>Dimension</th>
                        <th>Quantity</th>
                        <th>Sources</th>
                        <th>Remark</th>
                    </tr>
                </thead>
                <tbody>
    `;
    
    data.preview.forEach(item => {
        preview_html += `
            <tr>
                <td>${item.fg_code || ''}</td>
                <td>${item.item_code || ''}</td>
                <td>${item.dimension || ''}</td>
                <td>${item.quantity}</td>
                <td>${item.source_count} document(s)</td>
                <td>${item.remark || ''}</td>
            </tr>
        `;
    });
    
    preview_html += `
                </tbody>
            </table>
        </div>
    `;
    
    frappe.msgprint({
        title: "Consolidation Preview",
        message: preview_html,
        wide: true
    });
}

// Show design upload summary
function show_design_upload_summary(data) {
    let summary_html = `
        <div class="design-upload-summary">
            <h4>Selected Project Design Upload Summary</h4>
            <p><strong>Total Documents:</strong> ${data.total_documents}</p>
            <p><strong>Total Items:</strong> ${data.total_items}</p>
            <table class="table table-bordered">
                <thead>
                    <tr>
                        <th>Document Name</th>
                        <th>Project</th>
                        <th>Upload Date</th>
                        <th>Item Count</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
    `;
    
    data.summary.forEach(doc => {
        summary_html += `
            <tr>
                <td><a href="/app/project-design-upload/${doc.name}" target="_blank">${doc.name}</a></td>
                <td>${doc.project || ''}</td>
                <td>${doc.upload_date || ''}</td>
                <td>${doc.item_count}</td>
                <td><span class="indicator ${doc.processed_status === 'Completed' ? 'green' : 'orange'}">${doc.processed_status || 'Pending'}</span></td>
            </tr>
        `;
    });
    
    summary_html += `
                </tbody>
            </table>
        </div>
    `;
    
    frappe.msgprint({
        title: "Project Design Upload Summary",
        message: summary_html,
        wide: true
    });
}

// Update summary section in the form
function update_summary_section(frm) {
    frappe.call({
        method: "sb.sb.doctype.planning_bom.planning_bom.get_project_design_upload_summary",
        args: { docname: frm.doc.name },
        callback(r) {
            if (!r.exc && r.message) {
                // You can add a custom HTML field to show this summary in the form
                // or display it as an indicator
                frm.dashboard.add_indicator(
                    __("Selected Documents: {0}", [r.message.total_documents]),
                    "blue"
                );
                frm.dashboard.add_indicator(
                    __("Total Items: {0}", [r.message.total_items]),
                    "green"
                );
            }
        }
    });
}

// Handle changes in project design upload multiselect
frappe.ui.form.on("BOM Multiselect", {
    project_design_upload_add(frm, cdt, cdn) {
        update_summary_section(frm);
    },
    
    project_design_upload_remove(frm, cdt, cdn) {
        update_summary_section(frm);
    }
});