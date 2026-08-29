# Copyright (c) 2026, Hbs and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class HbsCrmLead(Document):
	@property
	def user(self):
		"""Fallback helper for 'user' attribute in custom email templates."""
		return self.owner or (frappe.session.user if frappe.session else "System")

	def validate(self):
		if not self.contact_name:
			self.contact_name = self.company_name or f"Lead #{self.name}"
		self.set_default_terms_if_empty()
		self.validate_tally_serial_for_won()
		self.validate_won_status_lock()
		self.validate_no_duplicate_lead_type()
		self.validate_follow_up_date()
		self.validate_contact_phone_length()
		self.validate_item_min_rate()
		self.sync_primary_contact_to_all_contacts()
		self.sync_or_create_customer()
		self.record_remark_activity()
		self.calculate_totals()
		self.render_activity_html()

	def validate_tally_serial_for_won(self):
		"""Validate that Tally Serial Number is mandatory when status is Won."""
		if self.status == "won" and not self.tally_serial:
			frappe.throw(_("Tally Serial Number is required when Lead Status is Won."), title=_("Tally Serial Required"))

	def set_default_terms_if_empty(self):
		"""Pre-fill terms and conditions fields with defaults on save if empty."""
		if not self.payment_terms:
			self.payment_terms = "100% advance along with confirm order."
		if not self.delivery:
			self.delivery = "2-3 working days."
		if not self.support:
			self.support = "3 Months Telephonic Support from invoice date."
		if not self.taxes:
			self.taxes = "All Inclusive"
		if not self.validity:
			self.validity = "ONE WEEK"

	def calculate_totals(self):
		"""Calculate totals and taxes taking additional discount into account first."""
		if not getattr(self, "items", None):
			self.total_before_tax = 0
			self.total_tax = 0
			self.total_after_tax = 0
			self.final_total = 0
			return

		total_before_tax = 0
		for row in self.items:
			qty = frappe.utils.flt(row.qty) or 1
			rate = frappe.utils.flt(row.rate) or 0
			discount = frappe.utils.flt(row.discount_amount) or 0
			row_subtotal = (qty * rate) - discount
			total_before_tax += row_subtotal

		additional_discount = frappe.utils.flt(self.additional_discount) or 0
		total_tax = 0
		total_after_tax = 0

		for row in self.items:
			qty = frappe.utils.flt(row.qty) or 1
			rate = frappe.utils.flt(row.rate) or 0
			discount = frappe.utils.flt(row.discount_amount) or 0
			row_subtotal = (qty * rate) - discount

			row_additional_discount = 0
			if total_before_tax > 0:
				row_additional_discount = (row_subtotal / total_before_tax) * additional_discount

			net_subtotal = row_subtotal - row_additional_discount
			tax_percent = frappe.utils.flt(row.tax) or 0
			tax_amt = (net_subtotal * tax_percent) / 100.0
			row_amount = net_subtotal + tax_amt

			row.tax_amount = tax_amt
			row.amount = row_amount

			total_tax += tax_amt
			total_after_tax += row_amount

		self.total_before_tax = total_before_tax
		self.total_tax = total_tax
		self.total_after_tax = total_before_tax - additional_discount
		self.final_total = int(frappe.utils.flt(total_before_tax - additional_discount + total_tax) + 0.5)

	def validate_contact_phone_length(self):
		"""Enforce pure 10-digit mobile numbers without prepending +91."""
		if self.contact_phone:
			raw = str(self.contact_phone).strip()
			if raw.startswith("+91-"): raw = raw[4:].strip()
			elif raw.startswith("+91"): raw = raw[3:].strip()
			elif raw.startswith("91") and len(raw) > 10: raw = raw[2:].strip()

			digits = "".join(filter(str.isdigit, raw))[:10]
			self.contact_phone = digits

		if getattr(self, "all_contacts", None):
			for row in self.all_contacts:
				if row.contact_phone:
					raw = str(row.contact_phone).strip()
					if raw.startswith("+91-"): raw = raw[4:].strip()
					elif raw.startswith("+91"): raw = raw[3:].strip()
					elif raw.startswith("91") and len(raw) > 10: raw = raw[2:].strip()

					digits = "".join(filter(str.isdigit, raw))[:10]
					row.contact_phone = digits

	def sync_primary_contact_to_all_contacts(self):
		"""Ensure primary contact details populate automatically in the All Contacts table and stay in sync."""
		if not self.contact_name and not self.contact_phone and not self.contact_email:
			return

		if not getattr(self, "all_contacts", None):
			self.all_contacts = []

		matched_row = None
		for row in self.all_contacts:
			if (
				(self.contact_phone and row.contact_phone == self.contact_phone) or
				(self.contact_email and row.contact_email == self.contact_email) or
				(self.contact_name and row.contact_name == self.contact_name)
			):
				matched_row = row
				break

		if matched_row:
			matched_row.contact_designation = self.contact_designation
		else:
			self.append("all_contacts", {
				"contact_name": self.contact_name,
				"contact_phone": self.contact_phone,
				"contact_email": self.contact_email,
				"contact_designation": self.contact_designation,
			})

	def validate_follow_up_date(self):
		"""Ensure follow-up date is valid based on whether the lead is new or existing."""
		if self.status in ("won", "lost") or not self.follow_up_date:
			return

		server_today = frappe.utils.getdate(frappe.utils.today())
		follow_up = frappe.utils.getdate(self.follow_up_date)

		if self.is_new():
			# On lead creation: follow-up date must be exactly today (cannot be past or future)
			if follow_up != server_today:
				frappe.throw(
					_("When creating a new lead, the Follow-up Date must be set to today's date ({0}).").format(frappe.utils.formatdate(server_today)),
					title=_("Invalid Lead Creation Date")
				)
		else:
			# On subsequent follow-ups: follow-up date cannot be set to a past date
			if follow_up < server_today:
				frappe.throw(
					_("Follow-up Date cannot be set to a past date. (Server Today: {0})").format(frappe.utils.formatdate(server_today)),
					title=_("Invalid Follow-up Date")
				)

	def validate_item_min_rate(self):
		"""Validate that no quotation item rate is lower than the product's min_rate."""
		if not getattr(self, "items", None):
			return

		for idx, row in enumerate(self.items, 1):
			if not row.item_name:
				continue

			min_rate = frappe.db.get_value("Hbs Product", row.item_name, "min_rate") or 0
			min_rate = frappe.utils.flt(min_rate)
			row_rate = frappe.utils.flt(row.rate)

			if min_rate > 0 and row_rate < min_rate:
				product_doc = frappe.db.get_value("Hbs Product", row.item_name, ["item_name", "product_name"], as_dict=True)
				p_name = product_doc.get("item_name") or product_doc.get("product_name") or row.item_name if product_doc else row.item_name

				msg = _(
					"<b>Invalid Item Rate in Row #{0}!</b><br><br>"
					"Rate for item <b>{1}</b> cannot be lower than the Minimum Allowed Rate (<b>₹{2}</b>).<br>"
					"Entered Rate: <b>₹{3}</b>."
				).format(idx, p_name, min_rate, row_rate)

				frappe.throw(msg, title=_("Minimum Rate Violation"))

	def onload(self):
		self.render_activity_html()

	def after_insert(self):
		"""Auto-send welcome email on new lead creation."""
		self.send_auto_welcome_email()

	def validate_won_status_lock(self):
		"""Block altering status if lead is already saved as 'won' or 'lost'."""
		if not self.is_new():
			db_status = frappe.db.get_value("Hbs Crm Lead", self.name, "status")
			if db_status in ("won", "lost") and self.status != db_status:
				frappe.throw(_("Status cannot be altered once a lead is saved as '{0}'.").format(db_status.title()), title=_("Status Lock Active"))

	def validate_no_duplicate_lead_type(self):
		"""Block saving if an active lead (<= 15 days without follow-up) for the same party and lead type exists."""
		if not self.lead_type:
			return

		dup = check_duplicate_lead(
			company_name=self.company_name,
			contact_name=self.contact_name,
			contact_phone=self.contact_phone,
			contact_email=self.contact_email,
			customer=self.customer,
			lead_type=self.lead_type,
			company_gst=self.company_gst,
			current_lead_name=self.name
		)

		if dup:
			# If lead has been inactive for > 15 days, do NOT block saving! Allow takeover/editing.
			if dup.get("is_inactive"):
				return

			party = dup.get("company_name") or dup.get("contact_name") or "this party"
			exec_name = dup.get("executive_full_name") or dup.get("executive_1") or dup.get("owner") or "another user"
			lead_id = dup.get("name")
			creation_date = dup.get("creation_date")

			msg = _(
				"<b>Active Duplicate Lead Blocked!</b><br><br>"
				"A lead for party <b>{0}</b> with Lead Type <b>{1}</b> has already been created by <b>{2}</b> on <b>{3}</b> (Lead #{4}).<br>"
				"Active follow-ups are ongoing ({5} days since last follow-up).<br><br>"
				"<i>You cannot save a new lead until Lead Type '{1}' is changed.</i>"
			).format(party, self.lead_type, exec_name, creation_date, lead_id, dup.get("days_inactive", 0))

			frappe.throw(msg, title=_("Duplicate Lead Type Blocked"))

	def record_remark_activity(self):
		"""Record new remark in Hbs Lead Activity child table and clear input field."""
		if self.remarks and self.remarks.strip():
			user_email = frappe.session.user if frappe.session and frappe.session.user else "System"
			self.append("custom_activities", {
				"user": user_email,
				"date_time": frappe.utils.now_datetime(),
				"remark": self.remarks.strip()
			})
			self.remarks = ""

	def render_activity_html(self):
		"""Render chronological All Activities timeline from custom_activities, DB, and comments."""
		raw_list = []

		if hasattr(self, "custom_activities") and self.custom_activities:
			for row in self.custom_activities:
				u = getattr(row, "user", None) or "System"
				dt = getattr(row, "date_time", None) or getattr(row, "creation", None)
				rem = getattr(row, "remark", None) or ""
				if rem:
					raw_list.append({"user": u, "date_time": dt, "remark": rem})

		if not self.is_new():
			db_activities = frappe.get_all(
				"Hbs Lead Activity",
				filters={"parent": self.name},
				fields=["user", "date_time", "remark"]
			)
			for d in db_activities:
				rem = d.get("remark", "")
				if rem and not any(r["remark"] == rem for r in raw_list):
					raw_list.append({
						"user": d.get("user") or "System",
						"date_time": d.get("date_time"),
						"remark": rem
					})



		if not raw_list:
			self.activity = "<div style='color:#a0aec0; font-style:italic; padding:10px;'>No activities recorded yet.</div>"
			return

		sorted_list = sorted(raw_list, key=lambda item: str(item.get("date_time") or ""), reverse=True)

		user_tz = frappe.db.get_value("User", frappe.session.user, "time_zone") if (frappe.session and frappe.session.user) else None
		if not user_tz:
			user_tz = frappe.utils.get_system_timezone() or "Asia/Kolkata"
		html = ['<div class="activity-timeline" style="margin-top: 15px; margin-left: 10px; border-left: 2px solid #e2e8f0; padding-left: 24px; position: relative;">']
		for item in sorted_list:
			user_email = item.get("user") or "System"
			dt = item.get("date_time")
			remark_text = item.get("remark") or ""
			
			formatted_datetime = ""
			if dt:
				from zoneinfo import ZoneInfo
				from frappe.utils import get_datetime, get_system_timezone
				system_tz = frappe.utils.get_system_timezone() or "Asia/Kolkata"
				dt_obj = get_datetime(dt)
				if dt_obj.tzinfo is None:
					dt_obj = dt_obj.replace(tzinfo=ZoneInfo(system_tz))
				local_dt = dt_obj.astimezone(ZoneInfo(user_tz))
				formatted_datetime = frappe.utils.format_datetime(local_dt, "dd/MM/yyyy, HH:mm")

			html.append(f'''
				<div class="timeline-item" style="margin-bottom: 14px; position: relative;">
					<div style="position: absolute; left: -35px; top: 1px; background: #ffffff; padding: 2px;">
						<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#6c757d" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
							<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
						</svg>
					</div>
					<div style="font-size: 12.5px; color: #505a62; margin-bottom: 3px;">
						<b style="color: #1c2126; font-weight: 600;">{user_email}</b> <span style="color: #8d99a6;">commented • {formatted_datetime}</span>
					</div>
					<div style="background: #fcfcfc; border: 1px solid #d1d8dd; border-radius: 8px; padding: 10px 14px; font-size: 13px; color: #1c2126; white-space: pre-wrap; line-height: 1.35; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">{remark_text}</div>
				</div>
			''')
		html.append('</div>')

		self.activity = "".join(html)

	def on_trash(self):
		"""Unlink and clean up customer link when lead is deleted."""
		if self.customer:
			cust_name = self.customer
			self.db_set("customer", None)
			if frappe.db.get_value("Hbs Customer", cust_name, "lead_reference") == self.name:
				frappe.delete_doc("Hbs Customer", cust_name, ignore_permissions=True)

	def sync_or_create_customer(self):
		"""Auto-create or update Hbs Customer record upon Lead creation/save."""
		cust_name = self.contact_name or self.company_name or self.contact_email or self.contact_phone
		if not cust_name:
			return

		existing_cust = None
		if self.contact_email:
			existing_cust = frappe.db.get_value("Hbs Customer", {"contact_email": self.contact_email})
		if not existing_cust and self.contact_phone:
			existing_cust = frappe.db.get_value("Hbs Customer", {"contact_phone": self.contact_phone})
		if not existing_cust and cust_name:
			existing_cust = frappe.db.get_value("Hbs Customer", {"customer_name": cust_name})

		if existing_cust:
			self.customer = existing_cust
			cust_doc = frappe.get_doc("Hbs Customer", existing_cust)
			cust_doc.company_name = self.company_name or cust_doc.company_name
			cust_doc.company_gst = self.company_gst or cust_doc.company_gst
			cust_doc.contact_phone = self.contact_phone or cust_doc.contact_phone
			cust_doc.contact_email = self.contact_email or cust_doc.contact_email
			cust_doc.tally_serial = self.tally_serial or cust_doc.tally_serial
			cust_doc.license_type = self.license_type or cust_doc.license_type
			cust_doc.address = getattr(self, "address", None) or cust_doc.address
			cust_doc.save(ignore_permissions=True)
		else:
			cust_doc = frappe.new_doc("Hbs Customer")
			cust_doc.customer_name = cust_name
			cust_doc.company_name = self.company_name
			cust_doc.company_gst = self.company_gst
			cust_doc.contact_phone = self.contact_phone
			cust_doc.contact_email = self.contact_email
			cust_doc.tally_serial = self.tally_serial
			cust_doc.license_type = self.license_type
			cust_doc.address = getattr(self, "address", None)
			if not self.is_new():
				cust_doc.lead_reference = self.name
			cust_doc.insert(ignore_permissions=True)
			self.customer = cust_doc.name

		if not self.is_new() and self.customer:
			self.db_set("customer", self.customer)

	def send_auto_welcome_email(self):
		"""Send automated welcome email if enabled in Hbs CRM Email Settings."""
		if not self.contact_email or not frappe.db.exists("Hbs CRM Email Settings"):
			return

		settings = frappe.get_doc("Hbs CRM Email Settings", ignore_permissions=True)
		if not settings.enable_auto_email:
			return

		self.dispatch_email(settings)

	def dispatch_email(self, settings=None):
		"""Render quotation template and dispatch email with PDF attachment."""
		if not self.contact_email:
			return

		if not settings:
			if frappe.db.exists("Hbs CRM Email Settings"):
				settings = frappe.get_doc("Hbs CRM Email Settings", ignore_permissions=True)
			else:
				return

		# Get logged in user details for the template context
		user_doc = None
		current_user = frappe.session.user if frappe.session else "Administrator"
		if frappe.db.exists("User", current_user):
			user_doc = frappe.get_doc("User", current_user)

		phone_val = ""
		if user_doc:
			phone_val = user_doc.get("phone_number") or user_doc.get("mobile_no") or user_doc.get("phone") or ""

		logged_in_user_dict = {
			"full_name": user_doc.full_name if user_doc and user_doc.full_name else "Sales Representative",
			"mobile_no": phone_val,
			"phone": phone_val,
			"phone_number": phone_val,
			"email": user_doc.email if user_doc and user_doc.email else ""
		}

		subject_template = settings.email_subject or "Quotation {{ doc.name }} for {{ doc.company_name or doc.contact_name or 'Valued Client' }}"
		subject = frappe.render_template(subject_template, {"doc": self, "logged_in_user": logged_in_user_dict})

		body_template = settings.email_body or "Hello {{ doc.contact_name or doc.company_name }},\n\nPlease find attached the quotation details."
		message = frappe.render_template(body_template, {"doc": self, "logged_in_user": logged_in_user_dict})

		display_name = settings.sender_name or "HBS Sales Team"
		email_addr = settings.email_id or "tally@hbsmail.in"
		sender = f"{display_name} <{email_addr}>"

		attachments = []
		try:
			pdf_content = frappe.get_print(
				doctype=self.doctype,
				name=self.name,
				print_format="HBS Quotation",
				as_pdf=True
			)
			if pdf_content:
				attachments.append({
					"fname": f"{self.company_name or self.name}.pdf",
					"fcontent": pdf_content
				})
		except Exception as e:
			frappe.log_error(f"PDF generation error for Lead {self.name}: {str(e)}", "Quotation PDF Warning")

		frappe.sendmail(
			recipients=[self.contact_email],
			sender=sender,
			subject=subject,
			message=message,
			attachments=attachments if attachments else None,
			reference_doctype=self.doctype,
			reference_name=self.name,
			now=True
		)


