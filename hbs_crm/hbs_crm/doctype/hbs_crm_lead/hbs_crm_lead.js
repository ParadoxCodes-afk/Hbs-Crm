// Copyright (c) 2026, Hbs and contributors
// For license information, please see license.txt

frappe.ui.form.on("Hbs Crm Lead", {
	onload(frm) {
		set_customer_details_read_only(frm);
		if (frm.is_new()) {
			if (!frm.doc.executive_1) {
				frm.set_value("executive_1", frappe.session.user);
			}
			if (!frm.doc.follow_up_date) {
				frm.set_value("follow_up_date", frappe.datetime.get_today());
			}
			if (!frm.doc.follow_up_time) {
				frm.set_value("follow_up_time", frappe.datetime.now_time());
			}
			if (!frm.doc.quotation_date) {
				frm.set_value("quotation_date", frappe.datetime.get_today());
			}
		}
		handle_executive_1_permission(frm);
	},

	refresh(frm) {
		render_activity_timeline_js(frm);
		toggle_won_status_read_only(frm);
		set_customer_details_read_only(frm);
		handle_lead_type_terms(frm);
		handle_referred_by_dependency(frm);
		handle_executive_1_permission(frm);
		apply_quotation_format_color(frm);
		frm.set_df_property("pi_number", "read_only", 1);

		frm.clear_custom_buttons();

		if (frm.doc.status !== "won" && frm.doc.status !== "lost") {
			let autofill_btn = frm.add_custom_button(__("🔍 Auto Fill Details"), function () {
				open_auto_fill_customer_dialog(frm);
			});
			if (frm.is_new()) {
				autofill_btn.addClass("btn-primary");
			}
		}

		if (!frm.is_new()) {
			if (frm.doc.status !== "won" && frm.doc.status !== "lost") {
				let last_date = frm.doc.last_remarks_date || (frm.doc.creation ? frm.doc.creation.split(" ")[0] : null);
				if (last_date) {
					let days = frappe.datetime.get_diff(frappe.datetime.get_today(), last_date);
					if (days >= 10) {
						frm.dashboard.set_headline_alert(
							__("⚠️ Overdue Follow-up: This lead has not received any follow-up remarks in the last {0} days!", [days]),
							"orange"
						);
					}
				}
			}

			frm.add_custom_button(__("📄 View Quotation"), function () {
				open_quotation_preview_dialog(frm, "Hbs Crm Lead");
			});

			if (frm.doc.status !== "won" && frm.doc.status !== "lost") {
				frm.add_custom_button(__("+ Follow-up"), function () {
					open_log_follow_up_dialog(frm);
				}).addClass("btn-primary");

				if (frm.doc.executive_1 !== frappe.session.user) {
					let last_date = frm.doc.creation;
					if (frm.doc.custom_activities && frm.doc.custom_activities.length > 0) {
						let dates = frm.doc.custom_activities
							.map(row => row.date_time)
							.filter(dt => dt);
						if (dates.length > 0) {
							dates.sort();
							last_date = dates[dates.length - 1];
						}
					}
					if (last_date) {
						let today = frappe.datetime.get_today();
						let diff = frappe.datetime.get_diff(today, last_date);
						if (diff > 15) {
							frm.add_custom_button(__("⚡ Take Over Lead"), function () {
								frappe.confirm(
									__("Are you sure you want to take over Lead #{0}? You will become Executive 1.", [frm.doc.name]),
									function () {
										frappe.call({
											method: "hbs_crm.hbs_crm.doctype.hbs_crm_lead.hbs_crm_lead.take_over_lead",
											args: { lead_name: frm.doc.name },
											callback: function (res) {
												if (res.message) {
													frappe.show_alert({
														message: res.message.message,
														indicator: "green"
													});
													frm.reload_doc();
												}
											}
										});
									}
								);
							}, __("Actions"));
						}
					}
				}

				frm.add_custom_button(__("Send Email to Client"), function () {
					open_email_dialog(frm);
				}, __("Actions"));
			}
		}
	},

	status(frm) {
		toggle_won_status_read_only(frm);
		set_customer_details_read_only(frm);
	},
	lead_source(frm) {
		handle_referred_by_dependency(frm);
	},
	quotation_format(frm) {
		apply_quotation_format_color(frm);
		if (frm.doc.pi_number) {
			let is_new_age = (frm.doc.quotation_format === "New Age Quotation");
			if ((is_new_age && !frm.doc.pi_number.startsWith("NIPL/")) || (!is_new_age && !frm.doc.pi_number.startsWith("HBS/"))) {
				frm.set_value("pi_number", "");
			}
		}
	},

	lead_type(frm) {
		check_and_warn_duplicate_lead(frm);
		handle_lead_type_terms(frm);
	},
	company_name(frm) {
		check_and_warn_duplicate_lead(frm);
	},
	contact_name(frm) {
		check_and_warn_duplicate_lead(frm);
	},
	contact_phone(frm) {
		check_and_warn_duplicate_lead(frm);
		validate_phone_field_length(frm, "contact_phone");
		check_phone_number_in_use(frm);
	},
	contact_email(frm) {
		check_and_warn_duplicate_lead(frm);
	},
	customer(frm) {
		check_and_warn_duplicate_lead(frm);
		if (frm.doc.customer) {
			frappe.db.get_doc("Hbs Customer", frm.doc.customer).then((doc) => {
				if (doc && doc.address && !frm.doc.address) {
					frm.set_value("address", doc.address);
				}
			});
		}
	},

	follow_up_date(frm) {
		if (frm.doc.follow_up_date) {
			// Get browser's actual local today date in YYYY-MM-DD format
			let d = new Date();
			let year = d.getFullYear();
			let month = String(d.getMonth() + 1).padStart(2, '0');
			let day = String(d.getDate()).padStart(2, '0');
			let browser_today = `${year}-${month}-${day}`;

			if (frappe.datetime.str_to_obj(frm.doc.follow_up_date) < frappe.datetime.str_to_obj(browser_today)) {
				let formatted_fup = frappe.datetime.str_to_user(frm.doc.follow_up_date);
				let formatted_today = frappe.datetime.str_to_user(browser_today);
				frappe.msgprint({
					title: __("Invalid Follow-up Date"),
					indicator: "orange",
					message: __("Follow-up Date cannot be set to a past date (<b>{0}</b>). Auto-resetting to Today (<b>{1}</b>).", [formatted_fup, formatted_today])
				});
				frm.set_value("follow_up_date", browser_today);
			}
		}
	},

	validate(frm) {
		// 1. Contact Phone Validation
		if (frm.doc.contact_phone) {
			let cleaned = format_phone_with_country_code(frm.doc.contact_phone);
			if (cleaned.length !== 10) {
				frappe.msgprint({
					title: __("Invalid Mobile Number"),
					indicator: "red",
					message: __("<b>Wrong Mobile Number ({0})!</b><br>Mobile number must be exactly 10 digits.", [frm.doc.contact_phone])
				});
				frappe.validated = false;
				return;
			}
		}

		for (let row of (frm.doc.all_contacts || [])) {
			if (row.contact_phone) {
				let cleaned = format_phone_with_country_code(row.contact_phone);
				if (cleaned.length !== 10) {
					frappe.msgprint({
						title: __("Invalid Mobile Number"),
						indicator: "red",
						message: __("<b>Wrong Mobile Number in All Contacts ({0})!</b><br>Mobile number must be exactly 10 digits.", [row.contact_phone])
					});
					frappe.validated = false;
					return;
				}
			}
		}

		// 2. Tally Serial Number Validation
		if (frm.doc.tally_serial) {
			let s = String(frm.doc.tally_serial).trim();
			if (!is_genuine_tally_serial(s)) {
				frappe.msgprint({
					title: __("Invalid Serial Number"),
					indicator: "red",
					message: __("Invalid Serial Number")
				});
				frappe.validated = false;
				return;
			}
		}
	},

	additional_discount(frm) {
		calculate_totals(frm);
	}
});

