# Copyright (c) 2026, Hbs and contributors
# For license information, please see license.txt

from zoneinfo import ZoneInfo
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_datetime
from hbs_crm.hbs_crm.utils import is_owner_or_admin


class HbsOutstanding(Document):
	def onload(self):
		self.render_activity_html()

	def validate(self):
		# Auto-derive status from pending_amt
		bill_val = frappe.utils.flt(self.bill_amt)
		pending_val = frappe.utils.flt(self.pending_amt)
		if pending_val == 0:
			self.status = "Cleared"
		elif bill_val and abs(pending_val) < abs(bill_val):
			self.status = "Partially Paid"
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
					<div style="background: #fcfcfc; border: 1px solid #d1d8dd; border-radius: 8px; padding: 10px 14px; font-size: 13px; color: #1c2126; white-space: pre-wrap; line-height: 1.35; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">{frappe.utils.escape_html(remark_text.strip())}</div>
				</div>
			''')

		html.append('</div>')
		self.activity = "".join(html)


def get_permission_query_conditions(user=None):
	"""Permission hook for Hbs Outstanding.
	- Admin / Owner: Full visibility to all records.
	- Sales Executive: Strictly scoped to records where executive_1 or executive_2 matches user.
	"""
	if not user:
		user = frappe.session.user

	if is_owner_or_admin(user):
		return ""

	user_escaped = frappe.db.escape(user)
	return f"(`tabHbs Outstanding`.`executive_1` = {user_escaped} OR `tabHbs Outstanding`.`executive_2` = {user_escaped})"


def has_permission(doc, ptype="read", user=None):
	"""Permission hook for Hbs Outstanding.
	- Admin / Owner: Full access (read, write, create, delete).
	- Sales Executive: Strictly READ-ONLY. No alteration, creation, or deletion.
	  Can only read if assigned to executive_1 or executive_2.
	"""
	if not user:
		user = frappe.session.user

	if is_owner_or_admin(user):
		return True

	# Non-admin users are strictly blocked from alteration, creation, deletion
	if ptype != "read":
		return False

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
def log_remark(name, remark, payment_status=None, status=None):
	"""Log remark for Hbs Outstanding record and update activity timeline and payment_status."""
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

	doc.append("custom_activities", {
		"user": user_email,
		"date_time": now_dt,
		"remark": clean_rem
	})
	doc.last_remark = clean_rem
	doc.last_remarks_date = now_d
	doc.remarks = ""

	chosen_ps = payment_status if payment_status is not None else status
	if chosen_ps is not None:
		doc.payment_status = chosen_ps.strip()

	doc.render_activity_html()

	doc.flags.in_log_remark = True
	doc.save(ignore_permissions=True)
	frappe.db.commit()

	return {
		"status": "success",
		"message": _("Follow-up remark logged successfully!"),
		"activity_html": doc.activity,
		"payment_status": doc.payment_status,
		"status": doc.status
	}


@frappe.whitelist()
def get_activity_html(name):
	"""Fetch rendered activity timeline HTML for desk form display."""
	if not name:
		return ""
	doc = frappe.get_doc("Hbs Outstanding", name)
	doc.render_activity_html()
	return doc.activity


