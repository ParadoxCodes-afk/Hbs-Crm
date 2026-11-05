# Copyright (c) 2026, HBS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, cint, getdate, nowdate, add_months, format_date, get_last_day
import math

def is_admin_or_manager(user=None):
	"""Check if user has full administrative privileges over the dashboard."""
	user = user or frappe.session.user
	if user in ("Administrator", "admin"):
		return True
	roles = frappe.get_roles(user)
	return bool(set(roles) & {"System Manager", "Sales Manager"})


def get_user_hierarchy_subordinates(user=None):
	"""Return list of executive user emails that report to the given supervisor."""
	user = user or frappe.session.user
	# Check Hbs Lead Team Hierarchy
	execs = set()
	team_parents = frappe.db.sql("""
		SELECT DISTINCT parent FROM `tabHbs Team Supervisor`
		WHERE user = %s AND parenttype = 'Hbs Lead Team Hierarchy'
	""", (user,))
	if team_parents:
		p_names = [p[0] for p in team_parents]
		res = frappe.db.sql("""
			SELECT DISTINCT user FROM `tabHbs Team Executive`
			WHERE parent IN %s AND parenttype = 'Hbs Lead Team Hierarchy' AND user IS NOT NULL
		""", [tuple(p_names)])
		for r in res:
			if r[0]:
				execs.add(r[0])
	
	# Also include self
	execs.add(user)
	return list(execs)


@frappe.whitelist()
def get_dashboard_meta():
	"""Fetch dashboard metadata: allowed executives list, session user privileges, and default dates."""
	user = frappe.session.user
	is_admin = is_admin_or_manager(user)

	today = getdate(nowdate())
	first_of_month = today.replace(day=1)
	last_of_month = get_last_day(today)

	# Fetch all active system users who have sales / CRM presence
	all_users_res = frappe.db.sql("""
		SELECT DISTINCT u.name, u.full_name, u.email
		FROM `tabUser` u
		WHERE u.enabled = 1 AND u.user_type = 'System User' AND u.name NOT IN ('Administrator', 'Guest')
		ORDER BY u.full_name ASC
	""", as_dict=True)

	user_lookup = {u["name"]: u for u in all_users_res}
	if user in ("Administrator", "admin") and user not in user_lookup:
		user_lookup[user] = {"name": user, "full_name": "Administrator", "email": user}

	if is_admin:
		# Admin sees Company Total + all active users
		allowed_execs = [
			{"id": "ALL", "name": "Company Total", "email": ""}
		]
		for u in all_users_res:
			allowed_execs.append({
				"id": u["name"],
				"name": u["full_name"] or u["name"],
				"email": u["email"] or u["name"]
			})
	else:
		subordinate_ids = get_user_hierarchy_subordinates(user)
		allowed_execs = []
		if len(subordinate_ids) > 1:
			# Supervisor can see "My Team"
			allowed_execs.append({"id": "ALL", "name": "Team Total", "email": ""})

		for sub_id in subordinate_ids:
			u_info = user_lookup.get(sub_id) or {"name": sub_id, "full_name": sub_id, "email": sub_id}
			allowed_execs.append({
				"id": u_info["name"],
				"name": u_info["full_name"] or u_info["name"],
				"email": u_info["email"] or u_info["name"]
			})

	return {
		"user": user,
		"user_full_name": frappe.utils.get_fullname(user),
		"is_admin": is_admin,
		"default_from_date": str(first_of_month),
		"default_to_date": str(last_of_month),
		"allowed_executives": allowed_execs
	}


def _resolve_scope_conditions(executive, user):
	"""Return allowed executive list and SQL condition snippet."""
	is_admin = is_admin_or_manager(user)
	allowed_subordinates = None
	if not is_admin:
		allowed_subordinates = get_user_hierarchy_subordinates(user)

	if executive in (None, "", "ALL"):
		if is_admin:
			target_execs = None  # None means all records
		else:
			target_execs = allowed_subordinates
	else:
		if is_admin or (allowed_subordinates and executive in allowed_subordinates):
			target_execs = [executive]
		else:
			target_execs = [user]

	return target_execs


def _get_exec_aliases(exec_ids):
	"""Resolve full name, first name, email, and user id for the given executive identifiers."""
	if not exec_ids:
		return []
	aliases = set(exec_ids)
	users = frappe.db.sql("""
		SELECT name, full_name, first_name, username, email
		FROM `tabUser`
		WHERE name IN %s OR email IN %s
	""", (tuple(exec_ids), tuple(exec_ids)), as_dict=True)
	for u in users:
		for k in ("name", "full_name", "first_name", "username", "email"):
			val = u.get(k)
			if val:
				aliases.add(val.strip())
	return list(aliases)


