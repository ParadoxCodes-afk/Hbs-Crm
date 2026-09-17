// Copyright (c) 2026, Hbs and contributors
// For license information, please see license.txt

frappe.listview_settings["Hbs Tally Renewal"] = {
	add_fields: [
		"tally_serial", "tss_tally_serial", "cc_acc_name", "portal_acc_name",
		"cc_contact", "portal_contact", "cc_mobile", "portal_mobile", "cc_phone",
		"portal_phone", "cc_email", "portal_email", "license", "flavour",
		"tally_version", "product_ver", "acc_expiry_date", "portal_expiry_date",
		"crm_status", "crm_stage", "crm_priority", "rfm_segment", "crm_ex_1", "last_remark",
		"last_remarks_date"
	],
	formatters: {
		tally_serial(val, df, doc) {
			return val || doc.tss_tally_serial || doc.tally_serial || doc.name;
		}
	},
	refresh(listview) {
		attach_serial_remarks_and_preview(listview);
	},
	onload(listview) {
		setup_renewal_caller_preview(listview);

		if (!frappe.route_options) {
			frappe.route_options = {};
		}

		if (!frappe.route_options["crm_status"]) {
			frappe.route_options["crm_status"] = "PENDING";
		}
		if (!frappe.route_options["follow_up_date"]) {
			frappe.route_options["follow_up_date"] = ["<=", frappe.datetime.get_today()];
		}

		setTimeout(() => {
			if (frappe.route_options) {
				delete frappe.route_options.crm_status;
				delete frappe.route_options.follow_up_date;
			}
		}, 100);

		// 1. Bulk Email toolbar button (Available to all users under Operations)
		listview.page.add_inner_button(__("📧 Send Bulk Quotation"), () => {
			open_bulk_email_dialog(listview);
		}, __("Operations"));

		check_if_owner_or_admin(function (is_owner_admin) {
			if (!is_owner_admin) return;

			// Sync Portal API (Admin & Owner only under Operations)
			listview.page.add_inner_button(__("🔄 Sync Portal API"), () => {
				let checked = listview.get_checked_items(true);
				if (checked && checked.length > 0) {
					frappe.call({
						method: "hbs_crm.hbs_crm.doctype.hbs_tally_renewal.hbs_tally_renewal.check_selected_portal",
						args: { names: JSON.stringify(checked) },
						freeze: true,
						freeze_message: __("Syncing {0} selected records with Tally Portal API...", [checked.length]),
						callback: function (r) {
							if (r.message) {
								frappe.show_alert({
									message: r.message.message || __("Portal sync completed!"),
									indicator: "green"
								});
								listview.refresh();
							}
						}
					});
				} else {
					frappe.confirm(
						__("No records selected. Do you want to sync all records with Tally Portal API?"),
						() => {
							frappe.call({
								method: "hbs_crm.hbs_crm.doctype.hbs_tally_renewal.hbs_tally_renewal.sync_all_portal_records",
								freeze: true,
								freeze_message: __("Syncing all records with Tally Portal API..."),
								callback: function (r) {
									if (r.message) {
										frappe.show_alert({
											message: r.message.message || __("Portal sync completed!"),
											indicator: r.message.status === "info" ? "blue" : "green"
										});
										listview.refresh();
									}
								}
							});
						}
					);
				}
			}, __("Operations"));

			// Import Past Remarks Excel (Admin & Owner only under Operations)
			listview.page.add_inner_button(__("📂 Import Past Remarks"), () => {
				open_import_remarks_dialog(listview);
			}, __("Operations"));

			// Assign Executive (Admin & Owner only under Operations)
			listview.page.add_inner_button(__("👤 Assign Executive"), () => {
				open_assign_executive_list_dialog(listview);
			}, __("Operations"));

			// Quick Edit Records (Admin & Owner only)
			listview.page.add_inner_button(__("⚡ Quick Edit Records"), () => {
				open_owner_bulk_edit_dialog(listview);
			}, __("Operations"));
		});
	}
};

