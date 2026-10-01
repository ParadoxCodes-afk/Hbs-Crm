// Copyright (c) 2026, Hbs and contributors
// For license information, please see license.txt

frappe.query_reports["Lead Executive Summary"] = {
	filters: [
		{
			fieldname: "group_by",
			label: __("Group By"),
			fieldtype: "Select",
			options: "Executive 1\nExecutive 2\nLead Type\nSummary",
			default: "Executive 1",
			reqd: 1
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -1)
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today()
		},
		{
			fieldname: "status",
			label: __("Lead Status"),
			fieldtype: "Select",
			options: "\nnew\npending\nwon\nlost"
		},
		{
			fieldname: "pending_ageing",
			label: __("Pending Ageing"),
			fieldtype: "Select",
			options: "\n>= 5 Days\n>= 10 Days\n>= 15 Days\n>= 20 Days\n>= 25 Days\n>= 30 Days\n>= 45 Days\n>= 60 Days"
		},
		{
			fieldname: "lead_type",
			label: __("Lead Type"),
			fieldtype: "Link",
			options: "hbs product type",
			get_query: function() {
				return {
					query: "hbs_crm.hbs_crm.doctype.hbs_lead_team_hierarchy.hbs_lead_team_hierarchy.get_assigned_lead_types_query"
				};
			}
		},
		{
			fieldname: "executive_1",
			label: __("Executive 1"),
			fieldtype: "Link",
			options: "User",
			get_query: function() {
				return {
					query: "hbs_crm.hbs_crm.doctype.hbs_lead_team_hierarchy.hbs_lead_team_hierarchy.get_assigned_executives_query"
				};
			}
		},
		{
			fieldname: "executive_2",
			label: __("Executive 2"),
			fieldtype: "Link",
			options: "User",
			get_query: function() {
				return {
					query: "hbs_crm.hbs_crm.doctype.hbs_lead_team_hierarchy.hbs_lead_team_hierarchy.get_assigned_executives_query"
				};
			}
		}
	],

	formatter: function(value, row, column, data, default_formatter) {
		if (column.fieldname === "action") {
			return value || "";
		}
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "won_leads" && data && data.won_leads > 0) {
			value = `<span style="color: #059669; font-weight: bold;">${value}</span>`;
		}
		if (column.fieldname === "total_leads" && data) {
			value = `<b>${value}</b>`;
		}
		return value;
	},

	open_leads: function(btn, e) {
		if (e) {
			e.stopPropagation();
			e.preventDefault();
		}
		let $btn = $(btn).closest(".btn-drilldown-lead");
		let report = frappe.query_report;
		let group_by = $btn.attr("data-group-by") || (report && report.get_filter_value ? report.get_filter_value("group_by") : "Executive") || "Executive";
		let val = $btn.attr("data-val") || $btn.attr("data-exec");
		open_drilldown_dialog(report, group_by, val);
	},

	get_datatable_options: function(options) {
		return Object.assign(options, {
			layout: "fluid"
		});
	},

	after_datatable_render: function(datatable) {
		$(datatable.wrapper).find(".dt-scrollable").css("overflow-x", "auto");
	},

	onload: function(report) {
		frappe.breadcrumbs.add("Hbs Crm", "Hbs Crm Lead");
		if (frappe.app && frappe.app.sidebar) {
			frappe.app.sidebar.setup("HBS CRM");
		}

		// Restrict Group By options for supervisors to Executive 1 and Executive 2
		function set_group_by_options(only_execs) {
			let group_by_filter = report.get_filter("group_by");
			if (!group_by_filter) return;
			let opts = only_execs ? "Executive 1\nExecutive 2" : "Executive 1\nExecutive 2\nLead Type\nSummary";
			group_by_filter.df.options = opts;
			if (group_by_filter.set_options) {
				group_by_filter.set_options(opts);
			}
			let cur = group_by_filter.get_value();
			if (only_execs && cur !== "Executive 1" && cur !== "Executive 2") {
				group_by_filter.set_value("Executive 1");
			}
			group_by_filter.refresh();
		}

		let is_owner = frappe.session.user === "Administrator" || (frappe.user_roles || []).some(r => ["System Manager", "Administrator", "Owner", "Hbs Owner"].includes(r));
		if (!is_owner) {
			set_group_by_options(true);
		}

		frappe.call({
			method: "hbs_crm.hbs_crm.doctype.hbs_crm_lead.hbs_crm_lead.check_is_admin_or_owner",
			callback: function(r) {
				set_group_by_options(!r.message);
			}
		});

		// Bind delegated click listener on both wrapper and document for bulletproof triggering
		report.page.wrapper.off("click", ".btn-drilldown-lead").on("click", ".btn-drilldown-lead", function(e) {
			frappe.query_reports["Lead Executive Summary"].open_leads(this, e);
		});

		$(document).off("click.lead_drilldown").on("click.lead_drilldown", ".btn-drilldown-lead", function(e) {
			frappe.query_reports["Lead Executive Summary"].open_leads(this, e);
		});

		// Dynamically sync status filter options from Hbs Crm Lead DocType
		frappe.model.with_doctype("Hbs Crm Lead", function() {
			let meta = frappe.get_meta("Hbs Crm Lead");
			let status_df = meta && meta.fields && meta.fields.find(f => f.fieldname === "status");
			if (status_df && status_df.options) {
				let opts = status_df.options.split("\n").map(s => s.trim()).filter(Boolean);
				opts.unshift("");
				let status_filter = report.get_filter("status");
				if (status_filter) {
					status_filter.df.options = opts.join("\n");
					status_filter.refresh();
				}
			}
		});

		// Also handle double-click or row click on data rows
		if (report.datatable) {
			report.page.wrapper.on("dblclick", ".dt-row", function() {
				let row_idx = $(this).attr("data-row-index");
				if (row_idx !== undefined && report.data && report.data[row_idx]) {
					let group_by = report.get_filter_value("group_by") || "Executive";
					let val = group_by === "Lead Type" ? report.data[row_idx].lead_type : report.data[row_idx].executive;
					if (val) {
						open_drilldown_dialog(report, group_by, val);
					}
				}
			});
		}
	}
};

