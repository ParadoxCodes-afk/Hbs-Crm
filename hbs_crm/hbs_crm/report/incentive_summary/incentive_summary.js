// Copyright (c) 2026, Hbs and contributors
// For license information, please see license.txt

frappe.query_reports["Incentive Summary"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.month_start(),
			reqd: 1
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.month_end(),
			reqd: 1
		},
		{
			fieldname: "executive",
			label: __("Executive"),
			fieldtype: "Link",
			options: "User",
			get_query: function () {
				return {
					filters: {
						enabled: 1
					}
				};
			}
		},
		{
			fieldname: "company_name",
			label: __("Company Name"),
			fieldtype: "Data"
		}
	],

	onload: function (report) {
		frappe.breadcrumbs.add("Hbs Crm", "Hbs Incentive Sheet");
		if (frappe.app && frappe.app.sidebar) {
			frappe.app.sidebar.setup("Hbs Crm");
		}

		// Enforce executive permission on the frontend filter
		frappe.call({
			method: "hbs_crm.hbs_crm.doctype.hbs_tally_renewal.hbs_tally_renewal.check_user_hierarchy_role",
			callback: function (r) {
				let is_admin_or_owner = !!(r.message && r.message.is_owner_or_admin);
				if (!is_admin_or_owner && frappe.session.user !== "Administrator" && !frappe.user.has_role("System Manager")) {
					report.set_filter_value("executive", frappe.session.user);
					let exec_filter = report.get_filter("executive");
					if (exec_filter) {
						exec_filter.df.read_only = 1;
						exec_filter.refresh();
					}
				}
			}
		});

		// Yellow/golden highlight for Executive Parent group rows matching the report mockup
		frappe.dom.set_style(`
			.report-wrapper .dt-row[data-is-group="1"],
			.report-wrapper .dt-row.is-group,
			.report-wrapper .dt-row:has(.dt-cell__content.is-group-cell) {
				background-color: #fef08a !important;
				font-weight: 700 !important;
			}
			.report-wrapper .dt-row[data-is-group="1"] .dt-cell__content,
			.report-wrapper .dt-row.is-group .dt-cell__content {
				font-weight: 700 !important;
				color: #1e293b !important;
			}
			.report-wrapper .dt-row[data-indent="1"] {
				background-color: #ffffff !important;
			}
			.report-wrapper .dt-cell--highlight {
				background-color: #fef08a !important;
			}
		`);
	},

	get_datatable_options: function (options) {
		return Object.assign(options, {
			hooks: Object.assign({}, options.hooks, {
				columnTotal: function (values, cell) {
					if (cell.column.id === "executive_name" || cell.colIndex === 0) {
						return __("Total");
					}
					if (!cell.column.fieldtype || !frappe.model.is_numeric_field(cell.column.fieldtype)) {
						return "";
					}

					let total = 0;
					let rows = (this.bodyRenderer && this.bodyRenderer.visibleRows && this.bodyRenderer.visibleRows.length)
						? this.bodyRenderer.visibleRows
						: (this.datamanager ? this.datamanager.getRows() : []);

					for (let row of rows) {
						// Only sum highlighted parent rows (indent === 0), exclusive of child rows
						if (row && row.meta && !row.meta.indent) {
							let cellData = row[cell.colIndex];
							let val = cellData ? cellData.content : 0;
							total += flt(val);
						}
					}
					return total;
				}
			})
		});
	},

	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		if (data && data.is_group) {
			return `<span class="is-group-cell" style="font-weight: 700; color: #0f172a;">${value}</span>`;
		}

		if (column.fieldname === "amount" && (!data || !data.is_group)) {
			return `<span style="font-weight: 600; color: #166534;">${value}</span>`;
		}

		return value;
	}
};
