# Copyright (c) 2026, Hbs and contributors
# For license information, please see license.txt

from zoneinfo import ZoneInfo
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_datetime
from hbs_crm.hbs_crm.utils import is_owner_or_admin, get_logged_in_user_context


class HbsOutstanding(Document):
	def onload(self):
		self.render_activity_html()

	def validate(self):
		# Auto-derive status from pending_amt if not explicitly set
		if not self.status:
			bill_val = frappe.utils.flt(self.bill_amt)
			pending_val = frappe.utils.flt(self.pending_amt)
			if pending_val == 0:
				self.status = "Complete"
			else:
				self.status = "Pending"

		# Auto-calculate overdue days from current date - due_date
		if self.due_date:
			diff = frappe.utils.date_diff(frappe.utils.nowdate(), self.due_date)
			self.overdue_days = max(0, diff)
		else:
			self.overdue_days = 0

		# Read-only enforcement for executives on bill fields
		user = frappe.session.user if frappe.session else "System"
		if not is_owner_or_admin(user) and not getattr(self.flags, "in_log_remark", False) and not getattr(self.flags, "in_api_sync", False) and not self.is_new():
			old_doc = frappe.db.get_value(
				"Hbs Outstanding", self.name,
				["bill_no", "party_name", "company_name", "bill_amt", "pending_amt", "due_date", "executive_1", "executive_2"],
				as_dict=True
			)
			if old_doc:
				for field in ["bill_no", "party_name", "company_name", "bill_amt", "pending_amt", "due_date", "executive_1", "executive_2"]:
					if str(self.get(field) or "").strip() != str(old_doc.get(field) or "").strip():
						frappe.throw(
							_("Sales executives cannot modify bill details. Only remarks can be logged."),
							title=_("Read-Only Restricted")
						)

		# Reset billing_notified if payment status changed away from Payment Received
		if hasattr(self, "billing_notified"):
			if self.payment_status != "Payment Received":
				self.billing_notified = 0
			elif self.is_new() or (self.get_doc_before_save() and self.get_doc_before_save().get("payment_status") != "Payment Received"):
				self.billing_notified = 0

		self.record_remark_activity()
		self.render_activity_html()

	def record_remark_activity(self):
		"""Record new remark in Hbs Lead Activity child table."""
		if self.remarks and self.remarks.strip():
			user_email = frappe.session.user if frappe.session and frappe.session.user else "System"
			new_remark = self.remarks.strip()
			self.append("custom_activities", {
				"user": user_email,
				"date_time": frappe.utils.now_datetime(),
				"remark": new_remark
			})
			self.last_remark = new_remark
			self.last_remarks_date = frappe.utils.nowdate()
			self.remarks = ""
		elif getattr(self, "custom_activities", None) and not self.last_remark:
			self.last_remark = self.custom_activities[-1].remark

	def render_activity_html(self):
		"""Render chronological All Activities timeline from custom_activities and DB."""
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
				filters={"parent": self.name, "parenttype": "Hbs Outstanding", "parentfield": "custom_activities"},
				fields=["user", "date_time", "remark"]
			)
			for d in db_activities:
				rem = d.get("remark", "")
				if rem and not any(r["remark"] == rem and str(r.get("date_time")) == str(d.get("date_time")) for r in raw_list):
					raw_list.append({
						"user": d.get("user") or "System",
						"date_time": d.get("date_time"),
						"remark": rem
					})

		if not raw_list:
			self.activity = "<div style='color:#a0aec0; font-style:italic; padding:10px;'>No remarks recorded yet. Click <b>+ Add Remark</b> to log a note.</div>"
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
				system_tz = frappe.utils.get_system_timezone() or "Asia/Kolkata"
				dt_obj = get_datetime(dt)
				if dt_obj.tzinfo is None:
					dt_obj = dt_obj.replace(tzinfo=ZoneInfo(system_tz))
				local_dt = dt_obj.astimezone(ZoneInfo(user_tz))
				formatted_datetime = frappe.utils.format_datetime(local_dt, "dd/MM/yyyy, HH:mm")

			# Render attachment preview if present
			attachment_preview = ""
			clean_remark_display = remark_text
			if "Attachment: " in remark_text:
				parts = remark_text.split("Attachment: ")
				clean_remark_display = parts[0].strip()
				att_link = parts[1].strip().split("\n")[0].strip()
				file_ext = att_link.lower().split(".")[-1] if "." in att_link else ""
				if file_ext in ("png", "jpg", "jpeg", "webp", "gif"):
					attachment_preview = f'''
						<div style="margin-top: 8px;">
							<a href="{att_link}" target="_blank" style="display: inline-block;">
								<img src="{att_link}" alt="Screenshot" style="max-width: 260px; max-height: 200px; border-radius: 6px; border: 1px solid #cbd5e1; box-shadow: 0 1px 3px rgba(0,0,0,0.05); display: block;" />
							</a>
						</div>
					'''
				elif att_link:
					file_name = att_link.split("/")[-1]
					attachment_preview = f'''
						<div style="margin-top: 8px;">
							<a href="{att_link}" target="_blank" style="display: inline-flex; align-items: center; gap: 6px; background: #eff6ff; border: 1px solid #bfdbfe; color: #1d4ed8; padding: 4px 10px; border-radius: 6px; font-size: 12px; text-decoration: none;">
								📎 <b>Attached Document:</b> {file_name}
							</a>
						</div>
					'''

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
					<div style="background: #fcfcfc; border: 1px solid #d1d8dd; border-radius: 8px; padding: 10px 14px; font-size: 13px; color: #1c2126; white-space: pre-wrap; line-height: 1.35; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">{frappe.utils.escape_html(clean_remark_display.strip())}{attachment_preview}</div>
				</div>
			''')

		html.append('</div>')
		self.activity = "".join(html)


def get_permission_query_conditions(user=None):
	"""Permission hook for Hbs Outstanding.
	- Admin / Owner / Outstanding Viewer: Full visibility to all records.
	- Sales Executive: Strictly scoped to records where executive_1 or executive_2 matches user.
	"""
	if not user:
		user = frappe.session.user

	if is_owner_or_admin(user) or "Outstanding Viewer" in frappe.get_roles(user):
		return ""

	user_escaped = frappe.db.escape(user)
	return f"(`tabHbs Outstanding`.`executive_1` = {user_escaped} OR `tabHbs Outstanding`.`executive_2` = {user_escaped})"


def has_permission(doc, ptype="read", user=None):
	"""Permission hook for Hbs Outstanding.
	- Admin / Owner: Full access (read, write, create, delete).
	- Outstanding Viewer: Strictly READ-ONLY across all records.
	- Sales Executive: Strictly READ-ONLY for assigned records (executive_1 or executive_2).
	"""
	if not user:
		user = frappe.session.user

	if is_owner_or_admin(user):
		return True

	# Non-admin users are strictly blocked from alteration, creation, deletion
	if ptype != "read":
		return False

	if "Outstanding Viewer" in frappe.get_roles(user):
		return True

	if not doc:
		return True

	doc_obj = doc if hasattr(doc, "get") else frappe.get_doc("Hbs Outstanding", doc)
	return user in (doc_obj.get("executive_1"), doc_obj.get("executive_2"))


@frappe.whitelist()
def get_outstanding_statuses():
	"""Fetch configured statuses from Hbs CRM Settings, ensuring blank option is included."""
	options = [""]
	try:
		settings = frappe.get_single("Hbs CRM Settings")
		if hasattr(settings, "outstanding_statuses") and settings.outstanding_statuses:
			for row in settings.outstanding_statuses:
				s = (row.status_name or "").strip()
				if s and s not in options:
					options.append(s)
	except Exception:
		pass

	if "Payment Received" not in options:
		options.append("Payment Received")
	return options


@frappe.whitelist()
def log_remark(name, remark, payment_status=None, attachment=None, **kwargs):
	"""Log remark for Hbs Outstanding record and update activity timeline, payment_status, and attachments.
	Strictly updates payment_status only — leaves bill status untouched.
	"""
	if not name:
		frappe.throw(_("Record name is required."))
	if not remark or not str(remark).strip():
		frappe.throw(_("Remark is required to log follow-up."))

	user = frappe.session.user
	doc = frappe.get_doc("Hbs Outstanding", name)

	if not is_owner_or_admin(user) and user not in (doc.executive_1, doc.executive_2):
		frappe.throw(_("You are not authorized to log remarks on this bill."), title=_("Permission Denied"))

	user_email = user or "System"
	clean_rem = str(remark).strip()
	now_dt = frappe.utils.now_datetime()
	now_d = frappe.utils.nowdate()

	if attachment and str(attachment).strip():
		clean_att = str(attachment).strip()
		file_name = frappe.db.get_value("File", {"file_url": clean_att}, "name")
		if file_name:
			frappe.db.set_value("File", file_name, {
				"attached_to_doctype": "Hbs Outstanding",
				"attached_to_name": doc.name
			}, update_modified=False)
		clean_rem = f"{clean_rem}\n\nAttachment: {clean_att}"

	doc.append("custom_activities", {
		"user": user_email,
		"date_time": now_dt,
		"remark": clean_rem
	})
	doc.last_remark = clean_rem
	doc.last_remarks_date = now_d
	doc.remarks = ""

	if payment_status is not None:
		doc.payment_status = str(payment_status).strip()
		if doc.payment_status != "Payment Received" and hasattr(doc, "billing_notified"):
			doc.billing_notified = 0

	doc.render_activity_html()

	doc.flags.in_log_remark = True
	doc.save(ignore_permissions=True)
	frappe.db.commit()

	return {
		"status": "success",
		"message": _("Follow-up remark logged successfully!"),
		"activity_html": doc.activity,
		"payment_status": doc.payment_status
	}


@frappe.whitelist()
def send_daily_payment_received_digest():
	"""Send 12:00 AM daily digest email to billing executive for outstanding bills where payment status is Payment Received."""
	settings = frappe.get_single("Hbs CRM Settings")
	billing_email = getattr(settings, "billing_executive_email", None)
	if not billing_email or not str(billing_email).strip():
		return {"status": "skipped", "reason": "No billing executive email configured"}

	billing_email = str(billing_email).strip()
	recipients = [e.strip() for e in billing_email.replace(";", ",").split(",") if e.strip()]
	if not recipients:
		return {"status": "skipped", "reason": "No valid recipients"}

	# Fetch un-notified records with Payment Status == 'Payment Received'
	has_col = frappe.db.has_column("Hbs Outstanding", "billing_notified")
	if has_col:
		records = frappe.db.sql("""
			SELECT `name`, `bill_no`, `bill_date`, `party_name`, `executive_1`, `payment_status`, `last_remark`
			FROM `tabHbs Outstanding`
			WHERE `payment_status` = 'Payment Received'
			  AND (`billing_notified` = 0 OR `billing_notified` IS NULL)
			ORDER BY `bill_date` DESC, `name` ASC
		""", as_dict=True)
	else:
		records = frappe.db.sql("""
			SELECT `name`, `bill_no`, `bill_date`, `party_name`, `executive_1`, `payment_status`, `last_remark`
			FROM `tabHbs Outstanding`
			WHERE `payment_status` = 'Payment Received'
			  AND `modified` >= DATE_SUB(NOW(), INTERVAL 1 DAY)
			ORDER BY `bill_date` DESC, `name` ASC
		""", as_dict=True)

	if not records:
		return {"status": "skipped", "reason": "No pending Payment Received records found"}

	site_url = frappe.utils.get_url()
	today_str = frappe.utils.format_date(frappe.utils.nowdate(), "dd/MM/yyyy")

	# Build rows matching strictly: Bill Number, Bill Date, Party Name, Executive 1, Payment Status
	rows_html = []
	attachments = []
	for r in records:
		doc_link = f"{site_url}/app/hbs-outstanding/{r.name}"
		b_no = frappe.utils.escape_html(r.bill_no or r.name or "-")
		b_date = frappe.utils.format_date(r.bill_date, "dd/MM/yyyy") if r.bill_date else "-"
		p_name = frappe.utils.escape_html(r.party_name or "-")
		ex1 = frappe.utils.escape_html(r.executive_1 or "-")
		p_status = frappe.utils.escape_html(r.payment_status or "Payment Received")

		att_note = ""
		if r.last_remark and "Attachment: " in r.last_remark:
			att_url = r.last_remark.split("Attachment: ")[1].strip().split("\n")[0].strip()
			if att_url:
				full_att = att_url if att_url.startswith("http") else f"{site_url}{att_url}"
				att_name = att_url.split("/")[-1]
				att_note = f'<br/><a href="{full_att}" target="_blank" style="font-size: 11px; color: #0284c7;">📎 {frappe.utils.escape_html(att_name)}</a>'
				attachments.append({"file_url": att_url})

		rows_html.append(f'''
			<tr style="border-bottom: 1px solid #e5e7eb;">
				<td style="padding: 10px 8px; font-weight: 500;">
					<a href="{doc_link}" target="_blank" style="color: #2563eb; text-decoration: underline;">
						{b_no}
					</a>{att_note}
				</td>
				<td style="padding: 10px 8px; color: #4b5563;">{b_date}</td>
				<td style="padding: 10px 8px; color: #111827; font-weight: 500;">{p_name}</td>
				<td style="padding: 10px 8px; color: #4b5563;">{ex1}</td>
				<td style="padding: 10px 8px; color: #166534; font-weight: 600;">{p_status}</td>
			</tr>
		''')

	tbody_content = "".join(rows_html)
	subject = f"Payment Received Report ({len(records)} Bills) - {today_str}"
	message = f'''
	<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #1f2937; line-height: 1.5; font-size: 14px;">
		<div style="background-color: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 14px 18px; margin-bottom: 16px;">
			<h3 style="margin: 0 0 4px 0; color: #166534; font-size: 16px;">Daily Payment Received Summary</h3>
			<p style="margin: 0; color: #15803d; font-size: 13px;">The following <b>{len(records)}</b> bill(s) have payment status marked as <b>Payment Received</b> as of {today_str}.</p>
		</div>

		<table style="width: 100%; border-collapse: collapse; margin-bottom: 16px; font-size: 13px;">
			<thead>
				<tr style="background-color: #f9fafb; border-bottom: 2px solid #e5e7eb; text-align: left;">
					<th style="padding: 10px 8px; font-weight: 600; color: #374151;">Bill Number</th>
					<th style="padding: 10px 8px; font-weight: 600; color: #374151;">Bill Date</th>
					<th style="padding: 10px 8px; font-weight: 600; color: #374151;">Party Name</th>
					<th style="padding: 10px 8px; font-weight: 600; color: #374151;">Executive 1</th>
					<th style="padding: 10px 8px; font-weight: 600; color: #374151;">Payment Status</th>
				</tr>
			</thead>
			<tbody>
				{tbody_content}
			</tbody>
		</table>

		<div style="margin-top: 18px;">
			<a href="{site_url}/app/hbs-outstanding" target="_blank" style="display: inline-block; background-color: #2563eb; color: #ffffff; padding: 8px 16px; border-radius: 6px; text-decoration: none; font-size: 13px; font-weight: 500;">
				View Outstanding in CRM →
			</a>
		</div>
	</div>
	'''

	frappe.sendmail(
		recipients=recipients,
		subject=subject,
		message=message,
		attachments=attachments if attachments else None,
		delayed=False
	)

	# Mark records as notified if column exists
	if has_col:
		doc_names = [r.name for r in records]
		frappe.db.set_value("Hbs Outstanding", {"name": ["in", doc_names]}, "billing_notified", 1, update_modified=False)
		frappe.db.commit()

	return {"status": "success", "sent_count": len(records), "recipients": recipients}


@frappe.whitelist()
def get_activity_html(name):
	"""Fetch rendered activity timeline HTML for desk form display."""
	if not name:
		return ""
	doc = frappe.get_doc("Hbs Outstanding", name)
	doc.render_activity_html()
	return doc.activity


@frappe.whitelist()
def get_rendered_outstanding_email_template(outstanding_name):
	"""Render email subject and body template from Hbs CRM Email Settings for the given outstanding bill."""
	doc = frappe.get_doc("Hbs Outstanding", outstanding_name)
	settings = frappe.get_doc("Hbs CRM Email Settings", ignore_permissions=True)

	logged_in_user_dict = get_logged_in_user_context()

	subject_template = getattr(settings, "outstanding_email_subject", None) or "Outstanding Payment Reminder - Bill No: {{ doc.bill_no or '' }} ({{ doc.party_name or 'Valued Client' }})"
	subject = frappe.render_template(subject_template, {"doc": doc, "logged_in_user": logged_in_user_dict})

	fallback_body = (
		"<p>Dear Sir/Madam,</p>"
		"<p>This is a gentle reminder regarding the outstanding payment details mentioned below:</p>"
		"<p>"
		"<b>Company Name :</b> {{ doc.company_name or '' }}<br>"
		"<b>Party Name:</b> {{ doc.party_name or '' }}<br>"
		"<b>Invoice Number:</b> {{ doc.bill_no or '' }}<br>"
		"<b>Pending Since:</b> {{ frappe.utils.format_date(doc.bill_date, 'dd/MM/yyyy') if doc.bill_date else '' }}<br>"
		"<b>Outstanding Amount:</b> ₹{{ frappe.utils.fmt_money(doc.pending_amt) if doc.pending_amt else '0.00' }}"
		"</p>"
		"<p>Kindly arrange to clear the outstanding payment at the earliest.</p>"
		"<p>"
		"Regards,<br>"
		"<b>{{ doc.company_name or '' }}</b><br>"
		"{{ frappe.db.get_value('User', doc.executive_1, 'full_name') or doc.executive_1 or logged_in_user.full_name or '' }}<br>"
		"{{ logged_in_user.mobile_no or logged_in_user.phone or '' }}"
		"</p>"
	)
	body_template = getattr(settings, "outstanding_email_body", None) or fallback_body
	message = frappe.render_template(body_template, {"doc": doc, "logged_in_user": logged_in_user_dict})

	# Discover client contact email if available
	client_email = ""
	if doc.party_name:
		try:
			contacts = frappe.db.sql("""
				SELECT c.email_id FROM `tabContact` c
				INNER JOIN `tabDynamic Link` dl ON dl.parent = c.name
				WHERE dl.link_name = %s AND c.email_id IS NOT NULL AND c.email_id != ''
				LIMIT 1
			""", (doc.party_name,), as_dict=True)
			if contacts:
				client_email = contacts[0].email_id
		except Exception:
			pass

		if not client_email:
			try:
				lead_email = frappe.db.get_value("Hbs Crm Lead", {"company_name": doc.party_name}, "contact_email") or \
							 frappe.db.get_value("Hbs Crm Lead", {"contact_name": doc.party_name}, "contact_email")
				if lead_email:
					client_email = lead_email
			except Exception:
				pass

	user_email = logged_in_user_dict.get("email") or frappe.db.get_value("User", frappe.session.user, "email") or (frappe.session.user if frappe.session and "@" in str(frappe.session.user) else "")

	return {
		"subject": subject,
		"message": message,
		"from_email": settings.email_id or "tally@hbsmail.in",
		"sender_name": settings.sender_name or "HBS Accounts Team",
		"cc_email": user_email,
		"to_email": client_email
	}


@frappe.whitelist()
def send_manual_outstanding_email(outstanding_name, to_email, subject, message, cc_email=None, from_email=None, sender_name=None, extra_attachments=None):
	"""Backend endpoint for the interactive 'Send email to client' dialog for Hbs Outstanding."""
	import json
	doc = frappe.get_doc("Hbs Outstanding", outstanding_name)
	if not to_email:
		frappe.throw(_("Recipient 'To' Email is required."))

	if not cc_email:
		user_dict = get_logged_in_user_context()
		cc_email = user_dict.get("email") or frappe.db.get_value("User", frappe.session.user, "email") or (frappe.session.user if frappe.session and "@" in str(frappe.session.user) else None)

	display_name = sender_name or "HBS Accounts Team"
	email_addr = from_email or "tally@hbsmail.in"

	if frappe.db.exists("Hbs CRM Email Settings"):
		settings = frappe.get_doc("Hbs CRM Email Settings")
		if not from_email and settings.email_id:
			email_addr = settings.email_id
		if not sender_name and settings.sender_name:
			display_name = settings.sender_name

	sender = f"{display_name} <{email_addr}>"
	attachments = []

	# Process extra uploaded attachments (Excel, PDF, Word, Images, etc.)
	if extra_attachments:
		if isinstance(extra_attachments, str):
			try:
				extra_attachments = json.loads(extra_attachments)
			except Exception:
				extra_attachments = [extra_attachments]

		for file_url in extra_attachments:
			if not file_url or not isinstance(file_url, str):
				continue
			file_url = file_url.strip()
			if not file_url:
				continue
			try:
				file_names = frappe.get_all("File", filters={"file_url": file_url}, fields=["name", "file_name"])
				if file_names:
					file_doc = frappe.get_doc("File", file_names[0].name)
					attachments.append({
						"fname": file_doc.file_name,
						"fcontent": file_doc.get_content()
					})
			except Exception as e:
				frappe.log_error(f"Failed to attach file {file_url}: {str(e)}", "Outstanding Email Attachment Error")

	frappe.sendmail(
		recipients=[e.strip() for e in to_email.split(",") if e.strip()],
		cc=[e.strip() for e in cc_email.split(",") if e.strip()] if cc_email else None,
		sender=sender,
		reply_to=email_addr,
		subject=subject,
		message=message,
		attachments=attachments if attachments else None,
		reference_doctype=doc.doctype,
		reference_name=doc.name,
		expose_recipients="header",
		now=True
	)

	# Record email activity in custom_activities
	user_email = frappe.session.user or "System"
	now_dt = frappe.utils.now_datetime()
	now_d = frappe.utils.nowdate()
	remark_text = f"Email sent to client ({to_email})\nSubject: {subject}"
	doc.append("custom_activities", {
		"user": user_email,
		"date_time": now_dt,
		"remark": remark_text
	})
	doc.last_remark = remark_text
	doc.last_remarks_date = now_d
	doc.render_activity_html()
	doc.flags.in_log_remark = True
	doc.save(ignore_permissions=True)
	frappe.db.commit()

	return True

