import frappe
from frappe import _
from frappe.model.document import Document


class HbsCustomer(Document):
	def validate(self):
		self.check_duplicate()

	def check_duplicate(self):
		c_name = str(self.company_name or "").strip()
		c_gst = str(self.company_gst or "").strip()

		# 1. Check by Company Name (company_name must be strictly unique)
		if c_name:
			existing_name = frappe.db.get_value(
				"Hbs Customer",
				{"company_name": c_name, "name": ["!=", self.name or ""]},
			)
			if existing_name:
				msg = _(
					'<div style="border: 2px solid #ef4444; background-color: #fef2f2; padding: 15px; border-radius: 6px; font-family: sans-serif; text-align: left;">'
					'  <h4 style="color: #b91c1c; margin-top: 0; font-weight: bold; font-size: 16px; display: flex; align-items: center; gap: 8px;">'
					'    🚨 Duplicate Company Name Blocked!'
					'  </h4>'
					'  <hr style="border-top: 1px solid #fecaca; margin: 10px 0;">'
					'  <p style="margin: 0; font-size: 14px; line-height: 1.5; color: #1f2937;">'
					'    A customer with Company Name <b>{0}</b> already exists in the system.'
					'  </p>'
					'  <p style="margin: 8px 0 0 0; font-size: 14px; line-height: 1.5; color: #1f2937;">'
					'    Existing Customer ID: <b>{1}</b>.'
					'  </p>'
					'  <p style="margin: 12px 0 0 0; font-size: 13px; font-style: italic; color: #b91c1c; font-weight: bold;">'
					'    You cannot create a duplicate company record.'
					'  </p>'
					'</div>'
				).format(c_name, existing_name)
				frappe.throw(msg, title=_("Duplicate Company Name"))

		# 2. Check by Company GST (GST must be unique if provided)
		if c_gst:
			existing_gst = frappe.db.get_value(
				"Hbs Customer",
				{"company_gst": c_gst, "name": ["!=", self.name or ""]},
			)
			if existing_gst:
				msg = _(
					'<div style="border: 2px solid #ef4444; background-color: #fef2f2; padding: 15px; border-radius: 6px; font-family: sans-serif; text-align: left;">'
					'  <h4 style="color: #b91c1c; margin-top: 0; font-weight: bold; font-size: 16px; display: flex; align-items: center; gap: 8px;">'
					'    🚨 Duplicate Customer GST Blocked!'
					'  </h4>'
					'  <hr style="border-top: 1px solid #fecaca; margin: 10px 0;">'
					'  <p style="margin: 0; font-size: 14px; line-height: 1.5; color: #1f2937;">'
					'    A customer with GST Number <b>{0}</b> already exists in the system.'
					'  </p>'
					'  <p style="margin: 8px 0 0 0; font-size: 14px; line-height: 1.5; color: #1f2937;">'
					'    Existing Customer ID: <b>{1}</b>.'
					'  </p>'
					'  <p style="margin: 12px 0 0 0; font-size: 13px; font-style: italic; color: #b91c1c; font-weight: bold;">'
					'    You cannot create a duplicate customer record.'
					'  </p>'
					'</div>'
				).format(c_gst, existing_gst)
				frappe.throw(msg, title=_("Duplicate Customer GST"))

	def on_trash(self):
		"""Clear customer link from Hbs Crm Lead before deleting Hbs Customer."""
		frappe.db.sql(
			"UPDATE `tabHbs Crm Lead` SET `customer` = NULL WHERE `customer` = %s",
			self.name
		)
