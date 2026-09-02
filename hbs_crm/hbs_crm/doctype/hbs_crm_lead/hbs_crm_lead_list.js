// Copyright (c) 2026, Hbs and contributors
// For license information, please see license.txt

frappe.listview_settings['Hbs Crm Lead'] = {
	add_fields: ["contact_name", "company_name", "last_remark", "executive_1", "executive_2", "tally_serial", "status", "follow_up_date", "follow_up_time"],
	hide_name_column: true,
	order_by: "follow_up_date asc, follow_up_time asc",
	formatters: {
		company_name(val, df, doc) {
			let text = val ? frappe.utils.escape_html(val) : "";
			if (!doc.last_remark) {
				return `<span><b>${text}</b></span>`;
			}
			let remark = frappe.utils.escape_html(doc.last_remark);
			return `
				<span style="display: inline-flex; align-items: center; gap: 6px;">
					<span><b>${text}</b></span>
					<span style="cursor: help; display: inline-flex; align-items: center; justify-content: center; width: 20px; height: 20px; border-radius: 50%; background: #eff6ff; color: #2563eb; border: 1px solid #bfdbfe;" title="Latest Remark:&#10;${remark}">
						<svg style="width: 11px; height: 11px; fill: currentColor;" viewBox="0 0 24 24"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm-2 12H6v-2h12v2zm0-3H6V9h12v2zm0-3H6V6h12v2z"/></svg>
					</span>
				</span>
			`;
		},
		executive_1(val) {
			if (!val) return "";
			let info = (typeof frappe !== "undefined" && frappe.user_info) ? frappe.user_info[val] : null;
			let name = (info && info.fullname) ? info.fullname : val;
			return name.split(" ")[0].split("@")[0];
		},
		executive_2(val) {
			if (!val) return "";
			let info = (typeof frappe !== "undefined" && frappe.user_info) ? frappe.user_info[val] : null;
			let name = (info && info.fullname) ? info.fullname : val;
			return name.split(" ")[0].split("@")[0];
		}
	},
	onload(listview) {
		// Set default follow-up date route options for standard users
		if (!frappe.user.has_role("System Manager") && frappe.session.user !== "Administrator") {
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