function is_genuine_tally_serial(serial) {
	if (!serial) return true;
	let s = String(serial).trim();
	if (s.length !== 9 || !/^\d+$/.test(s)) return false;
	if (!s.startsWith("7")) return false;
	let sum = s.split("").reduce((acc, d) => acc + parseInt(d, 10), 0);
	while (sum >= 10) {
		sum = String(sum).split("").reduce((acc, d) => acc + parseInt(d, 10), 0);
	}
	return sum === 9;
}

function toggle_won_status_read_only(frm) {
	if (frm.doc.status === "won" || frm.doc.status === "lost") {
		(frm.fields || []).forEach((field) => {
			if (field.df.fieldtype !== "Section Break" && field.df.fieldtype !== "Tab Break" && field.df.fieldtype !== "Column Break" && field.df.fieldtype !== "HTML") {
				frm.set_df_property(field.df.fieldname, "read_only", 1);
			}
		});
		frm.set_df_property("items", "read_only", 1);
		
		// Disable save on saved won/lost leads
		if (!frm.is_new()) {
			frm.disable_save();
		}
	} else {
		let naturally_read_only = ["pi_number", "total_before_tax", "total_tax", "total_after_tax", "final_total", "activity"];
		(frm.fields || []).forEach((field) => {
			if (!naturally_read_only.includes(field.df.fieldname) && field.df.fieldtype !== "Section Break" && field.df.fieldtype !== "Tab Break" && field.df.fieldtype !== "Column Break" && field.df.fieldtype !== "HTML") {
				frm.set_df_property(field.df.fieldname, "read_only", 0);
			}
		});
		frm.set_df_property("items", "read_only", 0);
		frm.set_df_property("status", "read_only", 0);
		frm.enable_save();
	}
}

function apply_quotation_format_color(frm) {
	let field = frm.get_field("quotation_format");
	if (!field || !field.$input) return;

	let is_new_age = (frm.doc.quotation_format === "New Age Quotation");
	if (is_new_age) {
		field.$input.css({
			"background-color": "#f0fdf4",
			"color": "#15803d",
			"border": "1.5px solid #86efac",
			"font-weight": "600"
		});
	} else {
		field.$input.css({
			"background-color": "#eff6ff",
			"color": "#1d4ed8",
			"border": "1.5px solid #93c5fd",
			"font-weight": "600"
		});
	}
}

function check_and_warn_duplicate_lead(frm) {
	if (!frm.doc.lead_type) return;

	let comp = (frm.doc.company_name || "").trim();
	let cont = (frm.doc.contact_name || "").trim();
	let phone = (frm.doc.contact_phone || "").trim();
	let email = (frm.doc.contact_email || "").trim();
	let cust = (frm.doc.customer || "").trim();

	if (!comp && !cust && !phone && !email && !cont) return;

	frappe.call({
		method: "hbs_crm.hbs_crm.doctype.hbs_crm_lead.hbs_crm_lead.check_duplicate_lead",
		args: {
			company_name: comp,
			contact_name: cont,
			contact_phone: phone,
			contact_email: email,
			customer: cust,
			lead_type: frm.doc.lead_type,
			current_lead_name: frm.doc.name
		},
		callback: function (r) {
			if (r.message) {
				let dup = r.message;
				let party = dup.company_name || dup.contact_name || "this party";
				let exec = dup.executive_full_name || dup.executive_1 || dup.owner || "another user";

				if (dup.is_inactive) {
					// 15+ Days Dormant Lead Rule: Show link to open existing lead
					let msg = `
						<div style="padding: 10px; font-size: 14px; line-height: 1.6;">
							<p style="color: #dd6b20; font-weight: 600; font-size: 15px; margin-bottom: 8px;">
								⚠️ Inactive Duplicate Lead Found (15+ Days)!
							</p>
							<p>
								A lead for party <b>${party}</b> with Lead Type <b>${dup.lead_type}</b> was created by <b>${exec}</b> on <b>${dup.creation_date}</b> (Lead #${dup.name}).
							</p>
							<p style="background: #fffaf0; border: 1px solid #fbd38d; border-radius: 6px; padding: 10px; margin-top: 10px; color: #744210;">
								<b>No follow-up remarks</b> have been logged on this lead for <b>${dup.days_inactive} days</b> (Last follow-up: ${dup.last_follow_up_formatted || dup.creation_date}).
							</p>
							<p style="margin-top: 10px; color: #2d3748;">
								You can open the existing lead to alter its status, update details, or add new follow-up activities.
							</p>
						</div>
					`;

					let d = new frappe.ui.Dialog({
						title: __("Dormant Lead Found"),
						indicator: "orange",
						fields: [
							{
								fieldtype: "HTML",
								fieldname: "warning_html",
								options: msg
							}
						],
						primary_action_label: __(`⚡ Take Over & Open Lead (#${dup.name})`),
						primary_action() {
							d.hide();
							frappe.call({
								method: "hbs_crm.hbs_crm.doctype.hbs_crm_lead.hbs_crm_lead.take_over_lead",
								args: { lead_name: dup.name },
								callback: function (res) {
									if (res.message) {
										frappe.show_alert({
											message: res.message.message,
											indicator: "green"
										});
										frappe.set_route("Form", "Hbs Crm Lead", dup.name);
									}
								}
							});
						},
						secondary_action_label: __("Close"),
						secondary_action() {
							d.hide();
						}
					});
					d.show();
				} else {
					// Active Lead Rule (<= 15 days): Block creation, must change Lead Type
					let msg = `
						<div style="padding: 10px; font-size: 14px; line-height: 1.6;">
							<p style="color: #c53030; font-weight: 600; font-size: 15px; margin-bottom: 8px;">
								⚠️ Active Duplicate Lead Blocked!
							</p>
							<p>
								A lead for party <b>${party}</b> with Lead Type <b>${dup.lead_type}</b> has already been generated by <b>${exec}</b> on <b>${dup.creation_date}</b> (Lead #${dup.name}).
							</p>
							<p style="color: #c53030; margin-top: 10px; font-weight: 600;">
								❌ Active follow-ups are ongoing (${dup.days_inactive} days since last follow-up). You CANNOT save this lead with Lead Type "${dup.lead_type}".
							</p>
						</div>
					`;

					let d = new frappe.ui.Dialog({
						title: __("Duplicate Lead Blocked"),
						indicator: "red",
						fields: [
							{
								fieldtype: "HTML",
								fieldname: "warning_html",
								options: msg
							}
						],
						primary_action_label: __("OK, I will change Lead Type"),
						primary_action() {
							d.hide();
						}
					});
					d.show();
				}
			}
		}
	});
}

