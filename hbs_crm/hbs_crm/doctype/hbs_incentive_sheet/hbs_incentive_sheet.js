// Copyright (c) 2026, Hbs and contributors
// For license information, please see license.txt

frappe.ui.form.on("Hbs Incentive Sheet", {
	onload(frm) {
		if (frm.is_new()) {
			if (!frm.doc.from_date) {
				frm.set_value("from_date", frappe.datetime.month_start());
			}
			if (!frm.doc.to_date) {
				frm.set_value("to_date", frappe.datetime.month_end());
			}
		}
	},
	refresh(frm) {
	}
});
