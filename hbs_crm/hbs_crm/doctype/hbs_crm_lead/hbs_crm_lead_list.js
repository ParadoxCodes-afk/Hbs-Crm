// Copyright (c) 2026, Hbs and contributors
// For license information, please see license.txt

frappe.listview_settings['Hbs Crm Lead'] = {
	add_fields: ["contact_name", "company_name", "last_remark", "lead_type", "executive_1", "executive_2", "tally_serial", "status", "follow_up_date", "follow_up_time"],
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
			return `<span style="white-space: nowrap; font-size: 12px;" title="${frappe.utils.escape_html(name)}">${short}</span>`;
		},
		executive_2(val) {
			if (!val) return "";
			let info = (typeof frappe !== "undefined" && frappe.user_info) ? frappe.user_info[val] : null;
			let name = (info && info.fullname) ? info.fullname : val;
			let short = name.split(" ")[0].split("@")[0];
			return `<span style="white-space: nowrap; font-size: 12px;" title="${frappe.utils.escape_html(name)}">${short}</span>`;
		},
		follow_up_date(val) {
			if (!val) return "";
			return `<span style="white-space: nowrap; font-size: 11.5px;">${frappe.datetime.str_to_user(val)}</span>`;
		}
	},
	onload(listview) {
		frappe.dom.set_style(`
			.frappe-list[data-doctype="Hbs Crm Lead"] .list-row-col:nth-child(3),
			.frappe-list[data-doctype="Hbs Crm Lead"] .list-subject {
				min-width: 260px !important;
			}
		`);

		// Only set default follow-up date filter for standard sales users (NOT Admin/Owner/System Manager)
		let user = frappe.session.user || "";
		let roles = frappe.user_roles || [];
		let is_admin = user === "Administrator" || user.startsWith("admin@") || user === "admin@hbsmail.in" ||
			roles.some(r => ["System Manager", "Administrator", "HBS Admin", "hbs admin", "Owner", "owner", "Hbs Owner"].includes(r));

		if (!is_admin) {
			if (!frappe.route_options) {
				frappe.route_options = {};
			}
			frappe.route_options["follow_up_date"] = ["<=", frappe.datetime.get_today()];
			
			// Clear it after load so it doesn't stick in memory and conflict with UI filters
			setTimeout(() => {
				if (frappe.route_options && frappe.route_options.follow_up_date) {
					delete frappe.route_options.follow_up_date;
				}
			}, 100);
		}
	}
};
