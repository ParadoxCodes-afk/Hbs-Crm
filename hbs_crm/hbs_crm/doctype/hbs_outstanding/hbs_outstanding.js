// Copyright (c) 2026, Hbs and contributors
// For license information, please see license.txt

frappe.ui.form.on("Hbs Outstanding", {
	refresh: function (frm) {
		// Render activity timeline matching Hbs Tally Renewal and Hbs Crm Lead
		render_activity_timeline(frm);

		// Load dynamic statuses from Hbs CRM Settings
		frappe.call({
			method: "hbs_crm.hbs_crm.doctype.hbs_outstanding.hbs_outstanding.get_outstanding_statuses",
			callback: function (r) {
				if (r.message && r.message.length) {
					frm.set_df_property("status", "options", r.message.join("\n"));
				}
			}
		});

		// Color status indicator
		if (frm.doc.status === "Payment Received") {
			frm.dashboard.set_headline_alert(__("Payment Received for this bill."), "green");
		} else if (frm.doc.overdue_days > 0) {
			frm.dashboard.set_headline_alert(
				__("Overdue by {0} days (Pending: ₹{1})", [frm.doc.overdue_days, frappe.format(frm.doc.pending_amt, { fieldtype: "Currency" })]),
				"orange"
			);
		}

		frm.clear_custom_buttons();

		// Add Follow-up dialog button
		if (!frm.is_new()) {
			frm.add_custom_button(__("+ Follow-up"), function () {
				open_follow_up_dialog(frm);
			}).addClass("btn-primary");
		}

		// Read-only guard for non-admin users (all bill fields read-only; remarks field remains editable)
		frappe.call({
			method: "hbs_crm.hbs_crm.doctype.hbs_crm_lead.hbs_crm_lead.check_is_admin_or_owner",
			callback: function (r) {
				if (!r.message) {
					frm.fields_dict && Object.keys(frm.fields_dict).forEach(function (f) {
						if (f !== "remarks") {
							frm.set_df_property(f, "read_only", 1);
						}
					});
				}
			}
		});
	},

	after_save: function (frm) {
		render_activity_timeline(frm);
	}
});

function render_activity_timeline(frm) {
	if (frm.is_new() || !frm.doc.name) {
		if (frm.fields_dict.activity && frm.fields_dict.activity.$wrapper) {
			frm.fields_dict.activity.$wrapper.html("<div style='color:#a0aec0; font-style:italic; padding:10px;'>No activities recorded yet. Click <b>+ Follow-up</b> to log notes.</div>");
		}
		return;
	}

	if (frm.doc.activity && frm.doc.activity.trim() && frm.fields_dict.activity && frm.fields_dict.activity.$wrapper) {
		frm.fields_dict.activity.$wrapper.html(frm.doc.activity);
		return;
	}

	frappe.call({
		method: "hbs_crm.hbs_crm.doctype.hbs_outstanding.hbs_outstanding.get_activity_html",
		args: {
			name: frm.doc.name
		},
		callback: function (r) {
			if (r.message && frm.fields_dict.activity && frm.fields_dict.activity.$wrapper) {
				frm.fields_dict.activity.$wrapper.html(r.message);
			}
		}
	});
}

function open_follow_up_dialog(frm) {
	frappe.call({
		method: "hbs_crm.hbs_crm.doctype.hbs_outstanding.hbs_outstanding.get_outstanding_statuses",
		callback: function (r) {
			let status_options = r.message || ["", "Payment Received"];
			let d = new frappe.ui.Dialog({
				title: __("Log Follow-up Remark"),
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
						label: __("Status"),
						fieldname: "status",
						fieldtype: "Select",
						options: status_options,
						default: frm.doc.status || ""
					},
					{
						label: __("Remarks / Notes"),
						fieldname: "remarks",
						fieldtype: "Small Text",
						reqd: 1,
						description: __("Enter details of discussion, customer feedback, or payment commitment.")
					}
				],
				primary_action_label: __("Save Follow-up"),
				primary_action: function (values) {
					frappe.call({
						method: "hbs_crm.hbs_crm.doctype.hbs_outstanding.hbs_outstanding.log_remark",
						args: {
							name: frm.doc.name,
							remark: values.remarks,
							status: values.status || ""
						},
						freeze: true,
						freeze_message: __("Saving follow-up remark..."),
						callback: function (res) {
							if (res.message && res.message.status === "success") {
								d.hide();
								frappe.show_alert({
									message: res.message.message,
									indicator: "green"
								});
								frm.reload_doc();
							}
						}
					});
				}
			});
			d.show();
		}
	});
}
