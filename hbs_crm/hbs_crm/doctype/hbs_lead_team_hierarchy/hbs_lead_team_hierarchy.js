// Copyright (c) 2026, Hbs and contributors
// For license information, please see license.txt

frappe.ui.form.on("Hbs Lead Team Hierarchy", {
	setup(frm) {
		frm.set_query("user", "executives", function() {
			return {
				filters: {
					enabled: 1,
					user_type: "System User"
				}
			};
		});
		frm.set_query("user", "supervisors", function() {
			return {
				filters: {
					enabled: 1,
					user_type: "System User"
				}
			};
		});
	}
});
