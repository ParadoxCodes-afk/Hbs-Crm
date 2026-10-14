# Copyright (c) 2026, Hbs and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt
from hbs_crm.hbs_crm.utils import is_admin_owner_or_manager


def execute(filters=None):
	user = frappe.session.user if frappe.session else "Administrator"
	filters = frappe._dict(filters or {})

	# Strict permission isolation: Sales executives can ONLY see their own records
	if not is_admin_owner_or_manager(user) and "Incentive Viewer" not in frappe.get_roles(user):
		filters.executive = user

	columns = get_columns()
	data = get_data(filters)
	report_summary = get_report_summary(data)
	return columns, data, None, None, report_summary


def get_columns():
	return [
		{
			"fieldname": "executive_name",
			"label": _("Executive Name"),
			"fieldtype": "Data",
			"width": 160,
		},
		{
			"fieldname": "roll_type",
			"label": _("Roll Type"),
			"fieldtype": "Data",
			"width": 140,
		},
		{
			"fieldname": "item_name",
			"label": _("Item Name"),
			"fieldtype": "Data",
			"width": 240,
		},
		{
			"fieldname": "qty",
			"label": _("Qty"),
			"fieldtype": "Float",
			"width": 80,
		},
		{
			"fieldname": "item_value",
			"label": _("Item Value"),
			"fieldtype": "Currency",
			"width": 120,
		},
		{
			"fieldname": "amount",
			"label": _("Amount"),
			"fieldtype": "Currency",
			"width": 120,
		},
		{
			"fieldname": "action",
			"label": _("Action"),
			"fieldtype": "Data",
			"width": 140,
			"sortable": False,
			"filterable": False,
		},
	]


def get_conditions(filters):
	conditions = []
	values = {}

	if filters.get("from_date"):
		conditions.append("voucher_date >= %(from_date)s")
		values["from_date"] = filters.from_date

	if filters.get("to_date"):
		conditions.append("voucher_date <= %(to_date)s")
		values["to_date"] = filters.to_date

	if filters.get("executive"):
		conditions.append("executive = %(executive)s")
		values["executive"] = filters.executive

	if filters.get("company_name"):
		conditions.append("company_name = %(company_name)s")
		values["company_name"] = filters.company_name

	return (" AND " + " AND ".join(conditions)) if conditions else "", values


def get_data(filters):
	cond_str, values = get_conditions(filters)

	query = f"""
		SELECT 
			COALESCE(NULLIF(u.full_name, ''), NULLIF(u.first_name, ''), NULLIF(his.executive_name, ''), his.executive, 'Unknown') AS exec_display_name,
			his.executive,
			COALESCE(NULLIF(his.roll_type, ''), '-') AS roll_type,
			COALESCE(NULLIF(his.item_name, ''), '-') AS item_name,
			SUM(COALESCE(his.qty, 0)) AS total_qty,
			SUM(COALESCE(his.actual_amt, 0)) AS total_item_value,
			SUM(COALESCE(his.incentive, 0)) AS total_amount
		FROM `tabHbs Incentive Sheet` his
		LEFT JOIN `tabUser` u ON u.name = his.executive
		WHERE 1=1 {cond_str}
		GROUP BY his.executive, exec_display_name, his.roll_type, his.item_name
		ORDER BY exec_display_name ASC, roll_type ASC, item_name ASC
	"""
	raw_records = frappe.db.sql(query, values, as_dict=True)

	if not raw_records:
		return []

	# Group by executive
	grouped_by_exec = {}
	for r in raw_records:
		key = (r.exec_display_name or "Unknown", r.executive or "")
		if key not in grouped_by_exec:
			grouped_by_exec[key] = []
		grouped_by_exec[key].append(r)

	data = []
	for (exec_name, exec_user), items in grouped_by_exec.items():
		exec_total_qty = sum(flt(i.total_qty) for i in items)
		exec_total_item_value = sum(flt(i.total_item_value) for i in items)
		exec_total_amount = sum(flt(i.total_amount) for i in items)

		# Level 0: Executive Parent Summary Row (highlighted/bold)
		data_attr = f'data-exec="{frappe.utils.escape_html(exec_user or "")}" data-exec-name="{frappe.utils.escape_html(exec_name or "")}"'
		action_btn = (
			f'<button class="btn btn-default btn-xs btn-drilldown-incentive" {data_attr} '
			'onclick="frappe.query_reports[\'Incentive Summary\'].open_incentives(this, event)" '
			'style="border: 1px solid var(--border-color, #cbd5e1); border-radius: 4px; padding: 2px 10px; '
			'font-size: 11px; font-weight: 500; background: #ffffff; color: #1e293b; box-shadow: none; display: inline-flex; align-items: center; gap: 4px; cursor: pointer; pointer-events: auto;">'
			'<svg class="icon icon-xs" style="width: 11px; height: 11px; pointer-events: none;"><use href="#icon-list"></use></svg>'
			'<span style="pointer-events: none;">View Incentives</span>'
			'</button>'
		)
		data.append({
			"executive_name": exec_name,
			"roll_type": "",
			"item_name": "",
			"qty": exec_total_qty,
			"item_value": exec_total_item_value,
			"amount": exec_total_amount,
			"action": action_btn,
			"indent": 0,
			"is_group": 1,
			"has_value": True,
		})

		# Level 1: Child Roll Type & Item Rows
		for it in items:
			data.append({
				"executive_name": "",
				"roll_type": it.roll_type,
				"item_name": it.item_name,
				"qty": flt(it.total_qty),
				"item_value": flt(it.total_item_value),
				"amount": flt(it.total_amount),
				"action": "",
				"indent": 1,
				"is_group": 0,
			})

	return data


