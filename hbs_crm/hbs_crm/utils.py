# Copyright (c) 2026, Hbs and contributors
# For license information, please see license.txt

import frappe


def has_app_permission():
	"""Check if current user has permission to access HBS CRM App Switcher card."""
	return True


# ---------------------------------------------------------------------------
# Shared helpers — single source of truth used by hbs_crm_lead and
# hbs_tally_renewal (and the lead executive summary report).
# ---------------------------------------------------------------------------

def is_owner_or_admin(user=None):
	"""True if user is Administrator/System, has System Manager role, or is Owner in Hbs User Hierarchy."""
	if not user:
		user = frappe.session.user if frappe.session else "Administrator"
	if user in ("Administrator", "System"):
		return True
	if "System Manager" in frappe.get_roles(user):
		return True
	role_type = frappe.db.get_value("Hbs User Hierarchy", {"user": user}, "role_type")
	return role_type == "Owner"


def is_admin_owner_or_manager(user=None):
	"""True if user is Admin, Owner, Manager in hierarchy, or the default lead owner in CRM Settings."""
	user = user or (frappe.session.user if frappe.session else "Administrator")
	if not user or user in ("Administrator", "System"):
		return True
	user_roles = frappe.get_roles(user) if hasattr(frappe, "get_roles") else []
	admin_roles = ["System Manager", "Administrator", "HBS Admin", "hbs admin", "Owner", "owner", "Hbs Owner"]
	if any(r in user_roles for r in admin_roles):
		return True
	role_type = frappe.db.get_value("Hbs User Hierarchy", {"user": user}, "role_type")
	if role_type in ("Owner", "Manager"):
		return True
	default_owner = frappe.db.get_single_value("Hbs CRM Settings", "default_lead_owner")
	if default_owner and default_owner == user:
		return True
	return False


def get_subordinates_from_hierarchy(user, visited=None, is_root=True):
	"""Recursively get all users reporting directly or indirectly to user in Hbs User Hierarchy (request-cached)."""
	if not hasattr(frappe.local, "subordinates_cache"):
		frappe.local.subordinates_cache = {}

	if is_root and user in frappe.local.subordinates_cache:
		return frappe.local.subordinates_cache[user]

	if visited is None:
		visited = set()
	if user in visited:
		return []
	visited.add(user)

	subordinates = []
	direct_reports = frappe.get_all("Hbs User Hierarchy", filters={"reports_to": user}, pluck="user")
	for report in direct_reports:
		if report not in subordinates:
			subordinates.append(report)
			subordinates.extend(get_subordinates_from_hierarchy(report, visited, is_root=False))

	result = list(set(subordinates))
	if is_root:
		frappe.local.subordinates_cache[user] = result
	return result


def get_logged_in_user_context(user=None):
	"""Build the executive dict used by email templates. Includes designation (used by renewal emails)."""
	user_name = user or (frappe.session.user if frappe.session else "Administrator")
	user_doc = (
		frappe.get_doc("User", user_name)
		if user_name and user_name != "Guest" and frappe.db.exists("User", user_name)
		else None
	)
	full_name = (user_doc.get("full_name") or user_doc.get("first_name") or "Executive") if user_doc else "Executive"
	mobile_no = (user_doc.get("mobile_no") or user_doc.get("phone") or user_doc.get("phone_number") or "") if user_doc else ""
	email = (user_doc.get("email") or "") if user_doc else ""
	designation = (user_doc.get("designation") or "") if user_doc else ""
	return {
		"full_name": full_name,
		"email": email,
		"mobile_no": mobile_no,
		"phone": mobile_no,
		"phone_number": mobile_no,
		"designation": designation,
	}