function open_bulk_email_dialog(listview) {
	let checked = listview.get_checked_items(true);
	if (!checked || checked.length === 0) {
		frappe.msgprint({
			title: __("No Records Selected"),
			indicator: "orange",
			message: __("Please select one or more records using checkboxes to send bulk quotation email.")
		});
		return;
	}

	frappe.call({
		method: "hbs_crm.hbs_crm.doctype.hbs_tally_renewal.hbs_tally_renewal.get_renewal_email_template_defaults",
		freeze: true,
		freeze_message: __("Loading email template..."),
		callback: function (res) {
			let defaults = res.message || {};
			let default_subject = defaults.subject || "Quotation for Tally TSS Renewal - Serial: {{ doc.tss_tally_serial or doc.tally_serial or '' }} ({{ doc.cc_acc_name or doc.portal_acc_name or 'Valued Client' }})";
			let default_message = defaults.message || "";
			let default_sender = defaults.sender_name || "HBS Sales Team";
			let default_from = defaults.from_email || "tally@hbsmail.in";

			let d = new frappe.ui.Dialog({
				title: __("📧 Send Bulk TSS Quotation ({0} Records Selected)", [checked.length]),
				size: "large",
				fields: [
					{
						label: __("Sender Display Name"),
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
						label: __("CC (Executive Copy)"),
						fieldname: "cc_email",
						fieldtype: "Data",
						default: (frappe.session.user && frappe.session.user.indexOf("@") !== -1) ? frappe.session.user : "",
						description: __("Logged in user email will receive a copy of each sent quotation")
					},
					{
						label: __("Subject Template"),
						fieldname: "subject",
						fieldtype: "Data",
						default: default_subject,
						reqd: 1
					},
					{
						label: __("Message Template"),
						fieldname: "message",
						fieldtype: "Text Editor",
						default: default_message,
						reqd: 1
					}
				],
				primary_action_label: __("Send Quotation to {0} Clients", [checked.length]),
				primary_action(values) {
			frappe.confirm(
				__("Are you sure you want to send this bulk email to <b>{0}</b> selected records?", [checked.length]),
				function () {
					d.hide();
					frappe.call({
						method: "hbs_crm.hbs_crm.doctype.hbs_tally_renewal.hbs_tally_renewal.send_bulk_renewal_email",
						args: {
							names: JSON.stringify(checked),
							subject_template: values.subject,
							message_template: values.message,
							cc_email: values.cc_email,
							from_email: values.from_email,
							sender_name: values.sender_name
						},
						freeze: true,
						freeze_message: __("Sending bulk emails to {0} records...", [checked.length]),
						callback: function (r) {
							if (r.message) {
								let res = r.message;
								let html = `<div><b>${res.success_count}</b> emails sent successfully.</div>`;
								if (res.skipped_no_email && res.skipped_no_email.length > 0) {
									html += `<div style="color: #c2410c; margin-top: 6px;"><b>${res.skipped_no_email.length}</b> records skipped (no Email ID found).</div>`;
								}
								if (res.failed_records && res.failed_records.length > 0) {
									html += `<div style="color: #dc2626; margin-top: 6px;"><b>${res.failed_records.length}</b> records failed to send.</div>`;
								}
								frappe.msgprint({
									title: __("Bulk Email Result"),
									message: html,
									indicator: res.success_count > 0 ? "green" : "orange"
								});
								listview.refresh();
							}
						}
					});
				}
			);
		}
	});

	d.show();
		}
	});
}

function check_if_owner_or_admin(callback) {
	if (frappe.session.user === "Administrator" || frappe.user.has_role("System Manager")) {
		callback(true);
		return;
	}

	frappe.call({
		method: "hbs_crm.hbs_crm.doctype.hbs_tally_renewal.hbs_tally_renewal.check_user_hierarchy_role",
		callback: function (r) {
			let is_allowed = r.message && r.message.is_owner_or_admin;
			callback(!!is_allowed);
		}
	});
}

function open_import_remarks_dialog(listview) {
	let d = new frappe.ui.Dialog({
		title: __("📂 Import Past Remarks (Excel)"),
		fields: [
			{
				label: __("Remarks Excel File (.xlsx or .xls)"),
				fieldname: "file_url",
				fieldtype: "Attach",
				reqd: 1,
				description: __("Upload Excel containing columns: Serial No, User, Date, Time, Remarks")
			},
			{
				label: __("Overwrite existing remarks"),
				fieldname: "overwrite",
				fieldtype: "Check",
				default: 0,
				description: __("If checked, existing past remarks will be replaced. If unchecked, only records with empty past remarks will be updated.")
			}
		],
		primary_action_label: __("Start Import"),
		primary_action(values) {
			if (!values.file_url) {
				frappe.msgprint(__("Please upload an Excel file first."));
				return;
			}
			frappe.call({
				method: "hbs_crm.hbs_crm.doctype.hbs_tally_renewal.hbs_tally_renewal.import_past_remarks_from_file",
				args: {
					file_url: values.file_url,
					overwrite: values.overwrite ? 1 : 0
				},
				freeze: true,
				freeze_message: __("Processing remarks Excel and matching serial numbers..."),
				callback: function (r) {
					if (r.message) {
						d.hide();
						frappe.msgprint({
							title: __("Remarks Import Result"),
							indicator: r.message.status === "success" ? "green" : "orange",
							message: r.message.message
						});
						listview.refresh();
					}
				}
			});
		}
	});
	d.show();
}

