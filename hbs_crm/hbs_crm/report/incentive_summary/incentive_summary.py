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
			COALESCE(NULLIF(executive_name, ''), executive, 'Unknown') AS exec_display_name,
			executive,
			COALESCE(NULLIF(roll_type, ''), '-') AS roll_type,
			COALESCE(NULLIF(item_name, ''), '-') AS item_name,
			SUM(COALESCE(qty, 0)) AS total_qty,
			SUM(COALESCE(actual_amt, 0)) AS total_item_value,
			SUM(COALESCE(incentive, 0)) AS total_amount
		FROM `tabHbs Incentive Sheet`
		WHERE 1=1 {cond_str}
		GROUP BY executive, executive_name, roll_type, item_name
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
		data.append({
			"executive_name": exec_name,
			"roll_type": "",
			"item_name": "",
			"qty": exec_total_qty,
			"item_value": exec_total_item_value,
			"amount": exec_total_amount,
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
