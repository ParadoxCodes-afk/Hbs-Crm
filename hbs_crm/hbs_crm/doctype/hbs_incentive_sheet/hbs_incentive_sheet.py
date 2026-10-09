# Copyright (c) 2026, Hbs and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


def is_owner_or_admin(user=None):
	if not user:
		user = frappe.session.user
	if user == "Administrator":
		return True
	roles = frappe.get_roles(user)
	return any(r in roles for r in ("Administrator", "System Manager", "CRM Manager", "HBS Admin", "hbs admin", "Owner", "owner", "Hbs Owner"))


def get_permission_query_conditions(user=None):
	"""Permission hook for Hbs Incentive Sheet.
	- Admin / Manager / Owner: Full access to all incentive records.
	- Sales Executive: Strictly scoped to their own records where executive == user.
	"""
	if not user:
		user = frappe.session.user

	if is_owner_or_admin(user):
		return ""

	user_escaped = frappe.db.escape(user)
	return f"`tabHbs Incentive Sheet`.`executive` = {user_escaped}"


def has_permission(doc, ptype="read", user=None):
	"""Permission hook for Hbs Incentive Sheet.
	- Admin / Owner: Full access (read, write, create, delete).
	- Sales Executive: Strictly READ-ONLY for their own records.
	"""
	if not user:
		user = frappe.session.user

	if is_owner_or_admin(user):
		return True

	if ptype != "read":
		return False

	if not doc:
		return True

	doc_obj = doc if hasattr(doc, "get") else frappe.get_doc("Hbs Incentive Sheet", doc)
	return doc_obj.get("executive") == user


class HbsIncentiveSheet(Document):
	pass
