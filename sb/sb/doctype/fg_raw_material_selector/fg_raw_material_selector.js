frappe.ui.form.on('FG Raw Material Selector', {
    fg_code: function(frm) {
        // Validate FG code format
        const fg_code = (frm.doc.fg_code || "").trim();
        if (!fg_code) {
            frappe.msgprint({
                title: __("Invalid FG Code"),
                message: __("FG Code cannot be empty."),
                indicator: "red"
            });
            frm.set_value("fg_code", "");
            return;
        }

        // Log input and character codes
        console.log("FG Code Input:", fg_code);
        console.log("Character Codes:", fg_code.split('').map(c => c.charCodeAt(0)));

        // Try regex first
        const regex = /^(\d+)\|\-\|([A-Z]+)\|(\d+)\|(\d+)$/;
        const match = fg_code.match(regex);
        console.log("Regex Match:", match);

        let a, b, l1, l2;
        if (match && match.length === 5) {
            [, a, b, l1, l2] = match;
            console.log("Regex Parsed Successfully");
        } else {
            // Fallback to manual splitting
            console.log("Regex failed, trying manual split");
            const parts = fg_code.split("|");
            console.log("Manual Split Parts:", parts);
            if (parts.length !== 5 || parts[1] !== "-") {
                console.log("Invalid split parts:", parts);
                frappe.msgprint({
                    title: __("Invalid FG Code"),
                    message: __("Expected format: A|-|B|L1|L2 (e.g., 125|-|BC|400|175). Must split into 5 parts with second part as '-'."),
                    indicator: "red"
                });
                frm.set_value("fg_code", "");
                return;
            }
            [a, , b, l1, l2] = parts;
        }

        // Log parsed components
        console.log("Parsed Components: A =", a, "B =", b, "L1 =", l1, "L2 =", l2);

        // Validate parts
        if (!a || !/^\d+$/.test(a)) {
            console.log("Invalid A:", a);
            frappe.msgprint({
                title: __("Invalid FG Code"),
                message: __("A must be a positive integer."),
                indicator: "red"
            });
            frm.set_value("fg_code", "");
            return;
        }

        if (!b || !/^[A-Z]+$/.test(b)) {
            console.log("Invalid B:", b);
            frappe.msgprint({
                title: __("Invalid FG Code"),
                message: __("B must be uppercase letters."),
                indicator: "red"
            });
            frm.set_value("fg_code", "");
            return;
        }

        if (!l1 || !/^\d+$/.test(l1)) {
            console.log("Invalid L1:", l1);
            frappe.msgprint({
                title: __("Invalid FG Code"),
                message: __("L1 must be a positive integer."),
                indicator: "red"
            });
            frm.set_value("fg_code", "");
            return;
        }

        if (['BC', 'BCE', 'KC', 'KCE'].includes(b) && (!l2 || !/^\d+$/.test(l2))) {
            console.log("Invalid L2:", l2);
            frappe.msgprint({
                title: __("Invalid FG Code"),
                message: __("L2 must be a positive integer for CH Corner types (BC, BCE, KC, KCE)."),
                indicator: "red"
            });
            frm.set_value("fg_code", "");
            return;
        }

        // Trigger server-side processing
        frm.refresh();
    }
});