# Copyright (c) 2026, Hbs and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from hbs_crm.hbs_crm.doctype.hbs_crm_lead.hbs_crm_lead import is_owner_or_admin


class HbsLeadTeamHierarchy(Document):
	def validate(self):
		if not self.lead_types:
			frappe.throw(_("Please select at least one Lead Type."), title=_("Missing Information"))
		if not self.executives:
			frappe.throw(_("Please select at least one Executive in the team."), title=_("Missing Information"))
		if not self.supervisors:
			frappe.throw(_("Please select at least one Reports To / Manager."), title=_("Missing Information"))


def has_permission(doc=None, ptype="read", user=None):
	"""Admins, System Managers, and Owners have full access. Configured supervisors can read."""
	if not user:
		user = frappe.session.user
	if is_owner_or_admin(user):
		return True
	if ptype == "read" and doc:
		doc_obj = doc if hasattr(doc, "get") else frappe.get_doc("Hbs Lead Team Hierarchy", doc)
		sup_users = [row.get("user") for row in (doc_obj.get("supervisors") or [])]
		return user in sup_users
	return False


def get_user_lead_team_permissions(user=None):
	"""
	Resolve all supervised executives, lead types, and edit capabilities for a user.
	Returns:
	{
		"is_owner_admin": bool,
		"executives": set of executive user IDs,
		"lead_types": set of lead types,
		"manager_for_execs": set of execs where user is Manager (can edit),
		"readonly_for_execs": set of execs where user is Supervisor (read-only)
	}
	"""
	if not user:
		user = frappe.session.user

	if is_owner_or_admin(user):
		return {
			"is_owner_admin": True,
			"executives": set(),
			"lead_types": set(),
			"manager_for_execs": set(),
			"readonly_for_execs": set()
		}

	# Check enabled team hierarchies where user is supervisor
	teams = frappe.db.sql("""
		SELECT DISTINCT parent
		FROM `tabHbs Team Supervisor`
		WHERE user = %s AND parenttype = 'Hbs Lead Team Hierarchy'
	""", (user,), as_dict=True)

	team_names = [t.parent for t in teams if t.parent]

	executives = set()
	lead_types = set()
	manager_for_execs = set()
	readonly_for_execs = set()

	for t_name in team_names:
		t_doc = frappe.get_doc("Hbs Lead Team Hierarchy", t_name)
		if not t_doc.enabled:
			continue

		# Determine user's role in this team
		user_role = "Supervisor (Read-Only)"
		for s in t_doc.supervisors:
			if s.user == user:
				user_role = s.role_type
				break

		t_leads = [lt.lead_type for lt in t_doc.lead_types if lt.lead_type]
		lead_types.update(t_leads)

		t_execs = [e.user for e in t_doc.executives if e.user]
		executives.update(t_execs)

		if user_role == "Manager":
			manager_for_execs.update(t_execs)
		else:
			readonly_for_execs.update(t_execs)

	# Manager overrides readonly if user is supervisor in multiple teams for same exec
	readonly_for_execs = readonly_for_execs - manager_for_execs

	return {
		"is_owner_admin": False,
		"executives": executives,
		"lead_types": lead_types,
		"manager_for_execs": manager_for_execs,
		"readonly_for_execs": readonly_for_execs
	}


@frappe.whitelist()
def get_assigned_executives_query(doctype, txt, searchfield, start, page_len, filters):
	user = frappe.session.user
	if is_owner_or_admin(user):
		return frappe.db.sql("""
			SELECT name, full_name
			FROM `tabUser`
			WHERE enabled = 1 AND user_type = 'System User' AND name != 'Guest'
				AND (`name` LIKE %(txt)s OR `full_name` LIKE %(txt)s)
			ORDER BY full_name ASC
			LIMIT %(start)s, %(page_len)s
		""", {"txt": f"%{txt}%", "start": int(start or 0), "page_len": int(page_len or 20)})

	perms = get_user_lead_team_permissions(user)
	from hbs_crm.hbs_crm.doctype.hbs_crm_lead.hbs_crm_lead import get_subordinates_from_hierarchy
	subordinates = get_subordinates_from_hierarchy(user)
	allowed = list(perms["executives"].union(subordinates))
	if not allowed:
		return []

	return frappe.db.sql("""
		SELECT name, full_name
		FROM `tabUser`
		WHERE name IN %(allowed)s
			AND (`name` LIKE %(txt)s OR `full_name` LIKE %(txt)s)
		ORDER BY full_name ASC
		LIMIT %(start)s, %(page_len)s
	""", {"allowed": tuple(allowed), "txt": f"%{txt}%", "start": int(start or 0), "page_len": int(page_len or 20)})


@frappe.whitelist()
def get_assigned_lead_types_query(doctype, txt, searchfield, start, page_len, filters):
	user = frappe.session.user
	if is_owner_or_admin(user):
		return frappe.db.sql("""
			SELECT name FROM `tabhbs product type`
			WHERE `name` LIKE %(txt)s
			ORDER BY name ASC
			LIMIT %(start)s, %(page_len)s
		""", {"txt": f"%{txt}%", "start": int(start or 0), "page_len": int(page_len or 20)})

	perms = get_user_lead_team_permissions(user)
	if not perms["lead_types"]:
		return frappe.db.sql("""
			SELECT name FROM `tabhbs product type`
			WHERE `name` LIKE %(txt)s
			ORDER BY name ASC
			LIMIT %(start)s, %(page_len)s
		""", {"txt": f"%{txt}%", "start": int(start or 0), "page_len": int(page_len or 20)})

	return frappe.db.sql("""
		SELECT name FROM `tabhbs product type`
		WHERE name IN %(lead_types)s
			AND `name` LIKE %(txt)s
		ORDER BY name ASC
		LIMIT %(start)s, %(page_len)s
	""", {"lead_types": tuple(perms["lead_types"]), "txt": f"%{txt}%", "start": int(start or 0), "page_len": int(page_len or 20)})

