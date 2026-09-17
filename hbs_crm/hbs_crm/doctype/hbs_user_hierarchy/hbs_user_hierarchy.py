# Copyright (c) 2026, Hbs and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class HbsUserHierarchy(Document):
	def validate(self):
		if self.user and self.reports_to and self.user == self.reports_to:
			frappe.throw(_("User cannot report to themselves."), title=_("Invalid Hierarchy"))

		# Prevent circular reporting cycles
		curr = self.reports_to
		visited = {self.user}
		while curr:
			if curr in visited:
				frappe.throw(
					_("Circular reporting detected: {0} cannot report to {1}.").format(self.user, self.reports_to),
					title=_("Invalid Hierarchy")
				)
			visited.add(curr)
			curr = frappe.db.get_value("Hbs User Hierarchy", {"user": curr}, "reports_to")


def has_permission(doc=None, ptype="read", user=None):
	"""Only Administrator, System Manager, or Hierarchy Owner can access Hbs User Hierarchy."""
	if not user:
		user = frappe.session.user
	if user in ("Administrator", "System"):
		return True
	if "System Manager" in frappe.get_roles(user):
		return True
	role_type = frappe.db.get_value("Hbs User Hierarchy", {"user": user}, "role_type")
	return role_type == "Owner"
