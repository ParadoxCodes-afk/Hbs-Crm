# Copyright (c) 2026, Hbs and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class HbsUserHierarchy(Document):
	def validate(self):
		if self.user and self.reports_to and self.user == self.reports_to:
			frappe.throw(_("User cannot report to themselves."), title=_("Invalid Hierarchy"))