function open_assign_executive_list_dialog(listview) {
	let checked = listview.get_checked_items(true);
	if (!checked || checked.length === 0) {
		frappe.msgprint({
			title: __("No Records Selected"),
			indicator: "orange",
			message: __("Please select one or more records using the checkboxes to assign an executive.")
		});
		return;
	}

	let d = new frappe.ui.Dialog({
		title: __("Assign Executive ({0} records selected)", [checked.length]),
		fields: [
			{
				label: __("Executive 1"),
				fieldname: "executive_1",
				fieldtype: "Link",
				options: "User",
				default: frappe.session.user,
				reqd: 1
			},
			{
				label: __("Executive 2 (Optional)"),
				fieldname: "executive_2",
				fieldtype: "Link",
				options: "User"
			}
		],
		primary_action_label: __("Assign"),
		primary_action(values) {
			frappe.call({
				method: "hbs_crm.hbs_crm.doctype.hbs_tally_renewal.hbs_tally_renewal.assign_executive",
				args: {
					names: JSON.stringify(checked),
					executive_1: values.executive_1,
					executive_2: values.executive_2 || ""
				},
				freeze: true,
				freeze_message: __("Assigning executive to {0} records...", [checked.length]),
				callback: function (r) {
					if (!r.exc) {
						d.hide();
						frappe.show_alert({
							message: __("Executive assigned successfully to {0} records!", [checked.length]),
							indicator: "green"
						});
						listview.refresh();
					}
				}
			});
		}
	});
	d.show();
}

function open_owner_bulk_edit_dialog(listview) {
	let checked = listview.get_checked_items(true);
	if (!checked || checked.length === 0) {
		frappe.msgprint({
			title: __("No Records Selected"),
			indicator: "orange",
			message: __("Please select one or more records using checkboxes to update.")
		});
		return;
	}

	let d = new frappe.ui.Dialog({
		title: __("⚡ Quick Edit Records ({0} selected)", [checked.length]),
		size: "large",
		fields: [
			{
				fieldname: "help_html",
				fieldtype: "HTML",
				options: `<div style="margin-bottom: 12px; padding: 8px 12px; background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 6px; color: #166534; font-size: 12px;">
					<b>Note:</b> Only filled fields will be updated on the selected records. Leave any field empty if you do not wish to change it.
				</div>`
			},
			{
				fieldname: "col1",
				fieldtype: "Column Break"
			},
			{
				label: __("CRM Status"),
				fieldname: "crm_status",
				fieldtype: "Select",
				options: "\nPENDING\nSold\nLost"
			},
			{
				label: __("CRM Stage"),
				fieldname: "crm_stage",
				fieldtype: "Select",
				options: "\nCustomer Not Responding\nCUSTOMER REQ PENDING\nDEMO/MEETING DONE\nDEMO/ MEETING FIXED\nIN FOLLOW-UP\nLEAD\nNEGOTIATION\nPAYMENT RECEIVED\nPENDING FOR INSTALLATION\nPENDING PAYMENT\nQUOTATION PENDING\nQUOTATION SENT\nWAITING FOR CONFIRMATION"
			},
			{
				label: __("Reference Status"),
				fieldname: "crm_ref",
				fieldtype: "Select",
				options: "\nActive\nMoved Out"
			},
			{
				fieldname: "col2",
				fieldtype: "Column Break"
			},
			{
				label: __("Follow-up Date"),
				fieldname: "follow_up_date",
				fieldtype: "Date"
			},
			{
				label: __("Last Remarks Date"),
				fieldname: "last_remarks_date",
				fieldtype: "Date"
			},
			{
				fieldname: "sec_remarks",
				fieldtype: "Section Break",
				label: __("Activity / Remarks")
			},
			{
				label: __("Add Remark / Activity Note (Optional)"),
				fieldname: "remark",
				fieldtype: "Small Text",
				description: __("If provided, this remark will be logged into the activity timeline for each selected record.")
			}
		],
		primary_action_label: __("Update Records"),
		primary_action(values) {
			let fields_to_update = {};
			["crm_status", "crm_stage", "crm_ref", "follow_up_date", "last_remarks_date"].forEach(f => {
				if (values[f] !== undefined && values[f] !== null && String(values[f]).trim() !== "") {
					fields_to_update[f] = values[f];
				}
			});

			let remark = (values.remark || "").trim();
			if (Object.keys(fields_to_update).length === 0 && !remark) {
				frappe.msgprint({
					title: __("No Changes Specified"),
					indicator: "orange",
					message: __("Please specify at least one field value or enter a remark.")
				});
				return;
			}

			frappe.call({
				method: "hbs_crm.hbs_crm.doctype.hbs_tally_renewal.hbs_tally_renewal.bulk_update_renewal_fields",
				args: {
					names: JSON.stringify(checked),
					updates: JSON.stringify(fields_to_update),
					remark: remark
				},
				freeze: true,
				freeze_message: __("Updating {0} records...", [checked.length]),
				callback: function (r) {
					if (!r.exc && r.message) {
						d.hide();
						frappe.show_alert({
							message: r.message.message || __("Updated successfully!"),
							indicator: "green"
						});
						listview.refresh();
					}
				}
			});
		}
	});
	d.show();
}

