// Copyright (c) 2026, Hbs and contributors
// For license information, please see license.txt

frappe.ui.form.on("Hbs Outstanding", {
	refresh: function (frm) {
		// Color status indicator
		if (frm.doc.status === "Cleared") {
			frm.dashboard.set_headline_alert(__("This bill is fully cleared."), "green");
		} else if (frm.doc.overdue_days > 0) {
			frm.dashboard.set_headline_alert(
				__("Overdue by {0} days (Pending: ₹{1})", [frm.doc.overdue_days, frappe.format(frm.doc.pending_amt, { fieldtype: "Currency" })]),
				"orange"
			);
		}

		// Read-only guard for non-admin users
		frappe.call({
			method: "hbs_crm.hbs_crm.doctype.hbs_crm_lead.hbs_crm_lead.check_is_admin_or_owner",
			callback: function (r) {
				if (!r.message) {
					frm.disable_save();
					frm.fields_dict && Object.keys(frm.fields_dict).forEach(function (f) {
						frm.set_df_property(f, "read_only", 1);
					});
				}
			}
		});
	}
});
