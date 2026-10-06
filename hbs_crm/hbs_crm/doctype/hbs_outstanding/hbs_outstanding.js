// Copyright (c) 2026, Hbs and contributors
// For license information, please see license.txt

frappe.ui.form.on("Hbs Outstanding", {
	refresh: function (frm) {
		// Render activity timeline matching Hbs Tally Renewal and Hbs Crm Lead
		render_activity_timeline(frm);

		// Load dynamic payment statuses from Hbs CRM Settings
		frappe.call({
			method: "hbs_crm.hbs_crm.doctype.hbs_outstanding.hbs_outstanding.get_outstanding_statuses",
			callback: function (r) {
				if (r.message && r.message.length) {
					frm._cached_payment_statuses = r.message;
					frm.set_df_property("payment_status", "options", r.message.join("\n"));
				}
			}
		});

		// Color status indicator
		if (frm.doc.status === "Cleared") {
			frm.dashboard.set_headline_alert(__("This bill is fully cleared."), "green");
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

		// Read-only guard for non-admin users (all bill fields strictly read-only)
		frappe.call({
			method: "hbs_crm.hbs_crm.doctype.hbs_crm_lead.hbs_crm_lead.check_is_admin_or_owner",
			callback: function (r) {
				if (!r.message) {
					frm.fields_dict && Object.keys(frm.fields_dict).forEach(function (f) {
						frm.set_df_property(f, "read_only", 1);
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
	// Clean up any existing dialog instance
	if (frm._follow_up_dialog) {
		try {
			frm._follow_up_dialog.hide();
			frm._follow_up_dialog.$wrapper && frm._follow_up_dialog.$wrapper.remove();
		} catch (e) {}
		frm._follow_up_dialog = null;
	}

	let status_options = frm._cached_payment_statuses;
	if (!status_options || !status_options.length) {
		if (frm.fields_dict.payment_status && frm.fields_dict.payment_status.df && frm.fields_dict.payment_status.df.options) {
			status_options = frm.fields_dict.payment_status.df.options.split("\n");
		} else {
			status_options = ["", "Payment Received"];
		}
	}

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
				label: __("Payment Status"),
				fieldname: "payment_status",
				fieldtype: "Select",
				options: status_options,
				default: frm.doc.payment_status || ""
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
			if (!values || !values.remarks || !values.remarks.trim()) {
				frappe.msgprint(__("Remark is required."));
				return;
			}

			let btn = d.get_primary_btn();
			btn.prop("disabled", true);

			frappe.call({
				method: "hbs_crm.hbs_crm.doctype.hbs_outstanding.hbs_outstanding.log_remark",
				args: {
					name: frm.doc.name,
					remark: values.remarks,
					payment_status: values.payment_status || ""
				},
				freeze: true,
				freeze_message: __("Saving follow-up remark..."),
				callback: function (res) {
					d.hide();
					try {
						d.$wrapper && d.$wrapper.modal("hide");
						setTimeout(function () {
							d.$wrapper && d.$wrapper.remove();
							$(".modal-backdrop").remove();
							$("body").removeClass("modal-open");
						}, 300);
					} catch (e) {}

					frm._follow_up_dialog = null;

					frappe.show_alert({
						message: (res && res.message && res.message.message) ? res.message.message : __("Follow-up remark logged successfully!"),
						indicator: "green"
					});

					frm.reload_doc();
				},
				error: function () {
					btn.prop("disabled", false);
				}
			});
		}
	});

	frm._follow_up_dialog = d;
	d.show();
}
