# Copyright (c) 2026, Hbs and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt
from hbs_crm.hbs_crm.utils import is_admin_owner_or_manager


def execute(filters=None):
	user = frappe.session.user if frappe.session else "Administrator"
	filters = frappe._dict(filters or {})

	# Strict permission isolation: Non-admin/non-manager/non-Incentive-Viewer can strictly only view own sales
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
			"width": 220,
		},
		{
			"fieldname": "item_name",
			"label": _("Item Name"),
			"fieldtype": "Data",
			"width": 260,
		},
		{
			"fieldname": "qty",
			"label": _("Total Qty"),
			"fieldtype": "Float",
			"width": 100,
		},
		{
			"fieldname": "avg_rate",
			"label": _("Avg Rate"),
			"fieldtype": "Currency",
			"width": 140,
		},
		{
			"fieldname": "amount",
			"label": _("Total Amount"),
			"fieldtype": "Currency",
			"width": 150,
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

	if filters.get("item_name"):
		conditions.append("item_name LIKE %(item_name)s")
		val = filters.item_name.strip()
		values["item_name"] = val if "%" in val else f"%{val}%"

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
			COALESCE(NULLIF(his.item_name, ''), 'Unknown Item') AS item_name,
			SUM(COALESCE(his.qty, 0)) AS total_qty,
			SUM(COALESCE(his.amount, his.actual_amt, 0)) AS total_amount
		FROM `tabHbs Incentive Sheet` his
		LEFT JOIN `tabUser` u ON u.name = his.executive
		WHERE 1=1 {cond_str}
		GROUP BY his.executive, exec_display_name, his.item_name
		ORDER BY exec_display_name ASC, total_amount DESC, item_name ASC
	"""
	raw_records = frappe.db.sql(query, values, as_dict=True)

	if not raw_records:
		return []

	# Group items under their executive
	grouped_by_exec = {}
	for r in raw_records:
		key = (r.exec_display_name or "Unknown", r.executive or "")
		if key not in grouped_by_exec:
			grouped_by_exec[key] = []
		grouped_by_exec[key].append(r)

	data = []
	for (exec_name, exec_user), items in grouped_by_exec.items():
		exec_total_qty = sum(flt(i.total_qty) for i in items)
		exec_total_amount = sum(flt(i.total_amount) for i in items)
		exec_avg_rate = (exec_total_amount / exec_total_qty) if exec_total_qty else 0

		# Level 0: Executive Parent Summary Row (highlighted/bold)
		data.append({
			"executive_name": exec_name,
			"item_name": "",
			"qty": exec_total_qty,
			"avg_rate": exec_avg_rate,
			"amount": exec_total_amount,
			"indent": 0,
			"is_group": 1,
			"has_value": True,
		})

		# Level 1: Child Item Breakdown Rows
		for it in items:
			qty = flt(it.total_qty)
			amount = flt(it.total_amount)
			avg_rate = (amount / qty) if qty else 0

			data.append({
				"executive_name": "",
				"item_name": it.item_name,
				"qty": qty,
				"avg_rate": avg_rate,
				"amount": amount,
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
	total_amount = sum(flt(r.get("amount", 0)) for r in child_rows)
	distinct_items = len(set(r.get("item_name") for r in child_rows if r.get("item_name")))

	return [
		{
			"value": total_qty,
			"label": _("Total Qty Sold"),
			"datatype": "Float",
		},
		{
			"value": total_amount,
			"label": _("Total Sales Value"),
			"datatype": "Currency",
			"currency": "INR",
			"indicator": "Green",
		},
		{
			"value": distinct_items,
			"label": _("Distinct Items Sold"),
			"datatype": "Int",
			"indicator": "Blue",
		},
	]
