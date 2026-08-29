# Copyright (c) 2026, Hbs and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class HbsCustomer(Document):
	def on_trash(self):
		"""Clear customer link from Hbs Crm Lead before deleting Hbs Customer."""
		frappe.db.sql(
			"UPDATE `tabHbs Crm Lead` SET `customer` = NULL WHERE `customer` = %s",
			self.name
		)
