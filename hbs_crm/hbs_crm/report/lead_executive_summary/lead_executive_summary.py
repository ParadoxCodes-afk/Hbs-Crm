# Copyright (c) 2026, Hbs and contributors
# For license information, please see license.txt

import re
import frappe
from frappe import _
from hbs_crm.hbs_crm.doctype.hbs_crm_lead.hbs_crm_lead import is_owner_or_admin


def execute(filters=None):
	user = frappe.session.user
	if not is_owner_or_admin(user):
		from hbs_crm.hbs_crm.doctype.hbs_lead_team_hierarchy.hbs_lead_team_hierarchy import get_user_lead_team_permissions
		from hbs_crm.hbs_crm.doctype.hbs_crm_lead.hbs_crm_lead import get_subordinates_from_hierarchy

		team_perms = get_user_lead_team_permissions(user)
		subordinates = get_subordinates_from_hierarchy(user)
		allowed_execs = set(team_perms["executives"]).union(subordinates)

		if not allowed_execs:
			frappe.throw(_("Only supervisors can access the Lead Executive Summary report."), frappe.PermissionError)

	filters = frappe._dict(filters or {})
	columns = get_columns(filters)
	data = get_data(filters)
	report_summary = get_report_summary(data, filters)
	return columns, data, None, None, report_summary


def get_columns(filters=None):
	group_by = (filters or {}).get("group_by") or "Executive 1"
	if group_by == "Lead Type":
		group_cols = [
			{
				"fieldname": "lead_type",
				"label": _("Lead Type"),
				"fieldtype": "Link",
				"options": "hbs product type",
				"width": 180,
			}
		]
	elif group_by == "Executive 2":
		group_cols = [
			{
				"fieldname": "executive",
				"label": _("Executive 2 ID"),
				"fieldtype": "Link",
				"options": "User",
				"width": 180,
			},
			{
				"fieldname": "executive_name",
				"label": _("Executive 2 Name"),
				"fieldtype": "Data",
				"width": 180,
			},
		]
	elif group_by == "Summary":
		group_cols = [
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
		]
	else:
		group_cols = [
			{
				"fieldname": "executive",
				"label": _("Executive 1 ID"),
				"fieldtype": "Link",
				"options": "User",
				"width": 180,
			},
			{
				"fieldname": "executive_name",
				"label": _("Executive 1 Name"),
				"fieldtype": "Data",
				"width": 180,
			},
		]

	common_cols = [
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
			"resizable": 0,
		},
	]
	return group_cols + common_cols