function render_activity_timeline_js(frm) {
	if (frm.is_new() || !frm.doc.name) {
		if (frm.fields_dict.activity) {
			frm.fields_dict.activity.$wrapper.html("<div style='color:#a0aec0; font-style:italic; padding:10px;'>No activities recorded yet.</div>");
		}
		return;
	}

	if (frm.doc.activity && frm.doc.activity.trim() && frm.fields_dict.activity) {
		frm.fields_dict.activity.$wrapper.html(frm.doc.activity);
		return;
	}

	frappe.call({
		method: "hbs_crm.hbs_crm.doctype.hbs_crm_lead.hbs_crm_lead.get_activity_html",
		args: {
			lead_name: frm.doc.name
		},
		callback: function (r) {
			if (r.message && frm.fields_dict.activity) {
				frm.fields_dict.activity.$wrapper.html(r.message);
			}
		}
	});
}

function open_email_dialog(frm) {
	let client_email = (frm.doc.contact_email || "").trim();
	if (!client_email && frm.doc.all_contacts && frm.doc.all_contacts.length > 0) {
		for (let c of frm.doc.all_contacts) {
			if (c.contact_email && c.contact_email.trim()) {
				client_email = c.contact_email.trim();
				break;
			}
		}
	}

	if (!client_email) {
		frappe.msgprint({
			title: __("Client Email Required"),
			indicator: "orange",
			message: __("<b>Contact Email is not set on this Lead!</b><br>Please enter the client's email in <b>Contact Email</b> field on the form, or enter the client's email in the <b>To</b> field in the dialog.")
		});
	}

	frappe.call({
		method: "hbs_crm.hbs_crm.doctype.hbs_crm_lead.hbs_crm_lead.get_rendered_email_template",
		args: { lead_name: frm.doc.name },
		callback: function (res) {
			if (res.message) {
				let default_subject = res.message.subject;
				let default_message = res.message.message;
				let default_from = res.message.from_email;
				let default_sender = res.message.sender_name;
				let default_cc = res.message.cc_email ||
					(frappe.boot && frappe.boot.user && frappe.boot.user.email) ||
					(frappe.user_info && frappe.user_info[frappe.session.user] && frappe.user_info[frappe.session.user].email) ||
					(frappe.session.user && frappe.session.user.indexOf("@") !== -1 ? frappe.session.user : "");

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
							label: __("Attach Quotation PDF Print"),
							fieldname: "attach_print",
							fieldtype: "Check",
							default: 1
						},
						{
							label: __("Attach Document"),
							fieldname: "attach_btn",
							fieldtype: "Button",
							click: function() {
								new frappe.ui.FileUploader({
									doctype: "Hbs Crm Lead",
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
						let do_send = function() {
							let extra_urls = attached_files.map(f => f.file_url).filter(u => u);
							frappe.call({
								method: "hbs_crm.hbs_crm.doctype.hbs_crm_lead.hbs_crm_lead.send_manual_lead_email",
								args: {
									lead_name: frm.doc.name,
									sender_name: values.sender_name,
									from_email: values.from_email,
									to_email: values.to_email,
									cc_email: values.cc_email,
									subject: values.subject,
									message: values.message,
									attach_print: values.attach_print ? 1 : 0,
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
						};

						do_send();
					}
				});

				function render_attached_files() {
					if (attached_files.length === 0) {
						d.set_df_property("attached_files_html", "options", '<div class="text-muted" style="font-size: 12px; margin-top: 5px;">No additional documents attached. Click the button above to upload Excel, PDF, Word, or other files.</div>');
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

				d.show();
				d.add_custom_action(__("📄 View Quotation"), function () {
					open_quotation_preview_dialog(frm, "Hbs Crm Lead");
				});
				if (default_cc) {
					d.set_value("cc_email", default_cc);
				}
				render_attached_files();
			}
		}
	});
}

frappe.ui.form.on("hbs crm items", {
	item_name(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		if (row.item_name) {
			frappe.db.get_doc("Hbs Product", row.item_name).then((doc) => {
				frappe.model.set_value(cdt, cdn, "rate", doc.rate || 0);
				frappe.model.set_value(cdt, cdn, "description", "");
				frappe.model.set_value(cdt, cdn, "tax", doc.tax || 0);
				frappe.model.set_value(cdt, cdn, "hsn", doc.hsn || "");
				if (!row.qty) {
					frappe.model.set_value(cdt, cdn, "qty", 1);
				}
				validate_row_min_rate(frm, cdt, cdn, doc);
				calculate_item_amount(frm, cdt, cdn);
			});
		}
	},

	qty(frm, cdt, cdn) {
		calculate_item_amount(frm, cdt, cdn);
	},

	rate(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		if (row.item_name) {
			frappe.db.get_doc("Hbs Product", row.item_name).then((doc) => {
				validate_row_min_rate(frm, cdt, cdn, doc);
				calculate_item_amount(frm, cdt, cdn);
			});
		} else {
			calculate_item_amount(frm, cdt, cdn);
		}
	},

	discount_amount(frm, cdt, cdn) {
		calculate_item_amount(frm, cdt, cdn);
	},

	tax(frm, cdt, cdn) {
		calculate_item_amount(frm, cdt, cdn);
	},

	items_remove(frm) {
		calculate_totals(frm);
	}
});

function calculate_item_amount(frm, cdt, cdn) {
	let row = locals[cdt][cdn];
	let qty = flt(row.qty) || 1;
	let rate = flt(row.rate) || 0;
	let discount = flt(row.discount_amount) || 0;
	let tax_percent = flt(row.tax) || 0;

	let subtotal = (qty * rate) - discount;
	let tax_amount = (subtotal * tax_percent) / 100.0;
	let total_amount = subtotal + tax_amount;

	row.tax_amount = tax_amount;
	row.amount = total_amount;

	calculate_totals(frm);
}

function calculate_totals(frm) {
	let total_before_tax = 0;
	(frm.doc.items || []).forEach((row) => {
		let qty = flt(row.qty) || 1;
		let rate = flt(row.rate) || 0;
		let discount = flt(row.discount_amount) || 0;
		total_before_tax += (qty * rate) - discount;
	});

	let additional_discount = flt(frm.doc.additional_discount) || 0;
	let total_tax = 0;

	(frm.doc.items || []).forEach((row) => {
		let qty = flt(row.qty) || 1;
		let rate = flt(row.rate) || 0;
		let discount = flt(row.discount_amount) || 0;
		let row_subtotal = (qty * rate) - discount;

		let row_additional_discount = 0;
		if (total_before_tax > 0) {
			row_additional_discount = (row_subtotal / total_before_tax) * additional_discount;
		}

		let net_subtotal = row_subtotal - row_additional_discount;
		let tax_percent = flt(row.tax) || 0;
		let tax_amt = (net_subtotal * tax_percent) / 100.0;
		let row_amount = net_subtotal + tax_amt;

		row.tax_amount = tax_amt;
		row.amount = row_amount;
		total_tax += tax_amt;
	});

	frm.refresh_field("items");

	let final_total = (total_before_tax - additional_discount) + total_tax;

	frm.set_value("total_before_tax", total_before_tax);
	frm.set_value("total_tax", total_tax);
	frm.set_value("total_after_tax", total_before_tax - additional_discount);
	frm.set_value("final_total", final_total);
}

function validate_row_min_rate(frm, cdt, cdn, product_doc) {
	let row = locals[cdt][cdn];
	let min_rate = flt(product_doc.min_rate || 0);
	let current_rate = flt(row.rate || 0);

	if (min_rate > 0 && current_rate < min_rate) {
		let item_title = product_doc.item_name || product_doc.product_name || row.item_name;
		frappe.msgprint({
			title: __("Minimum Rate Warning"),
			indicator: "orange",
			message: __("Rate for item <b>{0}</b> cannot be lower than the Minimum Allowed Rate (<b>₹{1}</b>). Auto-resetting rate to ₹{1}.", [item_title, min_rate])
		});
		frappe.model.set_value(cdt, cdn, "rate", min_rate);
	}
}

function open_log_follow_up_dialog(frm) {
	let today = frappe.datetime.get_today();
	let now_time = frappe.datetime.now_time();

	let default_date = frm.doc.follow_up_date && frappe.datetime.str_to_obj(frm.doc.follow_up_date) >= frappe.datetime.str_to_obj(today) ? frm.doc.follow_up_date : today;

	let d = new frappe.ui.Dialog({
		title: __("Log Follow-up Section Details"),
		fields: [
			{
				label: __("Next Follow-up Date"),
				fieldname: "follow_up_date",
				fieldtype: "Date",
				default: default_date,
				reqd: 1
			},
			{
				label: __("Next Follow-up Time"),
				fieldname: "follow_up_time",
				fieldtype: "Time",
				default: frm.doc.follow_up_time || now_time,
				reqd: 1
			},
			{
				label: __("Lead Status"),
				fieldname: "status",
				fieldtype: "Select",
				options: "new\npending\nwon\nlost",
				default: frm.doc.status || "new",
				reqd: 1,
				read_only: frm.doc.status === "won" && !frm.is_new() ? 1 : 0
			},
			{
				label: __("Serial Num"),
				fieldname: "tally_serial",
				fieldtype: "Data",
				default: frm.doc.tally_serial || "",
				read_only: 1
			},
			{
				fieldtype: "Column Break"
			},
			{
				label: __("Requirement Received"),
				fieldname: "requirement_received",
				fieldtype: "Check",
				default: frm.doc.requirement_received || 0
			},
			{
				label: __("Proposal Sent"),
				fieldname: "proposal_sent",
				fieldtype: "Check",
				default: frm.doc.proposal_sent || 0
			},
			{
				label: __("Demo Done"),
				fieldname: "demo_done",
				fieldtype: "Check",
				default: frm.doc.demo_done || 0
			},
			{
				fieldtype: "Section Break",
				label: __("Activity Remarks (Mandatory)")
			},
			{
				label: __("Follow-up Remarks / Activity Note"),
				fieldname: "remarks",
				fieldtype: "Small Text",
				reqd: 1,
				description: __("Enter details of discussion, customer feedback, or next steps.")
			}
		],
		primary_action_label: __("Save Follow-up Section"),
		primary_action(values) {
			let fup_date = values.follow_up_date;
			if (frappe.datetime.str_to_obj(fup_date) < frappe.datetime.str_to_obj(today)) {
				frappe.msgprint({
					title: __("Invalid Follow-up Date"),
					indicator: "orange",
					message: __("Next Follow-up Date cannot be set to a past date.")
				});
				return;
			}

			if (values.status === "won" && (!values.tally_serial || !values.tally_serial.trim())) {
				frappe.msgprint({
					title: __("Tally Serial Required"),
					indicator: "red",
					message: __("Tally Serial Number is required on the main form when status is changed to Won.")
				});
				return;
			}

			if (!values.remarks || !values.remarks.trim()) {
				frappe.msgprint({
					title: __("Remarks Required"),
					indicator: "orange",
					message: __("Please enter follow-up remarks before saving.")
				});
				return;
			}

			frm.set_value("follow_up_date", values.follow_up_date);
			frm.set_value("follow_up_time", values.follow_up_time);
			frm.set_value("status", values.status);
			frm.set_value("requirement_received", values.requirement_received ? 1 : 0);
			frm.set_value("proposal_sent", values.proposal_sent ? 1 : 0);
			frm.set_value("demo_done", values.demo_done ? 1 : 0);
			frm.set_value("remarks", values.remarks.trim());

			d.hide();
			frm.save().then(() => {
				frappe.show_alert({
					message: __("Follow-up section details saved & activity logged!"),
					indicator: "green"
				});
			});
		}
	});

	d.show();
}

let in_phone_validation = false;

function format_phone_with_country_code(val) {
	if (!val) return "";
	let raw = String(val).trim();
	if (raw.startsWith("+91-")) raw = raw.substring(4).trim();
	else if (raw.startsWith("+91")) raw = raw.substring(3).trim();
	else if (raw.startsWith("91") && raw.length > 10) raw = raw.substring(2).trim();

	let digits = raw.replace(/\D/g, "");
	if (!digits) return "";

	return digits.substring(0, 10);
}

frappe.ui.form.on("Hbs Lead Contact", {
	contact_phone(frm, cdt, cdn) {
		if (in_phone_validation) return;
		let row = locals[cdt][cdn];
		if (row && row.contact_phone) {
			let formatted = format_phone_with_country_code(row.contact_phone);
			if (formatted !== row.contact_phone) {
				in_phone_validation = true;
				row.contact_phone = formatted;
				if (frm.fields_dict.all_contacts && frm.fields_dict.all_contacts.grid) {
					frm.fields_dict.all_contacts.grid.refresh();
				}
				setTimeout(() => { in_phone_validation = false; }, 50);
			}
		}
	}
});

function validate_phone_field_length(frm, fieldname) {
	if (in_phone_validation) return;
	let val = frm.doc[fieldname];
	if (val) {
		let formatted = format_phone_with_country_code(val);
		if (formatted !== val) {
			in_phone_validation = true;
			frm.doc[fieldname] = formatted;
			frm.refresh_field(fieldname);
			setTimeout(() => { in_phone_validation = false; }, 50);
		}
	}
}

function handle_lead_type_terms(frm) {
	if (!frm.doc.lead_type) return;

	let is_amc = frm.doc.lead_type === "AMC";

	if (is_amc) {
		frm.set_df_property("delivery", "label", "Scope of Work");
		frm.set_df_property("support", "label", "Site Visits");
		frm.set_df_property("taxes", "label", "Performa Invoice");

		// Pre-fill AMC defaults if fields are empty or contain normal defaults
		if (!frm.doc.payment_terms || frm.doc.payment_terms === "100% advance along with confirm order.") {
			frm.set_value("payment_terms", "100% Advance with signing of the agreement");
		}
		if (!frm.doc.delivery || frm.doc.delivery === "2-3 working days.") {
			frm.set_value("delivery", "For Tally Related Queries only.");
		}
		if (!frm.doc.support || frm.doc.support === "3 Months Telephonic Support from invoice date.") {
			frm.set_value("support", "On site visits will be restricted to 7 visits. Extra visits will be charged as applicable. Each visit restricted to max. of 2 Hrs.");
		}
		if (!frm.doc.taxes || frm.doc.taxes === "All Inclusive") {
			frm.set_value("taxes", "This is a performa Invoice. Actual Invoice will be delivered to you later.");
		}
		if (!frm.doc.validity || frm.doc.validity === "ONE WEEK") {
			frm.set_value("validity", "One Year from signing of the Agreement");
		}
	} else {
		frm.set_df_property("delivery", "label", "Delivery");
		frm.set_df_property("support", "label", "Support");
		frm.set_df_property("taxes", "label", "Taxes");

		// Pre-fill normal defaults if fields are empty or contain AMC defaults
		if (!frm.doc.payment_terms || frm.doc.payment_terms === "100% Advance with signing of the agreement") {
			frm.set_value("payment_terms", "100% advance along with confirm order.");
		}
		if (!frm.doc.delivery || frm.doc.delivery === "For Tally Related Queries only.") {
			frm.set_value("delivery", "2-3 working days.");
		}
		if (!frm.doc.support || frm.doc.support === "On site visits will be restricted to 7 visits. Extra visits will be charged as applicable. Each visit restricted to max. of 2 Hrs.") {
			frm.set_value("support", "3 Months Telephonic Support from invoice date.");
		}
		if (!frm.doc.taxes || frm.doc.taxes === "This is a performa Invoice. Actual Invoice will be delivered to you later.") {
			frm.set_value("taxes", "All Inclusive");
		}
		if (!frm.doc.validity || frm.doc.validity === "One Year from signing of the Agreement") {
			frm.set_value("validity", "ONE WEEK");
		}
	}
}

function handle_referred_by_dependency(frm) {
	if (frm.doc.lead_source === "Reference") {
		frm.set_df_property("referred_by", "read_only", 0);
	} else {
		frm.set_value("referred_by", "");
		frm.set_df_property("referred_by", "read_only", 1);
	}
}

function check_phone_number_in_use(frm) {
	if (frm.doc.contact_phone) {
		frappe.call({
			method: "hbs_crm.hbs_crm.doctype.hbs_crm_lead.hbs_crm_lead.check_phone_in_use",
			args: {
				contact_phone: frm.doc.contact_phone,
				current_lead_name: frm.doc.name
			},
			callback: function (r) {
				if (r.message) {
					frappe.msgprint({
						title: __("Phone Number In Use"),
						message: r.message,
						indicator: "orange"
					});
				}
			}
		});
	}
}

function is_admin_or_owner(callback) {
	if (frappe.session.user === "Administrator" || frappe.user.has_role("System Manager")) {
		callback(true);
		return;
	}

	if (window._hbs_is_admin_or_owner !== undefined) {
		callback(window._hbs_is_admin_or_owner);
		return;
	}

	frappe.call({
		method: "hbs_crm.hbs_crm.doctype.hbs_crm_lead.hbs_crm_lead.check_is_admin_or_owner",
		callback: function(r) {
			window._hbs_is_admin_or_owner = !!r.message;
			callback(window._hbs_is_admin_or_owner);
		},
		error: function() {
			window._hbs_is_admin_or_owner = false;
			callback(false);
		}
	});
}

function set_customer_details_read_only(frm) {
	if (frm.doc.status === "won" || frm.doc.status === "lost") {
		return;
	}

	const editable_fields = [
		"company_gst",
		"contact_name",
		"contact_designation",
		"contact_phone",
		"contact_email",
		"tally_serial",
		"license_type",
		"address"
	];

	const locked_fields = [
		"customer",
		"company_name"
	];

	is_admin_or_owner(function(is_admin) {
		if (is_admin) {
			[...locked_fields, ...editable_fields].forEach(f => {
				frm.set_df_property(f, "read_only", 0);
				let field = frm.get_field(f);
				if (field && field.$wrapper) {
					field.$wrapper.find("input, textarea, select").prop("readonly", false).prop("disabled", false).css({
						"background-color": "",
						"cursor": "",
						"pointer-events": ""
					});
					field.$wrapper.find(".link-btn").show();
				}
			});
		} else {
			// Standard users: only company_name & customer link are read-only
			locked_fields.forEach(f => {
				// Keep df.read_only as 0 so Frappe does not hide empty fields on new leads
				frm.set_df_property(f, "read_only", 0);
				let field = frm.get_field(f);
				if (field && field.$wrapper) {
					field.$wrapper.find("input, textarea").prop("readonly", true).css({
						"background-color": "var(--control-bg-read-only, #f8fafc)",
						"cursor": "not-allowed",
						"pointer-events": f === "customer" ? "none" : "auto"
					});
					if (f === "company_name") {
						if (!frm.doc.company_name) {
							field.$wrapper.find("input").attr("placeholder", __("Click 'Auto Fill Details' above to enter customer"));
						}
						field.$wrapper.find("input").off("click.hbs_autofill_prompt").on("click.hbs_autofill_prompt", function() {
							if (!frm.doc.company_name) {
								open_auto_fill_customer_dialog(frm);
							}
						});
					}
					field.$wrapper.find(".link-btn").hide();
				}
			});

			// Rest of the customer fields can be edited by the user
			editable_fields.forEach(f => {
				frm.set_df_property(f, "read_only", 0);
				let field = frm.get_field(f);
				if (field && field.$wrapper) {
					field.$wrapper.find("input, textarea, select").prop("readonly", false).prop("disabled", false).css({
						"background-color": "",
						"cursor": "",
						"pointer-events": ""
					});
				}
			});
		}
	});
}

function open_auto_fill_customer_dialog(frm) {
	let dialog = new frappe.ui.Dialog({
		title: __("Search & Auto Fill Customer Details"),
		size: "large",
		fields: [
			{
				label: __("Search Customer"),
				fieldname: "search_term",
				fieldtype: "Data",
				placeholder: __("Search by name, company, phone, email, GST, serial..."),
				description: __("Type to search live (pasting disabled). Or click 'Add Customer' to create new.")
			},
			{
				fieldtype: "Button",
				label: __("➕ Add Customer"),
				fieldname: "add_customer_btn",
				click: function() {
					open_quick_add_customer_dialog(frm, dialog);
				}
			},
			{
				fieldtype: "HTML",
				fieldname: "results_html",
				label: __("Results")
			}
		],
		secondary_action_label: __("➕ Add Customer"),
		secondary_action: function() {
			open_quick_add_customer_dialog(frm, dialog);
		}
	});

	dialog.$wrapper.find(".modal-dialog").css({
		"max-width": "950px",
		"width": "90%"
	});

	dialog.show();

	// Style add customer button
	let addCustField = dialog.get_field("add_customer_btn");
	if (addCustField && addCustField.$input) {
		addCustField.$input.addClass("btn-primary").css({"margin-top": "5px", "margin-bottom": "10px"});
	}

	let search_timer = null;
	let $input = dialog.get_input("search_term");

	if ($input && $input.length) {
		// Disable paste via right-click, keyboard, or drop
		$input.attr("onpaste", "return false;");
		$input.attr("autocomplete", "off");

		$input.on("paste", function(e) {
			e.preventDefault();
			frappe.show_alert({
				message: __("Pasting is disabled in search box. Please type manually."),
				indicator: "orange"
			});
			return false;
		});

		$input.on("keydown", function(e) {
			let isCtrlOrCmd = e.ctrlKey || e.metaKey;
			if (isCtrlOrCmd && (e.key === "v" || e.key === "V" || e.keyCode === 86)) {
				e.preventDefault();
				frappe.show_alert({
					message: __("Pasting (Ctrl+V) is disabled. Please type manually."),
					indicator: "orange"
				});
				return false;
			}
			if (e.shiftKey && (e.key === "Insert" || e.keyCode === 45)) {
				e.preventDefault();
				frappe.show_alert({
					message: __("Pasting is disabled. Please type manually."),
					indicator: "orange"
				});
				return false;
			}
			if (e.which === 13) {
				e.preventDefault();
				clearTimeout(search_timer);
				perform_customer_search(dialog, frm);
			}
		});

		$input.on("drop", function(e) {
			e.preventDefault();
			return false;
		});

		// Live search as user types with 300ms debounce
		$input.on("input", function() {
			clearTimeout(search_timer);
			search_timer = setTimeout(function() {
				perform_customer_search(dialog, frm);
			}, 300);
		});
	}

	// Delegated click listener - Fill details
	dialog.$wrapper.off("click", ".btn-fill-detail").on("click", ".btn-fill-detail", function() {
		clearTimeout(search_timer);
		let key = $(this).attr("data-key");
		let customer_doc = window.customer_search_results && window.customer_search_results[key];
		if (customer_doc) {
			frm.set_value({
				customer: customer_doc.name ? String(customer_doc.name) : "",
				company_name: customer_doc.company_name || "",
				company_gst: customer_doc.company_gst || "",
				contact_name: customer_doc.customer_name || "",
				contact_phone: customer_doc.contact_phone || "",
				contact_email: customer_doc.contact_email || "",
				address: customer_doc.address || "",
				tally_serial: customer_doc.tally_serial || "",
				license_type: customer_doc.license_type || ""
			}).then(() => {
				set_customer_details_read_only(frm);
			});

			frappe.show_alert({
				message: __("Customer details auto-filled successfully!"),
				indicator: "green"
			});

			dialog.hide();
		}
	});

	// Delegated click listener - Add Customer button inside empty result box
	dialog.$wrapper.off("click", ".btn-add-cust-from-search").on("click", ".btn-add-cust-from-search", function() {
		open_quick_add_customer_dialog(frm, dialog);
	});

	// Immediately load recent customers list
	perform_customer_search(dialog, frm);
}

function perform_customer_search(dialog, frm) {
	let term = (dialog.get_value("search_term") || "").trim();

	dialog.set_df_property("results_html", "options", '<div class="text-center text-muted" style="padding: 20px;"><i class="fa fa-spinner fa-spin"></i> ' + __("Loading customers...") + '</div>');

	frappe.call({
		method: "hbs_crm.hbs_crm.doctype.hbs_crm_lead.hbs_crm_lead.search_customers",
		args: {
			search_term: term
		},
		callback: function(r) {
			if ((dialog.get_value("search_term") || "").trim() !== term) {
				return;
			}

			if (r.message && r.message.length > 0) {
				let title_html = term
					? `<div style="font-size: 12px; color: #4b5563; margin-bottom: 8px;">${__("Found {0} matching customer(s):", [r.message.length])}</div>`
					: `<div style="font-size: 12px; color: #4b5563; margin-bottom: 8px;">${__("Recent Customers ({0}):", [r.message.length])}</div>`;

				let html = title_html + `
					<div style="max-height: 420px; overflow-y: auto;">
						<table class="table table-bordered table-hover" style="font-size: 13px;">
							<thead>
								<tr class="active">
									<th>${__("Name")}</th>
									<th>${__("Company")}</th>
									<th>${__("Phone")}</th>
									<th>${__("Email")}</th>
									<th style="width: 120px; text-align: center;">${__("Action")}</th>
								</tr>
							</thead>
							<tbody>
				`;

				r.message.forEach((cust, index) => {
					let cust_key = `cust_res_${index}`;
					if (!window.customer_search_results) {
						window.customer_search_results = {};
					}
					window.customer_search_results[cust_key] = cust;

					html += `
						<tr>
							<td><b>${frappe.utils.escape_html(cust.customer_name || '')}</b><br><small class="text-muted">ID: ${cust.name}</small></td>
							<td>${frappe.utils.escape_html(cust.company_name || '')}<br><small class="text-muted">GST: ${frappe.utils.escape_html(cust.company_gst || '-')}</small></td>
							<td>${frappe.utils.escape_html(cust.contact_phone || '')}</td>
							<td>${frappe.utils.escape_html(cust.contact_email || '')}</td>
							<td class="text-center" style="vertical-align: middle;">
								<button class="btn btn-xs btn-primary btn-fill-detail" data-key="${cust_key}">
									${__("Fill Details")}
								</button>
							</td>
						</tr>
					`;
				});

				html += `
							</tbody>
						</table>
					</div>
				`;

				dialog.set_df_property("results_html", "options", html);
			} else {
				dialog.set_df_property("results_html", "options", `
					<div class="text-center" style="padding: 25px; border: 1px dashed #d1d5db; border-radius: 6px; margin-top: 10px;">
						<div class="text-muted" style="margin-bottom: 12px; font-size: 14px;">${__("No matching customers found.")}</div>
						<button class="btn btn-sm btn-primary btn-add-cust-from-search">
							<i class="fa fa-plus"></i> ${__("➕ Add New Customer")}
						</button>
					</div>
				`);
			}
		}
	});
}

function open_quick_add_customer_dialog(frm, parent_dialog) {
	let term = parent_dialog ? (parent_dialog.get_value("search_term") || "").trim() : "";
	let initial_company = "";
	let initial_phone = "";
	if (term) {
		if (/^\d{10}$/.test(term)) {
			initial_phone = term;
		} else if (!/^\d+$/.test(term)) {
			initial_company = term;
		}
	}

	let add_dialog = new frappe.ui.Dialog({
		title: __("Add New Customer"),
		fields: [
			{
				label: __("Company Name"),
				fieldname: "company_name",
				fieldtype: "Data",
				reqd: 1,
				default: initial_company
			},
			{
				label: __("Customer / Contact Name"),
				fieldname: "customer_name",
				fieldtype: "Data",
				reqd: 1
			},
			{
				label: __("Contact Phone"),
				fieldname: "contact_phone",
				fieldtype: "Data",
				reqd: 1,
				default: initial_phone
			},
			{
				label: __("Contact Email"),
				fieldname: "contact_email",
				fieldtype: "Data"
			},
			{
				fieldtype: "Column Break"
			},
			{
				label: __("Company GST"),
				fieldname: "company_gst",
				fieldtype: "Data"
			},
			{
				label: __("Tally Serial"),
				fieldname: "tally_serial",
				fieldtype: "Data"
			},
			{
				label: __("License Type"),
				fieldname: "license_type",
				fieldtype: "Select",
				options: "\nAuditor\nGold\nSilver"
			},
			{
				label: __("Address"),
				fieldname: "address",
				fieldtype: "Small Text"
			}
		],
		primary_action_label: __("Save & Auto Fill"),
		primary_action: function(values) {
			if (!values.company_name || !values.customer_name || !values.contact_phone) {
				frappe.msgprint(__("Company Name, Customer Name, and Contact Phone are required."));
				return;
			}
			add_dialog.get_primary_btn().prop("disabled", true);
			frappe.call({
				method: "hbs_crm.hbs_crm.doctype.hbs_crm_lead.hbs_crm_lead.quick_create_customer",
				args: {
					company_name: values.company_name,
					customer_name: values.customer_name,
					contact_phone: values.contact_phone,
					contact_email: values.contact_email || "",
					company_gst: values.company_gst || "",
					tally_serial: values.tally_serial || "",
					license_type: values.license_type || "",
					address: values.address || ""
				},
				freeze: true,
				freeze_message: __("Creating Customer..."),
				callback: function(r) {
					add_dialog.get_primary_btn().prop("disabled", false);
					if (r.message) {
						let cust = r.message;
						frm.set_value({
							customer: cust.name ? String(cust.name) : "",
							company_name: cust.company_name || "",
							company_gst: cust.company_gst || "",
							contact_name: cust.customer_name || "",
							contact_phone: cust.contact_phone || "",
							contact_email: cust.contact_email || "",
							address: cust.address || "",
							tally_serial: cust.tally_serial || "",
							license_type: cust.license_type || ""
						}).then(() => {
							set_customer_details_read_only(frm);
						});

						frappe.show_alert({
							message: __("Customer created and details auto-filled successfully!"),
							indicator: "green"
						});

						add_dialog.hide();
						if (parent_dialog) {
							parent_dialog.hide();
						}
					}
				},
				error: function() {
					add_dialog.get_primary_btn().prop("disabled", false);
				}
			});
		}
	});

	add_dialog.show();
}

function handle_executive_1_permission(frm) {
	is_admin_or_owner(function(is_admin) {
		frm.set_df_property("executive_1", "read_only", is_admin ? 0 : 1);
	});
}

function handle_referred_by_dependency(frm) {
	if (frm.doc.lead_source === "Reference") {
		frm.set_df_property("referred_by", "hidden", 0);
		frm.set_df_property("referred_by", "reqd", 1);
	} else {
		frm.set_df_property("referred_by", "hidden", 1);
		frm.set_df_property("referred_by", "reqd", 0);
	}
}

function open_quotation_preview_dialog(frm, doctype) {
	if (frm.is_new()) {
		frappe.msgprint(__("Please save the record first before viewing quotation."));
		return;
	}
	if (!frm.doc.items || frm.doc.items.length === 0) {
		frappe.msgprint({
			title: __("No Items"),
			indicator: "orange",
			message: __("Please add at least one item in the Items table to preview quotation.")
		});
		return;
	}

	let method_name = (doctype === "Hbs Tally Renewal" || frm.doctype === "Hbs Tally Renewal")
		? "hbs_crm.hbs_crm.doctype.hbs_tally_renewal.hbs_tally_renewal.get_renewal_quotation_html"
		: "hbs_crm.hbs_crm.doctype.hbs_crm_lead.hbs_crm_lead.get_lead_quotation_html";

	frappe.call({
		method: method_name,
		args: {
			name: frm.doc.name,
			print_format: frm.doc.quotation_format || "HBS Quotation"
		},
		freeze: true,
		freeze_message: __("Generating Quotation Preview..."),
		callback: function (r) {
			if (!r || !r.message) {
				frappe.msgprint(__("Unable to load quotation preview."));
				return;
			}

			let raw_html = r.message;

			// Strip out action-banner (Print and Get PDF) if present in raw_html
			let cleaned_html = raw_html.replace(/<div class="action-banner[^>]*>[\s\S]*?<\/div>/gi, "");

			let security_tags = `
				<style>
					.action-banner, .print-hide {
						display: none !important;
						visibility: hidden !important;
					}
					.print-format-gutter {
						padding: 0 !important;
						background: transparent !important;
					}
					@media print {
						html, body, * {
							display: none !important;
							visibility: hidden !important;
						}
					}
					body {
						-webkit-user-select: none !important;
						-moz-user-select: none !important;
						-ms-user-select: none !important;
						user-select: none !important;
					}
				</style>
				<script>
					document.addEventListener('contextmenu', function(e) { e.preventDefault(); return false; });
					document.addEventListener('keydown', function(e) {
						if ((e.ctrlKey || e.metaKey) && (e.key === 'p' || e.key === 'P' || e.key === 's' || e.key === 'S')) {
							e.preventDefault();
							e.stopPropagation();
							return false;
						}
					});
				<\/script>
			`;

			let final_html = cleaned_html;
			if (final_html.indexOf("<head>") !== -1) {
				final_html = final_html.replace("<head>", "<head>" + security_tags);
			} else {
				final_html = security_tags + final_html;
			}

			let d = new frappe.ui.Dialog({
				title: __("📄 Quotation Preview (View Only)"),
				size: "extra-large",
				fields: [
					{
						fieldtype: "HTML",
						fieldname: "quotation_preview_html"
					}
				],
				primary_action_label: __("Close"),
				primary_action() {
					d.hide();
				}
			});

			d.$wrapper.addClass("quotation-preview-modal no-print-quotation-dialog");

			let preview_container = `
				<style>
					.quotation-preview-modal .modal-dialog {
						max-width: 1250px !important;
						width: 96vw !important;
						margin: 15px auto !important;
					}
					.quotation-preview-modal .modal-content {
						border-radius: 8px !important;
						box-shadow: 0 10px 30px rgba(0,0,0,0.3) !important;
					}
					.quotation-preview-modal .modal-body {
						padding: 8px !important;
					}
					@media print {
						.no-print-quotation-dialog, .no-print-quotation-dialog * {
							display: none !important;
							visibility: hidden !important;
						}
					}
					.quotation-iframe-wrapper {
						background: #334155;
						padding: 8px;
						border-radius: 6px;
						box-shadow: inset 0 2px 5px rgba(0,0,0,0.25);
					}
					.quotation-preview-iframe {
						width: 100%;
						height: 87vh;
						border: none;
						border-radius: 4px;
						background: #fff;
						display: block;
					}
				</style>
				<div class="quotation-iframe-wrapper" oncontextmenu="return false;">
					<iframe class="quotation-preview-iframe" srcdoc="${frappe.utils.escape_html(final_html)}"></iframe>
				</div>
			`;

			d.fields_dict.quotation_preview_html.$wrapper.html(preview_container);

			let iframe_el = d.fields_dict.quotation_preview_html.$wrapper.find("iframe")[0];
			if (iframe_el) {
				iframe_el.onload = function() {
					try {
						let doc = iframe_el.contentDocument || iframe_el.contentWindow.document;
						doc.addEventListener("contextmenu", function(e) { e.preventDefault(); return false; });
						doc.addEventListener("keydown", function(e) {
							if ((e.ctrlKey || e.metaKey) && (e.key === 'p' || e.key === 'P' || e.key === 's' || e.key === 'S')) {
								e.preventDefault();
								e.stopPropagation();
								return false;
							}
						});
					} catch(err) {}
				};
			}

			let block_print = function(e) {
				if ((e.ctrlKey || e.metaKey) && (e.key === 'p' || e.key === 'P' || e.key === 's' || e.key === 'S')) {
					e.preventDefault();
					e.stopPropagation();
					frappe.show_alert({ message: __("Printing and exporting is disabled in Quotation Preview."), indicator: "orange" }, 3);
					return false;
				}
			};

			$(window).on("keydown.block_quotation_print", block_print);
			d.onhide = function () {
				$(window).off("keydown.block_quotation_print");
			};

			d.show();
		}
	});
}


