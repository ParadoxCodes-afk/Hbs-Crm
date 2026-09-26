# Copyright (c) 2026, Hbs and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = get_columns()
	data = get_data(filters)
	report_summary = get_report_summary(data)
	return columns, data, None, None, report_summary


def get_columns():
	return [
		{
			"fieldname": "executive",
			"label": _("Executive ID"),
			"fieldtype": "Link",
			"options": "User",
			"width": 180,
		},
		{
			"fieldname": "executive_name",
			"label": _("Executive Name"),
			"fieldtype": "Data",
			"width": 180,
		},
		{
			"fieldname": "total_leads",
			"label": _("Total Leads"),
			"fieldtype": "Int",
			"width": 110,
		},
		{
			"fieldname": "pending_leads",
			"label": _("Total Pending Lead"),
			"fieldtype": "Int",
			"width": 130,
		},
		{
			"fieldname": "won_leads",
			"label": _("Total Won Lead"),
			"fieldtype": "Int",
			"width": 120,
		},
		{
			"fieldname": "lost_leads",
			"label": _("Total Lost Lead"),
			"fieldtype": "Int",
			"width": 120,
		},
		{
			"fieldname": "total_value",
			"label": _("Total Lead Value (₹)"),
			"fieldtype": "Currency",
			"options": "currency",
			"width": 160,
		},
		{
			"fieldname": "action",
			"label": _("Action"),
			"fieldtype": "Data",
			"width": 120,
			"sortable": False,
			"filterable": False,
		},
	]


def get_data(filters):
	conditions = []
	params = {}

	if filters.get("from_date"):
		conditions.append("DATE(l.creation) >= %(from_date)s")
		params["from_date"] = filters.get("from_date")

	if filters.get("to_date"):
		conditions.append("DATE(l.creation) <= %(to_date)s")
		params["to_date"] = filters.get("to_date")

	if filters.get("status"):
		conditions.append("l.status = %(status)s")
		params["status"] = filters.get("status")

	if filters.get("lead_type"):
		conditions.append("l.lead_type = %(lead_type)s")
		params["lead_type"] = filters.get("lead_type")

	exec_1 = filters.get("executive_1") or filters.get("executive")
	if exec_1:
		conditions.append("l.executive_1 = %(executive_1)s")
		params["executive_1"] = exec_1

	if filters.get("executive_2"):
		conditions.append("l.executive_2 = %(executive_2)s")
		params["executive_2"] = filters.get("executive_2")

	where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

	query = f"""
		SELECT
			COALESCE(NULLIF(TRIM(l.executive_1), ''), 'Unassigned') AS executive,
			COALESCE(NULLIF(TRIM(u.full_name), ''), l.executive_1, 'Unassigned') AS executive_name,
			COUNT(l.name) AS total_leads,
			SUM(CASE WHEN l.status NOT IN ('won', 'lost') THEN 1 ELSE 0 END) AS pending_leads,
			SUM(CASE WHEN l.status = 'won' THEN 1 ELSE 0 END) AS won_leads,
			SUM(CASE WHEN l.status = 'lost' THEN 1 ELSE 0 END) AS lost_leads,
			SUM(COALESCE(l.final_total, 0)) AS total_value
		FROM `tabHbs Crm Lead` l
		LEFT JOIN `tabUser` u ON u.name = l.executive_1
		{where_clause}
		GROUP BY l.executive_1, u.full_name
		ORDER BY total_leads DESC, total_value DESC
	"""
	data = frappe.db.sql(query, params, as_dict=True)
	for row in data:
		row["total_leads"] = int(row.get("total_leads") or 0)
		row["pending_leads"] = int(row.get("pending_leads") or 0)
		row["won_leads"] = int(row.get("won_leads") or 0)
		row["lost_leads"] = int(row.get("lost_leads") or 0)
		exec_escaped = frappe.utils.escape_html(str(row.executive))
		row["action"] = (
			f'<button class="btn btn-default btn-xs btn-drilldown-lead" data-exec="{exec_escaped}" '
			'style="border: 1px solid var(--border-color); border-radius: 4px; padding: 2px 10px; '
			'font-size: 11px; font-weight: 500; box-shadow: none; display: inline-flex; align-items: center; gap: 4px;">'
			'<svg class="icon icon-xs" style="width: 11px; height: 11px;"><use href="#icon-list"></use></svg>'
			'View Leads'
			'</button>'
		)
	return data


def get_report_summary(data):
	if not data:
		return None

	total_leads = sum(d.total_leads for d in data)
	pending_leads = sum(d.pending_leads for d in data)
	won_leads = sum(d.won_leads for d in data)
	lost_leads = sum(d.lost_leads for d in data)
	total_value = sum(d.total_value for d in data)

	return [
		{
			"value": total_leads,
			"label": _("Total Leads"),
			"datatype": "Int",
		},
		{
			"value": pending_leads,
			"label": _("Total Pending Leads"),
			"datatype": "Int",
			"indicator": "orange",
		},
		{
			"value": won_leads,
			"label": _("Total Won Leads"),
			"datatype": "Int",
			"indicator": "green",
		},
		{
			"value": lost_leads,
			"label": _("Total Lost Leads"),
			"datatype": "Int",
			"indicator": "red",
		},
		{
			"value": total_value,
			"label": _("Total Lead Value"),
			"datatype": "Currency",
			"indicator": "blue",
		},
	]


@frappe.whitelist()
def get_executive_lead_details(executive, from_date=None, to_date=None, status=None, lead_type=None, executive_2=None):
	"""Return all leads belonging to the specified executive matching the report filters."""
	conditions = []
	params = {}

	if not executive or executive == "Unassigned":
		conditions.append("(l.executive_1 IS NULL OR TRIM(l.executive_1) = '' OR l.executive_1 = 'Unassigned')")
	else:
		conditions.append("l.executive_1 = %(executive)s")
		params["executive"] = executive

	if executive_2:
		conditions.append("l.executive_2 = %(executive_2)s")
		params["executive_2"] = executive_2

	if from_date:
		conditions.append("DATE(l.creation) >= %(from_date)s")
		params["from_date"] = from_date

	if to_date:
		conditions.append("DATE(l.creation) <= %(to_date)s")
		params["to_date"] = to_date

	if status:
		conditions.append("l.status = %(status)s")
		params["status"] = status

	if lead_type:
		conditions.append("l.lead_type = %(lead_type)s")
		params["lead_type"] = lead_type

	where_clause = f"WHERE {' AND '.join(conditions)}"

	query = f"""
		SELECT
			l.name,
			COALESCE(l.company_name, '') AS company_name,
			COALESCE(l.contact_name, '') AS contact_name,
			COALESCE(l.final_total, 0) AS final_total,
			DATE_FORMAT(l.creation, '%%Y-%%m-%%d') AS creation_date,
			COALESCE(DATE_FORMAT(l.last_remarks_date, '%%Y-%%m-%%d'), '') AS last_remarks_date,
			COALESCE(l.status, '') AS status,
			COALESCE(l.lead_type, '') AS lead_type,
			COALESCE(l.last_remark, '') AS last_remark
		FROM `tabHbs Crm Lead` l
		{where_clause}
		ORDER BY l.creation DESC
		LIMIT 500
	"""
	return frappe.db.sql(query, params, as_dict=True)
