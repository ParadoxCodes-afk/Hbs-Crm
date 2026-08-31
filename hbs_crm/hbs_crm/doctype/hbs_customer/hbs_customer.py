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
				frappe.throw(
					_("A customer with GST Number <b>{0}</b> already exists: <b>{1}</b>.").format(gst, existing),
					title=_("Duplicate Customer GST")
				)

		# 2. Check by Contact Phone
		if self.contact_phone and self.contact_phone.strip():
			phone = self.contact_phone.strip()
			existing = frappe.db.exists("Hbs Customer", {"contact_phone": phone, "name": ["!=", self.name]})
			if existing:
				frappe.throw(
					_("A customer with Phone Number <b>{0}</b> already exists: <b>{1}</b>.").format(phone, existing),
					title=_("Duplicate Customer Phone")
				)

		# 3. Check by Contact Email
		if self.contact_email and self.contact_email.strip():
			email = self.contact_email.strip()
			existing = frappe.db.exists("Hbs Customer", {"contact_email": email, "name": ["!=", self.name]})
			if existing:
				frappe.throw(
					_("A customer with Email ID <b>{0}</b> already exists: <b>{1}</b>.").format(email, existing),
					title=_("Duplicate Customer Email")
				)

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
				frappe.throw(
					_("A customer with Name <b>{0}</b> already exists: <b>{1}</b>.").format(name_str, existing[0].name),
					title=_("Duplicate Customer Name")
				)

	def on_trash(self):
		"""Clear customer link from Hbs Crm Lead before deleting Hbs Customer."""
		frappe.db.sql(
			"UPDATE `tabHbs Crm Lead` SET `customer` = NULL WHERE `customer` = %s",
			self.name
		)
