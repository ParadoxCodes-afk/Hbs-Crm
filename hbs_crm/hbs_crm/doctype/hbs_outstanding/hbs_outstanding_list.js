// Copyright (c) 2026, Hbs and contributors
// For license information, please see license.txt

frappe.listview_settings["Hbs Outstanding"] = {
	hide_name_column: true,
	hide_name_filter: true,
	filters: [["status", "=", "Pending"]],
	add_fields: [
		"bill_no",
		"party_name",
		"company_name",
		"bill_date",
		"bill_amt",
		"pending_amt",
		"due_date",
		"overdue_days",
		"status",
		"payment_status",
		"last_remark",
		"last_remarks_date",
		"executive_1",
		"executive_2"
	],
	formatters: {
		party_name(val, df, doc) {
			let text = val ? frappe.utils.escape_html(val) : "";
			if (!doc.last_remark) {
				return `<span class="text-truncate" style="display: inline-block; max-width: 140px; vertical-align: middle;" title="${text}"><b>${text}</b></span>`;
			}
			let remark = frappe.utils.escape_html(doc.last_remark);
			return `
				<span style="display: inline-flex; align-items: center; gap: 4px; max-width: 100%;">
					<span class="text-truncate" style="display: inline-block; max-width: 125px; vertical-align: middle;" title="${text}"><b>${text}</b></span>
					<span style="cursor: help; flex-shrink: 0; display: inline-flex; align-items: center; justify-content: center; width: 16px; height: 16px; border-radius: 50%; background: #eff6ff; color: #2563eb; border: 1px solid #bfdbfe;" title="Latest Remark:&#10;${remark}">
						<svg style="width: 9px; height: 9px; fill: currentColor;" viewBox="0 0 24 24"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm-2 12H6v-2h12v2zm0-3H6V9h12v2zm0-3H6V6h12v2z"/></svg>
					</span>
				</span>
			`;
		},
		status(val) {
			if (!val) return "";
			let color = (val === "Complete" || val === "Cleared") ? "green" : (val === "Partially Paid" ? "orange" : "blue");
			return `<span class="indicator-pill ${color}" style="font-size: 10.5px; padding: 2px 6px; white-space: nowrap;">${frappe.utils.escape_html(val)}</span>`;
		},
		payment_status(val) {
			if (!val) return "";
			if (val === "Payment Received") {
				return `<span class="indicator-pill green" style="font-size: 10.5px; padding: 2px 6px; white-space: nowrap;">Received</span>`;
			}
			return `<span class="text-muted text-truncate" style="font-size: 11px; max-width: 80px;" title="${val}">${frappe.utils.escape_html(val)}</span>`;
		},
		last_remark(val) {
			if (!val) return "";
			let text = frappe.utils.escape_html(val.trim());
			return `<span class="text-truncate text-muted" style="display: inline-block; max-width: 130px;" title="${text}">${text}</span>`;
		},
		executive_1(val) {
			if (!val) return "";
			let short_name = val.includes("@") ? val.split("@")[0] : val;
			return `<span class="text-truncate text-muted" style="max-width: 75px; display: inline-block;" title="${val}">${short_name}</span>`;
		},
		executive_2(val) {
			if (!val) return "";
			let short_name = val.includes("@") ? val.split("@")[0] : val;
			return `<span class="text-truncate text-muted" style="max-width: 75px; display: inline-block;" title="${val}">${short_name}</span>`;
		}
	},
	get_indicator: function (doc) {
		if (doc.status === "Complete" || doc.status === "Cleared") {
			return [__("Complete"), "green", "status,=,Complete"];
		} else if (doc.overdue_days > 0) {
			return [__("Overdue ({0} d)", [doc.overdue_days]), "red", "status,=,Pending"];
		} else {
			return [__("Pending"), "blue", "status,=,Pending"];
		}
	},
	refresh(listview) {
		if (listview.column_max_widths) {
			listview.column_max_widths["bill_no"] = 85;
			listview.column_max_widths["bill_date"] = 75;
			listview.column_max_widths["party_name"] = 135;
			listview.column_max_widths["company_name"] = 85;
			listview.column_max_widths["status"] = 75;
			listview.column_max_widths["payment_status"] = 80;
			listview.column_max_widths["bill_amt"] = 80;
			listview.column_max_widths["pending_amt"] = 80;
			listview.column_max_widths["due_date"] = 75;
			listview.column_max_widths["overdue_days"] = 55;
			listview.column_max_widths["executive_1"] = 75;
			listview.column_max_widths["executive_2"] = 75;
			listview.column_max_widths["last_remark"] = 130;
			listview.column_max_widths["last_remarks_date"] = 75;
			if (typeof listview.apply_column_widths === "function") {
				listview.apply_column_widths();
			}
		}
	},
	onload(listview) {
		if (!frappe.route_options) {
			const current_filters = listview.filter_area ? listview.filter_area.get() : [];
			const has_status_filter = current_filters.some(f => f[1] === "status");
			if (!has_status_filter && listview.filter_area) {
				listview.filter_area.add([[listview.doctype, "status", "=", "Pending"]]);
			}
		}

		frappe.dom.set_style(`
			.frappe-list[data-doctype="Hbs Outstanding"] .list-row,
			.list-view[data-doctype="Hbs Outstanding"] .list-row,
			.frappe-list[data-doctype="Hbs Outstanding"] .list-row-head,
			.list-view[data-doctype="Hbs Outstanding"] .list-row-head {
				padding-left: 8px !important;
				padding-right: 8px !important;
				font-size: 12px !important;
			}

			.frappe-list[data-doctype="Hbs Outstanding"] .list-row-col,
			.list-view[data-doctype="Hbs Outstanding"] .list-row-col {
				padding-right: 4px !important;
				padding-left: 4px !important;
				min-width: 0 !important;
			}

			.frappe-list[data-doctype="Hbs Outstanding"] .list-row-col.bill_no,
			.list-view[data-doctype="Hbs Outstanding"] .list-row-col.bill_no {
				max-width: 95px !important;
				width: 85px !important;
				flex: 0 0 85px !important;
			}

			.frappe-list[data-doctype="Hbs Outstanding"] .list-row-col.bill_date,
			.list-view[data-doctype="Hbs Outstanding"] .list-row-col.bill_date {
				max-width: 85px !important;
				width: 75px !important;
				flex: 0 0 75px !important;
			}

			.frappe-list[data-doctype="Hbs Outstanding"] .list-row-col.party_name,
			.list-view[data-doctype="Hbs Outstanding"] .list-row-col.party_name {
				max-width: 155px !important;
				min-width: 110px !important;
				flex: 1 1 135px !important;
			}

			.frappe-list[data-doctype="Hbs Outstanding"] .list-row-col.company_name,
			.list-view[data-doctype="Hbs Outstanding"] .list-row-col.company_name {
				max-width: 95px !important;
				width: 85px !important;
				flex: 0 0 85px !important;
			}

			.frappe-list[data-doctype="Hbs Outstanding"] .list-row-col.status,
			.list-view[data-doctype="Hbs Outstanding"] .list-row-col.status {
				max-width: 85px !important;
				width: 75px !important;
				flex: 0 0 75px !important;
			}

			.frappe-list[data-doctype="Hbs Outstanding"] .list-row-col.payment_status,
			.list-view[data-doctype="Hbs Outstanding"] .list-row-col.payment_status {
				max-width: 90px !important;
				width: 80px !important;
				flex: 0 0 80px !important;
			}

			.frappe-list[data-doctype="Hbs Outstanding"] .list-row-col.bill_amt,
			.list-view[data-doctype="Hbs Outstanding"] .list-row-col.bill_amt {
				max-width: 90px !important;
				width: 80px !important;
				flex: 0 0 80px !important;
				text-align: right !important;
			}

			.frappe-list[data-doctype="Hbs Outstanding"] .list-row-col.pending_amt,
			.list-view[data-doctype="Hbs Outstanding"] .list-row-col.pending_amt {
				max-width: 90px !important;
				width: 80px !important;
				flex: 0 0 80px !important;
				text-align: right !important;
			}

			.frappe-list[data-doctype="Hbs Outstanding"] .list-row-col.due_date,
			.list-view[data-doctype="Hbs Outstanding"] .list-row-col.due_date {
				max-width: 85px !important;
				width: 75px !important;
				flex: 0 0 75px !important;
			}

			.frappe-list[data-doctype="Hbs Outstanding"] .list-row-col.overdue_days,
			.list-view[data-doctype="Hbs Outstanding"] .list-row-col.overdue_days {
				max-width: 60px !important;
				width: 55px !important;
				flex: 0 0 55px !important;
				text-align: center !important;
			}

			.frappe-list[data-doctype="Hbs Outstanding"] .list-row-col.executive_1,
			.list-view[data-doctype="Hbs Outstanding"] .list-row-col.executive_1,
			.frappe-list[data-doctype="Hbs Outstanding"] .list-row-col.executive_2,
			.list-view[data-doctype="Hbs Outstanding"] .list-row-col.executive_2 {
				max-width: 85px !important;
				width: 75px !important;
				flex: 0 0 75px !important;
			}

			.frappe-list[data-doctype="Hbs Outstanding"] .list-row-col.last_remark,
			.list-view[data-doctype="Hbs Outstanding"] .list-row-col.last_remark {
				max-width: 145px !important;
				min-width: 90px !important;
				flex: 1 1 125px !important;
			}

			.frappe-list[data-doctype="Hbs Outstanding"] .list-row-col.last_remarks_date,
			.list-view[data-doctype="Hbs Outstanding"] .list-row-col.last_remarks_date {
				max-width: 85px !important;
				width: 75px !important;
				flex: 0 0 75px !important;
			}
		`);
	}
};
