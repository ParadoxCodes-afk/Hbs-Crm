// Copyright (c) 2026, Hbs and contributors
// For license information, please see license.txt

frappe.ui.form.on("Hbs Outstanding", {
	payment_status: function (frm) {
		// Changing payment status should only update payment_status, leave status untouched
	},
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

			frm.add_custom_button(__("Send email to client"), function () {
				open_outstanding_email_dialog(frm);
			}, __("Action"));
		}

		// Read-only guard for non-admin users (bill fields strictly read-only)
		frappe.call({
			method: "hbs_crm.hbs_crm.doctype.hbs_crm_lead.hbs_crm_lead.check_is_admin_or_owner",
			callback: function (r) {
				if (!r.message) {
					frm.fields_dict && Object.keys(frm.fields_dict).forEach(function (f) {
						if (f !== "payment_status") {
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
			},
			{
				label: __("Attach Doc"),
				fieldname: "attachment",
				fieldtype: "Attach",
				description: __("Attach payment screenshot or document shared by client.")
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
					payment_status: values.payment_status || "",
					attachment: values.attachment || ""
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

function open_outstanding_email_dialog(frm) {
	if (frm.is_dirty()) {
		frm.save(() => {
			open_outstanding_email_dialog(frm);
		});
		return;
	}

	frappe.call({
		method: "hbs_crm.hbs_crm.doctype.hbs_outstanding.hbs_outstanding.get_rendered_outstanding_email_template",
		args: { outstanding_name: frm.doc.name },
		freeze: true,
		freeze_message: __("Loading email template..."),
		callback: function (res) {
			if (res.message) {
				let default_subject = res.message.subject;
				let default_message = res.message.message;
				let default_from = res.message.from_email;
				let default_sender = res.message.sender_name;
				let client_email = (res.message.to_email || "").trim();
				let default_cc = res.message.cc_email ||
					(frappe.boot && frappe.boot.user && frappe.boot.user.email) ||
					(frappe.user_info && frappe.user_info[frappe.session.user] && frappe.user_info[frappe.session.user].email) ||
					(frappe.session.user && frappe.session.user.indexOf("@") !== -1 ? frappe.session.user : "");

				if (!client_email) {
					frappe.msgprint({
						title: __("Client Email"),
						indicator: "orange",
						message: __("<b>Client email was not automatically found for this Party!</b><br>Please enter the client's email in the <b>To (Client Email)</b> field in the dialog.")
					});
				}

				let attached_files = [];

				let d = new frappe.ui.Dialog({
					title: __("Enter email details"),
					size: "large",
					fields: [
						{
							label: __("Sender Name"),
							fieldname: "sender_name",
							fieldtype: "Data",
							default: default_sender,
							reqd: 1
						},
						{
							label: __("From Email"),
							fieldname: "from_email",
							fieldtype: "Data",
							default: default_from,
							reqd: 1
						},
						{
							label: __("To (Client Email)"),
							fieldname: "to_email",
							fieldtype: "Data",
							default: client_email,
							reqd: 1,
							description: __("Client's email address")
						},
						{
							label: __("CC (Executive / Internal)"),
							fieldname: "cc_email",
							fieldtype: "Data",
							default: default_cc,
							description: __("Executive email copy")
						},
						{
							label: __("Subject"),
							fieldname: "subject",
							fieldtype: "Data",
							default: default_subject,
							reqd: 1
						},
						{
							label: __("Message"),
							fieldname: "message",
							fieldtype: "Text Editor",
							default: default_message,
							reqd: 1
						},
						{
							fieldtype: "Section Break",
							label: __("Attachments")
						},
						{
							label: __("Attach Document"),
							fieldname: "attach_btn",
							fieldtype: "Button",
							click: function() {
								new frappe.ui.FileUploader({
									doctype: "Hbs Outstanding",
									docname: frm.doc.name,
									allow_multiple: true,
									on_success(file_doc) {
										if (file_doc) {
											if (Array.isArray(file_doc)) {
												file_doc.forEach(f => {
													if (f && f.file_url) attached_files.push({ file_name: f.file_name, file_url: f.file_url });
												});
											} else if (file_doc.file_url) {
												attached_files.push({ file_name: file_doc.file_name, file_url: file_doc.file_url });
											}
											render_attached_files();
										}
									}
								});
							}
						},
						{
							fieldtype: "HTML",
							fieldname: "attached_files_html",
							label: __("Attached Files")
						}
					],
					primary_action_label: __("Send"),
					primary_action(values) {
						if (!values.to_email || !values.to_email.trim()) {
							frappe.msgprint(__("Recipient 'To' Email is required."));
							return;
						}
						let extra_urls = attached_files.map(f => f.file_url).filter(u => u);
						frappe.call({
							method: "hbs_crm.hbs_crm.doctype.hbs_outstanding.hbs_outstanding.send_manual_outstanding_email",
							args: {
								outstanding_name: frm.doc.name,
								sender_name: values.sender_name,
								from_email: values.from_email,
								to_email: values.to_email,
								cc_email: values.cc_email,
								subject: values.subject,
								message: values.message,
								extra_attachments: JSON.stringify(extra_urls)
							},
							freeze: true,
							freeze_message: __("Sending email with attachments..."),
							callback: function (r) {
								if (!r.exc) {
									d.hide();
									frappe.show_alert({
										message: __("Email sent successfully to {0}!", [values.to_email]),
										indicator: "green"
									});
									frm.reload_doc();
								}
							}
						});
					}
				});

				function render_attached_files() {
					if (attached_files.length === 0) {
						d.set_df_property("attached_files_html", "options", '<div class="text-muted" style="font-size: 12px; margin-top: 5px;">No additional documents attached. Click the button above to upload invoice copies, payment receipts, or other files.</div>');
						return;
					}
					let html = '<div style="display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px;">';
					attached_files.forEach((f, idx) => {
						let fname = frappe.utils.escape_html(f.file_name || f.file_url.split("/").pop());
						html += `
							<span style="display: inline-flex; align-items: center; background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 6px; padding: 4px 10px; font-size: 13px; color: #1e40af;">
								<span style="margin-right: 8px;">📄 <b>${fname}</b></span>
								<span class="btn-remove-attachment" data-idx="${idx}" style="cursor: pointer; color: #ef4444; font-weight: bold; font-size: 16px; line-height: 1;" title="Remove this file">×</span>
							</span>
						`;
					});
					html += '</div>';
					d.set_df_property("attached_files_html", "options", html);

					d.$wrapper.find(".btn-remove-attachment").off("click").on("click", function() {
						let remove_idx = parseInt($(this).attr("data-idx"), 10);
						attached_files.splice(remove_idx, 1);
						render_attached_files();
					});
				}

				render_attached_files();
				d.show();
			}
		}
	});
}

