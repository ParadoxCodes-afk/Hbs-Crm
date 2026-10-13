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
	- Admin / Manager / Owner / Incentive Viewer: Full access to all incentive records.
	- Sales Executive: Strictly scoped to their own records where executive == user.
	"""
	if not user:
		user = frappe.session.user

	if is_owner_or_admin(user) or "Incentive Viewer" in frappe.get_roles(user):
		return ""

	user_escaped = frappe.db.escape(user)
	return f"`tabHbs Incentive Sheet`.`executive` = {user_escaped}"


def has_permission(doc, ptype="read", user=None):
	"""Permission hook for Hbs Incentive Sheet.
	- Admin / Owner: Full access (read, write, create, delete).
	- Incentive Viewer: Strictly READ-ONLY across all records.
	- Sales Executive: Strictly READ-ONLY for their own records.
	"""
	if not user:
		user = frappe.session.user

	if is_owner_or_admin(user):
		return True

	if ptype != "read":
		return False

	if "Incentive Viewer" in frappe.get_roles(user):
		return True

	if not doc:
		return True

	doc_obj = doc if hasattr(doc, "get") else frappe.get_doc("Hbs Incentive Sheet", doc)
	return doc_obj.get("executive") == user


class HbsIncentiveSheet(Document):
	pass

def ensure_incentive_viewer_role_and_profile():
	"""Ensure Role 'Incentive Viewer' and Role Profile 'Incentive Viewer' exist with desk access."""
	try:
		if not frappe.db.exists("Role", "Incentive Viewer"):
			role_doc = frappe.get_doc({
				"doctype": "Role",
				"role_name": "Incentive Viewer",
				"desk_access": 1
			})
			role_doc.insert(ignore_permissions=True)
		else:
			frappe.db.set_value("Role", "Incentive Viewer", "desk_access", 1)

		if not frappe.db.exists("Role Profile", "Incentive Viewer"):
			rp = frappe.get_doc({
				"doctype": "Role Profile",
				"role_profile": "Incentive Viewer",
				"roles": [
					{"role": "Incentive Viewer"},
					{"role": "Desk User"},
					{"role": "All"}
				]
			})
			rp.insert(ignore_permissions=True)
		else:
			rp = frappe.get_doc("Role Profile", "Incentive Viewer")
			existing_roles = {r.role for r in rp.roles}
			for r_name in ("Incentive Viewer", "Desk User", "All"):
				if r_name not in existing_roles:
					rp.append("roles", {"role": r_name})
			rp.save(ignore_permissions=True)

		frappe.db.commit()
	except Exception:
		pass
