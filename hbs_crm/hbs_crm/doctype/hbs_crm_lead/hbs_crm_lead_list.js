// Copyright (c) 2026, Hbs and contributors
// For license information, please see license.txt

frappe.listview_settings['Hbs Crm Lead'] = {
	add_fields: ["contact_name", "company_name", "last_remark", "last_remarks_date", "creation", "lead_type", "executive_1", "executive_2", "executive_3", "tally_serial", "status", "follow_up_date", "follow_up_time"],
	hide_name_column: true,
	order_by: "follow_up_date asc, follow_up_time asc",
	formatters: {
		company_name(val, df, doc) {
			let text = val ? frappe.utils.escape_html(val) : "";
			if (!doc.last_remark) {
				return `<span title="${text}"><b>${text}</b></span>`;
			}
			let remark = frappe.utils.escape_html(doc.last_remark);
			return `
				<span style="display: inline-flex; align-items: center; gap: 6px; max-width: 100%;">
					<span class="text-truncate" style="display: inline-block; max-width: 230px; vertical-align: middle;" title="${text}"><b>${text}</b></span>
					<span style="cursor: help; flex-shrink: 0; display: inline-flex; align-items: center; justify-content: center; width: 19px; height: 19px; border-radius: 50%; background: #eff6ff; color: #2563eb; border: 1px solid #bfdbfe; margin-left: 2px;" title="Latest Remark:&#10;${remark}">
						<svg style="width: 11px; height: 11px; fill: currentColor;" viewBox="0 0 24 24"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm-2 12H6v-2h12v2zm0-3H6V9h12v2zm0-3H6V6h12v2z"/></svg>
					</span>
				</span>
			`;
		},
		executive_1(val) {
			if (!val) return "";
			let info = (typeof frappe !== "undefined" && frappe.user_info) ? frappe.user_info[val] : null;
			let name = (info && info.fullname) ? info.fullname : val;
			let short = name.split(" ")[0].split("@")[0];
			return `<span title="${frappe.utils.escape_html(name)}">${short}</span>`;
		},
		executive_2(val) {
			if (!val) return "";
			let info = (typeof frappe !== "undefined" && frappe.user_info) ? frappe.user_info[val] : null;
			let name = (info && info.fullname) ? info.fullname : val;
			let short = name.split(" ")[0].split("@")[0];
			return `<span title="${frappe.utils.escape_html(name)}">${short}</span>`;
		},
		executive_3(val) {
			if (!val) return "";
			let info = (typeof frappe !== "undefined" && frappe.user_info) ? frappe.user_info[val] : null;
			let name = (info && info.fullname) ? info.fullname : val;
			let short = name.split(" ")[0].split("@")[0];
			return `<span title="${frappe.utils.escape_html(name)}">${short}</span>`;
		},
		tally_serial(val) {
			if (!val) return "";
			return `<span>${frappe.utils.escape_html(val)}</span>`;
		},
		follow_up_date(val) {
			if (!val) return "";
			return `<span>${frappe.datetime.str_to_user(val)}</span>`;
		}
	},
	onload(listview) {
		frappe.dom.set_style(`
			.frappe-list[data-doctype="Hbs Crm Lead"] .list-row-col:nth-child(3),
			.frappe-list[data-doctype="Hbs Crm Lead"] .list-subject {
				min-width: 260px !important;
			}
			.frappe-list[data-doctype="Hbs Crm Lead"] .list-row-col[data-sort-by="executive_1"],
			.frappe-list[data-doctype="Hbs Crm Lead"] .list-row-col[data-sort-by="executive_2"],
			.frappe-list[data-doctype="Hbs Crm Lead"] .list-row-col[data-sort-by="executive_3"],
			.frappe-list[data-doctype="Hbs Crm Lead"] .list-row-col[data-sort-by="tally_serial"] {
				max-width: 105px !important;
				min-width: 75px !important;
				flex-grow: 0 !important;
			}
		`);

		if (!frappe.route_options) {
			frappe.route_options = {};
		}

		// Default filters for standard user level only (NOT Admin/Owner/System Manager)
		let user = frappe.session.user || "";
		let roles = frappe.user_roles || [];
		let is_admin = user === "Administrator" || user.startsWith("admin@") || user === "admin@hbsmail.in" ||
			roles.some(r => ["System Manager", "Administrator", "HBS Admin", "hbs admin", "Owner", "owner", "Hbs Owner"].includes(r));

		if (!is_admin) {
			frappe.route_options["status"] = "pending";
			frappe.route_options["follow_up_date"] = ["<=", frappe.datetime.get_today()];
		}

		// Clear route_options after load so it does not persist in memory and interfere when user changes filter
		setTimeout(() => {
			if (frappe.route_options) {
				delete frappe.route_options.status;
				delete frappe.route_options.follow_up_date;
			}
		}, 100);

		// Overdue follow-up alert banner (>= 10 days inactive)
		frappe.call({
			method: "hbs_crm.hbs_crm.doctype.hbs_crm_lead.hbs_crm_lead.get_overdue_followup_summary",
			callback: function (r) {
				if (r && r.message && r.message.count > 0) {
					listview.page.main.find(".lead-overdue-banner").remove();
					let lead_text = r.message.is_admin_or_manager
						? `<b>${r.message.count}</b> active lead(s) have not received any follow-up in the last 10+ days.`
						: `<b>${r.message.count}</b> of your active lead(s) have not received any follow-up in the last 10+ days.`;

					let banner_html = `
						<div class="lead-overdue-banner" style="display: flex; align-items: center; justify-content: space-between; margin: 8px 15px 4px 15px; padding: 9px 14px; background: #fffbeb; border: 1px solid #fde68a; border-radius: 6px; font-size: 13px; color: #92400e;">
							<div style="display: flex; align-items: center; gap: 8px;">
								<span style="font-size: 15px;">⚠️</span>
								<span><b>Attention:</b> ${lead_text}</span>
							</div>
							<button class="btn btn-xs btn-warning btn-filter-overdue" style="font-weight: 600; cursor: pointer; border-radius: 4px;">
								🔍 View Inactive Leads
							</button>
						</div>
					`;
					listview.page.main.prepend(banner_html);
					listview.page.main.find(".btn-filter-overdue").on("click", function () {
						listview.filter_area.clear();
						let filters = [
							["Hbs Crm Lead", "status", "not in", ["won", "lost"]],
							["Hbs Crm Lead", "last_remarks_date", "<=", r.message.cutoff_date]
						];
						if (!r.message.is_admin_or_manager) {
							filters.push(["Hbs Crm Lead", "executive_1", "=", frappe.session.user]);
						}
						listview.filter_area.add(filters);
					});
				}
			}
		});

		// View Quotation for selected lead
		listview.page.add_inner_button(__("📄 View Quotation"), () => {
			let checked = listview.get_checked_items(true);
			if (!checked || checked.length !== 1) {
				frappe.msgprint({
					title: __("Select One Lead"),
					indicator: "orange",
					message: __("Please select exactly 1 lead using checkbox to preview its quotation.")
				});
				return;
			}
			preview_lead_quotation_from_list(checked[0]);
		});
	}
};

function preview_lead_quotation_from_list(name) {
	frappe.call({
		method: "hbs_crm.hbs_crm.doctype.hbs_crm_lead.hbs_crm_lead.get_lead_quotation_html",
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