function open_drilldown_dialog(report, group_by, val) {
	let filters = report.get_values() || {};
	let label = val === "Unassigned" ? __("Unassigned Leads") : val;

	let args = {
		from_date: filters.from_date || "",
		to_date: filters.to_date || "",
		status: filters.status || "",
		pending_ageing: filters.pending_ageing || "",
		lead_type: filters.lead_type || "",
		executive_1: filters.executive_1 || "",
		executive_2: filters.executive_2 || "",
		group_by: group_by,
		group_val: val
	};

	frappe.call({
		method: "hbs_crm.hbs_crm.report.lead_executive_summary.lead_executive_summary.get_executive_lead_details",
		args: args,
		freeze: true,
		freeze_message: __("Loading leads for {0}...", [label]),
		callback: function(r) {
			let leads = r.message || [];
			render_leads_drilldown_dialog(group_by, val, label, leads, filters);
		}
	});
}

function render_leads_drilldown_dialog(group_by, val, label, leads, filters) {
	let total_val = leads.reduce((sum, l) => sum + (parseFloat(l.final_total) || 0), 0);
	let formatted_total = format_currency(total_val, "INR");

	let get_status_badge = function(st) {
		st = (st || "").toLowerCase();
		let color_map = {
			"won": "badge-success",
			"pending": "badge-warning",
			"new": "badge-info",
			"lost": "badge-secondary"
		};
		let cls = color_map[st] || "badge-light";
		return `<span class="badge ${cls}" style="text-transform: capitalize; font-size: 11px;">${st || 'Open'}</span>`;
	};

	let format_lead_ageing = function(days) {
		if (days === null || days === undefined) return '<span class="text-muted">-</span>';
		let d = parseInt(days, 10);
		if (isNaN(d)) return '<span class="text-muted">-</span>';
		if (d === 0) return `<span class="badge badge-info" style="font-size: 11px;">${__("Today")}</span>`;
		let badge_cls = d > 30 ? "badge-danger" : (d > 15 ? "badge-warning" : "badge-light");
		let unit = d === 1 ? __("day") : __("days");
		return `<span class="badge ${badge_cls}" style="font-size: 11px; font-weight: 600;">${d} ${unit}</span>`;
	};

	let build_table_rows = function(lead_list) {
		if (!lead_list || lead_list.length === 0) {
			return `<tr><td colspan="9" class="text-center text-muted" style="padding: 20px;">${__("No leads found.")}</td></tr>`;
		}
		return lead_list.map((l, idx) => `
			<tr>
				<td style="text-align: center; color: #6b7280; font-size: 11px;">${idx + 1}</td>
				<td>
					<a href="/app/hbs-crm-lead/${l.name}" target="_blank" style="font-weight: bold; font-family: monospace;">
						${l.name}
					</a>
				</td>
				<td><b>${frappe.utils.escape_html(l.company_name || '-')}</b></td>
				<td>${frappe.utils.escape_html(l.contact_name || '-')}</td>
				<td>${frappe.utils.escape_html(group_by === "Executive 2" ? (l.executive_2_name || l.executive_2 || '-') : (l.executive_name || l.executive_1 || '-'))}</td>
				<td style="text-align: right; font-weight: 600;">${format_currency(l.final_total, "INR")}</td>
				<td style="text-align: center; white-space: nowrap;">${l.creation_date || '-'}</td>
				<td style="text-align: center; white-space: nowrap;" title="${l.last_remarks_date ? __('Last Remark Date: {0}', [l.last_remarks_date]) : ''}">${format_lead_ageing(l.lead_ageing)}</td>
				<td style="text-align: center;">${get_status_badge(l.status)}</td>
			</tr>
		`).join("");
	};

	let dialog = new frappe.ui.Dialog({
		title: __("📋 Leads: {0}", [label]),
		size: "extra-large",
		fields: [
			{
				fieldname: "header_html",
				fieldtype: "HTML",
				options: `
					<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 10px 15px; flex-wrap: wrap; gap: 10px;">
						<div>
							<span style="font-size: 15px; font-weight: bold; color: #1e293b;">${frappe.utils.escape_html(label)}</span>
							<span class="text-muted" style="margin-left: 10px; font-size: 13px;">Total Leads: <b>${leads.length}</b> | Total Value: <b style="color: #059669;">${formatted_total}</b></span>
						</div>
						<div style="display: flex; gap: 8px;">
							<input type="text" class="form-control form-control-sm lead-filter-input" placeholder="${__('Filter leads by name, company...')}" style="width: 240px; font-size: 12px;">
							<button class="btn btn-xs btn-default btn-open-lead-list" style="font-weight: 600;">
								<i class="fa fa-external-link"></i> ${__('Open in List View')}
							</button>
						</div>
					</div>
				`
			},
			{
				fieldname: "leads_table_html",
				fieldtype: "HTML",
				options: `
					<div style="max-height: 480px; overflow-y: auto; border: 1px solid #e2e8f0; border-radius: 6px;">
						<table class="table table-bordered table-hover table-sm" style="margin: 0; font-size: 12px; width: 100%;">
							<thead style="position: sticky; top: 0; background: #f1f5f9; z-index: 2;">
								<tr style="color: #334155;">
									<th style="width: 40px; text-align: center;">#</th>
									<th style="width: 120px;">${__('Lead ID')}</th>
									<th style="width: 200px;">${__('Company Name')}</th>
									<th style="width: 160px;">${__('Contact Person')}</th>
									<th style="width: 150px;">${__('Executive')}</th>
									<th style="width: 120px; text-align: right;">${__('Lead Value (₹)')}</th>
									<th style="width: 110px; text-align: center;">${__('Created Date')}</th>
									<th style="width: 110px; text-align: center;">${__('Lead Ageing')}</th>
									<th style="width: 90px; text-align: center;">${__('Status')}</th>
								</tr>
							</thead>
							<tbody class="leads-table-body">
								${build_table_rows(leads)}
							</tbody>
						</table>
					</div>
				`
			}
		],
		primary_action_label: __("Close"),
		primary_action: function() {
			dialog.hide();
		}
	});

	dialog.$wrapper.find(".modal-dialog").css({
		"max-width": "1150px",
		"width": "95%"
	});

	// Live filter in dialog
	dialog.$wrapper.find(".lead-filter-input").on("input", function() {
		let q = $(this).val().toLowerCase().trim();
		if (!q) {
			dialog.$wrapper.find(".leads-table-body").html(build_table_rows(leads));
			return;
		}
		let filtered = leads.filter(l =>
			(l.name && l.name.toLowerCase().includes(q)) ||
			(l.company_name && l.company_name.toLowerCase().includes(q)) ||
			(l.contact_name && l.contact_name.toLowerCase().includes(q)) ||
			(l.executive_name && l.executive_name.toLowerCase().includes(q)) ||
			(l.executive_1 && l.executive_1.toLowerCase().includes(q)) ||
			(l.status && l.status.toLowerCase().includes(q))
		);
		dialog.$wrapper.find(".leads-table-body").html(build_table_rows(filtered));
	});

	// Button to open list view with filters applied
	dialog.$wrapper.find(".btn-open-lead-list").on("click", function() {
		let route_opts = {};
		if (group_by === "Lead Type") {
			if (val && val !== "Unassigned") {
				route_opts["lead_type"] = val;
			}
			if (filters.executive_1) {
				route_opts["executive_1"] = filters.executive_1;
			}
			if (filters.executive_2) {
				route_opts["executive_2"] = filters.executive_2;
			}
		} else if (group_by === "Executive 2") {
			if (val && val !== "Unassigned") {
				route_opts["executive_2"] = val;
			}
			if (filters.executive_1) {
				route_opts["executive_1"] = filters.executive_1;
			}
			if (filters.lead_type) {
				route_opts["lead_type"] = filters.lead_type;
			}
		} else {
			if (val && val !== "Unassigned") {
				route_opts["executive_1"] = val;
			}
			if (filters.executive_2) {
				route_opts["executive_2"] = filters.executive_2;
			}
			if (filters.lead_type) {
				route_opts["lead_type"] = filters.lead_type;
			}
		}
		if (filters.status) {
			route_opts["status"] = filters.status;
		}
		dialog.hide();
		frappe.set_route("List", "Hbs Crm Lead", route_opts);
	});

	dialog.show();
}
