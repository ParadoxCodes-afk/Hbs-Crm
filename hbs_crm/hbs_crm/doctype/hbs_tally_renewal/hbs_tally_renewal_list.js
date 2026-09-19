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
		},
		license(val) {
			if (!val) return "";
			let lower = val.toString().trim().toLowerCase();
			if (lower.includes("auditor")) return "AUDITOR";
			if (lower.includes("gold")) return "GOLD";
			if (lower.includes("silver")) return "SILVER";
			return val;
		}
	},
	refresh(listview) {
		if (listview.column_max_widths) {
			listview.column_max_widths["license"] = 80;
			listview.column_max_widths["crm_status"] = 80;
			listview.column_max_widths["crm_priority"] = 75;
			listview.column_max_widths["rfm_segment"] = 75;
			listview.column_max_widths["acc_expiry_date"] = 100;
			if (typeof listview.apply_column_widths === "function") {
				listview.apply_column_widths();
			}
		}
		attach_serial_remarks_and_preview(listview);
	},
	onload(listview) {
		frappe.dom.set_style(`
			.frappe-list[data-doctype="Hbs Tally Renewal"] .list-row-col.license,
			.list-view[data-doctype="Hbs Tally Renewal"] .list-row-col.license {
				max-width: 90px !important;
				min-width: 75px !important;
				width: 80px !important;
				flex: 0 0 80px !important;
			}
			.frappe-list[data-doctype="Hbs Tally Renewal"] .list-row-col.crm_status,
			.list-view[data-doctype="Hbs Tally Renewal"] .list-row-col.crm_status {
				max-width: 90px !important;
				min-width: 75px !important;
				width: 80px !important;
				flex: 0 0 80px !important;
			}
			.frappe-list[data-doctype="Hbs Tally Renewal"] .list-row-col.crm_priority,
			.list-view[data-doctype="Hbs Tally Renewal"] .list-row-col.crm_priority,
			.frappe-list[data-doctype="Hbs Tally Renewal"] .list-row-col.rfm_segment,
			.list-view[data-doctype="Hbs Tally Renewal"] .list-row-col.rfm_segment {
				max-width: 85px !important;
				min-width: 70px !important;
				width: 75px !important;
				flex: 0 0 75px !important;
			}
			.frappe-list[data-doctype="Hbs Tally Renewal"] .list-row-col.acc_expiry_date,
			.list-view[data-doctype="Hbs Tally Renewal"] .list-row-col.acc_expiry_date {
				max-width: 105px !important;
				min-width: 95px !important;
				width: 100px !important;
				flex: 0 0 100px !important;
			}
		`);

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
									indicator: r.message.status === "info" ? "orange" : "green"
								}, 7);
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

			// --- CUSTOM EXCEL IMPORT DATA (Fallback when standard Frappe Data Import tool fails) ---
			listview.page.add_inner_button(__("📥 Import Master Data"), () => {
				open_custom_import_data_dialog(listview);
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

// --- CUSTOM EXCEL IMPORT DATA DIALOG ---
function open_custom_import_data_dialog(listview) {
	let d = new frappe.ui.Dialog({
		title: __("📥 Import Master Data (Excel)"),
		fields: [
			{
				label: __("Excel File (.xlsx or .xls)"),
				fieldname: "file_url",
				fieldtype: "Attach",
				reqd: 1,
				description: __("Upload Excel with columns like Serial No, Status, Expiry Date, EXE, Customer Name, Mobile, etc.")
			}
		],
		primary_action_label: __("Start Import"),
		primary_action(values) {
			if (!values.file_url) {
				frappe.msgprint(__("Please upload an Excel file first."));
				return;
			}

			d.hide();

			frappe.call({
				method: "hbs_crm.hbs_crm.doctype.hbs_tally_renewal.hbs_tally_renewal.import_renewals_from_excel",
				args: {
					file_url: values.file_url
				},
				callback: function (r) {
					if (r.message) {
						show_import_result_report(r.message, listview);
					}
				}
			});
		}
	});
	d.show();
}

function show_import_result_report(data, listview) {
	let created = data.created_count || 0;
	let updated = data.updated_count || 0;
	let skipped = data.skipped_count || 0;
	let total = created + updated + skipped;
	let failed_rows = data.failed_rows || [];

	let failed_html = "";
	if (failed_rows.length > 0) {
		let rows_tr = failed_rows.map(row => `
			<tr>
				<td style="text-align: center; font-weight: bold; color: #4b5563;">${row.row}</td>
				<td style="font-family: monospace; font-weight: 600;">${frappe.utils.escape_html(String(row.serial || "-"))}</td>
				<td>${frappe.utils.escape_html(String(row.party || "-"))}</td>
				<td style="color: #b91c1c; font-weight: 500;">${frappe.utils.escape_html(String(row.reason || ""))}</td>
			</tr>
		`).join("");

		failed_html = `
			<div style="margin-top: 20px;">
				<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
					<h5 style="margin: 0; color: #b91c1c; font-weight: bold;">
						⚠️ Skipped / Unimported Records (${failed_rows.length})
					</h5>
					<button class="btn btn-xs btn-default btn-download-failed" style="font-weight: 600;">
						📥 Download Failed Rows (CSV)
					</button>
				</div>
				<div style="max-height: 320px; overflow-y: auto; border: 1px solid #e5e7eb; border-radius: 6px;">
					<table class="table table-bordered table-sm" style="margin: 0; font-size: 12px; width: 100%;">
						<thead style="position: sticky; top: 0; background-color: #f9fafb; z-index: 1;">
							<tr style="color: #374151;">
								<th style="width: 75px; text-align: center;">Excel Row</th>
								<th style="width: 140px;">Serial No</th>
								<th style="width: 200px;">Party / Company</th>
								<th>Exact Reason</th>
							</tr>
						</thead>
						<tbody>
							${rows_tr}
						</tbody>
					</table>
				</div>
			</div>
		`;
	} else {
		failed_html = `
			<div class="alert alert-success" style="margin-top: 20px; font-weight: 500;">
				🎉 <b>All records imported successfully!</b> No rows were skipped.
			</div>
		`;
	}

	let content = `
		<div style="padding: 10px 0;">
			<div style="display: flex; gap: 12px; margin-bottom: 12px; flex-wrap: wrap;">
				<div style="flex: 1; min-width: 120px; background-color: #ecfdf5; border: 1px solid #a7f3d0; border-radius: 6px; padding: 10px; text-align: center;">
					<div style="font-size: 20px; font-weight: bold; color: #065f46;">${created}</div>
					<div style="font-size: 12px; color: #047857; font-weight: 600;">New Created</div>
				</div>
				<div style="flex: 1; min-width: 120px; background-color: #eff6ff; border: 1px solid #bfdbfe; border-radius: 6px; padding: 10px; text-align: center;">
					<div style="font-size: 20px; font-weight: bold; color: #1e40af;">${updated}</div>
					<div style="font-size: 12px; color: #1d4ed8; font-weight: 600;">Existing Updated</div>
				</div>
				<div style="flex: 1; min-width: 120px; background-color: ${skipped > 0 ? '#fef2f2' : '#f9fafb'}; border: 1px solid ${skipped > 0 ? '#fecaca' : '#e5e7eb'}; border-radius: 6px; padding: 10px; text-align: center;">
					<div style="font-size: 20px; font-weight: bold; color: ${skipped > 0 ? '#b91c1c' : '#6b7280'};">${skipped}</div>
					<div style="font-size: 12px; color: ${skipped > 0 ? '#dc2626' : '#6b7280'}; font-weight: 600;">Skipped / Failed</div>
				</div>
				<div style="flex: 1; min-width: 120px; background-color: #f3f4f6; border: 1px solid #e5e7eb; border-radius: 6px; padding: 10px; text-align: center;">
					<div style="font-size: 20px; font-weight: bold; color: #374151;">${total}</div>
					<div style="font-size: 12px; color: #4b5563; font-weight: 600;">Total Rows</div>
				</div>
			</div>
			${failed_html}
		</div>
	`;

	let report_dialog = new frappe.ui.Dialog({
		title: __("📊 Renewal Data Import Report"),
		size: "large",
		fields: [
			{
				fieldname: "report_html",
				fieldtype: "HTML",
				options: content
			}
		],
		primary_action_label: __("Close"),
		primary_action() {
			report_dialog.hide();
			listview.refresh();
		}
	});

	report_dialog.show();

	report_dialog.$wrapper.find(".btn-download-failed").on("click", function () {
		let csv = "Excel Row,Serial Number,Party Name,Reason\n";
		failed_rows.forEach(r => {
			let safe_reason = `"${(r.reason || '').replace(/"/g, '""')}"`;
			let safe_party = `"${(r.party || '').replace(/"/g, '""')}"`;
			csv += `${r.row},"${r.serial || ''}",${safe_party},${safe_reason}\n`;
		});
		let blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
		let url = URL.createObjectURL(blob);
		let a = document.createElement("a");
		a.href = url;
		a.download = `Unimported_Renewals_${frappe.datetime.now_datetime().replace(/[: ]/g, "_")}.csv`;
		document.body.appendChild(a);
		a.click();
		document.body.removeChild(a);
		URL.revokeObjectURL(url);
	});
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
	let company = frappe.utils.escape_html(doc.portal_acc_name || doc.cc_acc_name || "No Company Name");
	let serial = frappe.utils.escape_html(String(doc.tally_serial || doc.tss_tally_serial || doc.name));
	let contact = frappe.utils.escape_html(doc.portal_contact || doc.cc_contact || "—");

	let mobile_parts = [doc.portal_mobile, doc.cc_mobile].filter(Boolean).map(m => m.trim()).filter((v, i, a) => a.indexOf(v) === i);
	let phone_parts = [doc.portal_phone, doc.cc_phone].filter(Boolean).map(p => p.trim()).filter((v, i, a) => a.indexOf(v) === i);

	let mobile_html = mobile_parts.length ? mobile_parts.map(m => `<a href="tel:${frappe.utils.escape_html(m)}" style="color: #2563eb; font-weight: 600; text-decoration: none;">📞 ${frappe.utils.escape_html(m)}</a>`).join(" / ") : "—";
	let phone_html = phone_parts.length ? phone_parts.map(p => `<a href="tel:${frappe.utils.escape_html(p)}" style="color: #2563eb; font-weight: 600; text-decoration: none;">☎️ ${frappe.utils.escape_html(p)}</a>`).join(" / ") : "—";

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

	let sub_company = (doc.portal_acc_name && doc.cc_acc_name && doc.portal_acc_name.trim().toLowerCase() !== doc.cc_acc_name.trim().toLowerCase())
		? `<div style="font-size: 11px; color: #64748b; margin-top: 2px;">Ledger: ${frappe.utils.escape_html(doc.cc_acc_name)}</div>`
		: "";

	popover.innerHTML = `
		<div style="border-bottom: 1px solid #e2e8f0; padding-bottom: 8px; margin-bottom: 8px; text-align: left;">
			<div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 8px; text-align: left;">
				<div>
					<div style="font-weight: 700; font-size: 13.5px; color: #0f172a; line-height: 1.25; overflow: hidden; text-overflow: ellipsis; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; text-align: left;">
						${company}
					</div>
					${sub_company}
				</div>
				<span style="background: #f1f5f9; color: #475569; font-size: 11px; font-weight: 600; padding: 2px 6px; border-radius: 4px; white-space: nowrap; flex-shrink: 0;">
					SN: ${serial}
				</span>
			</div>
		</div>

		<div style="display: grid; grid-template-columns: 85px 1fr; row-gap: 4px; column-gap: 8px; font-size: 11.5px; text-align: left;">
			<div style="color: #64748b;">Contact:</div>
			<div style="font-weight: 500; color: #1e293b;">${contact}</div>

			<div style="color: #64748b;">Mobile:</div>
			<div>${mobile_html}</div>

			<div style="color: #64748b;">Phone:</div>
			<div>${phone_html}</div>

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