# --- Whitelisted API Functions & Permission Query Hooks ---

@frappe.whitelist()
def get_rendered_email_template(lead_name):
	"""Render email subject and body template from Hbs CRM Email Settings for the given lead."""
	doc = frappe.get_doc("Hbs Crm Lead", lead_name)
	settings = frappe.get_doc("Hbs CRM Email Settings", ignore_permissions=True)
	
	# Get logged in user details for the template context
	user_doc = None
	current_user = frappe.session.user if frappe.session else "Administrator"
	if frappe.db.exists("User", current_user):
		user_doc = frappe.get_doc("User", current_user)

	phone_val = ""
	if user_doc:
		phone_val = user_doc.get("phone_number") or user_doc.get("mobile_no") or user_doc.get("phone") or ""

	logged_in_user_dict = {
		"full_name": user_doc.full_name if user_doc and user_doc.full_name else "Sales Representative",
		"mobile_no": phone_val,
		"phone": phone_val,
		"phone_number": phone_val,
		"email": user_doc.email if user_doc and user_doc.email else ""
	}

	subject_template = settings.email_subject or "Quotation {{ doc.name }} for {{ doc.company_name or doc.contact_name or 'Valued Client' }}"
	subject = frappe.render_template(subject_template, {"doc": doc, "logged_in_user": logged_in_user_dict})

	body_template = settings.email_body or "Hello {{ doc.contact_name or doc.company_name }},\n\nPlease find attached the quotation details."
	message = frappe.render_template(body_template, {"doc": doc, "logged_in_user": logged_in_user_dict})

	return {
		"subject": subject,
		"message": message,
		"from_email": settings.email_id or "tally@hbsmail.in",
		"sender_name": settings.sender_name or "HBS Sales Team"
	}