def get_report_summary(data):
	if not data:
		return []

	# Calculate summary across child rows to avoid double-counting parent totals
	child_rows = [r for r in data if r.get("indent") == 1]
	total_qty = sum(flt(r.get("qty", 0)) for r in child_rows)
	total_value = sum(flt(r.get("item_value", 0)) for r in child_rows)
	total_incentive = sum(flt(r.get("amount", 0)) for r in child_rows)

	return [
		{
			"value": total_qty,
			"label": _("Total Qty"),
			"datatype": "Float",
		},
		{
			"value": total_value,
			"label": _("Total Item Value"),
			"datatype": "Currency",
			"currency": "INR",
		},
		{
			"value": total_incentive,
			"label": _("Total Incentive"),
			"datatype": "Currency",
			"currency": "INR",
			"indicator": "Green",
		},
	]


@frappe.whitelist()
def get_executive_incentive_details(
	executive=None,
	from_date=None,
	to_date=None,
	company_name=None,
):
	"""Fetch individual Hbs Incentive Sheet records for drilldown dialog."""
	user = frappe.session.user if frappe.session else "Administrator"

	# Security check: Non-admin/non-Incentive-Viewer can strictly only query their own records
	if not is_admin_owner_or_manager(user) and "Incentive Viewer" not in frappe.get_roles(user):
		executive = user

	conditions = []
	values = {}

	if from_date:
		conditions.append("voucher_date >= %(from_date)s")
		values["from_date"] = from_date
	if to_date:
		conditions.append("voucher_date <= %(to_date)s")
		values["to_date"] = to_date
	if executive:
		conditions.append("executive = %(executive)s")
		values["executive"] = executive
	if company_name:
		conditions.append("company_name = %(company_name)s")
		values["company_name"] = company_name

	where_clause = (" AND " + " AND ".join(conditions)) if conditions else ""

	records = frappe.db.sql(f"""
		SELECT 
			name,
			vch_no,
			voucher_date,
			party_name,
			company_name,
			item_name,
			serial_no,
			roll_type,
			qty,
			actual_amt,
			incentive,
			executive,
			executive_name
		FROM `tabHbs Incentive Sheet`
		WHERE 1=1 {where_clause}
		ORDER BY voucher_date DESC, name DESC
		LIMIT 1000
	""", values, as_dict=True)

	return records
