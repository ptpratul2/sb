// Copyright (c) 2025, ptpratul2@gmail.com and contributors
// For license information, please see license.txt

frappe.query_reports["Consolidated Raw Material Report"] = {
    filters: [
        {
            fieldname: "fg_raw_material_selector",
            label: "FG Raw Material Selector",
            fieldtype: "Link",
            options: "FG Raw Material Selector",
            reqd: 1
        }
    ]
};
