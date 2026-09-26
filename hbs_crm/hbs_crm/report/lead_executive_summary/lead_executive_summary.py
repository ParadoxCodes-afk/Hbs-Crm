# Copyright (c) 2026, Hbs and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = get_columns()
	data = get_data(filters)
	chart = get_chart(data)
	report_summary = get_report_summary(data)
	return columns, data, None, chart, report_summary


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
			"fieldname": "total_value",
			"label": _("Total Lead Value (₹)"),
			"fieldtype": "Currency",
			"options": "currency",
			"width": 160,
		},
		{
			"fieldname": "won_leads",
			"label": _("Won Leads"),
			"fieldtype": "Int",
			"width": 110,
		},
		{
			"fieldname": "won_value",
			"label": _("Won Value (₹)"),
			"fieldtype": "Currency",
			"options": "currency",
			"width": 140,
		},
		{
			"fieldname": "open_leads",
			"label": _("Open Leads"),
			"fieldtype": "Int",
			"width": 110,
		},
		{
			"fieldname": "lost_leads",
			"label": _("Lost Leads"),
			"fieldtype": "Int",
			"width": 100,
		},
		{
			"fieldname": "action",
			"label": _("Action"),
			"fieldtype": "Data",
			"width": 130,
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

	if filters.get("executive"):
		conditions.append("l.executive_1 = %(executive)s")
		params["executive"] = filters.get("executive")

	where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

	query = f"""
		SELECT
			COALESCE(NULLIF(TRIM(l.executive_1), ''), 'Unassigned') AS executive,
			COALESCE(NULLIF(TRIM(u.full_name), ''), l.executive_1, 'Unassigned') AS executive_name,
			COUNT(l.name) AS total_leads,
			SUM(COALESCE(l.final_total, 0)) AS total_value,
			SUM(CASE WHEN l.status = 'won' THEN 1 ELSE 0 END) AS won_leads,
			SUM(CASE WHEN l.status = 'won' THEN COALESCE(l.final_total, 0) ELSE 0 END) AS won_value,
			SUM(CASE WHEN l.status NOT IN ('won', 'lost') THEN 1 ELSE 0 END) AS open_leads,
			SUM(CASE WHEN l.status = 'lost' THEN 1 ELSE 0 END) AS lost_leads
		FROM `tabHbs Crm Lead` l
		LEFT JOIN `tabUser` u ON u.name = l.executive_1
		{where_clause}
		GROUP BY l.executive_1, u.full_name
		ORDER BY total_leads DESC, total_value DESC
	"""
	data = frappe.db.sql(query, params, as_dict=True)
	for row in data:
		exec_escaped = frappe.utils.escape_html(str(row.executive))
		row["action"] = f'<button class="btn btn-xs btn-primary btn-drilldown-lead" data-exec="{exec_escaped}" style="font-weight: 600;">🔍 View Leads</button>'
	return data


def get_chart(data):
	if not data:
		return None

	labels = [d.executive_name for d in data[:10]]
	total_leads = [d.total_leads for d in data[:10]]
	won_leads = [d.won_leads for d in data[:10]]

	return {
		"data": {
			"labels": labels,
			"datasets": [
				{"name": _("Total Leads"), "values": total_leads},
				{"name": _("Won Leads"), "values": won_leads},
			],
		},
		"type": "bar",
		"colors": ["#3b82f6", "#10b981"],
	}


def get_report_summary(data):
	if not data:
		return None

	total_leads = sum(d.total_leads for d in data)
	total_value = sum(d.total_value for d in data)
	won_leads = sum(d.won_leads for d in data)
	won_value = sum(d.won_value for d in data)

	return [
		{
			"value": total_leads,
			"label": _("Total Leads"),
			"datatype": "Int",
		},
		{
			"value": total_value,
			"label": _("Total Pipeline Value"),
			"datatype": "Currency",
			"indicator": "blue",
		},
		{
			"value": won_leads,
			"label": _("Total Won Leads"),
			"datatype": "Int",
			"indicator": "green",
		},
		{
			"value": won_value,
			"label": _("Total Won Value"),
			"datatype": "Currency",
			"indicator": "green",
		},
	]


@frappe.whitelist()
def get_executive_lead_details(executive, from_date=None, to_date=None, status=None, lead_type=None):
	"""Return all leads belonging to the specified executive matching the report filters."""
	conditions = []
	params = {}

	if not executive or executive == "Unassigned":
		conditions.append("(l.executive_1 IS NULL OR TRIM(l.executive_1) = '' OR l.executive_1 = 'Unassigned')")
	else:
		conditions.append("l.executive_1 = %(executive)s")
		params["executive"] = executive

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