function attach_serial_remarks_and_preview(listview) {
	if (!listview || !listview.data) return;

	listview.$result.find(".list-row-container").each(function () {
		let $row = $(this);
		let $link = $row.find(".list-subject a[data-name]");
		if (!$link.length) return;

		let docname = $link.attr("data-name");
		let doc = (listview.data || []).find(d => String(d.name) === String(docname));
		if (!doc) return;

		let $parent = $link.parent();
		$parent.css({
			"display": "inline-flex",
			"align-items": "center",
			"max-width": "100%"
		});

		$link.addClass("renewal-hover-trigger");
		$parent.find(".renewal-remark-badge").remove();

		if (doc.last_remark) {
			let remark = frappe.utils.escape_html(doc.last_remark);
			let dt = doc.last_remarks_date ? ` (${frappe.datetime.str_to_user(doc.last_remarks_date)})` : "";
			let badge_html = `
				<span class="renewal-remark-badge" data-name="${doc.name}" style="cursor: pointer; flex-shrink: 0; display: inline-flex; align-items: center; justify-content: center; width: 19px; height: 19px; border-radius: 50%; background: #eff6ff; color: #2563eb; border: 1px solid #bfdbfe; margin-left: 6px; vertical-align: middle;" title="Latest Remark${dt}:&#10;${remark}">
					<svg style="width: 11px; height: 11px; fill: currentColor;" viewBox="0 0 24 24"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm-2 12H6v-2h12v2zm0-3H6V9h12v2zm0-3H6V6h12v2z"/></svg>
				</span>
			`;
			$link.after(badge_html);
		}
	});
}

