// Copyright (c) 2026, Hbs and contributors
// For license information, please see license.txt

frappe.ui.form.on("Hbs Crm Lead", {
	onload(frm) {
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
		}
		handle_executive_1_permission(frm);
	},

	refresh(frm) {
		render_activity_timeline_js(frm);
		toggle_won_status_read_only(frm);
		handle_lead_type_terms(frm);
		handle_referred_by_dependency(frm);
		handle_executive_1_permission(frm);

		frm.clear_custom_buttons();

		if (frm.doc.status !== "won" && frm.doc.status !== "lost") {
			frm.add_custom_button(__("🔍 Auto Fill Details"), function () {
				open_auto_fill_customer_dialog(frm);
			});
		}

		if (!frm.is_new()) {
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
	},
	lead_source(frm) {
		handle_referred_by_dependency(frm);
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

	additional_discount(frm) {
		calculate_totals(frm);
	}
});

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
		let naturally_read_only = ["customer", "total_before_tax", "total_tax", "total_after_tax", "final_total", "activity"];
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
	frappe.call({
		method: "hbs_crm.hbs_crm.doctype.hbs_crm_lead.hbs_crm_lead.get_rendered_email_template",
		args: { lead_name: frm.doc.name },
		callback: function (res) {
			if (res.message) {
				let default_subject = res.message.subject;
				let default_message = res.message.message;
				let default_from = res.message.from_email;
				let default_sender = res.message.sender_name;

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
							label: __("To"),
							fieldname: "to_email",
							fieldtype: "Data",
							default: frm.doc.contact_email || "",
							reqd: 1
						},
						{
							label: __("CC"),
							fieldname: "cc_email",
							fieldtype: "Data",
							default: (frappe.session.user && frappe.session.user.indexOf("@") !== -1) ? frappe.session.user : ""
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
							label: __("Attach Document 1 (Excel, PDF, etc.)"),
							fieldname: "attach_file_1",
							fieldtype: "Attach"
						},
						{
							label: __("Attach Document 2 (Excel, PDF, etc.)"),
							fieldname: "attach_file_2",
							fieldtype: "Attach"
						},
						{
							label: __("Attach Document 3 (Excel, PDF, etc.)"),
							fieldname: "attach_file_3",
							fieldtype: "Attach"
						}
					],
					primary_action_label: __("Send"),
					primary_action(values) {
						let extra_files = [values.attach_file_1, values.attach_file_2, values.attach_file_3].filter(f => f);
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
								extra_attachments: JSON.stringify(extra_files)
							},
							freeze: true,
							freeze_message: __("Sending email with attachments..."),
							callback: function (r) {
								if (!r.exc) {
									d.hide();
									frappe.show_alert({
										message: __("Email sent successfully!"),
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
		}
	});
}

frappe.ui.form.on("hbs crm items", {
	item_name(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		if (row.item_name) {
			frappe.db.get_doc("Hbs Product", row.item_name).then((doc) => {
				frappe.model.set_value(cdt, cdn, "rate", doc.rate || 0);
				frappe.model.set_value(cdt, cdn, "description", doc.description || "");
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

function open_auto_fill_customer_dialog(frm) {
	let dialog = new frappe.ui.Dialog({
		title: __("Search & Auto Fill Customer Details"),
		size: "large",
		fields: [
			{
				label: __("Search Customer"),
				fieldname: "search_term",
				fieldtype: "Data",
				description: __("Type Customer Name, Company Name, Phone, Email, or GST and press Enter to search"),
				onchange: function() {
					perform_customer_search(dialog, frm);
				}
			},
			{
				fieldtype: "Button",
				label: __("Search"),
				fieldname: "search_btn",
				click: function() {
					perform_customer_search(dialog, frm);
				}
			},
			{
				fieldtype: "HTML",
				fieldname: "results_html",
				label: __("Results")
			}
		]
	});

	dialog.$wrapper.find(".modal-dialog").css({
		"max-width": "950px",
		"width": "90%"
	});

	dialog.show();
}

function perform_customer_search(dialog, frm) {
	let term = dialog.get_value("search_term");
	if (!term || term.trim().length === 0) {
		dialog.set_df_property("results_html", "options", '<div class="text-muted text-center" style="padding: 10px;">Please enter a search term.</div>');
		return;
	}

	dialog.set_df_property("results_html", "options", '<div class="text-center" style="padding: 10px;"><i class="fa fa-spinner fa-spin"></i> Searching...</div>');

	frappe.call({
		method: "hbs_crm.hbs_crm.doctype.hbs_crm_lead.hbs_crm_lead.search_customers",
		args: {
			search_term: term
		},
		callback: function(r) {
			if (r.message && r.message.length > 0) {
				let html = `
					<div style="max-height: 420px; overflow-y: auto; margin-top: 15px;">
						<table class="table table-bordered table-hover" style="font-size: 13px;">
							<thead>
								<tr class="active">
									<th>${__("Name")}</th>
									<th>${__("Company")}</th>
									<th>${__("Phone")}</th>
									<th>${__("Email")}</th>
									<th>${__("Action")}</th>
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
							<td><b>${cust.customer_name || ''}</b><br><small class="text-muted">${cust.name}</small></td>
							<td>${cust.company_name || ''}<br><small class="text-muted">GST: ${cust.company_gst || ''}</small></td>
							<td>${cust.contact_phone || ''}</td>
							<td>${cust.contact_email || ''}</td>
							<td class="text-center" style="vertical-align: middle;">
								<button class="btn btn-xs btn-primary btn-fill-detail" data-key="${cust_key}">
									${__("Fill this detail")}
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

				// Attach click listener to the dynamically generated buttons
				dialog.$wrapper.find(".btn-fill-detail").on("click", function() {
					let key = $(this).attr("data-key");
					let customer_doc = window.customer_search_results[key];
					if (customer_doc) {
						// Auto fill values into lead form
						frm.set_value("customer", customer_doc.name);
						frm.set_value("company_name", customer_doc.company_name);
						frm.set_value("company_gst", customer_doc.company_gst);
						frm.set_value("contact_name", customer_doc.customer_name);
						frm.set_value("contact_phone", customer_doc.contact_phone);
						frm.set_value("contact_email", customer_doc.contact_email);
						frm.set_value("address", customer_doc.address);
						frm.set_value("tally_serial", customer_doc.tally_serial);
						frm.set_value("license_type", customer_doc.license_type);

						frappe.show_alert({
							message: __("Customer details auto-filled successfully!"),
							indicator: "green"
						});

						dialog.hide();
					}
				});
			} else {
				dialog.set_df_property("results_html", "options", '<div class="text-danger text-center" style="padding: 10px;">No matching customers found.</div>');
			}
		}
	});
}

function handle_executive_1_permission(frm) {
	if (frappe.session.user === "Administrator" || frappe.user.has_role("System Manager")) {
		frm.set_df_property("executive_1", "read_only", 0);
		return;
	}

	frappe.db.get_value("Hbs User Hierarchy", {"user": frappe.session.user}, "role_type", function(r) {
		let role = r && (r.role_type || (r.message && r.message.role_type));
		if (role === "Owner") {
			frm.set_df_property("executive_1", "read_only", 0);
		} else {
			frm.set_df_property("executive_1", "read_only", 1);
		}
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

