// Copyright (c) 2026, Hbs and contributors
// For license information, please see license.txt

frappe.listview_settings["Hbs Tally Renewal"] = {
	add_fields: [
		"tally_serial", "tss_tally_serial", "cc_acc_name", "portal_acc_name",
		"cc_contact", "portal_contact", "cc_mobile", "portal_mobile", "cc_phone",
		"portal_phone", "cc_email", "portal_email", "license", "flavour",
		"tally_version", "product_ver", "acc_expiry_date", "portal_expiry_date",
		"crm_status", "crm_stage", "crm_priority", "rfm_segment", "crm_ex_1", "last_remark",
		"last_remarks_date", "notes"
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
			if(lower.includes("server")) return "SERVER";
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
		if (typeof listview.lock_expiry_filter_tag === "function") {
			listview.lock_expiry_filter_tag();
		}
	},
	onload(listview) {
		frappe.dom.set_style(`
			.filter-tag[data-locked="true"] .remove-filter {
				display: none !important;
				pointer-events: none !important;
			}
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

		let is_admin_or_manager = has_common(frappe.user_roles, ["Administrator", "System Manager", "CRM Manager"]);
		let default_cutoff_date = moment().endOf("month").format("YYYY-MM-DD");

		// Render custom Date input in toolbar (NOT via page.add_field to avoid registering in page.fields_dict as an invalid query field)
		listview.page.main.find(".tss-expiry-cutoff-wrapper").remove();
		let $date_wrapper = $(`
			<div class="tss-expiry-cutoff-wrapper" style="display: inline-flex; align-items: center; gap: 5px; margin-right: 8px; vertical-align: middle;">
				<span style="font-size: 12px; font-weight: 600; color: var(--text-color);">📅 Date:</span>
				<input type="date" class="form-control input-xs tss-cutoff-date-input" value="${default_cutoff_date}" style="width: 130px; height: 28px; font-size: 12px; display: inline-block; cursor: pointer; border-radius: 4px;">
			</div>
		`);

		if (listview.page.custom_actions) {
			listview.page.custom_actions.removeClass("hide").prepend($date_wrapper);
		} else if (listview.page.page_actions) {
			listview.page.page_actions.prepend($date_wrapper);
		}

		$date_wrapper.find(".tss-cutoff-date-input").on("change", function () {
			let val = $(this).val();
			if (val) {
				apply_locked_expiry_filter(val);
			}
		});

		function get_current_cutoff_date() {
			return listview.page.main.find(".tss-cutoff-date-input").val() || default_cutoff_date;
		}

		function apply_locked_expiry_filter(date_val) {
			if (!listview.filter_area) return;
			let existing_filter = (listview.filter_area.filter_list?.filters || []).find(f => f.fieldname === "acc_expiry_date");
			if (existing_filter && typeof existing_filter.set_values === "function") {
				existing_filter.set_values(existing_filter.doctype, "acc_expiry_date", "<=", date_val);
			} else {
				let existing = listview.filter_area.get() || [];
				let filtered = existing.filter(f => f[1] !== "acc_expiry_date");
				filtered.push(["Hbs Tally Renewal", "acc_expiry_date", "<=", date_val]);
				listview.filter_area.filter_list.filters = [];
				listview.filter_area.add(filtered);
			}
			lock_expiry_filter_tag();
		}

		function lock_expiry_filter_tag() {
			if (is_admin_or_manager) return;
			setTimeout(() => {
				let $wrapper = $(listview.page.wrapper);
				$wrapper.find(".filter-tag").each(function () {
					let $tag = $(this);
					let text = ($tag.find(".toggle-filter").text() || "").trim();
					if (text.includes("TSS Expiry Date") || text.includes("acc_expiry_date")) {
						$tag.attr("data-locked", "true");
						$tag.find(".remove-filter").remove();
						$tag.find(".toggle-filter").css({
							"border-top-right-radius": "var(--border-radius)",
							"border-bottom-right-radius": "var(--border-radius)"
						});
					}
				});
			}, 30);
		}

		listview.lock_expiry_filter_tag = lock_expiry_filter_tag;

		if (!is_admin_or_manager && listview.filter_area) {
			let orig_remove = listview.filter_area.remove.bind(listview.filter_area);
			listview.filter_area.remove = function (fieldname) {
				if (fieldname === "acc_expiry_date") {
					frappe.show_alert({
						message: __("TSS Expiry Date filter cannot be removed."),
						indicator: "orange"
					});
					return Promise.resolve();
				}
				let res = orig_remove(fieldname);
				lock_expiry_filter_tag();
				return res;
			};

			let orig_clear = listview.filter_area.clear.bind(listview.filter_area);
			listview.filter_area.clear = function (refresh = true) {
				let current_date = get_current_cutoff_date();
				return orig_clear(refresh).then(() => {
					let current_filters = listview.filter_area.get() || [];
					let has_expiry = current_filters.some(f => f[1] === "acc_expiry_date");
					if (!has_expiry) {
						return listview.filter_area.add([["Hbs Tally Renewal", "acc_expiry_date", "<=", current_date]], refresh);
					}
				}).then(() => {
					lock_expiry_filter_tag();
				});
			};
		}

		// Ensure default filters (Pending, Follow Up <= Today, TSS Expiry Date <= Date) are applied
		function setup_default_renewal_filters() {
			if (!listview.filter_area) return;
			let current_filters = listview.filter_area.get() || [];
			let has_status = current_filters.some(f => f[1] === "crm_status");
			let has_follow_up = current_filters.some(f => f[1] === "follow_up_date");
			let has_expiry = current_filters.some(f => f[1] === "acc_expiry_date");

			let to_add = [];
			if (!has_status) {
				to_add.push(["Hbs Tally Renewal", "crm_status", "=", "PENDING"]);
			}
			if (!has_follow_up) {
				to_add.push(["Hbs Tally Renewal", "follow_up_date", "<=", frappe.datetime.get_today()]);
			}
			if (!has_expiry) {
				to_add.push(["Hbs Tally Renewal", "acc_expiry_date", "<=", default_cutoff_date]);
			}

			if (to_add.length) {
				listview.filter_area.add(to_add);
			}
			lock_expiry_filter_tag();
		}

		setTimeout(() => {
			setup_default_renewal_filters();
		}, 100);

		// Overdue remarks/follow-up alert banner (>= 10 days inactive)
		frappe.call({
			method: "hbs_crm.hbs_crm.doctype.hbs_tally_renewal.hbs_tally_renewal.get_overdue_renewal_summary",
			callback: function (r) {
				if (r && r.message && r.message.count > 0) {
					listview.page.main.find(".renewal-overdue-banner").remove();
					let renewal_text = r.message.is_admin_or_manager
						? `<b>${r.message.count}</b> active renewal(s) have not received any follow-up/remarks in the last 10+ days.`
						: `<b>${r.message.count}</b> of your active renewal(s) have not received any follow-up/remarks in the last 10+ days.`;

					let banner_html = `
						<div class="renewal-overdue-banner" style="display: flex; align-items: center; justify-content: space-between; margin: 8px 15px 4px 15px; padding: 9px 14px; background: #fffbeb; border: 1px solid #fde68a; border-radius: 6px; font-size: 13px; color: #92400e;">
							<div style="display: flex; align-items: center; gap: 8px;">
								<span style="font-size: 15px;">⚠️</span>
								<span><b>Attention:</b> ${renewal_text}</span>
							</div>
							<button class="btn btn-xs btn-warning btn-filter-overdue" style="font-weight: 600; cursor: pointer; border-radius: 4px;">
								🔍 View Inactive Renewals
							</button>
						</div>
					`;
					listview.page.main.prepend(banner_html);
					listview.page.main.find(".btn-filter-overdue").on("click", function () {
						listview.filter_area.clear(false);
						let current_date = get_current_cutoff_date();
						let filters = [
							["Hbs Tally Renewal", "crm_status", "=", "PENDING"],
							["Hbs Tally Renewal", "last_remarks_date", "<=", r.message.cutoff_date],
							["Hbs Tally Renewal", "acc_expiry_date", "<=", current_date]
						];
						if (!r.message.is_admin_or_manager) {
							filters.push(["Hbs Tally Renewal", "crm_ex_1", "=", frappe.session.user]);
						}
						listview.filter_area.add(filters);
						lock_expiry_filter_tag();
					});
				}
			}
		});

		// 1. Bulk Email toolbar button (Available to all users under Operations)
		listview.page.add_inner_button(__("📧 Send Bulk Quotation"), () => {
			open_bulk_email_dialog(listview);
		}, __("Operations"));

		// 2. View Quotation for selected record
		listview.page.add_inner_button(__("📄 View Quotation"), () => {
			let checked = listview.get_checked_items(true);
			if (!checked || checked.length !== 1) {
				frappe.msgprint({
					title: __("Select One Record"),
					indicator: "orange",
					message: __("Please select exactly 1 record using checkbox to preview its quotation.")
				});
				return;
			}
			preview_renewal_quotation_from_list(checked[0]);
		}, __("Operations"));

		check_if_owner_or_admin(function (is_owner_admin) {
			if (!is_owner_admin) return;

			// Sync Portal API in Batches (Admin & Owner only under Operations)
			listview.page.add_inner_button(__("🔄 Sync Portal API"), () => {
				let checked = listview.get_checked_items(true);
				if (checked && checked.length > 0) {
					start_portal_batch_sync_dialog(listview, checked);
				} else {
					frappe.confirm(
						__("No records selected. Do you want to sync all eligible records with Tally Portal API in batches?"),
						() => {
							frappe.call({
								method: "hbs_crm.hbs_crm.doctype.hbs_tally_renewal.hbs_tally_renewal.get_all_portal_sync_candidates",
								freeze: true,
								freeze_message: __("Fetching candidate records for sync..."),
								callback: function (r) {
									let candidates = r.message || [];
									if (candidates.length > 0) {
										start_portal_batch_sync_dialog(listview, candidates);
									} else {
										frappe.msgprint(__("No eligible records found with Tally Serial Number and Active/Moved Out status."));
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

			// --- UPDATE MASTER DATA (Customer Serials Report / Portal Updation) ---
			listview.page.add_inner_button(__("🔄 Update Master Data"), () => {
				open_update_master_data_dialog(listview);
			}, __("Operations"));

			// --- MOVED OUT UPDATION (Excel: TSS Tally Serial, License, TSS Expiry Date, Portal Partner Name, Reference Status) ---
			listview.page.add_inner_button(__("🔄 Moved Out Updation"), () => {
				open_update_secondary_data_dialog(listview);
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
						__("Are you sure you want to send this bulk email to <b>{0}</b> selected records in batches of 10?", [checked.length]),
						function () {
							d.hide();
							start_bulk_email_batch_runner(listview, checked, values);
						}
					);
				}
			});

			d.show();
		}
	});
}

// --- BATCH RUNNER FOR BULK EMAILS (10 per batch with live progress and full delivery report) ---
function start_bulk_email_batch_runner(listview, checked, email_params) {
	const BATCH_SIZE = 10;
	let batches = [];
	for (let i = 0; i < checked.length; i += BATCH_SIZE) {
		batches.push(checked.slice(i, i + BATCH_SIZE));
	}

	let current_batch_idx = 0;
	let total_batches = batches.length;
	let total_records = checked.length;

	let all_sent = [];
	let all_skipped = [];
	let all_failed = [];
	let is_stopped = false;

	let progress_dialog = new frappe.ui.Dialog({
		title: __("📧 Sending Bulk Quotations ({0} Records)", [total_records]),
		size: "large",
		fields: [
			{
				fieldtype: "HTML",
				fieldname: "progress_html"
			}
		],
		primary_action_label: __("Close"),
		primary_action: function () {
			progress_dialog.hide();
			listview.refresh();
		}
	});

	progress_dialog.$wrapper.find(".modal-dialog").css({
		"max-width": "920px",
		"width": "90%"
	});

	let $primary_btn = progress_dialog.get_primary_btn();
	$primary_btn.hide();

	progress_dialog.add_custom_action(__("⏹ Stop Sending"), function () {
		is_stopped = true;
		frappe.show_alert({
			message: __("Stopping after current batch completes..."),
			indicator: "orange"
		});
	});

	let $stop_btn = progress_dialog.$wrapper.find(".custom-actions button");

	progress_dialog.show();

	function render_ui(status_msg, is_done) {
		let processed = all_sent.length + all_skipped.length + all_failed.length;
		let pct = total_records > 0 ? Math.min(100, Math.round((processed / total_records) * 100)) : 0;

		let html = `
			<div style="padding: 6px 0;">
				<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
					<span style="font-weight: 600; font-size: 13px; color: var(--text-color);">
						${status_msg || ""}
					</span>
					<span style="font-weight: 700; font-size: 13px; color: ${is_done ? '#16a34a' : 'var(--primary-color)'};">
						${pct}% (${processed} / ${total_records})
					</span>
				</div>

				<div class="progress" style="height: 14px; border-radius: 7px; background-color: #f1f5f9; overflow: hidden; margin-bottom: 16px;">
					<div class="progress-bar ${is_done ? 'bg-success' : 'progress-bar-striped progress-bar-animated bg-primary'}"
						role="progressbar"
						style="width: ${pct}%; transition: width 0.3s ease;">
					</div>
				</div>

				<!-- Metric Summary Cards -->
				<div style="display: flex; gap: 12px; margin-bottom: 16px;">
					<div style="flex: 1; background: #ecfdf5; border: 1px solid #a7f3d0; border-radius: 8px; padding: 10px; text-align: center;">
						<div style="font-size: 22px; font-weight: 800; color: #059669;">${all_sent.length}</div>
						<div style="font-size: 11px; font-weight: 600; text-transform: uppercase; color: #047857; margin-top: 2px;">✅ Sent</div>
					</div>
					<div style="flex: 1; background: #fffbeb; border: 1px solid #fde68a; border-radius: 8px; padding: 10px; text-align: center;">
						<div style="font-size: 22px; font-weight: 800; color: #d97706;">${all_skipped.length}</div>
						<div style="font-size: 11px; font-weight: 600; text-transform: uppercase; color: #b45309; margin-top: 2px;">⚠️ No Email</div>
					</div>
					<div style="flex: 1; background: #fef2f2; border: 1px solid #fecaca; border-radius: 8px; padding: 10px; text-align: center;">
						<div style="font-size: 22px; font-weight: 800; color: #dc2626;">${all_failed.length}</div>
						<div style="font-size: 11px; font-weight: 600; text-transform: uppercase; color: #b91c1c; margin-top: 2px;">❌ Failed</div>
					</div>
				</div>
		`;

		if (is_done) {
			html += build_batch_report_table(all_sent, all_skipped, all_failed);
		}

		html += `</div>`;
		progress_dialog.fields_dict.progress_html.$wrapper.html(html);
	}

	function build_batch_report_table(sent, skipped, failed) {
		let all_rows = [];

		sent.forEach(r => {
			all_rows.push({
				serial: r.serial || "-",
				party: r.party || "-",
				email: r.email || "-",
				status_badge: `<span class="badge" style="background-color: #d1fae5; color: #065f46; font-size: 11px; padding: 4px 8px; border-radius: 4px;">✅ Sent</span>`,
				note: `<span style="color: #059669;">Email sent successfully</span>`
			});
		});

		skipped.forEach(r => {
			all_rows.push({
				serial: r.serial || "-",
				party: r.party || "-",
				email: "-",
				status_badge: `<span class="badge" style="background-color: #fef3c7; color: #92400e; font-size: 11px; padding: 4px 8px; border-radius: 4px;">⚠️ Skipped</span>`,
				note: `<span style="color: #b45309;">${r.reason || "No Email ID found"}</span>`
			});
		});

		failed.forEach(r => {
			all_rows.push({
				serial: r.serial || "-",
				party: r.party || "-",
				email: r.email || "-",
				status_badge: `<span class="badge" style="background-color: #fee2e2; color: #991b1b; font-size: 11px; padding: 4px 8px; border-radius: 4px;">❌ Failed</span>`,
				note: `<span style="color: #dc2626;">${r.error || "Send failed"}</span>`
			});
		});

		let rows_html = all_rows.map((row, idx) => `
			<tr style="border-bottom: 1px solid #f1f5f9; font-size: 12px;">
				<td style="padding: 8px 10px; color: #64748b;">${idx + 1}</td>
				<td style="padding: 8px 10px; font-weight: 600; font-family: monospace; color: var(--text-color);">${frappe.utils.escape_html(row.serial)}</td>
				<td style="padding: 8px 10px; color: var(--text-color);">${frappe.utils.escape_html(row.party)}</td>
				<td style="padding: 8px 10px; color: #475569;">${frappe.utils.escape_html(row.email)}</td>
				<td style="padding: 8px 10px;">${row.status_badge}</td>
				<td style="padding: 8px 10px;">${row.note}</td>
			</tr>
		`).join("");

		return `
			<div style="border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; margin-top: 12px;">
				<div style="background: #f8fafc; padding: 8px 12px; font-weight: 700; font-size: 12px; color: #334155; border-bottom: 1px solid #e2e8f0; display: flex; justify-content: space-between; align-items: center;">
					<span>📋 Delivery Report (${all_rows.length} Total Records)</span>
				</div>
				<div style="max-height: 280px; overflow-y: auto;">
					<table style="width: 100%; border-collapse: collapse; text-align: left;">
						<thead style="background: #f1f5f9; position: sticky; top: 0; z-index: 1;">
							<tr style="font-size: 11px; text-transform: uppercase; color: #475569; letter-spacing: 0.5px;">
								<th style="padding: 8px 10px;">#</th>
								<th style="padding: 8px 10px;">Serial No</th>
								<th style="padding: 8px 10px;">Company / Account</th>
								<th style="padding: 8px 10px;">Email</th>
								<th style="padding: 8px 10px;">Status</th>
								<th style="padding: 8px 10px;">Details</th>
							</tr>
						</thead>
						<tbody>
							${rows_html}
						</tbody>
					</table>
				</div>
			</div>
		`;
	}

	function run_batch() {
		if (is_stopped || current_batch_idx >= total_batches) {
			let done_msg = is_stopped ? __("⏹ Stopped by user.") : __("🎉 Bulk Email Process Complete!");
			render_ui(done_msg, true);
			$stop_btn.hide();
			$primary_btn.show();
			return;
		}

		let batch = batches[current_batch_idx];
		let b_num = current_batch_idx + 1;
		render_ui(__("Sending batch {0} of {1} ({2} records)...", [b_num, total_batches, batch.length]), false);

		frappe.call({
			method: "hbs_crm.hbs_crm.doctype.hbs_tally_renewal.hbs_tally_renewal.send_bulk_renewal_email",
			args: {
				names: JSON.stringify(batch),
				subject_template: email_params.subject,
				message_template: email_params.message,
				cc_email: email_params.cc_email,
				from_email: email_params.from_email,
				sender_name: email_params.sender_name
			},
			callback: function (r) {
				if (r.message) {
					let res = r.message;
					if (res.sent_records && res.sent_records.length > 0) {
						all_sent = all_sent.concat(res.sent_records);
					}
					if (res.skipped_records && res.skipped_records.length > 0) {
						all_skipped = all_skipped.concat(res.skipped_records);
					}
					if (res.failed_records && res.failed_records.length > 0) {
						all_failed = all_failed.concat(res.failed_records);
					}
				}
				current_batch_idx++;
				run_batch();
			},
			error: function () {
				batch.forEach(bname => {
					all_failed.push({
						name: bname,
						serial: bname,
						party: "-",
						email: "-",
						error: __("Batch server request failed")
					});
				});
				current_batch_idx++;
				run_batch();
			}
		});
	}

	run_batch();
}

function check_if_owner_or_admin(callback) {
	if (frappe.session.user === "Administrator" || frappe.user.has_role("System Manager")) {
		callback(true);
		return;
	}

	if (window._hbs_is_owner_or_admin !== undefined) {
		callback(window._hbs_is_owner_or_admin);
		return;
	}

	frappe.call({
		method: "hbs_crm.hbs_crm.doctype.hbs_tally_renewal.hbs_tally_renewal.check_user_hierarchy_role",
		callback: function (r) {
			let is_allowed = !!(r.message && r.message.is_owner_or_admin);
			window._hbs_is_owner_or_admin = is_allowed;
			callback(is_allowed);
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

// --- UPDATE SECONDARY DATA DIALOG ---
function open_update_secondary_data_dialog(listview) {
	let d = new frappe.ui.Dialog({
		title: __("🔄 Moved Out Updation (Excel)"),
		fields: [
			{
				label: __("Excel File (.xlsx or .xls)"),
				fieldname: "file_url",
				fieldtype: "Attach",
				reqd: 1,
				description: __("Columns expected: <b>TSS Tally Serial</b>, <b>License</b>, <b>TSS Expiry Date</b>, <b>Portal Partner Name</b>, <b>Reference Status</b>")
			}
		],
		primary_action_label: __("Update Data"),
		primary_action(values) {
			if (!values.file_url) {
				frappe.msgprint(__("Please upload an Excel file first."));
				return;
			}

			d.hide();

			frappe.call({
				method: "hbs_crm.hbs_crm.doctype.hbs_tally_renewal.hbs_tally_renewal.update_secondary_data_from_excel",
				args: {
					file_url: values.file_url
				},
				freeze: true,
				freeze_message: __("Updating Secondary Data from Excel..."),
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

// --- UPDATE MASTER DATA DIALOG (Customer Serials Report / Portal Updation) ---
function open_update_master_data_dialog(listview) {
	let d = new frappe.ui.Dialog({
		title: __("🔄 Update Master Data (Excel)"),
		fields: [
			{
				label: __("Excel File (.xlsx or .xls)"),
				fieldname: "file_url",
				fieldtype: "Attach",
				reqd: 1,
				description: __(
					"Upload Customer Serials Report. Updates <b>Portal Tab</b> (Flavor, Release, Expiry, Admin Email, GSTIN, Storage, TSS Status, etc.) matching by <b>Customer Serial Name / Tally Serial</b>."
				)
			}
		],
		primary_action_label: __("Update Master Data"),
		primary_action(values) {
			if (!values.file_url) {
				frappe.msgprint(__("Please upload an Excel file first."));
				return;
			}

			d.hide();

			frappe.call({
				method: "hbs_crm.hbs_crm.doctype.hbs_tally_renewal.hbs_tally_renewal.update_master_data_from_excel",
				args: {
					file_url: values.file_url
				},
				freeze: true,
				freeze_message: __("Updating Master Data from Excel..."),
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
		title: data.report_title || __("📊 Renewal Data Import Report"),
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

	let single_doc = null;
	if (checked.length === 1 && listview.data) {
		single_doc = listview.data.find(d => d.name === checked[0]);
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
				options: "\nPENDING\nSold\nLost",
				default: single_doc ? single_doc.crm_status : undefined
			},
			{
				label: __("CRM Stage"),
				fieldname: "crm_stage",
				fieldtype: "Select",
				options: "\nCUSTOMER NOT RESPONDING\nFORWARD TO\nCUSTOMER REQ PENDING\nDEMO/MEETING DONE\nDEMO/ MEETING FIXED\nIN FOLLOW-UP\nLEAD\nNEGOTIATION\nPAYMENT RECEIVED\nPENDING FOR INSTALLATION\nPENDING PAYMENT\nQUOTATION PENDING\nQUOTATION SENT\nWAITING FOR CONFIRMATION",
				default: single_doc ? single_doc.crm_stage : undefined
			},
			{
				label: __("Reference Status"),
				fieldname: "crm_ref",
				fieldtype: "Data",
				default: single_doc ? single_doc.crm_ref : undefined
			},
			{
				fieldname: "col2",
				fieldtype: "Column Break"
			},
			{
				label: __("Follow-up Date"),
				fieldname: "follow_up_date",
				fieldtype: "Date",
				default: single_doc ? single_doc.follow_up_date : undefined
			},
			{
				label: __("Last Remarks Date"),
				fieldname: "last_remarks_date",
				fieldtype: "Date",
				default: single_doc ? single_doc.last_remarks_date : undefined
			},
			{
				label: __("Last Remarks"),
				fieldname: "last_remark",
				fieldtype: "Small Text",
				description: __("Owner can directly edit or update the Last Remarks on the selected record(s)."),
				default: single_doc ? single_doc.last_remark : undefined
			},
			{
				fieldname: "sec_quote",
				fieldtype: "Section Break",
				label: __("Quotation")
			},
			{
				label: __("Change Item in Quote Tab"),
				fieldname: "quote_item",
				fieldtype: "Link",
				options: "Hbs Product",
				get_query: () => {
					return {
						filters: {
							is_active: 1
						}
					};
				},
				description: __("Replaces item in Quote tab and recalculates taxes & totals for selected record(s).")
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
			["crm_status", "crm_stage", "crm_ref", "follow_up_date", "last_remarks_date", "last_remark"].forEach(f => {
				if (values[f] !== undefined && values[f] !== null && String(values[f]).trim() !== "") {
					fields_to_update[f] = values[f];
				}
			});

			let quote_item = (values.quote_item || "").trim();
			let remark = (values.remark || "").trim();
			if (Object.keys(fields_to_update).length === 0 && !remark && !quote_item) {
				frappe.msgprint({
					title: __("No Changes Specified"),
					indicator: "orange",
					message: __("Please specify at least one field value, quote item, or enter a remark.")
				});
				return;
			}

			frappe.call({
				method: "hbs_crm.hbs_crm.doctype.hbs_tally_renewal.hbs_tally_renewal.bulk_update_renewal_fields",
				args: {
					names: JSON.stringify(checked),
					updates: JSON.stringify(fields_to_update),
					remark: remark,
					quote_item: quote_item
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
			<div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 4px; padding: 6px 8px; max-height: 65px; overflow-y: auto; font-size: 11.5px; color: #1e293b; line-height: 1.35; white-space: pre-wrap; word-break: break-word; text-align: left !important;">${frappe.utils.escape_html((doc.last_remark || "").trim())}</div>
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

		${(doc.notes && doc.notes.trim()) ? `
			<div style="margin-top: 6px; background: #fffdf5; border: 1px solid #fed7aa; border-left: 3px solid #f59e0b; border-radius: 4px; padding: 5px 8px; font-size: 11.5px; text-align: left;">
				<div style="font-weight: 700; font-size: 10px; color: #b45309; text-transform: uppercase; margin-bottom: 2px;">💡 Client Note (Pre-Call):</div>
				<div style="color: #1e293b; line-height: 1.35; white-space: pre-wrap; word-break: break-word;">${frappe.utils.escape_html(doc.notes.trim())}</div>
			</div>
		` : ""}

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

function preview_renewal_quotation_from_list(name) {
	frappe.call({
		method: "hbs_crm.hbs_crm.doctype.hbs_tally_renewal.hbs_tally_renewal.get_renewal_quotation_html",
		args: { name: name },
		freeze: true,
		freeze_message: __("Generating Quotation Preview..."),
		callback: function (r) {
			if (!r || !r.message) {
				frappe.msgprint(__("Unable to load quotation preview."));
				return;
			}
			let raw_html = r.message;
			let cleaned_html = raw_html.replace(/<div class="action-banner[^>]*>[\s\S]*?<\/div>/gi, "");
			let security_tags = `
				<style>
					.action-banner, .print-hide { display: none !important; visibility: hidden !important; }
					.print-format-gutter { padding: 0 !important; background: transparent !important; }
					@media print { html, body, * { display: none !important; visibility: hidden !important; } }
					body { -webkit-user-select: none !important; -moz-user-select: none !important; -ms-user-select: none !important; user-select: none !important; }
				</style>
				<script>
					document.addEventListener('contextmenu', function(e) { e.preventDefault(); return false; });
					document.addEventListener('keydown', function(e) {
						if ((e.ctrlKey || e.metaKey) && (e.key === 'p' || e.key === 'P' || e.key === 's' || e.key === 'S')) {
							e.preventDefault(); e.stopPropagation(); return false;
						}
					});
				<\/script>
			`;
			let final_html = cleaned_html.indexOf("<head>") !== -1 ? cleaned_html.replace("<head>", "<head>" + security_tags) : security_tags + cleaned_html;

			let d = new frappe.ui.Dialog({
				title: __("📄 Quotation Preview (View Only) - {0}", [name]),
				size: "extra-large",
				fields: [
					{
						fieldtype: "HTML",
						fieldname: "preview_area",
						options: `<div style="padding: 0; margin: 0; width: 100%; height: 87vh; overflow: auto; background: #ffffff; border-radius: 4px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);"><iframe id="print-view-frame" style="width: 100%; height: 100%; border: none; min-height: 85vh;" srcdoc="${frappe.utils.escape_html(final_html)}"></iframe></div>`
					}
				]
			});
			d.$wrapper.find(".modal-dialog").css({ "max-width": "1250px", "width": "96vw" });
			d.show();
		}
	});
}

function start_portal_batch_sync_dialog(listview, names) {
	if (!names || names.length === 0) {
		frappe.msgprint(__("No records selected for sync."));
		return;
	}

	const BATCH_SIZE = 50;
	let batches = [];
	for (let i = 0; i < names.length; i += BATCH_SIZE) {
		batches.push(names.slice(i, i + BATCH_SIZE));
	}

	let current_batch_idx = 0;
	let total_batches = batches.length;
	let total_records = names.length;
	let total_processed = 0;
	let total_synced = 0;
	let total_failed = 0;
	let total_fields = 0;
	let is_stopped = false;
	let is_running = true;

	let d = new frappe.ui.Dialog({
		title: __("🔄 Tally Portal API Batch Sync"),
		size: "large",
		fields: [
			{
				fieldname: "sync_ui_html",
				fieldtype: "HTML",
				options: `
					<div style="padding: 4px 0;">
						<div style="margin-bottom: 14px;">
							<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
								<span class="sync-status-badge badge badge-primary" style="font-size: 12px; padding: 4px 8px;">
									${__('In Progress')}
								</span>
								<span class="sync-status-counter" style="font-size: 13px; font-weight: 600; color: #334155;">
									0 / ${total_records} ${__('Records')} (0%)
								</span>
							</div>
							<div class="progress" style="height: 20px; border-radius: 6px; background-color: #e2e8f0; overflow: hidden; margin-bottom: 6px;">
								<div class="progress-bar progress-bar-striped progress-bar-animated bg-primary sync-progress-bar"
									role="progressbar" style="width: 0%; font-size: 11px; font-weight: bold; line-height: 20px;">
									0%
								</div>
							</div>
							<div class="sync-batch-info text-muted" style="font-size: 12px;">
								${__('Preparing batches ({0} records per batch)...', [BATCH_SIZE])}
							</div>
						</div>

						<div style="display: flex; gap: 10px; margin-bottom: 14px; flex-wrap: wrap;">
							<div style="flex: 1; min-width: 100px; background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 8px 12px; text-align: center;">
								<div class="sync-metric-total" style="font-size: 20px; font-weight: bold; color: #1e293b;">${total_records}</div>
								<div style="font-size: 11px; color: #64748b; font-weight: 600;">${__('Total')}</div>
							</div>
							<div style="flex: 1; min-width: 100px; background-color: #ecfdf5; border: 1px solid #a7f3d0; border-radius: 6px; padding: 8px 12px; text-align: center;">
								<div class="sync-metric-synced" style="font-size: 20px; font-weight: bold; color: #065f46;">0</div>
								<div style="font-size: 11px; color: #047857; font-weight: 600;">${__('Synced')}</div>
							</div>
							<div style="flex: 1; min-width: 100px; background-color: #eff6ff; border: 1px solid #bfdbfe; border-radius: 6px; padding: 8px 12px; text-align: center;">
								<div class="sync-metric-fields" style="font-size: 20px; font-weight: bold; color: #1e40af;">0</div>
								<div style="font-size: 11px; color: #1d4ed8; font-weight: 600;">${__('Fields Updated')}</div>
							</div>
							<div style="flex: 1; min-width: 100px; background-color: #fef2f2; border: 1px solid #fecaca; border-radius: 6px; padding: 8px 12px; text-align: center;">
								<div class="sync-metric-failed" style="font-size: 20px; font-weight: bold; color: #b91c1c;">0</div>
								<div style="font-size: 11px; color: #dc2626; font-weight: 600;">${__('Skipped / Failed')}</div>
							</div>
						</div>

						<div style="border: 1px solid #e2e8f0; border-radius: 6px; overflow: hidden;">
							<div style="background-color: #f8fafc; padding: 6px 12px; font-size: 12px; font-weight: 600; color: #475569; border-bottom: 1px solid #e2e8f0; display: flex; justify-content: space-between;">
								<span>${__('Live Sync Details')}</span>
								<span class="sync-live-item-count text-muted" style="font-size: 11px;">0 items processed</span>
							</div>
							<div class="sync-results-scroll" style="max-height: 220px; overflow-y: auto;">
								<table class="table table-bordered table-sm" style="margin: 0; font-size: 11px; width: 100%;">
									<thead style="position: sticky; top: 0; background-color: #f1f5f9; z-index: 1;">
										<tr style="color: #334155;">
											<th style="width: 40px; text-align: center;">#</th>
											<th style="width: 110px;">${__('Serial')}</th>
											<th>${__('Company')}</th>
											<th style="width: 85px; text-align: center;">${__('Status')}</th>
											<th>${__('Details')}</th>
										</tr>
									</thead>
									<tbody class="sync-results-body">
										<tr>
											<td colspan="5" class="text-center text-muted py-3">
												<i class="fa fa-spinner fa-spin"></i> ${__('Sync starting...')}
											</td>
										</tr>
									</tbody>
								</table>
							</div>
						</div>
					</div>
				`
			}
		],
		primary_action_label: __("Stop Sync"),
		primary_action: function () {
			if (is_running) {
				is_stopped = true;
				d.get_primary_btn().prop("disabled", true).text(__("Stopping..."));
			} else {
				d.hide();
				listview.refresh();
			}
		}
	});

	d.get_primary_btn().removeClass("btn-primary").addClass("btn-danger");
	d.show();

	d.$wrapper.on("hidden.bs.modal", function () {
		is_stopped = true;
		listview.refresh();
	});

	let has_rendered_first_row = false;

	function run_batch_step() {
		if (is_stopped || current_batch_idx >= total_batches) {
			finish_sync();
			return;
		}

		let batch = batches[current_batch_idx];
		let batch_num = current_batch_idx + 1;

		d.$wrapper.find(".sync-batch-info").text(
			__("Syncing batch {0} of {1} ({2} records)...", [batch_num, total_batches, batch.length])
		);

		frappe.call({
			method: "hbs_crm.hbs_crm.doctype.hbs_tally_renewal.hbs_tally_renewal.sync_portal_batch",
			args: { names: JSON.stringify(batch) },
			callback: function (r) {
				let data = r.message || {};
				let results = data.results || [];

				total_synced += (data.success_count || 0);
				total_failed += (data.failed_count || 0);
				total_fields += (data.total_fields_updated || 0);
				total_processed += batch.length;

				d.$wrapper.find(".sync-metric-synced").text(total_synced);
				d.$wrapper.find(".sync-metric-fields").text(total_fields);
				d.$wrapper.find(".sync-metric-failed").text(total_failed);

				let pct = Math.min(100, Math.round((total_processed / total_records) * 100));
				d.$wrapper.find(".sync-progress-bar")
					.css("width", pct + "%")
					.text(pct + "%");
				d.$wrapper.find(".sync-status-counter").text(
					`${total_processed} / ${total_records} ${__('Records')} (${pct}%)`
				);
				d.$wrapper.find(".sync-live-item-count").text(
					`${total_processed} items processed`
				);

				let $tbody = d.$wrapper.find(".sync-results-body");
				if (!has_rendered_first_row) {
					$tbody.empty();
					has_rendered_first_row = true;
				}

				results.forEach((item, idx) => {
					let row_num = total_processed - batch.length + idx + 1;
					let badge_class = item.status === "success" ? "badge-success" : (item.status === "skipped" ? "badge-warning" : "badge-danger");
					let badge_label = item.status === "success" ? "Synced" : (item.status === "skipped" ? "Skipped" : "Failed");

					$tbody.append(`
						<tr>
							<td style="text-align: center; color: #64748b;">${row_num}</td>
							<td style="font-family: monospace; font-weight: 600;">${frappe.utils.escape_html(item.serial || '-')}</td>
							<td>${frappe.utils.escape_html(item.company_name || item.name || '-')}</td>
							<td style="text-align: center;">
								<span class="badge ${badge_class}" style="font-size: 10px; text-transform: capitalize;">${badge_label}</span>
							</td>
							<td style="color: ${item.status === 'success' ? '#065f46' : '#991b1b'};">${frappe.utils.escape_html(item.message || '-')}</td>
						</tr>
					`);
				});

				let scroll_container = d.$wrapper.find(".sync-results-scroll")[0];
				if (scroll_container) {
					scroll_container.scrollTop = scroll_container.scrollHeight;
				}

				current_batch_idx++;
				run_batch_step();
			},
			error: function () {
				total_failed += batch.length;
				total_processed += batch.length;
				d.$wrapper.find(".sync-metric-failed").text(total_failed);

				current_batch_idx++;
				run_batch_step();
			}
		});
	}

	function finish_sync() {
		is_running = false;
		let $pbar = d.$wrapper.find(".sync-progress-bar");
		$pbar.removeClass("progress-bar-animated progress-bar-striped");

		if (is_stopped) {
			$pbar.addClass("bg-warning");
			d.$wrapper.find(".sync-status-badge")
				.removeClass("badge-primary")
				.addClass("badge-warning")
				.text(__("Sync Stopped"));
			d.$wrapper.find(".sync-batch-info").text(
				__("Sync was stopped by user. {0} records processed ({1} synced, {2} skipped/failed).", [total_processed, total_synced, total_failed])
			);
		} else {
			$pbar.addClass("bg-success").css("width", "100%").text("100%");
			d.$wrapper.find(".sync-status-badge")
				.removeClass("badge-primary")
				.addClass("badge-success")
				.text(__("Completed"));
			d.$wrapper.find(".sync-batch-info").text(
				__("All {0} records processed: {1} successfully synced ({2} fields updated), {3} skipped/failed.", [total_records, total_synced, total_fields, total_failed])
			);
		}

		let $btn = d.get_primary_btn();
		$btn.removeClass("btn-danger").addClass("btn-primary").prop("disabled", false).text(__("Close & Refresh"));
	}

	run_batch_step();
}
