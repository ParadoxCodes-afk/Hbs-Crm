// Copyright (c) 2026, Hbs and contributors
// For license information, please see license.txt

frappe.listview_settings["Hbs Outstanding"] = {
	hide_name_column: true,
	hide_name_filter: true,
	add_fields: [
		"bill_no",
		"party_name",
		"company_name",
		"bill_amt",
		"pending_amt",
		"due_date",
		"overdue_days",
		"status",
		"last_remark",
		"last_remarks_date",
		"executive_1",
		"executive_2"
	],
	formatters: {
		party_name(val, df, doc) {
			let text = val ? frappe.utils.escape_html(val) : "";
			if (!doc.last_remark) {
				return `<span title="${text}"><b>${text}</b></span>`;
			}
			let remark = frappe.utils.escape_html(doc.last_remark);
			return `
				<span style="display: inline-flex; align-items: center; gap: 6px; max-width: 100%;">
					<span class="text-truncate" style="display: inline-block; max-width: 220px; vertical-align: middle;" title="${text}"><b>${text}</b></span>
					<span style="cursor: help; flex-shrink: 0; display: inline-flex; align-items: center; justify-content: center; width: 18px; height: 18px; border-radius: 50%; background: #eff6ff; color: #2563eb; border: 1px solid #bfdbfe; margin-left: 2px;" title="Latest Remark:&#10;${remark}">
						<svg style="width: 10px; height: 10px; fill: currentColor;" viewBox="0 0 24 24"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm-2 12H6v-2h12v2zm0-3H6V9h12v2zm0-3H6V6h12v2z"/></svg>
					</span>
				</span>
			`;
		}
	},
	get_indicator: function (doc) {
		if (doc.status === "Cleared") {
			return [__("Cleared"), "green", "status,=,Cleared"];
		} else if (doc.status === "Partially Paid") {
			return [__("Partially Paid"), "orange", "status,=,Partially Paid"];
		} else if (doc.overdue_days > 0) {
			return [__("Overdue ({0} d)", [doc.overdue_days]), "red", "status,=,Pending"];
		} else {
			return [__("Pending"), "blue", "status,=,Pending"];
		}
	}
};