function setup_renewal_caller_preview(listview) {
	let popover = document.getElementById("renewal-caller-preview-popover");
	if (!popover) {
		popover = document.createElement("div");
		popover.id = "renewal-caller-preview-popover";
		popover.style.cssText = `
			position: fixed;
			z-index: 99999;
			display: none;
			width: 350px;
			background: #ffffff;
			border: 1px solid #cbd5e1;
			border-radius: 8px;
			box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.15), 0 8px 10px -6px rgba(0, 0, 0, 0.1);
			padding: 12px 14px;
			font-family: inherit;
			font-size: 12px;
			line-height: 1.4;
			color: #1e293b;
			text-align: left !important;
			pointer-events: auto;
		`;
		document.body.appendChild(popover);
	}

	let hide_timer = null;
	let show_timer = null;

	const clear_timers = () => {
		if (hide_timer) { clearTimeout(hide_timer); hide_timer = null; }
		if (show_timer) { clearTimeout(show_timer); show_timer = null; }
	};

	popover.onmouseenter = () => clear_timers();
	popover.onmouseleave = () => {
		clear_timers();
		hide_timer = setTimeout(() => {
			popover.style.display = "none";
		}, 200);
	};

	$(window).off("scroll.renewal_preview").on("scroll.renewal_preview", () => {
		if (popover) popover.style.display = "none";
	});

	// Delegate hover and click events
	$(listview.$result).off("mouseenter.renewal_preview mouseleave.renewal_preview", ".renewal-hover-trigger");
	$(listview.$result).off("click.renewal_remark", ".renewal-remark-badge");

	$(listview.$result).on("mouseenter.renewal_preview", ".renewal-hover-trigger", function () {
		clear_timers();
		let target = this;
		let docname = $(target).attr("data-name");
		if (!docname) return;

		show_timer = setTimeout(() => {
			let doc = (listview.data || []).find(d => String(d.name) === String(docname));
			if (!doc) return;

			render_preview_card(popover, doc, target);
		}, 180);
	});

	$(listview.$result).on("mouseleave.renewal_preview", ".renewal-hover-trigger", function () {
		clear_timers();
		hide_timer = setTimeout(() => {
			popover.style.display = "none";
		}, 220);
	});

	$(listview.$result).on("click.renewal_remark", ".renewal-remark-badge", function (e) {
		e.stopPropagation();
		e.preventDefault();
		let docname = $(this).attr("data-name");
		let doc = (listview.data || []).find(d => String(d.name) === String(docname));
		if (!doc || !doc.last_remark) return;

		let date_str = doc.last_remarks_date ? frappe.datetime.str_to_user(doc.last_remarks_date) : "—";
		let serial = doc.tally_serial || doc.tss_tally_serial || doc.name;
		let company = doc.cc_acc_name || doc.portal_acc_name || "";

		frappe.msgprint({
			title: __("Latest Remark - Serial {0}", [serial]),
			indicator: "blue",
			message: `
				<div style="font-size: 13px;">
					${company ? `<div style="font-weight: 600; font-size: 14px; margin-bottom: 6px; color: #1e293b;">${frappe.utils.escape_html(company)}</div>` : ""}
					<div style="color: #64748b; font-size: 12px; margin-bottom: 10px;"><b>Date:</b> ${date_str}</div>
					<div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 12px; white-space: pre-wrap; word-break: break-word; color: #1e293b; font-size: 13px; max-height: 250px; overflow-y: auto;">${frappe.utils.escape_html(doc.last_remark)}</div>
				</div>
			`
		});
	});
}