@frappe.whitelist()
def send_manual_lead_email(lead_name, to_email, subject, message, cc_email=None, from_email=None, sender_name=None, attach_print=1):
	"""Backend endpoint for the interactive 'Enter email details' dialog."""
	doc = frappe.get_doc("Hbs Crm Lead", lead_name)
	if not to_email:
		frappe.throw(_("Recipient 'To' Email is required."))

	display_name = sender_name or "HBS Sales Team"
	email_addr = from_email or "tally@hbsmail.in"

	if frappe.db.exists("Hbs CRM Email Settings"):
		settings = frappe.get_doc("Hbs CRM Email Settings")
		if not from_email and settings.email_id:
			email_addr = settings.email_id
		if not sender_name and settings.sender_name:
			display_name = settings.sender_name

	sender = f"{display_name} <{email_addr}>"

	attachments = []
	if frappe.utils.cint(attach_print) == 1:
		try:
			pdf_content = frappe.get_print(
				doctype=doc.doctype,
				name=doc.name,
				print_format="HBS Quotation",
				as_pdf=True
			)
			if pdf_content:
				attachments.append({
					"fname": f"{doc.company_name or doc.name}.pdf",
					"fcontent": pdf_content
				})
		except Exception as e:
			frappe.log_error(f"Attachment error for Lead {doc.name}: {str(e)}", "Quotation Attachment Warning")

	frappe.sendmail(
		recipients=[e.strip() for e in to_email.split(",") if e.strip()],
		cc=[e.strip() for e in cc_email.split(",") if e.strip()] if cc_email else None,
		sender=sender,
		subject=subject,
		message=message,
		attachments=attachments if attachments else None,
		reference_doctype=doc.doctype,
		reference_name=doc.name,
		now=True
	)
	return True