def _get_all_exec_aliases_map():
	"""Preload and map all active users to their respective alias tuples in a single query."""
	users = frappe.db.sql("""
		SELECT name, full_name, first_name, username, email
		FROM `tabUser`
		WHERE enabled = 1 AND user_type = 'System User' AND name NOT IN ('Administrator', 'Guest')
	""", as_dict=True)
	alias_map = {}
	for u in users:
		aliases = set()
		for k in ("name", "full_name", "first_name", "username", "email"):
			val = u.get(k)
			if val:
				aliases.add(val.strip())
		alias_map[u["name"]] = tuple(aliases)
	return alias_map


@frappe.whitelist()
def get_dashboard_data(executive=None, from_date=None, to_date=None):
	"""Aggregate all 4 core business verticals for the specified executive & date window."""
	user = frappe.session.user
	target_execs = _resolve_scope_conditions(executive, user)
	exec_aliases = _get_exec_aliases(target_execs) if target_execs else None

	today = getdate(nowdate())
	from_dt = getdate(from_date) if from_date else today.replace(day=1)
	to_dt = getdate(to_date) if to_date else get_last_day(today)

	# -------------------------------------------------------------
	# 1. LEADS SUMMARY
	# -------------------------------------------------------------
	lead_conds = ["docstatus < 2"]
	lead_params = {"from_date": from_dt, "to_date": to_dt}

	if target_execs:
		lead_conds.append("(executive_1 IN %(aliases)s OR executive_2 IN %(aliases)s OR executive_3 IN %(aliases)s)")
		lead_params["aliases"] = tuple(exec_aliases)

	lead_where = " AND ".join(lead_conds)
	lead_res = frappe.db.sql(f"""
		SELECT
			COUNT(CASE WHEN LOWER(status) IN ('open', 'pending', 'in progress', 'follow up', 'contacted', 'draft', 'new') THEN 1 END) as pending,
			COUNT(CASE WHEN follow_up_date < CURDATE() AND LOWER(status) NOT IN ('won', 'lost', 'cancelled', 'closed') THEN 1 END) as overdue,
			COUNT(CASE WHEN DATE(creation) BETWEEN %(from_date)s AND %(to_date)s THEN 1 END) as generated,
			COUNT(CASE WHEN LOWER(status) = 'won' AND DATE(COALESCE(modified, creation)) BETWEEN %(from_date)s AND %(to_date)s THEN 1 END) as won,
			COUNT(CASE WHEN LOWER(status) = 'lost' AND DATE(COALESCE(modified, creation)) BETWEEN %(from_date)s AND %(to_date)s THEN 1 END) as lost,
			COUNT(CASE WHEN demo_done = 1 THEN 1 END) as completed_visits
		FROM `tabHbs Crm Lead`
		WHERE {lead_where}
	""", lead_params, as_dict=True)
	leads_data = lead_res[0] if lead_res else {
		"pending": 0, "overdue": 0, "generated": 0, "won": 0, "lost": 0, "completed_visits": 0
	}

	# -------------------------------------------------------------
	# 2. TALLY TSS RENEWAL SUMMARY
	# -------------------------------------------------------------
	tss_conds = ["COALESCE(isdeleted, 0) = 0"]
	tss_params = {"from_date": from_dt, "to_date": to_dt}

	if target_execs:
		tss_conds.append("(crm_ex_1 IN %(aliases)s OR crm_executive IN %(aliases)s)")
		tss_params["aliases"] = tuple(exec_aliases)

	tss_where = " AND ".join(tss_conds)
	tss_res = frappe.db.sql(f"""
		SELECT
			COUNT(CASE WHEN COALESCE(LOWER(crm_status), '') IN ('', 'open', 'pending', 'follow up', 'in progress', 'new') AND COALESCE(portal_expiry_date, acc_expiry_date) BETWEEN %(from_date)s AND %(to_date)s THEN 1 END) as pending,
			COUNT(CASE WHEN follow_up_date < CURDATE() AND LOWER(crm_status) NOT IN ('won', 'renewed', 'closed', 'lost', 'sold') THEN 1 END) as overdue,
			COUNT(CASE WHEN LOWER(crm_status) IN ('won', 'renewed', 'closed - won', 'sold') AND (COALESCE(portal_expiry_date, acc_expiry_date) BETWEEN %(from_date)s AND %(to_date)s OR DATE(modified) BETWEEN %(from_date)s AND %(to_date)s) THEN 1 END) as won,
			COUNT(CASE WHEN LOWER(crm_status) IN ('lost', 'not interested', 'closed - lost') AND (COALESCE(portal_expiry_date, acc_expiry_date) BETWEEN %(from_date)s AND %(to_date)s OR DATE(modified) BETWEEN %(from_date)s AND %(to_date)s) THEN 1 END) as lost
		FROM `tabHbs Tally Renewal`
		WHERE {tss_where}
	""", tss_params, as_dict=True)
	tss_data = tss_res[0] if tss_res else {
		"pending": 0, "overdue": 0, "won": 0, "lost": 0
	}

	# -------------------------------------------------------------
	# 3. SALES & INCENTIVE (BILLING) SUMMARY
	# -------------------------------------------------------------
	sales_conds = ["voucher_date BETWEEN %(from_date)s AND %(to_date)s", "docstatus < 2"]
	sales_params = {"from_date": from_dt, "to_date": to_dt}

	if target_execs:
		# tabHbs Incentive Sheet stores executive user or executive full_name
		sales_conds.append("(executive IN %(aliases)s OR executive_name IN %(aliases)s)")
		sales_params["aliases"] = tuple(exec_aliases)

	sales_where = " AND ".join(sales_conds)
	sales_res = frappe.db.sql(f"""
		SELECT
			COALESCE(SUM(CASE WHEN voucher_type != 'Credit Note' THEN amount ELSE 0 END), 0) as total_billing,
			COALESCE(SUM(CASE WHEN voucher_type = 'Credit Note' THEN amount ELSE 0 END), 0) as credit_note,
			COALESCE(SUM(incentive), 0) as total_incentive,
			COUNT(DISTINCT vch_no) as total_transactions
		FROM `tabHbs Incentive Sheet`
		WHERE {sales_where}
	""", sales_params, as_dict=True)
	s_row = sales_res[0] if sales_res else {"total_billing": 0, "credit_note": 0, "total_incentive": 0, "total_transactions": 0}
	total_billing = flt(s_row["total_billing"])
	credit_note = flt(s_row["credit_note"])
	net_sales = total_billing - credit_note
	total_incentive = flt(s_row["total_incentive"])

	sales_data = {
		"total_billing": total_billing,
		"credit_note": credit_note,
		"net_sales": net_sales,
		"total_incentive": total_incentive,
		"total_transactions": s_row["total_transactions"]
	}

	# -------------------------------------------------------------
	# 4. OUTSTANDING SUMMARY
	# -------------------------------------------------------------
	out_conds = ["pending_amt > 0"]
	out_params = {}

	if target_execs:
		out_conds.append("(executive_1 IN %(aliases)s OR executive_2 IN %(aliases)s)")
		out_params["aliases"] = tuple(exec_aliases)

	out_where = " AND ".join(out_conds)
	out_res = frappe.db.sql(f"""
		SELECT
			COALESCE(SUM(pending_amt), 0) as total_outstanding,
			COALESCE(SUM(CASE WHEN DATEDIFF(CURDATE(), COALESCE(due_date, bill_date)) > 15 THEN pending_amt ELSE 0 END), 0) as above_15_days,
			COALESCE(SUM(CASE WHEN DATEDIFF(CURDATE(), COALESCE(due_date, bill_date)) > 30 THEN pending_amt ELSE 0 END), 0) as above_30_days,
			COUNT(DISTINCT party_name) as parties_count,
			COUNT(CASE WHEN overdue_days > 0 OR (last_remarks_date IS NOT NULL AND last_remarks_date < CURDATE()) THEN 1 END) as overdue_fu_count,
			COALESCE(SUM(CASE WHEN overdue_days > 0 THEN pending_amt ELSE 0 END), 0) as overdue_fu_value
		FROM `tabHbs Outstanding`
		WHERE {out_where}
	""", out_params, as_dict=True)
	out_data = out_res[0] if out_res else {
		"total_outstanding": 0, "above_15_days": 0, "above_30_days": 0, "parties_count": 0,
		"overdue_fu_count": 0, "overdue_fu_value": 0
	}

	# -------------------------------------------------------------
	# 5. EXECUTIVE CAROUSEL & BREAKDOWN STATS (Consolidated High-Perf)
	# -------------------------------------------------------------
	is_admin = is_admin_or_manager(user)
	allowed_ids = get_user_hierarchy_subordinates(user) if not is_admin else None

	carousel_execs = []
	exec_breakdown = []
	all_aliases_map = _get_all_exec_aliases_map()

	exec_query_cond = "enabled = 1 AND user_type = 'System User' AND name NOT IN ('Administrator', 'Guest')"
	if allowed_ids:
		exec_query_cond += f" AND name IN ({', '.join(['%s'] * len(allowed_ids))})"
		active_users = frappe.db.sql(f"SELECT name, full_name FROM `tabUser` WHERE {exec_query_cond} ORDER BY full_name", tuple(allowed_ids), as_dict=True)
	else:
		active_users = frappe.db.sql(f"SELECT name, full_name FROM `tabUser` WHERE {exec_query_cond} ORDER BY full_name", as_dict=True)

	for u in active_users:
		u_id = u["name"]
		u_name = u["full_name"] or u_id
		u_aliases = all_aliases_map.get(u_id) or (u_id,)

		# Consolidated Lead Metrics (Single query instead of 4 separate queries)
		l_row = frappe.db.sql("""
			SELECT
				COUNT(CASE WHEN LOWER(status) IN ('open', 'pending', 'in progress', 'follow up', 'contacted', 'new', 'draft') THEN 1 END) as p,
				COUNT(CASE WHEN follow_up_date < CURDATE() AND LOWER(status) NOT IN ('won', 'lost', 'cancelled', 'closed') THEN 1 END) as o,
				COUNT(CASE WHEN DATE(creation) BETWEEN %s AND %s THEN 1 END) as n,
				COUNT(CASE WHEN LOWER(status) = 'won' AND DATE(COALESCE(modified, creation)) BETWEEN %s AND %s THEN 1 END) as won,
				COUNT(CASE WHEN LOWER(status) = 'lost' AND DATE(COALESCE(modified, creation)) BETWEEN %s AND %s THEN 1 END) as lost,
				COUNT(CASE WHEN demo_done = 1 AND DATE(COALESCE(modified, creation)) BETWEEN %s AND %s THEN 1 END) as visits
			FROM `tabHbs Crm Lead`
			WHERE (executive_1 IN %s OR executive_2 IN %s OR executive_3 IN %s) AND docstatus < 2
		""", (from_dt, to_dt, from_dt, to_dt, from_dt, to_dt, from_dt, to_dt, u_aliases, u_aliases, u_aliases), as_dict=True)[0]

		# Consolidated TSS Metrics
		t_row = frappe.db.sql("""
			SELECT
				COUNT(CASE WHEN COALESCE(LOWER(crm_status), '') IN ('', 'open', 'pending', 'follow up', 'new') AND COALESCE(portal_expiry_date, acc_expiry_date) BETWEEN %s AND %s THEN 1 END) as p,
				COUNT(CASE WHEN follow_up_date < CURDATE() AND LOWER(crm_status) NOT IN ('won', 'renewed', 'closed', 'lost', 'sold') THEN 1 END) as o
			FROM `tabHbs Tally Renewal`
			WHERE (crm_ex_1 IN %s OR crm_executive IN %s) AND COALESCE(isdeleted, 0) = 0
		""", (from_dt, to_dt, u_aliases, u_aliases), as_dict=True)[0]

		# Outstanding Value
		out_val = frappe.db.sql("""
			SELECT COALESCE(SUM(pending_amt), 0) as val
			FROM `tabHbs Outstanding`
			WHERE (executive_1 IN %s OR executive_2 IN %s) AND pending_amt > 0
		""", (u_aliases, u_aliases))[0][0]

		# Consolidated Sales & Incentive Metrics (Single query instead of 2 separate queries)
		s_row = frappe.db.sql("""
			SELECT
				COALESCE(SUM(CASE WHEN voucher_type != 'Credit Note' THEN amount ELSE -amount END), 0) as net_sales,
				COALESCE(SUM(incentive), 0) as incentive
			FROM `tabHbs Incentive Sheet`
			WHERE (executive IN %s OR executive_name IN %s) AND voucher_date BETWEEN %s AND %s AND docstatus < 2
		""", (u_aliases, u_aliases, from_dt, to_dt), as_dict=True)[0]

		net_sales_val = flt(s_row["net_sales"])
		out_amt_val = flt(out_val)
		inc_val = flt(s_row["incentive"])

		carousel_execs.append({
			"id": u_id,
			"name": u_name,
			"leads_p": l_row["p"] or 0,
			"leads_o": l_row["o"] or 0,
			"leads_n": l_row["n"] or 0,
			"tss_p": t_row["p"] or 0,
			"tss_o": t_row["o"] or 0,
			"outstanding": out_amt_val,
			"net_sales": net_sales_val
		})

		exec_breakdown.append({
			"executive": u_name,
			"executive_id": u_id,
			"pending": l_row["p"] or 0,
			"overdue": l_row["o"] or 0,
			"generated": l_row["n"] or 0,
			"won": l_row["won"] or 0,
			"lost": l_row["lost"] or 0,
			"visits": l_row["visits"] or 0,
			"net_sales": net_sales_val,
			"outstanding": out_amt_val,
			"incentive": inc_val
		})

	# -------------------------------------------------------------
	# 7. TAB 2: PRODUCT / ITEM GROUP SALES & INCENTIVES
	# -------------------------------------------------------------
	prod_conds = ["voucher_date BETWEEN %(from_date)s AND %(to_date)s", "docstatus < 2"]
	prod_params = {"from_date": from_dt, "to_date": to_dt}
	if target_execs:
		prod_conds.append("(executive IN %(aliases)s OR executive_name IN %(aliases)s)")
		prod_params["aliases"] = tuple(exec_aliases)

	prod_where = " AND ".join(prod_conds)
	prod_sales_raw = frappe.db.sql(f"""
		SELECT
			COALESCE(NULLIF(TRIM(item_name), ''), 'Other Items') as item_group,
			SUM(CASE WHEN voucher_type != 'Credit Note' THEN qty ELSE 0 END) as gross_qty,
			SUM(CASE WHEN voucher_type != 'Credit Note' THEN amount ELSE 0 END) as gross_sales_value,
			COUNT(DISTINCT CASE WHEN voucher_type != 'Credit Note' THEN vch_no END) as gross_txns,
			SUM(CASE WHEN voucher_type = 'Credit Note' THEN amount ELSE 0 END) as credit_note_value,
			COUNT(DISTINCT CASE WHEN voucher_type = 'Credit Note' THEN vch_no END) as credit_txns,
			SUM(CASE WHEN voucher_type != 'Credit Note' THEN amount ELSE -amount END) as net_sales,
			SUM(incentive) as total_incentive
		FROM `tabHbs Incentive Sheet`
		WHERE {prod_where}
		GROUP BY item_group
		ORDER BY gross_sales_value DESC
		LIMIT 50
	""", prod_params, as_dict=True)

	# -------------------------------------------------------------
	# 8. TAB 3: PARTY-WISE OUTSTANDING CASES
	# -------------------------------------------------------------
	party_conds = ["pending_amt > 0"]
	party_params = {}
	if target_execs:
		party_conds.append("(executive_1 IN %(aliases)s OR executive_2 IN %(aliases)s)")
		party_params["aliases"] = tuple(exec_aliases)

	party_where = " AND ".join(party_conds)
	party_out_raw = frappe.db.sql(f"""
		SELECT
			party_name,
			contact_person,
			contact_number,
			status as crm_status,
			due_date,
			last_remarks_date as followup_date,
			SUM(pending_amt) as balance,
			SUM(CASE WHEN DATEDIFF(CURDATE(), COALESCE(due_date, bill_date)) <= 15 THEN pending_amt ELSE 0 END) as current_bucket,
			SUM(CASE WHEN DATEDIFF(CURDATE(), COALESCE(due_date, bill_date)) > 15 AND DATEDIFF(CURDATE(), COALESCE(due_date, bill_date)) <= 30 THEN pending_amt ELSE 0 END) as bucket_15_30,
			SUM(CASE WHEN DATEDIFF(CURDATE(), COALESCE(due_date, bill_date)) > 30 THEN pending_amt ELSE 0 END) as bucket_above_30
		FROM `tabHbs Outstanding`
		WHERE {party_where}
		GROUP BY party_name, contact_person, contact_number, status, due_date, last_remarks_date
		ORDER BY balance DESC
		LIMIT 100
	""", party_params, as_dict=True)

	return {
		"from_date": str(from_dt),
		"to_date": str(to_dt),
		"executive": executive or "ALL",
		"leads": leads_data,
		"tss": tss_data,
		"sales": sales_data,
		"outstanding": out_data,
		"carousel": carousel_execs,
		"breakdown": exec_breakdown,
		"product_sales": prod_sales_raw,
		"party_outstanding": party_out_raw
	}


