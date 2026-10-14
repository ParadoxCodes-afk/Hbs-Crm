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
				if (!is_admin_or_owner && frappe.session.user !== "Administrator" && !frappe.user.has_role("System Manager") && !frappe.user.has_role("Incentive Viewer")) {
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
			.btn-drilldown-incentive:hover {
				background-color: #f1f5f9 !important;
				border-color: #94a3b8 !important;
			}
		`);
	},

	open_incentives: function (btn, e) {
		if (e) {
			e.stopPropagation();
			e.preventDefault();
		}
		let $btn = $(btn).closest(".btn-drilldown-incentive");
		let report = frappe.query_report;
		let exec_user = $btn.attr("data-exec");
		let exec_name = $btn.attr("data-exec-name") || exec_user;
		open_incentive_drilldown_dialog(report, exec_user, exec_name);
	},

	get_datatable_options: function (options) {
		return Object.assign(options, {
			hooks: Object.assign({}, options.hooks, {
				columnTotal: function (values, cell) {
					if (cell.column.id === "executive_name" || cell.colIndex === 0) {
						return __("Total");
					}
					if (cell.column.id === "action") {
						return "";
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
		if (column.fieldname === "action") {
			return value || "";
		}

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

function open_incentive_drilldown_dialog(report, exec_user, exec_name) {
	let filters = report.get_values() || {};
	let label = exec_name || exec_user || __("Executive");

	let args = {
		executive: exec_user || "",
		from_date: filters.from_date || "",
		to_date: filters.to_date || "",
		company_name: filters.company_name || ""
	};

	frappe.call({
		method: "hbs_crm.hbs_crm.report.incentive_summary.incentive_summary.get_executive_incentive_details",
		args: args,
		freeze: true,
		freeze_message: __("Loading incentives for {0}...", [label]),
		callback: function (r) {
			let records = r.message || [];
			render_incentive_drilldown_dialog(exec_user, exec_name, label, records, filters);
		}
	});
}

function render_incentive_drilldown_dialog(exec_user, exec_name, label, records, filters) {
	let total_val = records.reduce((sum, r) => sum + (parseFloat(r.actual_amt) || 0), 0);
	let total_inc = records.reduce((sum, r) => sum + (parseFloat(r.incentive) || 0), 0);
	let formatted_val = format_currency(total_val, "INR");
	let formatted_inc = format_currency(total_inc, "INR");

	let build_table_rows = function (list) {
		if (!list || list.length === 0) {
			return `<tr><td colspan="10" class="text-center text-muted" style="padding: 20px;">${__("No incentive records found.")}</td></tr>`;
		}
		return list.map((r, idx) => `
			<tr>
				<td style="text-align: center; color: #6b7280; font-size: 11px;">${idx + 1}</td>
				<td style="text-align: center; white-space: nowrap;">
					<a href="/app/hbs-incentive-sheet/${r.name}" target="_blank" style="font-weight: bold; font-family: monospace;">
						${frappe.utils.escape_html(r.vch_no || r.name)}
					</a>
				</td>
				<td style="text-align: center; white-space: nowrap;">${r.voucher_date ? frappe.datetime.str_to_user(r.voucher_date) : '-'}</td>
				<td><b>${frappe.utils.escape_html(r.party_name || '-')}</b></td>
				<td>${frappe.utils.escape_html(r.item_name || '-')}</td>
				<td style="font-family: monospace; font-size: 11px;">${frappe.utils.escape_html(r.serial_no || '-')}</td>
				<td><span class="badge badge-light" style="font-size: 11px;">${frappe.utils.escape_html(r.roll_type || '-')}</span></td>
				<td style="text-align: right;">${r.qty || 0}</td>
				<td style="text-align: right; font-weight: 500;">${format_currency(r.actual_amt, "INR")}</td>
				<td style="text-align: right; font-weight: 700; color: #047857;">${format_currency(r.incentive, "INR")}</td>
			</tr>
		`).join("");
	};

	let dialog = new frappe.ui.Dialog({
		title: __("💰 Incentive Records: {0}", [label]),
		size: "extra-large",
		fields: [
			{
				fieldname: "header_html",
				fieldtype: "HTML",
				options: `
					<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 10px 15px; flex-wrap: wrap; gap: 10px;">
						<div>
							<span style="font-size: 15px; font-weight: bold; color: #1e293b;">${frappe.utils.escape_html(label)}</span>
							<span class="text-muted" style="margin-left: 10px; font-size: 13px;">
								Vouchers: <b>${records.length}</b> | 
								Item Value: <b>${formatted_val}</b> | 
								Total Incentive: <b style="color: #047857; font-size: 14px;">${formatted_inc}</b>
							</span>
						</div>
						<div style="display: flex; gap: 8px;">
							<input type="text" class="form-control form-control-sm inc-filter-input" placeholder="${__('Search voucher, party, item, serial...')}" style="width: 250px; font-size: 12px;">
							<button class="btn btn-xs btn-default btn-open-inc-list" style="font-weight: 600;">
								<i class="fa fa-external-link"></i> ${__('Open in List View')}
							</button>
						</div>
					</div>
				`
			},
			{
				fieldname: "records_table_html",
				fieldtype: "HTML",
				options: `
					<div style="max-height: 480px; overflow-y: auto; border: 1px solid #e2e8f0; border-radius: 6px;">
						<table class="table table-bordered table-hover table-sm" style="margin: 0; font-size: 12px; width: 100%;">
							<thead style="position: sticky; top: 0; background: #f1f5f9; z-index: 2;">
								<tr style="color: #334155;">
									<th style="width: 40px; text-align: center;">#</th>
									<th style="width: 100px; text-align: center;">${__('Vch No')}</th>
									<th style="width: 95px; text-align: center;">${__('Date')}</th>
									<th style="width: 200px;">${__('Party Name')}</th>
									<th style="width: 200px;">${__('Item Name')}</th>
									<th style="width: 110px;">${__('Serial No')}</th>
									<th style="width: 110px;">${__('Roll Type')}</th>
									<th style="width: 50px; text-align: right;">${__('Qty')}</th>
									<th style="width: 110px; text-align: right;">${__('Actual Amt')}</th>
									<th style="width: 110px; text-align: right;">${__('Incentive')}</th>
								</tr>
							</thead>
							<tbody class="inc-table-body">
								${build_table_rows(records)}
							</tbody>
						</table>
					</div>
				`
			}
		],
		primary_action_label: __("Close"),
		primary_action: function () {
			dialog.hide();
		}
	});

	dialog.$wrapper.find(".modal-dialog").css({
		"max-width": "1150px",
		"width": "95%"
	});

	// Live search inside modal dialog
	dialog.$wrapper.find(".inc-filter-input").on("input", function () {
		let q = $(this).val().toLowerCase().trim();
		if (!q) {
			dialog.$wrapper.find(".inc-table-body").html(build_table_rows(records));
			return;
		}
		let filtered = records.filter(r =>
			(r.vch_no && String(r.vch_no).toLowerCase().includes(q)) ||
			(r.party_name && r.party_name.toLowerCase().includes(q)) ||
			(r.item_name && r.item_name.toLowerCase().includes(q)) ||
			(r.serial_no && String(r.serial_no).toLowerCase().includes(q)) ||
			(r.roll_type && r.roll_type.toLowerCase().includes(q)) ||
			(r.company_name && r.company_name.toLowerCase().includes(q))
		);
		dialog.$wrapper.find(".inc-table-body").html(build_table_rows(filtered));
	});

	// 'Open in List View' redirection button
	dialog.$wrapper.find(".btn-open-inc-list").on("click", function () {
		let route_opts = {};
		if (exec_user) {
			route_opts["executive"] = exec_user;
		}
		if (filters.from_date && filters.to_date) {
			route_opts["voucher_date"] = ["Between", [filters.from_date, filters.to_date]];
		} else if (filters.from_date) {
			route_opts["voucher_date"] = [">=", filters.from_date];
		} else if (filters.to_date) {
			route_opts["voucher_date"] = ["<=", filters.to_date];
		}
		if (filters.company_name) {
			route_opts["company_name"] = filters.company_name;
		}
		dialog.hide();
		frappe.set_route("List", "Hbs Incentive Sheet", route_opts);
	});

	dialog.show();
}
