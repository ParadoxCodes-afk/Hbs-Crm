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
		// Add Remark dialog button
		if (!frm.is_new()) {
			frm.add_custom_button(__("+ Add Remark"), function () {
				let d = new frappe.ui.Dialog({
					title: __("Add Remark - Bill {0}", [frm.doc.bill_no]),
					fields: [
						{
							label: __("Party Name"),
							fieldname: "party_name",
							fieldtype: "Data",
							default: frm.doc.party_name,
							read_only: 1
						},
						{
							label: __("Pending Amount"),
							fieldname: "pending_amt",
							fieldtype: "Currency",
							default: frm.doc.pending_amt,
							read_only: 1
						},
						{
							label: __("Remark / Note"),
							fieldname: "remark",
							fieldtype: "Small Text",
							reqd: 1
						}
					],
					primary_action_label: __("Save Remark"),
					primary_action: function (values) {
						frappe.call({
							method: "hbs_crm.hbs_crm.doctype.hbs_outstanding.hbs_outstanding.log_remark",
							args: {
								name: frm.doc.name,
								remark: values.remark
							},
							freeze: true,
							freeze_message: __("Saving remark..."),
							callback: function (r) {
								if (r.message && r.message.status === "success") {
									d.hide();
									frappe.show_alert({
										message: r.message.message,
										indicator: "green"
									});
									frm.reload_doc();
								}
							}
						});
					}
				});
				d.show();
			}).addClass("btn-primary");
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