@frappe.whitelist()
def get_activity_html(lead_name):
	"""Endpoint to return rendered All Activities timeline HTML to Desk UI."""
	if not lead_name:
		return "<div style='color:#a0aec0; font-style:italic; padding:10px;'>No activities recorded yet.</div>"
	doc = frappe.get_doc("Hbs Crm Lead", lead_name)
	doc.render_activity_html()
	return doc.activity


def get_subordinates_from_hierarchy(user, visited=None):
	"""Recursively get all users reporting directly or indirectly to the given user in Hbs User Hierarchy."""
	if visited is None:
		visited = set()
	if user in visited:
		return []
	visited.add(user)

	subordinates = []
	direct_reports = frappe.get_all(
		"Hbs User Hierarchy",
		filters={"reports_to": user},
		pluck="user"
	)
	for report in direct_reports:
		if report not in subordinates:
			subordinates.append(report)
			subordinates.extend(get_subordinates_from_hierarchy(report, visited))
	return list(set(subordinates))


def get_permission_query_conditions(user=None):
	"""Permission hook to scope lead visibility based on User Hierarchy only."""
	if not user:
		user = frappe.session.user

	# Administrator / System Manager sees ALL leads without date restrictions
	roles = frappe.get_roles(user)
	if "System Manager" in roles or user == "Administrator":
		return ""

	# Check Hbs User Hierarchy entry for this user
	hierarchy_entry = frappe.db.get_value(
		"Hbs User Hierarchy",
		{"user": user},
		["role_type", "name"],
		as_dict=True
	)

	# If role is Owner, return "" (sees all leads across the company)
	if hierarchy_entry and hierarchy_entry.get("role_type") == "Owner":
		return ""

	# Standard user level (Manager, Executive): Team members only (no date restrictions on permissions)
	subordinates = get_subordinates_from_hierarchy(user)
	team_members = list(set([user] + subordinates))
	team_escaped = ", ".join([frappe.db.escape(u) for u in team_members])

	user_cond = f"(`tabHbs Crm Lead`.`executive_1` IN ({team_escaped}) OR `tabHbs Crm Lead`.`executive_2` IN ({team_escaped}) OR `tabHbs Crm Lead`.`owner` IN ({team_escaped}))"

	return user_cond


