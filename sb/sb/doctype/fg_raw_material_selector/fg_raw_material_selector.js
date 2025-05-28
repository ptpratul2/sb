frappe.ui.form.on('FG Raw Material Selector', {
    fg_code: function(frm) {
        let fg_code = (frm.doc.fg_code || "").trim();

        if (!fg_code) {
            frappe.msgprint({
                title: __("Invalid FG Code"),
                message: __("FG Code cannot be empty."),
                indicator: "red"
            });
            frm.set_value("fg_code", "");
            return;
        }

        const parts = fg_code.split("|");

        if (parts.length !== 5) {
            frappe.msgprint({
                title: __("Invalid FG Code"),
                message: __("FG Code must follow the format: a|b|fg|l1|l2"),
                indicator: "red"
            });
            frm.set_value("fg_code", "");
            return;
        }

        let [a, b, fg, l1, l2] = parts;

        if (!/^\d+$/.test(a)) {
            frappe.msgprint({ title: __("Invalid FG Code"), message: __("First part (a) must be a number."), indicator: "red" });
            frm.set_value("fg_code", "");
            return;
        }

        if (!(b === "-" || /^\d+$/.test(b))) {
            frappe.msgprint({ title: __("Invalid FG Code"), message: __("Second part (b) must be '-' or a number."), indicator: "red" });
            frm.set_value("fg_code", "");
            return;
        }

        if (!/^[A-Z]+$/.test(fg)) {
            frappe.msgprint({ title: __("Invalid FG Code"), message: __("Third part (fg) must be uppercase letters."), indicator: "red" });
            frm.set_value("fg_code", "");
            return;
        }

        if (!/^\d+$/.test(l1)) {
            frappe.msgprint({ title: __("Invalid FG Code"), message: __("Fourth part (l1) must be a number."), indicator: "red" });
            frm.set_value("fg_code", "");
            return;
        }

        if (!(l2 === "-" || /^\d+$/.test(l2))) {
            frappe.msgprint({ title: __("Invalid FG Code"), message: __("Fifth part (l2) must be a number or '-'."), indicator: "red" });
            frm.set_value("fg_code", "");
            return;
        }

        // You may use normalized value internally if needed
        const normalized_l2 = l2 === "-" ? "" : l2;

        console.log("FG Code Parts:", {
            a, b, fg, l1, l2: normalized_l2
        });

        // ✅ Do not set back the normalized fg_code on the form!
        // frm.set_value("fg_code", normalized_fg_code); <-- don't do this

        // Optionally store cleaned parts into hidden fields if needed:
        // frm.set_value("parsed_l2", normalized_l2);

        frm.refresh();
    }
});