def get_data(filters):
	conditions = []
	params = {}
	group_by = filters.get("group_by") or "Executive 1"

	if filters.get("from_date"):
		conditions.append("DATE(l.creation) >= %(from_date)s")
		params["from_date"] = filters.get("from_date")

	if filters.get("to_date"):
		conditions.append("DATE(l.creation) <= %(to_date)s")
		params["to_date"] = filters.get("to_date")

	if filters.get("status"):
		conditions.append("l.status = %(status)s")
		params["status"] = filters.get("status")

	if filters.get("pending_ageing"):
		match = re.search(r'\d+', str(filters.get("pending_ageing")))
		if match:
			conditions.append("l.status NOT IN ('won', 'lost')")
			conditions.append("""(
				CASE
					WHEN l.last_remarks_date IS NOT NULL AND l.last_remarks_date != ''
					THEN DATEDIFF(CURDATE(), l.last_remarks_date)
					ELSE DATEDIFF(CURDATE(), DATE(l.creation))
				END
			) >= %(min_pending_days)s""")
			params["min_pending_days"] = int(match.group())

	if filters.get("lead_type"):
		conditions.append("l.lead_type = %(lead_type)s")
		params["lead_type"] = filters.get("lead_type")

	# Apply hierarchy permission scoping for non-admin users
	user = frappe.session.user
	if not is_owner_or_admin(user):
		from hbs_crm.hbs_crm.doctype.hbs_lead_team_hierarchy.hbs_lead_team_hierarchy import get_user_lead_team_permissions
		from hbs_crm.hbs_crm.doctype.hbs_crm_lead.hbs_crm_lead import get_subordinates_from_hierarchy

		team_perms = get_user_lead_team_permissions(user)
		subordinates = get_subordinates_from_hierarchy(user)
		allowed_execs = set(team_perms["executives"]).union(subordinates)

		if not allowed_execs:
			return []

		params["scoped_execs"] = tuple(allowed_execs)
		if group_by == "Executive 2":
			conditions.append("l.executive_2 IN %(scoped_execs)s")
		elif group_by == "Executive 1" or group_by == "Summary":
			conditions.append("l.executive_1 IN %(scoped_execs)s")
		else:
			conditions.append("(l.executive_1 IN %(scoped_execs)s OR l.executive_2 IN %(scoped_execs)s)")

		if team_perms["lead_types"] and not filters.get("lead_type"):
			conditions.append("l.lead_type IN %(scoped_lead_types)s")
			params["scoped_lead_types"] = tuple(team_perms["lead_types"])

	if group_by == "Lead Type":
		if filters.get("executive_1"):
			conditions.append("l.executive_1 = %(executive_1)s")
			params["executive_1"] = filters.get("executive_1")

		if filters.get("executive_2"):
			conditions.append("l.executive_2 = %(executive_2)s")
			params["executive_2"] = filters.get("executive_2")

		where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
		query = f"""
			SELECT
				COALESCE(NULLIF(TRIM(l.lead_type), ''), 'Unassigned') AS lead_type,
				COUNT(l.name) AS total_leads,
				SUM(CASE WHEN l.status NOT IN ('won', 'lost') THEN 1 ELSE 0 END) AS pending_leads,
				SUM(CASE WHEN l.status = 'won' THEN 1 ELSE 0 END) AS won_leads,
				SUM(CASE WHEN l.status = 'lost' THEN 1 ELSE 0 END) AS lost_leads,
				SUM(COALESCE(l.final_total, 0)) AS total_value
			FROM `tabHbs Crm Lead` l
			{where_clause}
			GROUP BY l.lead_type
			ORDER BY total_leads DESC, total_value DESC
		"""
	else:
		if group_by == "Summary":
			join_on = "(l.executive_1 = u.name OR l.executive_2 = u.name)"
			unassigned_where = """(
				(l.executive_1 IS NULL OR TRIM(l.executive_1) = '' OR l.executive_1 = 'Unassigned')
				AND (l.executive_2 IS NULL OR TRIM(l.executive_2) = '' OR l.executive_2 = 'Unassigned')
			)"""
		elif group_by == "Executive 2":
			join_on = "l.executive_2 = u.name"
			unassigned_where = "(l.executive_2 IS NULL OR TRIM(l.executive_2) = '' OR l.executive_2 = 'Unassigned')"
		else:
			join_on = "l.executive_1 = u.name"
			unassigned_where = "(l.executive_1 IS NULL OR TRIM(l.executive_1) = '' OR l.executive_1 = 'Unassigned')"

		lead_conds = list(conditions)
		if group_by == "Executive 1" and filters.get("executive_2"):
			lead_conds.append("l.executive_2 = %(executive_2)s")
			params["executive_2"] = filters.get("executive_2")
		elif group_by == "Executive 2" and filters.get("executive_1"):
			lead_conds.append("l.executive_1 = %(executive_1)s")
			params["executive_1"] = filters.get("executive_1")

		lead_join_str = f"AND {' AND '.join(lead_conds)}" if lead_conds else ""

		if not is_owner_or_admin(user):
			user_conds = ["u.name IN %(scoped_execs)s"]
		else:
			if group_by == "Summary":
				active_cond = """(
					u.name IN (SELECT DISTINCT executive_1 FROM `tabHbs Crm Lead` WHERE executive_1 IS NOT NULL AND executive_1 != '')
					OR u.name IN (SELECT DISTINCT executive_2 FROM `tabHbs Crm Lead` WHERE executive_2 IS NOT NULL AND executive_2 != '')
				)"""
			else:
				exec_col = "executive_2" if group_by == "Executive 2" else "executive_1"
				active_cond = f"u.name IN (SELECT DISTINCT {exec_col} FROM `tabHbs Crm Lead` WHERE {exec_col} IS NOT NULL AND {exec_col} != '')"

			base_user_cond = f"""(
				(u.enabled = 1 AND u.user_type = 'System User' AND u.name != 'Guest')
				OR {active_cond}
			)"""
			user_conds = [base_user_cond]

		filter_exec = None
		if group_by == "Executive 2":
			filter_exec = filters.get("executive_2")
		elif group_by == "Executive 1":
			filter_exec = filters.get("executive_1")
		elif group_by == "Summary":
			filter_exec = filters.get("executive_1") or filters.get("executive_2") or filters.get("executive")

		if filter_exec:
			if filter_exec == "Unassigned":
				user_conds.append("1=0")
			else:
				user_conds.append("u.name = %(filter_exec)s")
				params["filter_exec"] = filter_exec

		user_where_str = f"WHERE {' AND '.join(user_conds)}"

		union_unassigned = ""
		if is_owner_or_admin(user):
			unassigned_conds = list(lead_conds)
			if filter_exec and filter_exec != "Unassigned":
				unassigned_conds.append("1=0")
			unassigned_str = f"AND {' AND '.join(unassigned_conds)}" if unassigned_conds else ""
			union_unassigned = f"""
				UNION ALL

				SELECT
					'Unassigned' AS executive,
					'Unassigned' AS executive_name,
					COUNT(l.name) AS total_leads,
					SUM(CASE WHEN l.name IS NOT NULL AND l.status NOT IN ('won', 'lost') THEN 1 ELSE 0 END) AS pending_leads,
					SUM(CASE WHEN l.name IS NOT NULL AND l.status = 'won' THEN 1 ELSE 0 END) AS won_leads,
					SUM(CASE WHEN l.name IS NOT NULL AND l.status = 'lost' THEN 1 ELSE 0 END) AS lost_leads,
					SUM(CASE WHEN l.name IS NOT NULL THEN COALESCE(l.final_total, 0) ELSE 0 END) AS total_value
				FROM `tabHbs Crm Lead` l
				WHERE {unassigned_where}
				{unassigned_str}
				HAVING total_leads > 0
			"""

		query = f"""
			SELECT
				u.name AS executive,
				COALESCE(NULLIF(TRIM(u.full_name), ''), u.name) AS executive_name,
				COUNT(l.name) AS total_leads,
				SUM(CASE WHEN l.name IS NOT NULL AND l.status NOT IN ('won', 'lost') THEN 1 ELSE 0 END) AS pending_leads,
				SUM(CASE WHEN l.name IS NOT NULL AND l.status = 'won' THEN 1 ELSE 0 END) AS won_leads,
				SUM(CASE WHEN l.name IS NOT NULL AND l.status = 'lost' THEN 1 ELSE 0 END) AS lost_leads,
				SUM(CASE WHEN l.name IS NOT NULL THEN COALESCE(l.final_total, 0) ELSE 0 END) AS total_value
			FROM `tabUser` u
			LEFT JOIN `tabHbs Crm Lead` l ON {join_on} {lead_join_str}
			{user_where_str}
			GROUP BY u.name, u.full_name

			{union_unassigned}

			ORDER BY total_leads DESC, total_value DESC, executive_name ASC
		"""

	data = frappe.db.sql(query, params, as_dict=True)
	for row in data:
		row["total_leads"] = int(row.get("total_leads") or 0)
		row["pending_leads"] = int(row.get("pending_leads") or 0)
		row["won_leads"] = int(row.get("won_leads") or 0)
		row["lost_leads"] = int(row.get("lost_leads") or 0)
		row["total_value"] = float(row.get("total_value") or 0)

		if group_by == "Lead Type":
			val_escaped = frappe.utils.escape_html(str(row.lead_type))
			data_attr = f'data-group-by="Lead Type" data-val="{val_escaped}"'
		elif group_by == "Executive 2":
			val_escaped = frappe.utils.escape_html(str(row.executive))
			data_attr = f'data-group-by="Executive 2" data-exec="{val_escaped}" data-val="{val_escaped}"'
		elif group_by == "Summary":
			val_escaped = frappe.utils.escape_html(str(row.executive))
			data_attr = f'data-group-by="Summary" data-exec="{val_escaped}" data-val="{val_escaped}"'
		else:
			val_escaped = frappe.utils.escape_html(str(row.executive))
			data_attr = f'data-group-by="Executive 1" data-exec="{val_escaped}" data-val="{val_escaped}"'

		row["action"] = (
			f'<button class="btn btn-default btn-xs btn-drilldown-lead" {data_attr} '
			'onclick="frappe.query_reports[\'Lead Executive Summary\'].open_leads(this, event)" '
			'style="border: 1px solid var(--border-color); border-radius: 4px; padding: 2px 10px; '
			'font-size: 11px; font-weight: 500; box-shadow: none; display: inline-flex; align-items: center; gap: 4px; pointer-events: auto;">'
			'<svg class="icon icon-xs" style="width: 11px; height: 11px; pointer-events: none;"><use href="#icon-list"></use></svg>'
			'<span style="pointer-events: none;">View Leads</span>'
			'</button>'
		)
	return data