def has_permission(doc, ptype="read", user=None):
	"""Check document-level read permission based on Hbs User Hierarchy."""
	if not user:
		user = frappe.session.user

	roles = frappe.get_roles(user)
	if "System Manager" in roles or user == "Administrator":
		return True

	hierarchy_entry = frappe.db.get_value(
		"Hbs User Hierarchy",
		{"user": user},
		["role_type", "name"],
		as_dict=True
	)

	if hierarchy_entry and hierarchy_entry.get("role_type") == "Owner":
		return True

	subordinates = get_subordinates_from_hierarchy(user)
	team_members = set([user] + subordinates)

	return (
		doc.executive_1 in team_members or
		doc.executive_2 in team_members or
		doc.owner in team_members
	)


@frappe.whitelist()
def check_duplicate_lead(company_name=None, contact_name=None, contact_phone=None, contact_email=None, customer=None, lead_type=None, company_gst=None, current_lead_name=None):
	"""Check if an active lead already exists for the same party/phone and lead type."""
	if not lead_type or not str(lead_type).strip():
		return None

	lead_type = str(lead_type).strip()
	company_name = str(company_name or "").strip()
	contact_name = str(contact_name or "").strip()
	contact_phone = str(contact_phone or "").strip()
	company_gst = str(company_gst or "").strip()

	params = {
		"lead_type": lead_type,
		"contact_phone": contact_phone,
		"company_name": company_name.lower(),
		"contact_name": contact_name.lower(),
		"company_gst": company_gst
	}

	base_clause = "`lead_type` = %(lead_type)s AND `status` NOT IN ('won', 'lost')"

	if current_lead_name and str(current_lead_name).strip() and not str(current_lead_name).startswith("new-"):
		base_clause += " AND `name` != %(current_lead_name)s"
		params["current_lead_name"] = str(current_lead_name).strip()

	# Match criteria options
	conds = []
	
	# Option 1: Match by Phone
	if contact_phone:
		conds.append("`contact_phone` = %(contact_phone)s")

	# Option 2: Match by Company Details (Company Name + Contact Name + optional GST)
	if company_name and contact_name:
		name_clause = "LOWER(`company_name`) = %(company_name)s AND LOWER(`contact_name`) = %(contact_name)s"
		if company_gst:
			name_clause += " AND (`company_gst` = %(company_gst)s OR `company_gst` IS NULL OR `company_gst` = '')"
		conds.append(f"({name_clause})")

	if not conds:
		return None

	where_clause = f"{base_clause} AND ({ ' OR '.join(conds) })"

	duplicates = frappe.db.sql(f"""
		SELECT name, contact_name, company_name, lead_type, executive_1, executive_2, owner, creation
		FROM `tabHbs Crm Lead`
		WHERE {where_clause}
		ORDER BY creation DESC
		LIMIT 1
	""", params, as_dict=True)

	if duplicates:
		dup = duplicates[0]

		exec_user = dup.get("executive_1") or dup.get("executive_2") or dup.get("owner")
		exec_name = frappe.db.get_value("User", exec_user, "full_name") or exec_user
		dup["executive_full_name"] = exec_name
		dup["creation_date"] = frappe.utils.formatdate(dup.creation, "dd/MM/yyyy")

		# Calculate last follow-up / activity date
		latest_activity_row = frappe.db.sql(
			"SELECT MAX(`date_time`) FROM `tabHbs Lead Activity` WHERE `parent` = %s",
			dup["name"]
		)
		latest_activity_date = latest_activity_row[0][0] if latest_activity_row and latest_activity_row[0][0] else None

		last_date = latest_activity_date or dup.get("creation")
		if last_date:
			today = frappe.utils.getdate()
			last_d = frappe.utils.getdate(last_date)
			days_diff = frappe.utils.date_diff(today, last_d)
			dup["days_inactive"] = max(0, days_diff)
			dup["last_follow_up_formatted"] = frappe.utils.formatdate(last_d, "dd/MM/yyyy")
			dup["is_inactive"] = days_diff > 15
		else:
			dup["days_inactive"] = 0
			dup["is_inactive"] = False

		return dup

	return None


