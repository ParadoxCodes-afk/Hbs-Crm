import frappe
from frappe import _
from frappe.model.document import Document


class HbsCustomer(Document):
	def validate(self):
		self.check_duplicate()

	def check_duplicate(self):
		# 1. Check by Company GST
		if self.company_gst and self.company_gst.strip():
			gst = self.company_gst.strip()
			existing = frappe.db.exists("Hbs Customer", {"company_gst": gst, "name": ["!=", self.name]})
			if existing:
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
				).format(gst, existing)
				frappe.throw(msg, title=_("Duplicate Customer GST"))

		# 2. Check by Contact Phone
		if self.contact_phone and self.contact_phone.strip():
			phone = self.contact_phone.strip()
			existing = frappe.db.exists("Hbs Customer", {"contact_phone": phone, "name": ["!=", self.name]})
			if existing:
				msg = _(
					'<div style="border: 2px solid #ef4444; background-color: #fef2f2; padding: 15px; border-radius: 6px; font-family: sans-serif; text-align: left;">'
					'  <h4 style="color: #b91c1c; margin-top: 0; font-weight: bold; font-size: 16px; display: flex; align-items: center; gap: 8px;">'
					'    🚨 Duplicate Customer Phone Blocked!'
					'  </h4>'
					'  <hr style="border-top: 1px solid #fecaca; margin: 10px 0;">'
					'  <p style="margin: 0; font-size: 14px; line-height: 1.5; color: #1f2937;">'
					'    A customer with Phone Number <b>{0}</b> already exists in the system.'
					'  </p>'
					'  <p style="margin: 8px 0 0 0; font-size: 14px; line-height: 1.5; color: #1f2937;">'
					'    Existing Customer ID: <b>{1}</b>.'
					'  </p>'
					'  <p style="margin: 12px 0 0 0; font-size: 13px; font-style: italic; color: #b91c1c; font-weight: bold;">'
					'    You cannot create a duplicate customer record.'
					'  </p>'
					'</div>'
				).format(phone, existing)
				frappe.throw(msg, title=_("Duplicate Customer Phone"))

		# 3. Check by Contact Email
		if self.contact_email and self.contact_email.strip():
			email = self.contact_email.strip()
			existing = frappe.db.exists("Hbs Customer", {"contact_email": email, "name": ["!=", self.name]})
			if existing:
				msg = _(
					'<div style="border: 2px solid #ef4444; background-color: #fef2f2; padding: 15px; border-radius: 6px; font-family: sans-serif; text-align: left;">'
					'  <h4 style="color: #b91c1c; margin-top: 0; font-weight: bold; font-size: 16px; display: flex; align-items: center; gap: 8px;">'
					'    🚨 Duplicate Customer Email Blocked!'
					'  </h4>'
					'  <hr style="border-top: 1px solid #fecaca; margin: 10px 0;">'
					'  <p style="margin: 0; font-size: 14px; line-height: 1.5; color: #1f2937;">'
					'    A customer with Email ID <b>{0}</b> already exists in the system.'
					'  </p>'
					'  <p style="margin: 8px 0 0 0; font-size: 14px; line-height: 1.5; color: #1f2937;">'
					'    Existing Customer ID: <b>{1}</b>.'
					'  </p>'
					'  <p style="margin: 12px 0 0 0; font-size: 13px; font-style: italic; color: #b91c1c; font-weight: bold;">'
					'    You cannot create a duplicate customer record.'
					'  </p>'
					'</div>'
				).format(email, existing)
				frappe.throw(msg, title=_("Duplicate Customer Email"))

		# 4. Check by Company Name or Customer Name
		name_to_check = self.company_name or self.customer_name
		if name_to_check and name_to_check.strip():
			name_str = name_to_check.strip()
			# Case insensitive match on company_name or customer_name
			existing = frappe.db.sql("""
				SELECT name FROM `tabHbs Customer`
				WHERE (LOWER(`company_name`) = LOWER(%s) OR LOWER(`customer_name`) = LOWER(%s))
				  AND `name` != %s
				LIMIT 1
			""", (name_str, name_str, self.name or ""), as_dict=True)
			if existing:
				msg = _(
					'<div style="border: 2px solid #ef4444; background-color: #fef2f2; padding: 15px; border-radius: 6px; font-family: sans-serif; text-align: left;">'
					'  <h4 style="color: #b91c1c; margin-top: 0; font-weight: bold; font-size: 16px; display: flex; align-items: center; gap: 8px;">'
					'    🚨 Duplicate Customer Name Blocked!'
					'  </h4>'
					'  <hr style="border-top: 1px solid #fecaca; margin: 10px 0;">'
					'  <p style="margin: 0; font-size: 14px; line-height: 1.5; color: #1f2937;">'
					'    A customer with Name/Company <b>{0}</b> already exists in the system.'
					'  </p>'
					'  <p style="margin: 8px 0 0 0; font-size: 14px; line-height: 1.5; color: #1f2937;">'
					'    Existing Customer ID: <b>{1}</b>.'
					'  </p>'
					'  <p style="margin: 12px 0 0 0; font-size: 13px; font-style: italic; color: #b91c1c; font-weight: bold;">'
					'    You cannot create a duplicate customer record.'
					'  </p>'
					'</div>'
				).format(name_str, existing[0].name)
				frappe.throw(msg, title=_("Duplicate Customer Name"))

	def on_trash(self):
		"""Clear customer link from Hbs Crm Lead before deleting Hbs Customer."""
		frappe.db.sql(
			"UPDATE `tabHbs Crm Lead` SET `customer` = NULL WHERE `customer` = %s",
			self.name
		)
