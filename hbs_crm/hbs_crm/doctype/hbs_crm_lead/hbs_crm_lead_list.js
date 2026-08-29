// Copyright (c) 2026, Hbs and contributors
// For license information, please see license.txt

frappe.listview_settings['Hbs Crm Lead'] = {
	add_fields: ["contact_name", "company_name", "executive_1", "executive_2", "tally_serial", "status", "follow_up_date", "follow_up_time"],
	hide_name_column: true,
	order_by: "follow_up_date asc, follow_up_time asc",
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