@frappe.whitelist()
def take_over_lead(lead_name):
	"""Allow a sales executive to take over ownership of a dormant lead (15+ days inactive)."""
	if not lead_name:
		frappe.throw(_("Lead Name is required."), title=_("Invalid Request"))

	doc = frappe.get_doc("Hbs Crm Lead", lead_name)

	# Calculate days inactive
	latest_activity_row = frappe.db.sql(
		"SELECT MAX(`date_time`) FROM `tabHbs Lead Activity` WHERE `parent` = %s",
		doc.name
	)
	latest_activity_date = latest_activity_row[0][0] if latest_activity_row and latest_activity_row[0][0] else None

	last_date = latest_activity_date or doc.creation
	days_diff = frappe.utils.date_diff(frappe.utils.getdate(), frappe.utils.getdate(last_date))

	if days_diff <= 15:
		frappe.throw(_("This lead has active follow-ups ({0} days ago) and cannot be taken over.").format(days_diff), title=_("Lead Active"))

	user = frappe.session.user
	user_full_name = frappe.db.get_value("User", user, "full_name") or user

	old_exec = doc.executive_1 or doc.owner or "Previous Executive"
	old_exec_name = frappe.db.get_value("User", old_exec, "full_name") or old_exec

	# Reassign Executive 1 to current user & reset follow-up date/time to today
	doc.executive_1 = user
	if doc.executive_2 in (user, old_exec):
		doc.executive_2 = None
	
	doc.follow_up_date = frappe.utils.today()
	doc.follow_up_time = frappe.utils.nowtime()

	# Append Activity Log
	remark_text = f"⚡ Lead taken over by {user_full_name} ({user}) due to {days_diff} days inactivity (Previous Executive: {old_exec_name})."
	doc.append("custom_activities", {
		"user": user,
		"date_time": frappe.utils.now_datetime(),
		"remark": remark_text
	})

	doc.save(ignore_permissions=True)
	frappe.db.set_value("Hbs Crm Lead", doc.name, "owner", user)
	frappe.db.commit()

	return {
		"status": "success",
		"message": _("Lead #{0} has been successfully taken over by you!").format(doc.name)
	}