function render_preview_card(popover, doc, target) {
	let company = frappe.utils.escape_html(doc.cc_acc_name || doc.portal_acc_name || "No Company Name");
	let serial = frappe.utils.escape_html(String(doc.tally_serial || doc.tss_tally_serial || doc.name));
	let contact = frappe.utils.escape_html(doc.cc_contact || doc.portal_contact || "—");
	let mobile = (doc.cc_mobile || doc.portal_mobile || "").trim();
	let phone = (doc.cc_phone || doc.portal_phone || "").trim();
	let email = (doc.cc_email || doc.portal_email || "").trim();

	let license = frappe.utils.escape_html(doc.license || "—");
	let version = frappe.utils.escape_html([doc.tally_version || doc.product_ver, doc.flavour].filter(Boolean).join(" ") || "—");

	let expiry = doc.acc_expiry_date || doc.portal_expiry_date || "";
	let expiry_html = "—";
	if (expiry) {
		let exp_user = frappe.datetime.str_to_user(expiry);
		let is_expired = frappe.datetime.get_diff(expiry, frappe.datetime.get_today()) < 0;
		if (is_expired) {
			expiry_html = `<span style="color: #dc2626; font-weight: 600;">${exp_user} (Expired)</span>`;
		} else {
			expiry_html = `<span style="color: #166534; font-weight: 600;">${exp_user}</span>`;
		}
	}

	let status = frappe.utils.escape_html(doc.crm_status || "PENDING");
	let stage = frappe.utils.escape_html(doc.crm_stage || "—");
	let rfm_segment = frappe.utils.escape_html(doc.rfm_segment || "—");
	let priority = frappe.utils.escape_html(doc.crm_priority || "");
	let executive = frappe.utils.escape_html(doc.crm_ex_1 || "—");

	let phone_html = "—";
	if (mobile && phone && mobile !== phone) {
		phone_html = `<a href="tel:${frappe.utils.escape_html(mobile)}" style="color: #2563eb; font-weight: 600; text-decoration: none;">📞 ${frappe.utils.escape_html(mobile)}</a> / <a href="tel:${frappe.utils.escape_html(phone)}" style="color: #2563eb; text-decoration: none;">${frappe.utils.escape_html(phone)}</a>`;
	} else if (mobile) {
		phone_html = `<a href="tel:${frappe.utils.escape_html(mobile)}" style="color: #2563eb; font-weight: 600; text-decoration: none;">📞 ${frappe.utils.escape_html(mobile)}</a>`;
	} else if (phone) {
		phone_html = `<a href="tel:${frappe.utils.escape_html(phone)}" style="color: #2563eb; font-weight: 600; text-decoration: none;">📞 ${frappe.utils.escape_html(phone)}</a>`;
	}

	let email_html = email ? `<a href="mailto:${frappe.utils.escape_html(email)}" style="color: #2563eb; text-decoration: none; word-break: break-all;">✉️ ${frappe.utils.escape_html(email)}</a>` : "—";

	let remark_html = `<span style="color: #94a3b8; font-style: italic; text-align: left; display: block;">No remarks</span>`;
	if (doc.last_remark) {
		let dt = doc.last_remarks_date ? `<span style="color: #64748b; font-size: 11px;"> (${frappe.datetime.str_to_user(doc.last_remarks_date)})</span>` : "";
		remark_html = `
			<div style="font-weight: 600; color: #64748b; font-size: 11px; margin-bottom: 3px; text-align: left;">
				Last Remark${dt}:
			</div>
			<div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 4px; padding: 6px 8px; max-height: 65px; overflow-y: auto; font-size: 11.5px; color: #1e293b; line-height: 1.35; white-space: pre-wrap; word-break: break-word; text-align: left !important;">
				${frappe.utils.escape_html((doc.last_remark || "").trim())}
			</div>
		`;
	}

	popover.innerHTML = `
		<div style="border-bottom: 1px solid #e2e8f0; padding-bottom: 8px; margin-bottom: 8px; text-align: left;">
			<div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 8px; text-align: left;">
				<div style="font-weight: 700; font-size: 13.5px; color: #0f172a; line-height: 1.25; overflow: hidden; text-overflow: ellipsis; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; text-align: left;">
					${company}
				</div>
				<span style="background: #f1f5f9; color: #475569; font-size: 11px; font-weight: 600; padding: 2px 6px; border-radius: 4px; white-space: nowrap; flex-shrink: 0;">
					SN: ${serial}
				</span>
			</div>
		</div>

		<div style="display: grid; grid-template-columns: 85px 1fr; row-gap: 4px; column-gap: 8px; font-size: 11.5px; text-align: left;">
			<div style="color: #64748b;">Contact:</div>
			<div style="font-weight: 500; color: #1e293b;">${contact}</div>

			<div style="color: #64748b;">Phone:</div>
			<div>${phone_html}</div>

			<div style="color: #64748b;">Email:</div>
			<div>${email_html}</div>

			<div style="color: #64748b;">License:</div>
			<div style="color: #1e293b;">${license} <span style="color: #64748b; font-size: 11px;">(${version})</span></div>

			<div style="color: #64748b;">TSS Expiry:</div>
			<div>${expiry_html}</div>

			<div style="color: #64748b;">Status / Stage:</div>
			<div><span style="font-weight: 600; color: #0284c7;">${status}</span> &bull; <span style="color: #475569;">${stage}</span></div>

			<div style="color: #64748b;">RFM Segment:</div>
			<div><span style="font-weight: 500; color: #1e293b;">${rfm_segment}</span>${priority ? ` <span style="color: #64748b; font-size: 11px;">(${priority})</span>` : ""}</div>

			<div style="color: #64748b;">Executive:</div>
			<div style="color: #1e293b; font-weight: 500;">${executive}</div>
		</div>

		<div style="margin-top: 8px; border-top: 1px solid #f1f5f9; padding-top: 6px; text-align: left;">
			${remark_html}
		</div>
	`;

	popover.style.display = "block";

	let rect = target.getBoundingClientRect();
	let popHeight = popover.offsetHeight || 260;
	let popWidth = popover.offsetWidth || 350;

	let left = rect.left;
	if (left + popWidth > window.innerWidth - 15) {
		left = window.innerWidth - popWidth - 15;
	}
	if (left < 10) left = 10;

	let top = rect.bottom + 6;
	if (top + popHeight > window.innerHeight - 15) {
		top = rect.top - popHeight - 6;
		if (top < 10) top = 10;
	}

	popover.style.left = `${left}px`;
	popover.style.top = `${top}px`;
}
