import frappe
from frappe import _
from frappe.model.document import Document


class HbsCustomer(Document):
	def validate(self):
		self.check_duplicate()

	def check_duplicate(self):
		c_name = str(self.company_name or "").strip()
		c_gst = str(self.company_gst or "").strip()

		# Block duplicate customer only when BOTH company name AND GST number match an existing customer
		if c_name and c_gst:
			existing = frappe.db.sql("""
				SELECT name FROM `tabHbs Customer`
				WHERE LOWER(`company_name`) = LOWER(%s)
				  AND `company_gst` = %s
				  AND `name` != %s
				LIMIT 1
			""", (c_name, c_gst, self.name or ""), as_dict=True)

			if existing:
				msg = _(
					'<div style="border: 2px solid #ef4444; background-color: #fef2f2; padding: 15px; border-radius: 6px; font-family: sans-serif; text-align: left;">'
					'  <h4 style="color: #b91c1c; margin-top: 0; font-weight: bold; font-size: 16px; display: flex; align-items: center; gap: 8px;">'
					'    🚨 Duplicate Customer Blocked!'
					'  </h4>'
					'  <hr style="border-top: 1px solid #fecaca; margin: 10px 0;">'
					'  <p style="margin: 0; font-size: 14px; line-height: 1.5; color: #1f2937;">'
					'    A customer with Company Name <b>{0}</b> and GST Number <b>{1}</b> already exists in the system.'
					'  </p>'
					'  <p style="margin: 8px 0 0 0; font-size: 14px; line-height: 1.5; color: #1f2937;">'
					'    Existing Customer ID: <b>{2}</b>.'
					'  </p>'
					'  <p style="margin: 12px 0 0 0; font-size: 13px; font-style: italic; color: #b91c1c; font-weight: bold;">'
					'    You cannot create a duplicate customer record.'
					'  </p>'
					'</div>'
				).format(c_name, c_gst, existing[0].name)
				frappe.throw(msg, title=_("Duplicate Customer Blocked"))

	def on_trash(self):
		"""Clear customer link from Hbs Crm Lead before deleting Hbs Customer."""
		frappe.db.sql(
			"UPDATE `tabHbs Crm Lead` SET `customer` = NULL WHERE `customer` = %s",
			self.name
		)
