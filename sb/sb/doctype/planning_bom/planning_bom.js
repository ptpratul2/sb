// Copyright (c) 2025
// For license information, see license.txt

frappe.ui.form.on("Planning BOM", {
    refresh(frm) {
        if (!frm.is_new()) {
            // ----- Button Group: Actions -----
            frm.add_custom_button("📦 Consolidate Items", () => {
                if (!frm.doc.project_design_upload?.length) {
                    frappe.msgprint("⚠️ Please select at least one Project Design Upload document");
                    return;
                }
                frappe.confirm(
                    __("This will <b>replace</b> all existing items with data from the selected Project Design Upload documents.<br><br>Do you want to continue?"),
                    () => {
                        frappe.call({
                            method: "sb.sb.doctype.planning_bom.planning_bom.consolidate_project_design_uploads",
                            args: { docname: frm.doc.name },
                            freeze: true,
                            freeze_message: __("Processing..."),
                            callback(r) {
                                if (!r.exc && r.message) {
                                    frappe.msgprint({
                                        title: __("✅ Consolidation Complete"),
                                        message: r.message.message,
                                        indicator: "green"
                                    });
                                    frm.reload_doc();
                                }
                            }
                        });
                    }
                );
            }, __("🔧 Actions")).addClass("btn-primary");

            frm.add_custom_button("👁 Preview Items", () => {
                if (!frm.doc.project_design_upload?.length) {
                    frappe.msgprint("⚠️ Please select at least one Project Design Upload document");
                    return;
                }
                frappe.call({
                    method: "sb.sb.doctype.planning_bom.planning_bom.get_consolidation_preview",
                    args: { docname: frm.doc.name },
                    freeze: true,
                    freeze_message: __("Loading Preview..."),
                    callback(r) {
                        if (!r.exc && r.message) {
                            show_consolidation_preview(r.message);
                        }
                    }
                });
            }, __("🔧 Actions")).addClass("btn-info");

            // ----- Button Group: View -----
            frm.add_custom_button("📄 Show Summary", () => {
                frappe.call({
                    method: "sb.sb.doctype.planning_bom.planning_bom.get_project_design_upload_summary",
                    args: { docname: frm.doc.name },
                    freeze: true,
                    freeze_message: __("Fetching Summary..."),
                    callback(r) {
                        if (!r.exc && r.message) {
                            show_design_upload_summary(r.message);
                        }
                    }
                });
            }, __("📊 View")).addClass("btn-secondary");
        }
    },

    project_design_upload_on_form_rendered(frm) {
        if (frm.doc.project_design_upload?.length) {
            update_summary_section(frm);
        }
    }
});

// ------------------ UI Helper Functions ------------------

// Consolidation Preview
function show_consolidation_preview(data) {
    let preview_html = `
        <div class="consolidation-preview">
            <h4 class="mb-3">📦 Consolidation Preview</h4>
            <p>
                <span class="badge badge-primary">Total Items: ${data.preview.length}</span>
                <span class="badge badge-success">Total Quantity: ${data.total_quantity}</span>
                <span class="badge badge-info">Total Unit Area: ${data.total_unit_area}</span>
            </p>
            <table class="table table-sm table-hover">
                <thead class="thead-dark">
                    <tr>
                        <th>FG Code</th>
                        <th>Item Code</th>
                        <th>Dimension</th>
                        <th class="text-right">Quantity</th>
                        <th>Sources</th>
                    </tr>
                </thead>
                <tbody>
    `;
    data.preview.forEach(item => {
        preview_html += `
            <tr>
                <td>${frappe.utils.escape_html(item.fg_code || '')}</td>
                <td>${frappe.utils.escape_html(item.item_code || '')}</td>
                <td>${frappe.utils.escape_html(item.dimension || '')}</td>
                <td class="text-right"><b>${item.quantity}</b></td>
                <td><span class="badge badge-info">${item.source_count} doc(s)</span></td>
            </tr>
        `;
    });
    preview_html += `</tbody></table></div>`;

    frappe.msgprint({
        title: "📝 Consolidation Preview",
        message: preview_html,
        wide: true
    });
}

// Summary of PDUs
function show_design_upload_summary(data) {
    let summary_html = `
        <div class="design-upload-summary">
            <h4 class="mb-3">📄 Selected Project Design Upload Summary</h4>
            <p>
                <span class="badge badge-primary">Documents: ${data.total_documents}</span>
                <span class="badge badge-success">Total Items: ${data.total_items}</span>
            </p>
            <table class="table table-sm table-hover">
                <thead class="thead-dark">
                    <tr>
                        <th>Document Name</th>
                        <th>Project</th>
                        <th>Upload Date</th>
                        <th class="text-right">Item Count</th>
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
                <td class="text-right"><b>${doc.item_count}</b></td>
                <td><span class="indicator ${doc.processed_status === 'Completed' ? 'green' : 'orange'}">
                    ${doc.processed_status || 'Pending'}
                </span></td>
            </tr>
        `;
    });
    summary_html += `</tbody></table></div>`;

    frappe.msgprint({
        title: "📊 Project Design Upload Summary",
        message: summary_html,
        wide: true
    });
}

// Update Summary Dashboard Indicators
function update_summary_section(frm) {
    frappe.call({
        method: "sb.sb.doctype.planning_bom.planning_bom.get_project_design_upload_summary",
        args: { docname: frm.doc.name },
        callback(r) {
            if (!r.exc && r.message) {
                frm.dashboard.clear_headline();
                frm.dashboard.add_indicator(
                    `📄 Selected Documents: ${r.message.total_documents}`,
                    "blue"
                );
                frm.dashboard.add_indicator(
                    `📦 Total Items: ${r.message.total_items}`,
                    "green"
                );
                frm.dashboard.show();
            }
        }
    });
}

frappe.ui.form.on("BOM Multiselect", {
    project_design_upload_add(frm) {
        update_summary_section(frm);
    },
    project_design_upload_remove(frm) {
        update_summary_section(frm);
    }
});
