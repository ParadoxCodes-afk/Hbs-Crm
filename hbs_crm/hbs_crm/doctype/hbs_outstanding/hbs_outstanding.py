# Copyright (c) 2026, Hbs and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from hbs_crm.hbs_crm.utils import is_owner_or_admin


class HbsOutstanding(Document):
	def validate(self):
		# Auto-derive status from pending_amt
		bill_val = frappe.utils.flt(self.bill_amt)
		pending_val = frappe.utils.flt(self.pending_amt)
		if pending_val == 0:
			self.status = "Cleared"
		elif bill_val and abs(pending_val) < abs(bill_val):
			self.status = "Partially Paid"
		else:
			self.status = "Pending"

		# Auto-calculate overdue days if due_date is provided and overdue_days is missing
		if self.due_date and self.overdue_days is None:
			diff = frappe.utils.date_diff(frappe.utils.nowdate(), self.due_date)
			self.overdue_days = max(0, diff)


def get_permission_query_conditions(user=None):
	"""Permission hook for Hbs Outstanding.
	- Admin / Owner: Full visibility to all records.
	- Sales Executive: Strictly scoped to records where executive_1 or executive_2 matches user.
	"""
	if not user:
		user = frappe.session.user

	if is_owner_or_admin(user):
		return ""

	user_escaped = frappe.db.escape(user)
	return f"(`tabHbs Outstanding`.`executive_1` = {user_escaped} OR `tabHbs Outstanding`.`executive_2` = {user_escaped})"


def has_permission(doc, ptype="read", user=None):
	"""Permission hook for Hbs Outstanding.
	- Admin / Owner: Full access (read, write, create, delete).
	- Sales Executive: Strictly READ-ONLY. No alteration, creation, or deletion.
	  Can only read if assigned to executive_1 or executive_2.
	"""
	if not user:
		user = frappe.session.user

	if is_owner_or_admin(user):
		return True

	# Non-admin users are strictly blocked from alteration, creation, deletion
	if ptype != "read":
		return False

	if not doc:
		return True

	doc_obj = doc if hasattr(doc, "get") else frappe.get_doc("Hbs Outstanding", doc)
	return user in (doc_obj.get("executive_1"), doc_obj.get("executive_2"))
