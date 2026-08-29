# Copyright (c) 2026, Hbs and contributors
# For license information, please see license.txt

import smtplib
import frappe
from frappe import _
from frappe.model.document import Document


class HbsCRMEmailSettings(Document):
	def validate(self):
		if self.enable_auto_email and not self.email_id:
			frappe.throw(_("Please provide an Email ID / Username when Auto Email is enabled."))

	def on_update(self):
		if self.smtp_server and self.email_id:
			self.sync_frappe_email_account()

	def sync_frappe_email_account(self):
		"""Sync settings to a standard Frappe Email Account to enable seamless email queuing."""
		account_name = "HBS CRM Email Account"

		if frappe.db.exists("Email Account", account_name):
			email_account = frappe.get_doc("Email Account", account_name)
		else:
			email_account = frappe.new_doc("Email Account")
			email_account.email_account_name = account_name

		email_account.email_id = self.email_id
		email_account.smtp_server = self.smtp_server
		email_account.smtp_port = self.smtp_port or 587
		email_account.use_tls = 1 if self.use_tls else 0
		email_account.use_ssl = 1 if self.use_ssl else 0
		email_account.enable_outgoing = 1
		email_account.default_outgoing = 1

		raw_password = self.get_password("password")
		if raw_password:
			email_account.password = raw_password

		email_account.flags.ignore_permissions = True
		email_account.save()

	@frappe.whitelist()
	def test_smtp_connection(self):
		"""Test connection to the SMTP server with provided credentials."""
		if not self.smtp_server:
			frappe.throw(_("Please specify an SMTP Server / Host."))
		if not self.email_id:
			frappe.throw(_("Please specify an Email ID / Username."))

		password = self.get_password("password")
		if not password and frappe.db.exists("Hbs CRM Email Settings"):
			password = frappe.get_doc("Hbs CRM Email Settings").get_password("password")

		if not password:
			frappe.throw(_("Please enter your SMTP Password before testing connection."))

		port = int(self.smtp_port or 587)

		try:
			if self.use_ssl:
				server = smtplib.SMTP_SSL(self.smtp_server, port, timeout=10)
			else:
				server = smtplib.SMTP(self.smtp_server, port, timeout=10)
				if self.use_tls:
					server.starttls()

			server.login(self.email_id, password)
			server.quit()
			frappe.msgprint(_("SMTP Connection Successful! Credentials are valid."), title=_("Success"), indicator="green")
			return True
		except Exception as e:
			frappe.msgprint(_("SMTP Connection Failed: {0}").format(str(e)), title=_("Connection Error"), indicator="red")
			return False
