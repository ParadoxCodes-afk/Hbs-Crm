# Copyright (c) 2026, Hbs and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


class HbsCRMSettings(Document):
	def on_update(self):
		self.sync_outstanding_statuses()

	def sync_outstanding_statuses(self):
		options = [""]
		if hasattr(self, "outstanding_statuses") and self.outstanding_statuses:
			for row in self.outstanding_statuses:
				s = (row.status_name or "").strip()
				if s and s not in options:
					options.append(s)

		if "Payment Received" not in options:
			options.append("Payment Received")

		opts_str = "\n".join(options)
		make_property_setter(
			"Hbs Outstanding",
			"payment_status",
			"options",
			opts_str,
			"Text",
			for_doctype=False,
			validate_fields_for_doctype=False,
			is_system_generated=True,
		)
		frappe.clear_cache(doctype="Hbs Outstanding")
