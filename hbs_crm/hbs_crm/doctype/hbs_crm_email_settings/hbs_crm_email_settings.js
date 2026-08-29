// Copyright (c) 2026, Hbs and contributors
// For license information, please see license.txt

frappe.ui.form.on("Hbs CRM Email Settings", {
	refresh(frm) {
		frm.add_custom_button(__("Test Connection"), function () {
			frm.call({
				method: "test_smtp_connection",
				doc: frm.doc,
				freeze: true,
				freeze_message: __("Testing SMTP Connection..."),
				callback: function (r) {
					if (r.message) {
						frappe.show_alert({
							message: __("SMTP server connected successfully!"),
							indicator: "green"
						});
					}
				}
			});
		}).addClass("btn-primary");
	}
});