def get_report_summary(data, filters=None):
	if not data:
		return None

	total_leads = sum(d.get("total_leads") or 0 for d in data)
	pending_leads = sum(d.get("pending_leads") or 0 for d in data)
	won_leads = sum(d.get("won_leads") or 0 for d in data)
	lost_leads = sum(d.get("lost_leads") or 0 for d in data)
	total_value = sum(d.get("total_value") or 0 for d in data)

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
def get_executive_lead_details(
	executive=None,
	from_date=None,
	to_date=None,
	status=None,
	lead_type=None,
	executive_1=None,
	executive_2=None,
	group_by=None,
	group_val=None,
	pending_ageing=None,
):
	user = frappe.session.user
	if not is_owner_or_admin(user):
		from hbs_crm.hbs_crm.doctype.hbs_lead_team_hierarchy.hbs_lead_team_hierarchy import get_user_lead_team_permissions
		from hbs_crm.hbs_crm.doctype.hbs_crm_lead.hbs_crm_lead import get_subordinates_from_hierarchy

		team_perms = get_user_lead_team_permissions(user)
		subordinates = get_subordinates_from_hierarchy(user)
		allowed_execs = set(team_perms["executives"]).union(subordinates)
		if not allowed_execs:
			frappe.throw(_("Not permitted"), frappe.PermissionError)

	conditions = []
	params = {}

	if not is_owner_or_admin(user):
		params["user_allowed_execs"] = tuple(allowed_execs)
		conditions.append("(l.executive_1 IN %(user_allowed_execs)s OR l.executive_2 IN %(user_allowed_execs)s)")

		if team_perms.get("lead_types") and not lead_type:
			params["user_allowed_lead_types"] = tuple(team_perms["lead_types"])
			conditions.append("l.lead_type IN %(user_allowed_lead_types)s")

	target_group = group_by or ("Lead Type" if (not executive and lead_type) else "Executive 1")

	if target_group == "Lead Type":
		target_type = group_val or lead_type
		if not target_type or target_type == "Unassigned":
			conditions.append("(l.lead_type IS NULL OR TRIM(l.lead_type) = '' OR l.lead_type = 'Unassigned')")
		else:
			conditions.append("l.lead_type = %(target_type)s")
			params["target_type"] = target_type

		exec_1 = executive_1 or (executive if executive != target_type else None)
		if exec_1 and exec_1 != "Unassigned":
			conditions.append("l.executive_1 = %(exec_1)s")
			params["exec_1"] = exec_1

		if executive_2 and executive_2 != "Unassigned":
			conditions.append("l.executive_2 = %(executive_2)s")
			params["executive_2"] = executive_2

	elif target_group == "Executive 2":
		target_exec = group_val or executive or executive_2
		if not target_exec or target_exec == "Unassigned":
			conditions.append("(l.executive_2 IS NULL OR TRIM(l.executive_2) = '' OR l.executive_2 = 'Unassigned')")
		else:
			conditions.append("l.executive_2 = %(target_exec)s")
			params["target_exec"] = target_exec

		if executive_1 and executive_1 != "Unassigned":
			conditions.append("l.executive_1 = %(executive_1)s")
			params["executive_1"] = executive_1

	elif target_group == "Summary":
		target_exec = group_val or executive or executive_1 or executive_2
		if not target_exec or target_exec == "Unassigned":
			conditions.append("""(
				(l.executive_1 IS NULL OR TRIM(l.executive_1) = '' OR l.executive_1 = 'Unassigned')
				AND (l.executive_2 IS NULL OR TRIM(l.executive_2) = '' OR l.executive_2 = 'Unassigned')
			)""")
		else:
			conditions.append("(l.executive_1 = %(target_exec)s OR l.executive_2 = %(target_exec)s)")
			params["target_exec"] = target_exec

		if lead_type:
			conditions.append("l.lead_type = %(lead_type)s")
			params["lead_type"] = lead_type

	else:
		target_exec = group_val or executive or executive_1
		if not target_exec or target_exec == "Unassigned":
			conditions.append("(l.executive_1 IS NULL OR TRIM(l.executive_1) = '' OR l.executive_1 = 'Unassigned')")
		else:
			conditions.append("l.executive_1 = %(target_exec)s")
			params["target_exec"] = target_exec

		if executive_2 and executive_2 != "Unassigned":
			conditions.append("l.executive_2 = %(executive_2)s")
			params["executive_2"] = executive_2

		if lead_type:
			conditions.append("l.lead_type = %(lead_type)s")
			params["lead_type"] = lead_type

	if from_date:
		conditions.append("DATE(l.creation) >= %(from_date)s")
		params["from_date"] = from_date

	if to_date:
		conditions.append("DATE(l.creation) <= %(to_date)s")
		params["to_date"] = to_date

	if status:
		conditions.append("l.status = %(status)s")
		params["status"] = status

	if pending_ageing:
		match = re.search(r'\d+', str(pending_ageing))
		if match:
			conditions.append("l.status NOT IN ('won', 'lost')")
			conditions.append("""(
				CASE
					WHEN l.last_remarks_date IS NOT NULL AND l.last_remarks_date != ''
					THEN DATEDIFF(CURDATE(), l.last_remarks_date)
					ELSE DATEDIFF(CURDATE(), DATE(l.creation))
				END
			) >= %(min_pending_days)s""")
			params["min_pending_days"] = int(match.group())

	where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

	query = f"""
		SELECT
			l.name,
			COALESCE(l.company_name, '') AS company_name,
			COALESCE(l.contact_name, '') AS contact_name,
			COALESCE(NULLIF(TRIM(u.full_name), ''), l.executive_1, 'Unassigned') AS executive_name,
			COALESCE(l.executive_1, '') AS executive_1,
			COALESCE(NULLIF(TRIM(u2.full_name), ''), l.executive_2, '') AS executive_2_name,
			COALESCE(l.executive_2, '') AS executive_2,
			COALESCE(l.final_total, 0) AS final_total,
			DATE_FORMAT(l.creation, '%%Y-%%m-%%d') AS creation_date,
			COALESCE(DATE_FORMAT(l.last_remarks_date, '%%Y-%%m-%%d'), '') AS last_remarks_date,
			CASE
				WHEN l.last_remarks_date IS NOT NULL AND l.last_remarks_date != ''
				THEN DATEDIFF(CURDATE(), l.last_remarks_date)
				ELSE DATEDIFF(CURDATE(), DATE(l.creation))
			END AS lead_ageing,
			COALESCE(l.status, '') AS status,
			COALESCE(l.lead_type, '') AS lead_type,
			COALESCE(l.last_remark, '') AS last_remark
		FROM `tabHbs Crm Lead` l
		LEFT JOIN `tabUser` u ON u.name = l.executive_1
		LEFT JOIN `tabUser` u2 ON u2.name = l.executive_2
		{where_clause}
		ORDER BY l.creation DESC
		LIMIT 500
	"""
	return frappe.db.sql(query, params, as_dict=True)