@frappe.whitelist()
def get_drilldown_records(metric_type, executive=None, from_date=None, to_date=None, page=1, limit=50):
	"""Fetch detailed record rows for in-page modal drill-down preview."""
	user = frappe.session.user
	target_execs = _resolve_scope_conditions(executive, user)
	exec_aliases = _get_exec_aliases(target_execs) if target_execs else None

	today = getdate(nowdate())
	from_dt = getdate(from_date) if from_date else today.replace(day=1)
	to_dt = getdate(to_date) if to_date else get_last_day(today)
	offset = (cint(page) - 1) * cint(limit)

	# Format response
	doctype = ""
	filters_list = {}
	columns = []
	rows = []

	if metric_type == "leads_won":
		doctype = "Hbs Crm Lead"
		conds = ["status = 'Won'", "DATE(COALESCE(modified, creation)) BETWEEN %s AND %s", "docstatus < 2"]
		params = [from_dt, to_dt]
		if target_execs:
			conds.append("(executive_1 IN %s OR executive_2 IN %s OR executive_3 IN %s)")
			params.extend([tuple(exec_aliases), tuple(exec_aliases), tuple(exec_aliases)])
		where = " AND ".join(conds)
		columns = ["ID", "Company Name", "Contact Name", "Mobile", "Quotation Date", "PI Number", "Status"]
		raw = frappe.db.sql(f"""
			SELECT name, company_name, contact_name, contact_phone, quotation_date, pi_number, status
			FROM `tabHbs Crm Lead` WHERE {where} ORDER BY modified DESC LIMIT %s OFFSET %s
		""", tuple(params + [cint(limit), offset]), as_dict=True)
		rows = raw
		filters_list = {"status": "Won"}

	elif metric_type == "leads_pending":
		doctype = "Hbs Crm Lead"
		conds = ["LOWER(status) IN ('open', 'pending', 'in progress', 'follow up', 'contacted', 'draft', 'new')", "docstatus < 2"]
		params = []
		if target_execs:
			conds.append("(executive_1 IN %s OR executive_2 IN %s OR executive_3 IN %s)")
			params.extend([tuple(exec_aliases), tuple(exec_aliases), tuple(exec_aliases)])
		where = " AND ".join(conds)
		columns = ["ID", "Company Name", "Contact Name", "Mobile", "Follow-up Date", "Status"]
		rows = frappe.db.sql(f"""
			SELECT name, company_name, contact_name, contact_phone, follow_up_date, status
			FROM `tabHbs Crm Lead` WHERE {where} ORDER BY modified DESC LIMIT %s OFFSET %s
		""", tuple(params + [cint(limit), offset]), as_dict=True)

	elif metric_type == "leads_overdue":
		doctype = "Hbs Crm Lead"
		conds = ["follow_up_date < CURDATE()", "status NOT IN ('Won', 'Lost', 'Cancelled', 'Closed')", "docstatus < 2"]
		params = []
		if target_execs:
			conds.append("(executive_1 IN %s OR executive_2 IN %s OR executive_3 IN %s)")
			params.extend([tuple(exec_aliases), tuple(exec_aliases), tuple(exec_aliases)])
		where = " AND ".join(conds)
		columns = ["ID", "Company Name", "Contact Name", "Follow-up Date", "Status", "Last Remark"]
		rows = frappe.db.sql(f"""
			SELECT name, company_name, contact_name, follow_up_date, status, last_remark
			FROM `tabHbs Crm Lead` WHERE {where} ORDER BY follow_up_date ASC LIMIT %s OFFSET %s
		""", tuple(params + [cint(limit), offset]), as_dict=True)

	elif metric_type == "leads_generated":
		doctype = "Hbs Crm Lead"
		conds = ["DATE(creation) BETWEEN %s AND %s", "docstatus < 2"]
		params = [from_dt, to_dt]
		if target_execs:
			conds.append("(executive_1 IN %s OR executive_2 IN %s OR executive_3 IN %s)")
			params.extend([tuple(exec_aliases), tuple(exec_aliases), tuple(exec_aliases)])
		where = " AND ".join(conds)
		columns = ["ID", "Company Name", "Contact Name", "Mobile", "Created On", "Status"]
		rows = frappe.db.sql(f"""
			SELECT name, company_name, contact_name, contact_phone, DATE(creation) as created_on, status
			FROM `tabHbs Crm Lead` WHERE {where} ORDER BY creation DESC LIMIT %s OFFSET %s
		""", tuple(params + [cint(limit), offset]), as_dict=True)

	elif metric_type == "leads_lost":
		doctype = "Hbs Crm Lead"
		conds = ["LOWER(status) = 'lost'", "DATE(COALESCE(modified, creation)) BETWEEN %s AND %s", "docstatus < 2"]
		params = [from_dt, to_dt]
		if target_execs:
			conds.append("(executive_1 IN %s OR executive_2 IN %s OR executive_3 IN %s)")
			params.extend([tuple(exec_aliases), tuple(exec_aliases), tuple(exec_aliases)])
		where = " AND ".join(conds)
		columns = ["ID", "Company Name", "Contact Name", "Mobile", "Lost Date", "Last Remark"]
		rows = frappe.db.sql(f"""
			SELECT name, company_name, contact_name, contact_phone, DATE(COALESCE(modified, creation)) as lost_date, last_remark
			FROM `tabHbs Crm Lead` WHERE {where} ORDER BY modified DESC LIMIT %s OFFSET %s
		""", tuple(params + [cint(limit), offset]), as_dict=True)

	elif metric_type == "leads_visits":
		doctype = "Hbs Crm Lead"
		conds = ["demo_done = 1", "docstatus < 2"]
		params = []
		if target_execs:
			conds.append("(executive_1 IN %s OR executive_2 IN %s OR executive_3 IN %s)")
			params.extend([tuple(exec_aliases), tuple(exec_aliases), tuple(exec_aliases)])
		where = " AND ".join(conds)
		columns = ["ID", "Company Name", "Contact Name", "Mobile", "Follow-up Date", "Status"]
		rows = frappe.db.sql(f"""
			SELECT name, company_name, contact_name, contact_phone, follow_up_date, status
			FROM `tabHbs Crm Lead` WHERE {where} ORDER BY modified DESC LIMIT %s OFFSET %s
		""", tuple(params + [cint(limit), offset]), as_dict=True)

	elif metric_type == "tss_pending":
		doctype = "Hbs Tally Renewal"
		conds = [
			"COALESCE(LOWER(crm_status), '') IN ('', 'open', 'pending', 'follow up', 'in progress', 'new')",
			"COALESCE(portal_expiry_date, acc_expiry_date) BETWEEN %s AND %s",
			"COALESCE(isdeleted, 0) = 0"
		]
		params = [from_dt, to_dt]
		if target_execs:
			conds.append("(crm_ex_1 IN %s OR crm_executive IN %s)")
			params.extend([tuple(exec_aliases), tuple(exec_aliases)])
		where = " AND ".join(conds)
		columns = ["ID", "Party Name", "Serial No", "Expiry Date", "Follow-up Date", "Status"]
		rows = frappe.db.sql(f"""
			SELECT name, cc_acc_name as party_name, tss_tally_serial as serial_no, COALESCE(portal_expiry_date, acc_expiry_date) as portal_expiry_date, follow_up_date, crm_status as status
			FROM `tabHbs Tally Renewal` WHERE {where} ORDER BY COALESCE(portal_expiry_date, acc_expiry_date) ASC LIMIT %s OFFSET %s
		""", tuple(params + [cint(limit), offset]), as_dict=True)

	elif metric_type == "tss_overdue":
		doctype = "Hbs Tally Renewal"
		conds = ["follow_up_date < CURDATE()", "crm_status NOT IN ('Won', 'Renewed', 'Closed', 'Lost', 'Sold')", "COALESCE(isdeleted, 0) = 0"]
		params = []
		if target_execs:
			conds.append("(crm_ex_1 IN %s OR crm_executive IN %s)")
			params.extend([tuple(exec_aliases), tuple(exec_aliases)])
		where = " AND ".join(conds)
		columns = ["ID", "Party Name", "Serial No", "Expiry Date", "Follow-up Date", "Status"]
		rows = frappe.db.sql(f"""
			SELECT name, cc_acc_name as party_name, tss_tally_serial as serial_no, COALESCE(portal_expiry_date, acc_expiry_date) as portal_expiry_date, follow_up_date, crm_status as status
			FROM `tabHbs Tally Renewal` WHERE {where} ORDER BY follow_up_date ASC LIMIT %s OFFSET %s
		""", tuple(params + [cint(limit), offset]), as_dict=True)

	elif metric_type == "tss_won":
		doctype = "Hbs Tally Renewal"
		conds = [
			"LOWER(crm_status) IN ('won', 'renewed', 'closed - won', 'sold')",
			"(COALESCE(portal_expiry_date, acc_expiry_date) BETWEEN %s AND %s OR DATE(modified) BETWEEN %s AND %s)",
			"COALESCE(isdeleted, 0) = 0"
		]
		params = [from_dt, to_dt, from_dt, to_dt]
		if target_execs:
			conds.append("(crm_ex_1 IN %s OR crm_executive IN %s)")
			params.extend([tuple(exec_aliases), tuple(exec_aliases)])
		where = " AND ".join(conds)
		columns = ["ID", "Party Name", "Serial No", "Expiry Date", "Follow-up Date", "Status"]
		rows = frappe.db.sql(f"""
			SELECT name, cc_acc_name as party_name, tss_tally_serial as serial_no, COALESCE(portal_expiry_date, acc_expiry_date) as portal_expiry_date, follow_up_date, crm_status as status
			FROM `tabHbs Tally Renewal` WHERE {where} ORDER BY modified DESC LIMIT %s OFFSET %s
		""", tuple(params + [cint(limit), offset]), as_dict=True)

	elif metric_type == "tss_lost":
		doctype = "Hbs Tally Renewal"
		conds = [
			"LOWER(crm_status) IN ('lost', 'not interested', 'closed - lost')",
			"(COALESCE(portal_expiry_date, acc_expiry_date) BETWEEN %s AND %s OR DATE(modified) BETWEEN %s AND %s)",
			"COALESCE(isdeleted, 0) = 0"
		]
		params = [from_dt, to_dt, from_dt, to_dt]
		if target_execs:
			conds.append("(crm_ex_1 IN %s OR crm_executive IN %s)")
			params.extend([tuple(exec_aliases), tuple(exec_aliases)])
		where = " AND ".join(conds)
		columns = ["ID", "Party Name", "Serial No", "Expiry Date", "Follow-up Date", "Status"]
		rows = frappe.db.sql(f"""
			SELECT name, cc_acc_name as party_name, tss_tally_serial as serial_no, COALESCE(portal_expiry_date, acc_expiry_date) as portal_expiry_date, follow_up_date, crm_status as status
			FROM `tabHbs Tally Renewal` WHERE {where} ORDER BY modified DESC LIMIT %s OFFSET %s
		""", tuple(params + [cint(limit), offset]), as_dict=True)

	elif metric_type in ("outstanding_15", "outstanding_30", "outstanding_all"):
		doctype = "Hbs Outstanding"
		conds = ["pending_amt > 0"]
		params = []
		if metric_type == "outstanding_30":
			conds.append("DATEDIFF(CURDATE(), COALESCE(due_date, bill_date)) > 30")
		elif metric_type == "outstanding_15":
			conds.append("DATEDIFF(CURDATE(), COALESCE(due_date, bill_date)) > 15")
		if target_execs:
			conds.append("(executive_1 IN %s OR executive_2 IN %s)")
			params.extend([tuple(exec_aliases), tuple(exec_aliases)])
		where = " AND ".join(conds)
		columns = ["Bill No", "Party Name", "Bill Date", "Due Date", "Pending Amt", "Overdue Days", "Status"]
		rows = frappe.db.sql(f"""
			SELECT bill_no, party_name, bill_date, due_date, pending_amt, overdue_days, status
			FROM `tabHbs Outstanding` WHERE {where} ORDER BY pending_amt DESC LIMIT %s OFFSET %s
		""", tuple(params + [cint(limit), offset]), as_dict=True)

	elif metric_type == "outstanding_parties":
		doctype = "Hbs Outstanding"
		conds = ["pending_amt > 0"]
		params = []
		if target_execs:
			conds.append("(executive_1 IN %s OR executive_2 IN %s)")
			params.extend([tuple(exec_aliases), tuple(exec_aliases)])
		where = " AND ".join(conds)
		columns = ["Party Name", "Contact Person", "Contact Number", "Total Balance", "Status"]
		rows = frappe.db.sql(f"""
			SELECT party_name, contact_person, contact_number, SUM(pending_amt) as total_balance, status
			FROM `tabHbs Outstanding` WHERE {where} GROUP BY party_name, contact_person, contact_number, status
			ORDER BY total_balance DESC LIMIT %s OFFSET %s
		""", tuple(params + [cint(limit), offset]), as_dict=True)

	elif metric_type in ("sales_all", "sales_credit"):
		doctype = "Hbs Incentive Sheet"
		conds = ["voucher_date BETWEEN %s AND %s", "docstatus < 2"]
		params = [from_dt, to_dt]
		if metric_type == "sales_credit":
			conds.append("voucher_type = 'Credit Note'")
		if target_execs:
			conds.append("(executive IN %s OR executive_name IN %s)")
			params.extend([tuple(exec_aliases), tuple(exec_aliases)])
		where = " AND ".join(conds)
		columns = ["ID", "Voucher Date", "Vch No", "Party Name", "Item Name", "Amount", "Executive", "Incentive"]
		rows = frappe.db.sql(f"""
			SELECT name, voucher_date, vch_no, party_name, item_name, amount, executive_name, incentive
			FROM `tabHbs Incentive Sheet` WHERE {where} ORDER BY voucher_date DESC LIMIT %s OFFSET %s
		""", tuple(params + [cint(limit), offset]), as_dict=True)

	return {
		"doctype": doctype,
		"columns": columns,
		"rows": rows,
		"filters": filters_list,
		"metric_type": metric_type
	}
