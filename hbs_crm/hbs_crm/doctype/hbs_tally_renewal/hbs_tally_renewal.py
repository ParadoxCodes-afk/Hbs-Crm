# Copyright (c) 2026, Hbs and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
import requests
import json
import datetime
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse


def format_tally_version(ver):
	"""Format version string so numeric/raw releases (e.g., '7.1') become 'Tally Prime 7.1'."""
	if not ver:
		return ""
	ver_str = str(ver).strip()
	if not ver_str:
		return ""
	if ver_str.lower().startswith("tally"):
		return ver_str
	if ver_str.lower().startswith("prime"):
		return f"Tally {ver_str}"
	return f"Tally Prime {ver_str}"


def safe_parse_portal_date(val):
	"""Parse date from portal response supporting multiple date formats."""
	if not val:
		return None
	val_str = str(val).strip()
	for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y", "%d-%b-%Y"):
		try:
			return datetime.datetime.strptime(val_str, fmt).date()
		except Exception:
			pass
	try:
		return frappe.utils.getdate(val_str)
	except Exception:
		return None


def is_genuine_tally_serial(serial):
	"""Validate that a serial conforms to genuine Tally serial rules:
	1. Exactly 9 numeric digits
	2. Starts with '7'
	3. Digital root sum equals 9
	"""
	if not serial:
		return False
	raw_serial = str(serial).strip()
	if raw_serial.endswith(".0"):
		raw_serial = raw_serial[:-2].strip()
	digits = "".join(filter(str.isdigit, raw_serial))
	if len(digits) != 9 or len(raw_serial) != 9 or not raw_serial.isdigit():
		return False
	if not digits.startswith("7"):
		return False
	sum_digits = sum(int(d) for d in digits)
	while sum_digits >= 10:
		sum_digits = sum(int(d) for d in str(sum_digits))
	return sum_digits == 9


def extract_renewal_pi_and_prefix(val):
	"""Extract prefix, serial number, and optional suffix from strings like 'HBS/PI/91957' or '91957'."""
	if not val:
		return "HBS/PI", 0, None
	val_str = str(val).strip()
	import re
	m = re.match(r"^(.*?/)?(\d+)(/.*)?$", val_str)
	if m:
		prefix = (m.group(1) or "HBS/PI/").rstrip("/")
		number = int(m.group(2))
		suffix = (m.group(3) or "").lstrip("/") or None
		return prefix, number, suffix
	digits = re.findall(r"\d+", val_str)
	if digits:
		return "HBS/PI", int(digits[0]), None
	return "HBS/PI", 0, None


def get_last_renewal_pi_info():
	"""Query highest renewal PI number in database."""
	rows = frappe.db.sql(
		"""
		SELECT pi_number FROM `tabHbs Tally Renewal`
		WHERE pi_number IS NOT NULL AND pi_number != ''
		ORDER BY creation DESC LIMIT 100
		""",
		as_dict=True
	)
	max_num = 0
	last_full_str = None
	for r in rows:
		val = (r.pi_number or "").strip()
		if not val:
			continue
		_, num, _ = extract_renewal_pi_and_prefix(val)
		if num > max_num:
			max_num = num
			last_full_str = val
	return max_num, last_full_str


def assign_renewal_pi_and_date(doc):
	"""Assign quotation date and increment renewal PI number checking both DB and Hbs CRM Settings."""
	today = frappe.utils.nowdate()
	if not getattr(doc, "quotation_date", None):
		doc.quotation_date = today
		if not doc.is_new():
			doc.db_set("quotation_date", today, update_modified=False)

	if not getattr(doc, "pi_number", None):
		admin_val = frappe.db.get_single_value("Hbs CRM Settings", "renewal_pi_number_order") or "HBS/PI/91957"
		last_gen_val = frappe.db.get_single_value("Hbs CRM Settings", "last_generated_renewal_pi_number")

		prefix, admin_num, suffix = extract_renewal_pi_and_prefix(admin_val)
		_, last_gen_num, _ = extract_renewal_pi_and_prefix(last_gen_val)
		last_db_num, _ = get_last_renewal_pi_info()

		next_num = max(admin_num, last_gen_num, last_db_num) + 1
		prefix_clean = prefix or "HBS/PI"
		if suffix:
			full_pi_number = f"{prefix_clean}/{next_num}/{suffix}"
		else:
			full_pi_number = f"{prefix_clean}/{next_num}"

		if not doc.is_new():
			doc.db_set("pi_number", full_pi_number, update_modified=False)
		doc.pi_number = full_pi_number

		# Only update last_generated_renewal_pi_number; preserve admin's base order in renewal_pi_number_order
		frappe.db.set_single_value("Hbs CRM Settings", "last_generated_renewal_pi_number", full_pi_number)


class HbsTallyRenewal(Document):
	def normalize_select_fields(self):
		"""Gracefully handle legacy or unlisted select values from historical imports."""
		for df in self.meta.get_select_fields():
			val = self.get(df.fieldname)
			if not val or df.fieldname == "naming_series":
				continue
			options = [opt.strip() for opt in (df.options or "").split("\n") if opt.strip()]
			if options and val not in options:
				val_upper = str(val).strip().upper()
				matched = None
				for opt in options:
					if opt.upper() == val_upper:
						matched = opt
						break
				if matched:
					setattr(self, df.fieldname, matched)
				elif df.fieldname == "crm_stage":
					if "FOLLOW" in val_upper:
						setattr(self, df.fieldname, "IN FOLLOW-UP")
					elif "RESPOND" in val_upper:
						setattr(self, df.fieldname, "CUSTOMER NOT RESPONDING")
					elif "DEMO" in val_upper or "MEETING" in val_upper:
						setattr(self, df.fieldname, "DEMO/MEETING DONE")
					elif "LEAD" in val_upper:
						setattr(self, df.fieldname, "LEAD")
					elif "QUOTE" in val_upper or "QUOTATION" in val_upper:
						setattr(self, df.fieldname, "QUOTATION SENT")
					else:
						setattr(self, df.fieldname, "")

	def validate(self):
		self.normalize_select_fields()
		if self.tally_serial:
			self.tally_serial = str(self.tally_serial).strip()
		if self.tss_tally_serial:
			self.tss_tally_serial = str(self.tss_tally_serial).strip()

		# Sync serial numbers
		if self.tally_serial and not self.tss_tally_serial:
			self.tss_tally_serial = self.tally_serial
		elif self.tss_tally_serial and not self.tally_serial:
			self.tally_serial = self.tss_tally_serial

		self.validate_tally_serial()
		self.validate_no_duplicate_serial()

		# Initial fallback from import raw fields if empty
		if not self.license and (self.tally_parent or self.flavour):
			self.license = self.tally_parent or self.flavour
		if not self.flavour and self.tally_parent:
			self.flavour = self.tally_parent
		if not self.edition and self.flavour:
			self.edition = self.flavour

		# Preserve exact Tally Version from Product Version; fallback to product_ver / release if empty
		if self.tally_version:
			self.tally_version = str(self.tally_version).strip()
		elif self.product_ver:
			self.tally_version = str(self.product_ver).strip()
		elif self.release:
			self.tally_version = str(self.release).strip()

		if not self.product_ver and self.release:
			self.product_ver = str(self.release).strip()

		# Portal Contact Person defaults to Account / Company Name
		if not self.portal_contact and (self.cc_acc_name or self.portal_acc_name):
			self.portal_contact = self.cc_acc_name or self.portal_acc_name

		self.set_terms_defaults()
		self.auto_fill_quote_items()

		# Auto-assign quotation date and PI number if items exist and not in import
		is_import = getattr(self.flags, "in_import", False) or getattr(frappe.flags, "in_import", False)
		if getattr(self, "items", None) and len(self.items) > 0 and not is_import:
			self.quotation_date = frappe.utils.nowdate()
			if not getattr(self, "pi_number", None):
				assign_renewal_pi_and_date(self)

		self.calculate_totals()
		self.validate_executive_permission()
		self.validate_alteration_locks()
		self.sync_primary_contact_to_all_contacts()
		self.record_remark_activity()
		self.render_activity_html()
		self.render_old_remarks_html()

	def set_terms_defaults(self):
		"""Populate quotation terms and conditions defaults if not already present."""
		defaults = {
			"payment_terms": "100% advance along with confirm order.",
			"delivery": "2-3 working days.",
			"support": "3 Months Telephonic Support from invoice date.",
			"taxes": "All Inclusive",
			"validity": "ONE WEEK",
		}
		for field, default_value in defaults.items():
			if not getattr(self, field, None):
				setattr(self, field, default_value)

	# Map license keywords (case-insensitive) → Hbs Product item_name
	_LICENSE_TO_PRODUCT = {
		"gold":    "TALLY SOFTWARE SERVICES GOLD",
		"silver":  "TALLY SOFTWARE SERVICES SILVER",
		"auditor": "TALLY SOFTWARE SERVICES AUDITOR",
	}

	def auto_fill_quote_items(self):
		"""Auto-populate the items table with the matching TSS product on first save.
		Only fills when items is empty; never overwrites manual edits.
		"""
		if getattr(self, "items", None) and len(self.items) > 0:
			return  # already has items – don't overwrite

		license_raw = " ".join(filter(None, [
			getattr(self, "license", None),
			getattr(self, "flavour", None),
			getattr(self, "license_type", None),
			getattr(self, "tally_parent", None),
			getattr(self, "edition", None)
		])).strip().lower()

		product_name = None
		for keyword, prod in self._LICENSE_TO_PRODUCT.items():
			if keyword in license_raw:
				product_name = prod
				break

		if not product_name:
			return  # unknown license type – leave items empty

		prod = frappe.db.get_value(
			"Hbs Product", {"item_name": product_name, "is_active": 1},
			["name", "item_name", "rate", "tax", "hsn", "description"],
			as_dict=True,
		)
		if not prod:
			return

		# Use cc_amount as rate override if it was already set by import
		rate = frappe.utils.cint(self.cc_amount) or prod.rate

		self.append("items", {
			"item_name": prod.name,
			"description": "",
			"qty": 1,
			"rate": rate,
			"tax": prod.tax or 0,
			"hsn": prod.hsn or "",
			"discount_amount": 0,
		})

	def calculate_totals(self):
		"""Calculate totals and taxes without discount (discount disabled)."""
		if not getattr(self, "items", None):
			self.total_before_tax = 0
			self.total_tax = 0
			self.total_after_tax = 0
			self.final_total = 0
			return

		row_subtotals = []
		total_before_tax = 0
		for row in self.items:
			qty = frappe.utils.flt(row.qty) or 1
			rate = frappe.utils.flt(row.rate) or 0
			row_subtotal = qty * rate
			row_subtotals.append(row_subtotal)
			total_before_tax += row_subtotal

		total_tax = 0
		total_after_tax = 0

		for row, row_subtotal in zip(self.items, row_subtotals):
			tax_percent = frappe.utils.flt(row.tax) or 0
			tax_amt = (row_subtotal * tax_percent) / 100.0
			row_amount = row_subtotal + tax_amt

			row.tax_amount = tax_amt
			row.amount = row_amount

			total_tax += tax_amt
			total_after_tax += row_amount

		self.total_before_tax = total_before_tax
		self.total_tax = total_tax
		self.total_after_tax = total_before_tax
		self.final_total = int(frappe.utils.flt(total_before_tax + total_tax) + 0.5)
		is_import = getattr(self.flags, "in_import", False) or getattr(frappe.flags, "in_import", False)
		if self.final_total > 0 and not is_import:
			self.cc_amount = self.final_total

	def onload(self):
		self.render_activity_html()
		self.render_old_remarks_html()

	def validate_executive_permission(self):
		"""Ensure Executive 1 is defaulted on new docs."""
		if self.is_new() and not self.crm_ex_1:
			user = frappe.session.user if frappe.session else "System"
			self.crm_ex_1 = user

	def on_update(self):
		if self.crm_ex_1 and self.owner != self.crm_ex_1:
			frappe.db.set_value("Hbs Tally Renewal", self.name, "owner", self.crm_ex_1, update_modified=False)
			self.owner = self.crm_ex_1

	def before_delete(self):
		"""Prevent regular users from deleting Hbs Tally Renewal records.
		Only Administrator, System Manager, or Owner in Hbs User Hierarchy can delete.
		"""
		user = frappe.session.user if frappe.session else "System"
		if not is_owner_or_admin(user):
			frappe.throw(
				_("Users are not permitted to delete Hbs Tally Renewal records. Only Owner or Administrator can delete."),
				title=_("Deletion Not Allowed")
			)

	def validate_alteration_locks(self):
		"""Enforce that non-admin/owner users can only alter cc_mobile on existing records."""
		if (
			self.is_new()
			or getattr(self.flags, "in_api_sync", False)
			or getattr(self.flags, "in_follow_up", False)
			or getattr(self.flags, "in_import", False)
			or getattr(frappe.flags, "in_import", False)
			or getattr(self.flags, "in_migrate", False)
			or getattr(self.flags, "in_takeover", False)
			or getattr(frappe.flags, "in_takeover", False)
		):
			return

		user = frappe.session.user if frappe.session else "System"
		if is_owner_or_admin(user):
			return

		# Fetch existing DB values
		old_doc = frappe.db.get_value(
			"Hbs Tally Renewal",
			self.name,
			[
				"tss_tally_serial", "license", "tally_version", "acc_expiry_date"
			],
			as_dict=True
		)
		if not old_doc:
			return

		# Check if locked fields were modified by normal user
		locked_fields = [
			("tss_tally_serial", "TSS Tally Serial"),
			("license", "License"),
			("tally_version", "Tally Version"),
			("acc_expiry_date", "TSS Expiry Date"),
		]

		for fn, label in locked_fields:
			old_val = str(old_doc.get(fn) or "").strip()
			new_val = str(self.get(fn) or "").strip()
			if old_val != new_val and old_val:
				frappe.throw(
					_("<b>Field Locked ({0})!</b><br>Serial, License, Version, and Expiry Date cannot be modified on saved records.").format(label),
					title=_("Alteration Restricted")
				)

		# Enforce additional discount lock for normal users
		old_discount = frappe.db.get_value("Hbs Tally Renewal", self.name, "additional_discount") or 0
		if frappe.utils.flt(self.additional_discount) != frappe.utils.flt(old_discount):
			frappe.throw(
				_("<b>Quote Locked!</b><br>Only Admin/Owner can change additional discount."),
				title=_("Alteration Restricted")
			)

		# Enforce old remarks lock for normal users
		old_remarks_val = frappe.db.get_value("Hbs Tally Renewal", self.name, "old_remarks") or ""
		if str(self.old_remarks or "").strip() != old_remarks_val.strip() and old_remarks_val.strip():
			frappe.throw(
				_("<b>Field Locked!</b><br>Only Admin/Owner can alter Old Remarks."),
				title=_("Alteration Restricted")
			)

	def validate_tally_serial(self):
		"""Validate that Tally Serial Number, if provided, conforms to genuine serial rules:
		1. Exactly 9 numeric digits
		2. Starts with '7'
		3. Digital root sum equals 9
		"""
		serial_to_check = self.tally_serial or self.tss_tally_serial
		if serial_to_check:
			raw_serial = str(serial_to_check).strip()
			if raw_serial.endswith(".0"):
				raw_serial = raw_serial[:-2].strip()
			if not is_genuine_tally_serial(raw_serial):
				frappe.throw(_("Invalid Serial Number"), title=_("Invalid Serial Number"))

			serial = "".join(filter(str.isdigit, raw_serial))
			self.tally_serial = serial
			self.tss_tally_serial = serial

	def validate_no_duplicate_serial(self):
		"""Block saving if any renewal for the same Tally serial exists in the database."""
		serial = self.tally_serial or self.tss_tally_serial
		if not serial:
			return

		dup = check_duplicate_renewal(serial, current_renewal_name=self.name)
		if dup:
			party = dup.get("cc_acc_name") or dup.get("cc_contact") or "this party"
			exec_name = dup.get("executive_full_name") or dup.get("crm_ex_1") or dup.get("owner") or "another executive"
			renewal_id = dup.get("name")
			creation_date = dup.get("creation_date") or ""

			msg = _(
				'<div style="border: 2px solid #ef4444; background-color: #fef2f2; padding: 15px; border-radius: 6px; font-family: sans-serif; text-align: left;">'
				'  <h4 style="color: #b91c1c; margin-top: 0; font-weight: bold; font-size: 16px; display: flex; align-items: center; gap: 8px;">'
				'    🚨 Active Duplicate Tally Serial Blocked!'
				'  </h4>'
				'  <hr style="border-top: 1px solid #fecaca; margin: 10px 0;">'
				'  <p style="margin: 0; font-size: 14px; line-height: 1.5; color: #1f2937;">'
				'    A renewal for Tally Serial <b>{0}</b> ({1}) has already been managed by <b>{2}</b> (Renewal #{3}).'
				'  </p>'
				'  <p style="margin: 8px 0 0 0; font-size: 14px; line-height: 1.5; color: #1f2937;">'
				'    Active follow-ups are ongoing (<b>{4}</b> days since last remark).'
				'  </p>'
				'  <p style="margin: 12px 0 0 0; font-size: 13px; font-style: italic; color: #b91c1c; font-weight: bold;">'
				'    You cannot save a duplicate renewal for this serial while follow-ups are active.'
				'  </p>'
				'</div>'
			).format(serial, party, exec_name, renewal_id, dup.get("days_inactive", 0))

			frappe.throw(msg, title=_("Duplicate Tally Serial Blocked"))

	def sync_primary_contact_to_all_contacts(self):
		"""Ensure mobile number, contact person, and email are preserved in All Contacts history."""
		name = (self.cc_contact or "").strip()
		mobile = (self.cc_mobile or "").strip()
		phone = (self.cc_phone or "").strip()
		email = (self.cc_email or "").strip()

		target_phone = mobile or phone

		if not name and not target_phone and not email:
			return

		if not getattr(self, "all_contacts", None):
			self.all_contacts = []

		phone_exists = False
		if target_phone:
			for row in self.all_contacts:
				if (row.contact_phone or "").strip() == target_phone:
					phone_exists = True
					if name and not (row.contact_name or "").strip():
						row.contact_name = name
					if email and not (row.contact_email or "").strip():
						row.contact_email = email
					break

		if target_phone and not phone_exists:
			self.append("all_contacts", {
				"contact_name": name,
				"contact_phone": target_phone,
				"contact_email": email,
			})
		elif not target_phone:
			has_match = any(
				(email and (r.contact_email or "").strip() == email) or
				(name and (r.contact_name or "").strip() == name)
				for r in self.all_contacts
			)
			if not has_match:
				self.append("all_contacts", {
					"contact_name": name,
					"contact_phone": "",
					"contact_email": email,
				})

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
			self.remarks = ""
		elif getattr(self, "custom_activities", None) and not self.last_remark:
			self.last_remark = self.custom_activities[-1].remark

	def render_old_remarks_html(self):
		"""Render old remarks text and activities into a formatted timeline."""
		html = []
		if self.old_remarks and self.old_remarks.strip():
			html.append(f'''
				<div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 14px 18px; margin-bottom: 16px;">
					<div style="font-weight: 600; font-size: 13px; color: #334155; margin-bottom: 8px;">
						📄 Imported Past Remarks (Last 2 Years)
					</div>
					<div style="white-space: pre-wrap; font-size: 13px; line-height: 1.6; color: #1e293b;">{self.old_remarks.strip()}</div>
				</div>
			''')

		if hasattr(self, "old_remarks_activities") and self.old_remarks_activities:
			html.append('<div style="font-weight: 600; font-size: 13px; color: #334155; margin-bottom: 8px;">📜 Remarks History Log</div>')
			html.append('<div class="old-remarks-timeline" style="border-left: 2px solid #cbd5e1; padding-left: 20px; margin-left: 8px;">')
			for row in self.old_remarks_activities:
				user = getattr(row, "user", None) or "Executive"
				dt = getattr(row, "date_time", None) or getattr(row, "creation", None)
				rem = getattr(row, "remark", None) or ""
				if rem:
					html.append(f'''
						<div style="margin-bottom: 12px;">
							<div style="font-size: 12px; color: #64748b;"><b>{user}</b> • {dt or ""}</div>
							<div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 6px; padding: 8px 12px; font-size: 13px; color: #0f172a; margin-top: 3px; white-space: pre-wrap;">{rem}</div>
						</div>
					''')
			html.append('</div>')

		if not html:
			self.old_remarks_html = "<div style='color:#94a3b8; font-style:italic; padding:10px;'>No past remarks imported yet. Remarks imported via Excel with Serial Number will appear here.</div>"
		else:
			self.old_remarks_html = "".join(html)

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
				filters={"parent": self.name, "parenttype": "Hbs Tally Renewal", "parentfield": "custom_activities"},
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
			self.activity = "<div style='color:#a0aec0; font-style:italic; padding:10px;'>No activities recorded yet. Click <b>+ Follow-up</b> to log notes.</div>"
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
				from frappe.utils import get_datetime
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
					<div style="background: #fcfcfc; border: 1px solid #d1d8dd; border-radius: 8px; padding: 10px 14px; font-size: 13px; color: #1c2126; white-space: pre-wrap; line-height: 1.35; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">{remark_text.strip()}</div>
				</div>
			''')

		html.append('</div>')
		self.activity = "".join(html)


@frappe.whitelist()
def check_duplicate_renewal(serial=None, current_renewal_name=None):
	"""Check if a renewal already exists for the given Tally serial number, regardless of status."""
	if not serial or not str(serial).strip():
		return None

	raw_serial = str(serial).strip()
	clean_digits = "".join(filter(str.isdigit, raw_serial))
	if not clean_digits:
		return None

	params = {
		"serial_raw": raw_serial,
		"serial_clean": clean_digits,
	}

	where = "(tally_serial IN (%(serial_raw)s, %(serial_clean)s) OR tss_tally_serial IN (%(serial_raw)s, %(serial_clean)s))"

	if current_renewal_name and str(current_renewal_name).strip() and not str(current_renewal_name).startswith("new-"):
		where += " AND name != %(current_name)s"
		params["current_name"] = str(current_renewal_name).strip()

	duplicates = frappe.db.sql(f"""
		SELECT name, cc_acc_name, cc_contact, tally_serial, tss_tally_serial,
		       crm_ex_1, owner, creation, last_remarks_date, contact_on,
		       crm_status, crm_stage
		FROM `tabHbs Tally Renewal`
		WHERE {where}
		ORDER BY creation DESC
		LIMIT 1
	""", params, as_dict=True)

	if not duplicates:
		return None

	dup = duplicates[0]
	exec_user = dup.get("crm_ex_1") or dup.get("owner")
	exec_name = frappe.db.get_value("User", exec_user, "full_name") or exec_user
	dup["executive_full_name"] = exec_name
	dup["creation_date"] = frappe.utils.formatdate(dup.creation, "dd/MM/yyyy") if dup.creation else ""

	is_lost = (
		str(dup.get("crm_status") or "").strip().lower() == "lost"
		or str(dup.get("crm_stage") or "").strip().lower() == "lost"
	)
	dup["is_lost"] = is_lost

	last_date = dup.get("last_remarks_date") or dup.get("contact_on") or dup.get("creation")
	if last_date:
		today = frappe.utils.getdate()
		last_d = frappe.utils.getdate(last_date)
		days_diff = frappe.utils.date_diff(today, last_d)
		dup["days_inactive"] = max(0, days_diff)
		dup["last_remarks_date_formatted"] = frappe.utils.formatdate(last_d, "dd/MM/yyyy")
	else:
		dup["days_inactive"] = 0
		dup["last_remarks_date_formatted"] = ""

	dup["is_inactive"] = is_lost or (dup.get("days_inactive", 0) > 15)

	return dup


@frappe.whitelist()
def take_over_renewal(renewal_name):
	"""Allow an executive to take over a dormant renewal, or a lost renewal without checking."""
	if not renewal_name:
		frappe.throw(_("Renewal Name is required."), title=_("Invalid Request"))

	doc = frappe.get_doc("Hbs Tally Renewal", renewal_name)
	user = frappe.session.user

	if doc.crm_ex_1 == user:
		frappe.throw(_("You are already assigned as Executive 1 on this renewal."), title=_("Invalid Action"))

	is_lost = (
		str(doc.crm_status or "").strip().lower() == "lost"
		or str(doc.crm_stage or "").strip().lower() == "lost"
	)

	if not is_lost:
		last_date = doc.last_remarks_date or doc.contact_on or doc.creation
		days_diff = frappe.utils.date_diff(frappe.utils.getdate(), frappe.utils.getdate(last_date))

		if days_diff <= 15:
			frappe.throw(
				_("This renewal has active follow-ups ({0} days ago) and cannot be taken over.").format(days_diff),
				title=_("Renewal Active")
			)
	else:
		days_diff = 0

	user = frappe.session.user
	user_full_name = frappe.db.get_value("User", user, "full_name") or user

	old_exec = doc.crm_ex_1 or doc.owner or "Previous Executive"
	old_exec_name = frappe.db.get_value("User", old_exec, "full_name") or old_exec

	# Reassign Executive 1 to current user & reset follow-up date to today
	doc.crm_ex_1 = user

	if is_lost:
		doc.crm_status = "PENDING"
		doc.crm_stage = "IN FOLLOW-UP"

	doc.follow_up_date = frappe.utils.today()
	doc.follow_up_time = frappe.utils.nowtime()

	if is_lost:
		remark_text = f"⚡ Lost renewal revived & taken over by {user_full_name} ({user}) (Previous Executive: {old_exec_name})."
	else:
		remark_text = f"⚡ Renewal taken over by {user_full_name} ({user}) due to {days_diff} days inactivity (Previous Executive: {old_exec_name})."

	doc.append("custom_activities", {
		"user": user,
		"date_time": frappe.utils.now_datetime(),
		"remark": remark_text
	})
	doc.last_remark = remark_text
	doc.last_remarks_date = frappe.utils.nowdate()
	doc.contact_on = doc.last_remarks_date
	doc.flags.in_takeover = True
	doc.flags.ignore_permissions = True
	frappe.flags.in_takeover = True
	try:
		doc.save(ignore_permissions=True)
	finally:
		frappe.flags.in_takeover = False
	frappe.db.set_value("Hbs Tally Renewal", doc.name, "owner", user)
	frappe.db.commit()

	msg = _("Lost renewal #{0} has been successfully taken over and revived by you!").format(doc.name) if is_lost else _("Renewal #{0} has been successfully taken over by you!").format(doc.name)

	return {
		"status": "success",
		"message": msg
	}


@frappe.whitelist()
def log_follow_up(name, follow_up_date=None, remark=None, crm_status=None, crm_stage=None, crm_lost_remarks=None):
	"""Save follow up note, update status/stage, and record to activity timeline."""
	if not name:
		frappe.throw(_("Record name is required."))
	if not remark or not str(remark).strip():
		frappe.throw(_("Remark is required to log follow-up."))

	doc = frappe.get_doc("Hbs Tally Renewal", name)
	user = frappe.session.user
	if not is_owner_or_admin(user) and not has_permission(doc, "write", user):
		frappe.throw(_("You do not have permission to log follow-up on this renewal."), title=_("Permission Denied"))
	if follow_up_date:
		if frappe.utils.getdate(follow_up_date) < frappe.utils.getdate(frappe.utils.nowdate()):
			frappe.throw(_("Follow-up date cannot be smaller than current date ({0}).").format(frappe.utils.nowdate()), title=_("Invalid Follow-up Date"))
		doc.follow_up_date = follow_up_date
	if crm_status:
		doc.crm_status = crm_status
	if crm_stage:
		doc.crm_stage = crm_stage
	if crm_lost_remarks is not None:
		doc.crm_lost_remarks = crm_lost_remarks
	elif crm_status == "Lost" and remark:
		doc.crm_lost_remarks = str(remark).strip()

	doc.last_remarks_date = frappe.utils.nowdate()
	doc.contact_on = doc.last_remarks_date
	doc.last_updated = frappe.utils.nowdate()

	user_email = frappe.session.user if frappe.session and frappe.session.user else "System"
	clean_rem = str(remark).strip()

	doc.append("custom_activities", {
		"user": user_email,
		"date_time": frappe.utils.now_datetime(),
		"remark": clean_rem
	})
	doc.last_remark = clean_rem
	doc.remarks = ""
	doc.render_activity_html()
	if hasattr(doc, "render_old_remarks_html"):
		doc.render_old_remarks_html()
	doc.flags.in_follow_up = True
	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return {"status": "success", "message": _("Follow-up logged successfully!")}


def build_tally_portal_url(base_url, apikey, serial):
	"""Build full Tally Portal API URL supporting base endpoint, placeholders, or full query URL."""
	if not base_url:
		base_url = "https://tallysolutions.com/api/v1/serialexpiry?apikey=<APIKEY>&slnum=<SERIAL>"

	base_url = base_url.strip()

	# 1. Handle template placeholders like {apikey}, {serial}, {slnum}
	if "{serial}" in base_url or "{slnum}" in base_url or "{apikey}" in base_url:
		formatted = base_url.replace("{apikey}", apikey)
		formatted = formatted.replace("{serial}", str(serial)).replace("{slnum}", str(serial))
		return formatted

	# 2. Parse query parameters and ensure apikey and slnum are properly set
	parsed = urlparse(base_url)
	if parsed.query:
		params = parse_qs(parsed.query)
		params["apikey"] = [apikey]
		params["slnum"] = [str(serial)]
		new_query = urlencode({k: v[0] for k, v in params.items()})
		return urlunparse(parsed._replace(query=new_query))

	# 3. Standard base URL without query parameters
	clean_base = base_url.rstrip("?").rstrip("&")
	return f"{clean_base}?apikey={apikey}&slnum={serial}"


def get_tally_portal_credentials():
	"""Retrieve and validate Tally Portal API credentials from Hbs CRM Settings."""
	base_url = (frappe.db.get_single_value("Hbs CRM Settings", "tally_portal_url") or "").strip()
	primary_key = (frappe.db.get_single_value("Hbs CRM Settings", "tally_portal_apikey") or "").strip()
	secondary_key = (frappe.db.get_single_value("Hbs CRM Settings", "tally_portal_apikey_secondary") or "").strip()

	if not base_url:
		frappe.throw(
			_("<b>Tally Portal API URL is missing!</b><br>Please configure <b>Tally Portal API URL</b> in <a href='/app/hbs-crm-settings' target='_blank'><b>Hbs CRM Settings</b></a> before syncing."),
			title=_("API Configuration Missing")
		)

	if not primary_key:
		frappe.throw(
			_("<b>Primary API Key is missing!</b><br>Please configure <b>Primary API Key</b> in <a href='/app/hbs-crm-settings' target='_blank'><b>Hbs CRM Settings</b></a> before syncing."),
			title=_("API Configuration Missing")
		)

	keys_to_try = [primary_key]
	if secondary_key and secondary_key != primary_key:
		keys_to_try.append(secondary_key)

	return base_url, keys_to_try


@frappe.whitelist()
def check_portal(name, only_expiry=False):
	"""Check Tally Portal API using credentials from Hbs CRM Settings and populate fields.
	If only_expiry is True, only portal_expiry_date is updated (used on lead open).
	If only_expiry is False, all portal data fields are updated (used on manual portal sync).
	"""
	only_expiry = bool(frappe.utils.cint(only_expiry) or (isinstance(only_expiry, str) and only_expiry.lower() in ("true", "1")) or only_expiry is True)

	doc = frappe.get_doc("Hbs Tally Renewal", name)
	user = frappe.session.user if frappe.session else "System"
	if not is_owner_or_admin(user) and not has_permission(doc, "read", user):
		frappe.throw(_("You do not have permission to sync this renewal."), title=_("Permission Denied"))

	serial = str(doc.tally_serial or "").strip()
	if not serial:
		frappe.throw(_("Tally Serial Number is required."), title=_("Serial Number Missing"))

	base_url, keys_to_try = get_tally_portal_credentials()

	res = None
	last_err = "Serial not mapped or inactive in portal"

	try:
		for apikey in keys_to_try:
			url = build_tally_portal_url(base_url, apikey, serial)
			try:
				r = requests.get(url, timeout=6)
				resp = r.json() if r.status_code == 200 else None
			except Exception:
				resp = None

			if resp and isinstance(resp, dict):
				exp_det = resp.get("expiry_details")
				if isinstance(exp_det, dict):
					serial_status = frappe.utils.cint(exp_det.get("serial_status"))
					has_data = bool(exp_det.get("serial_data"))
					if serial_status == 1 or has_data:
						res = resp
						break
					else:
						api_msg = exp_det.get("message")
						if api_msg and str(api_msg).strip().upper() != "SUCCESS":
							last_err = str(api_msg).strip()
						else:
							last_err = "Serial not mapped or inactive in portal"
				elif isinstance(exp_det, str) and exp_det.strip():
					last_err = exp_det.strip()
				elif resp.get("message"):
					last_err = str(resp.get("message")).strip()

		doc.response = json.dumps(res or resp, indent=2)

		if res and isinstance(res, dict):
			exp_det = res.get("expiry_details") if isinstance(res.get("expiry_details"), dict) else {}
			data = exp_det.get("serial_data", {}) if isinstance(exp_det.get("serial_data"), dict) else {}
			synced_fields = []
			unsynced_fields = []

			if not only_expiry:
				# 1. Tally Flavour (Ensure 'Tally Prime' prefix)
				raw_flavour = data.get("flavour")
				if raw_flavour and str(raw_flavour).strip():
					val_f = str(raw_flavour).strip()
					if not val_f.lower().startswith("tally prime") and not val_f.lower().startswith("tally.prime"):
						formatted_flavour = f"Tally Prime {val_f}"
					else:
						formatted_flavour = val_f
					doc.flavour = formatted_flavour
					synced_fields.append("Tally Flavour")
				else:
					unsynced_fields.append("Tally Flavour")

				# 2. Edition
				if data.get("edition"):
					doc.edition = data.get("edition")
					synced_fields.append("Edition")
				else:
					unsynced_fields.append("Edition")

				# 3. Release
				if data.get("release"):
					doc.release = data.get("release")
					synced_fields.append("Release / Version")
				else:
					unsynced_fields.append("Release / Version")

				# 4. Product Version
				if data.get("release"):
					doc.product_ver = data.get("release")
					synced_fields.append("Product Version")
				else:
					unsynced_fields.append("Product Version")

				# 5. Account Name
				if data.get("org_name"):
					doc.portal_acc_name = data.get("org_name")
					synced_fields.append("Portal Account Name")
				else:
					unsynced_fields.append("Portal Account Name")

				# 6. Contact Name
				if data.get("contact_name"):
					doc.portal_contact = data.get("contact_name")
					synced_fields.append("Portal Contact Person")
				else:
					unsynced_fields.append("Portal Contact Person")

				# 7. Contact Email
				if data.get("contact_email"):
					doc.portal_email = data.get("contact_email")
					synced_fields.append("Portal Email")
				else:
					unsynced_fields.append("Portal Email")

				# 8. Contact Mobile
				if data.get("contact_mobile"):
					doc.portal_mobile = data.get("contact_mobile")
					synced_fields.append("Portal Mobile")
				else:
					unsynced_fields.append("Portal Mobile")

				# 9. Priority
				if data.get("tss_priority"):
					doc.ts9_priority = data.get("tss_priority")
					synced_fields.append("TS9 Priority")
				else:
					unsynced_fields.append("TS9 Priority")

				# 10. Business Segment
				if data.get("business_segment"):
					doc.business_segment = data.get("business_segment")
					synced_fields.append("Business Segment")
				else:
					unsynced_fields.append("Business Segment")

				# 11. Account ID
				if data.get("account_id"):
					doc.account_id = data.get("account_id")
					synced_fields.append("Account ID")
				else:
					unsynced_fields.append("Account ID")

				# 12. Admin ID
				if data.get("account_admin_email_id"):
					doc.admin_id = data.get("account_admin_email_id")
					synced_fields.append("Admin Email ID")
				else:
					unsynced_fields.append("Admin Email ID")

				# 13. MAU
				if data.get("mau") is not None:
					doc.mau = str(data.get("mau"))
					synced_fields.append("Monthly Active Users (MAU)")
				else:
					unsynced_fields.append("Monthly Active Users (MAU)")

				# 14. QAU
				if data.get("qau") is not None:
					doc.qau = str(data.get("qau"))
					synced_fields.append("Quarterly Active Users (QAU)")
				else:
					unsynced_fields.append("Quarterly Active Users (QAU)")

				# 15. RFM Segment
				if data.get("rfm_segment"):
					doc.rfm_segment = data.get("rfm_segment")
					synced_fields.append("RFM Segment")
				else:
					unsynced_fields.append("RFM Segment")

				# Activation Date
				act_str = data.get("activation_date")
				if act_str:
					parsed_act = safe_parse_portal_date(act_str)
					if parsed_act:
						doc.acc_start_date = parsed_act
						synced_fields.append("Activation Date")

			# Portal Expiry Date (Always synced)
			exp_str = data.get("expiry")
			if exp_str:
				parsed_date = safe_parse_portal_date(exp_str)
				if parsed_date:
					doc.portal_expiry_date = parsed_date
					synced_fields.append("Portal Expiry Date")
				else:
					unsynced_fields.append("Portal Expiry Date")
			else:
				unsynced_fields.append("Portal Expiry Date")

			doc.status = "success"
			doc.error = None
			if not only_expiry:
				doc.crm_ref = "ACTIVE"
			if len(synced_fields) > 0:
				doc.last_updated_api = frappe.utils.nowdate()
			doc.flags.in_api_sync = True
			doc.save(ignore_permissions=True)
			frappe.db.commit()

			return {
				"status": "success",
				"message": _("Portal expiry synced successfully!") if only_expiry else _("Portal details fetched successfully!"),
				"synced_count": len(synced_fields),
				"unsynced_count": len(unsynced_fields),
				"synced_fields": synced_fields,
				"unsynced_fields": unsynced_fields,
				"portal_expiry_date": str(doc.portal_expiry_date or "")
			}
		else:
			if not only_expiry:
				doc.crm_ref = "MOVED OUT"
				doc.status = "error"
				doc.error = str(last_err)
				doc.flags.in_api_sync = True
				doc.save(ignore_permissions=True)
				frappe.db.commit()
			return {"status": "error", "message": last_err}
	except Exception as e:
		if not only_expiry:
			doc.status = "error"
			doc.error = str(e)
			doc.flags.in_api_sync = True
			doc.save(ignore_permissions=True)
			frappe.db.commit()
		frappe.throw(str(e))


@frappe.whitelist()
def assign_executive(name=None, names=None, executive_1=None, executive=None):
	"""Assign executive directly on doc or multiple docs (Owner / Admin only)."""
	user = frappe.session.user if frappe.session else "System"
	if not is_owner_or_admin(user):
		frappe.throw(_("Only Owner and Administrator can assign executives."), title=_("Permission Denied"))

	exec_val = executive_1 or executive
	updates = {}
	if exec_val is not None:
		updates["crm_ex_1"] = exec_val
		updates["owner"] = exec_val

	target_names = []
	if names:
		import json
		if isinstance(names, str):
			try:
				target_names = json.loads(names)
			except Exception:
				target_names = [names]
		elif isinstance(names, list):
			target_names = names
	elif name:
		target_names = [name]

	if updates and target_names:
		for n in target_names:
			frappe.db.set_value("Hbs Tally Renewal", n, updates, update_modified=True)
		frappe.db.commit()

	return {"status": "success", "message": _("Executive assigned successfully.")}


@frappe.whitelist()
def bulk_update_renewal_fields(names, updates=None, remark=None, quote_item=None):
	"""Bulk or quick update fields on Hbs Tally Renewal records (Owner / Admin only)."""
	user = frappe.session.user if frappe.session else "System"
	if not is_owner_or_admin(user):
		frappe.throw(_("Only Owner and Administrator can update these records."), title=_("Permission Denied"))

	target_names = []
	if names:
		if isinstance(names, str):
			try:
				target_names = json.loads(names)
			except Exception:
				target_names = [names]
		elif isinstance(names, list):
			target_names = names

	if not target_names:
		frappe.throw(_("No records selected to update."))

	update_dict = {}
	if updates:
		if isinstance(updates, str):
			try:
				updates = json.loads(updates)
			except Exception:
				updates = {}
		if isinstance(updates, dict):
			allowed_fields = {
				"crm_status", "crm_stage", "crm_ref",
				"follow_up_date", "last_remarks_date", "last_remark"
			}
			for k, v in updates.items():
				if k in allowed_fields and v is not None and str(v).strip() != "":
					update_dict[k] = v

	remark_text = str(remark).strip() if remark else ""
	quote_item = str(quote_item).strip() if quote_item else ""
	if not update_dict and not remark_text and not quote_item:
		frappe.throw(_("Please provide at least one field value, quote item, or remark to update."))

	prod = None
	if quote_item:
		if frappe.db.exists("Hbs Product", quote_item):
			prod = frappe.db.get_value(
				"Hbs Product",
				quote_item,
				["name", "item_name", "rate", "tax", "hsn", "description"],
				as_dict=True,
			)
		else:
			prod = frappe.db.get_value(
				"Hbs Product",
				{"item_name": quote_item},
				["name", "item_name", "rate", "tax", "hsn", "description"],
				as_dict=True,
			)
		if not prod:
			frappe.throw(_("Selected Quote Product {0} not found.").format(quote_item))

	for name in target_names:
		if remark_text or quote_item:
			doc = frappe.get_doc("Hbs Tally Renewal", name)
			for k, v in update_dict.items():
				setattr(doc, k, v)

			if quote_item and prod:
				doc.set("items", [])
				rate = frappe.utils.flt(prod.rate) or 0
				tax_pct = frappe.utils.flt(prod.tax) or 0
				tax_amt = (rate * tax_pct) / 100.0
				amount = rate + tax_amt
				doc.append("items", {
					"item_name": prod.name,
					"description": prod.description or "",
					"qty": 1,
					"rate": rate,
					"tax": tax_pct,
					"tax_amount": tax_amt,
					"hsn": prod.hsn or "",
					"discount_amount": 0,
					"amount": amount,
				})
				doc.calculate_totals()

			if remark_text:
				if doc.crm_status == "Lost":
					doc.crm_lost_remarks = remark_text

				if "last_remarks_date" not in update_dict:
					doc.last_remarks_date = frappe.utils.nowdate()
					doc.contact_on = doc.last_remarks_date
				else:
					doc.contact_on = doc.last_remarks_date

				user_email = frappe.session.user if frappe.session and frappe.session.user else "System"
				doc.append("custom_activities", {
					"user": user_email,
					"date_time": frappe.utils.now_datetime(),
					"remark": remark_text
				})
				if "last_remark" in update_dict:
					doc.last_remark = update_dict["last_remark"]
				else:
					doc.last_remark = remark_text
				doc.render_activity_html()
				if hasattr(doc, "render_old_remarks_html"):
					doc.render_old_remarks_html()
			else:
				if "last_remarks_date" in update_dict:
					doc.contact_on = update_dict["last_remarks_date"]
				elif "last_remark" in update_dict and "last_remarks_date" not in update_dict:
					doc.last_remarks_date = frappe.utils.nowdate()
					doc.contact_on = doc.last_remarks_date

			doc.last_updated = frappe.utils.nowdate()
			doc.flags.in_follow_up = True
			doc.save(ignore_permissions=True)
		else:
			doc_updates = dict(update_dict)
			if "last_remarks_date" in doc_updates:
				doc_updates["contact_on"] = doc_updates["last_remarks_date"]
			elif "last_remark" in doc_updates and "last_remarks_date" not in doc_updates:
				doc_updates["last_remarks_date"] = frappe.utils.nowdate()
				doc_updates["contact_on"] = doc_updates["last_remarks_date"]
			doc_updates["last_updated"] = frappe.utils.nowdate()
			frappe.db.set_value("Hbs Tally Renewal", name, doc_updates, update_modified=True)

	frappe.db.commit()
	return {
		"status": "success",
		"message": _("Successfully updated {0} record(s).").format(len(target_names))
	}


@frappe.whitelist()
def check_selected_portal(names):
	user = frappe.session.user if frappe.session else "System"
	if not is_owner_or_admin(user):
		frappe.throw(_("Only Owner and Administrator can sync Tally Portal API."), title=_("Permission Denied"))

	if isinstance(names, str):
		names = json.loads(names)

	if not names:
		return {"status": "info", "message": _("No records selected.")}

	# Filter: only sync records where reference status (crm_ref) is Active or Moved Out
	records = frappe.get_all(
		"Hbs Tally Renewal",
		filters={"name": ["in", names]},
		fields=["name", "crm_ref"]
	)

	valid_statuses = {"ACTIVE", "MOVED OUT"}
	to_sync = [r.name for r in records if (r.crm_ref or "").strip().upper() in valid_statuses]
	skipped = len(names) - len(to_sync)

	if not to_sync:
		return {
			"status": "info",
			"message": _("No selected records have Reference Status as Active or Moved Out ({0} skipped).").format(skipped),
			"success_count": 0,
			"failed_count": 0,
			"skipped_count": skipped,
			"total_fields_updated": 0
		}

	base_url, keys_to_try = get_tally_portal_credentials()

	success = 0
	failed = 0
	total_fields_updated = 0
	for name in to_sync:
		try:
			res = check_portal(name)
			if res and res.get("status") == "success":
				success += 1
				total_fields_updated += res.get("synced_count", 0)
			else:
				failed += 1
		except Exception:
			failed += 1

	msg = _("Portal sync completed! {0} records updated ({1} fields populated), {2} failed.").format(success, total_fields_updated, failed)
	if skipped > 0:
		msg += _(" {0} records skipped (Reference Status not Active or Moved Out).").format(skipped)

	return {
		"status": "success",
		"message": msg,
		"success_count": success,
		"failed_count": failed,
		"skipped_count": skipped,
		"total_fields_updated": total_fields_updated
	}


@frappe.whitelist()
def get_all_portal_sync_candidates():
	"""Return all Hbs Tally Renewal records eligible for Tally Portal API sync."""
	user = frappe.session.user if frappe.session else "System"
	if not is_owner_or_admin(user):
		frappe.throw(_("Only Owner and Administrator can sync Tally Portal API."), title=_("Permission Denied"))

	valid_statuses = (
		"ACTIVE", "MOVED OUT",
		"Active", "Moved Out",
		"active", "moved out"
	)
	return frappe.get_all(
		"Hbs Tally Renewal",
		filters={
			"tally_serial": ["is", "set"],
			"crm_ref": ["in", valid_statuses]
		},
		pluck="name",
		limit_page_length=0,
		order_by="creation desc"
	)


@frappe.whitelist()
def sync_portal_batch(names):
	"""Sync a batch of Hbs Tally Renewal records with Tally Portal API and return detailed per-record results."""
	user = frappe.session.user if frappe.session else "System"
	if not is_owner_or_admin(user):
		frappe.throw(_("Only Owner and Administrator can sync Tally Portal API."), title=_("Permission Denied"))

	if isinstance(names, str):
		try:
			names = json.loads(names)
		except Exception:
			names = [names]

	if not names:
		return {
			"status": "success",
			"success_count": 0,
			"failed_count": 0,
			"total_fields_updated": 0,
			"results": []
		}

	results = []
	success = 0
	failed = 0
	total_fields_updated = 0
	valid_statuses = {"ACTIVE", "MOVED OUT"}

	for name in names:
		try:
			row = frappe.db.get_value(
				"Hbs Tally Renewal",
				name,
				["name", "cc_acc_name", "portal_acc_name", "tally_serial", "crm_ref"],
				as_dict=True
			)
			if not row:
				failed += 1
				results.append({
					"name": name,
					"company_name": "-",
					"serial": "-",
					"status": "failed",
					"message": "Record not found"
				})
				continue

			company = (row.get("cc_acc_name") or row.get("portal_acc_name") or str(name)).strip()
			serial = str(row.get("tally_serial") or "").strip()
			if not serial:
				failed += 1
				results.append({
					"name": name,
					"company_name": company,
					"serial": "-",
					"status": "failed",
					"message": "Missing Tally Serial Number"
				})
				continue

			if (row.get("crm_ref") or "").strip().upper() not in valid_statuses:
				failed += 1
				results.append({
					"name": name,
					"company_name": company,
					"serial": serial,
					"status": "skipped",
					"message": f"Skipped: Reference status ({row.get('crm_ref') or 'Blank'}) not Active/Moved Out"
				})
				continue

			res = check_portal(name, only_expiry=False)
			if res and res.get("status") == "success":
				success += 1
				synced_count = res.get("synced_count", 0)
				total_fields_updated += synced_count
				results.append({
					"name": name,
					"company_name": company,
					"serial": serial,
					"status": "success",
					"fields_updated": synced_count,
					"message": f"Synced ({synced_count} fields updated)"
				})
			else:
				failed += 1
				err_msg = (res.get("message") if res else "") or "Portal sync returned no data"
				if str(err_msg).strip().upper() == "SUCCESS":
					err_msg = "Serial not mapped or inactive in portal"
				results.append({
					"name": name,
					"company_name": company,
					"serial": serial,
					"status": "failed",
					"message": err_msg
				})
		except Exception as e:
			failed += 1
			results.append({
				"name": name,
				"company_name": "-",
				"serial": "-",
				"status": "failed",
				"message": str(e)
			})

	return {
		"status": "success",
		"success_count": success,
		"failed_count": failed,
		"total_fields_updated": total_fields_updated,
		"results": results
	}


@frappe.whitelist()
def sync_all_portal_records():
	"""Sync all Hbs Tally Renewal records that have a tally_serial."""
	user = frappe.session.user if frappe.session else "System"
	if not is_owner_or_admin(user):
		frappe.throw(_("Only Owner and Administrator can sync Tally Portal API."), title=_("Permission Denied"))

	base_url, keys_to_try = get_tally_portal_credentials()
	records = frappe.get_all(
		"Hbs Tally Renewal",
		filters={"tally_serial": ["is", "set"]},
		pluck="name"
	)
	if not records:
		return {"status": "info", "message": _("No records found with Tally Serial Number.")}

	success = 0
	failed = 0
	total_fields_updated = 0
	for r_name in records:
		try:
			res = check_portal(r_name)
			if res and res.get("status") == "success":
				success += 1
				total_fields_updated += res.get("synced_count", 0)
			else:
				failed += 1
		except Exception:
			failed += 1

	return {
		"status": "success",
		"message": _("Portal sync completed! {0} records updated ({1} fields populated), {2} failed/moved out.").format(success, total_fields_updated, failed),
		"success_count": success,
		"failed_count": failed,
		"total_fields_updated": total_fields_updated
	}


@frappe.whitelist()
def get_activity_html(name):
	"""Endpoint to return rendered All Activities timeline HTML to Desk UI."""
	if not name:
		return "<div style='color:#a0aec0; font-style:italic; padding:10px;'>No activities recorded yet. Click <b>+ Follow-up</b> to log notes.</div>"
	doc = frappe.get_doc("Hbs Tally Renewal", name)
	doc.render_activity_html()
	return doc.activity


@frappe.whitelist()
def check_user_hierarchy_role(user=None):
	"""Check if current or given user is Owner or Admin safely without throwing permission errors."""
	if not user:
		user = frappe.session.user if frappe.session else "Administrator"
	return {
		"is_owner_or_admin": is_owner_or_admin(user)
	}



# Shared auth/hierarchy helpers — single source of truth in utils.py
from hbs_crm.hbs_crm.utils import (
	is_owner_or_admin,
	is_admin_owner_or_manager,
	get_subordinates_from_hierarchy,
	get_logged_in_user_context,
)


@frappe.whitelist()
def get_overdue_renewal_summary():
	"""Return count and cutoff date of active renewals with no follow-up for >= 10 days scoped by user role."""

	user = frappe.session.user
	cutoff_date = frappe.utils.add_days(frappe.utils.nowdate(), -10)
	is_admin_mgr = is_admin_owner_or_manager(user)

	if is_admin_mgr:
		count = frappe.db.sql("""
			SELECT COUNT(*) FROM `tabHbs Tally Renewal`
			WHERE (crm_status NOT IN ('SOLD', 'LOST', 'WON', 'Sold', 'Lost', 'Won') OR crm_status IS NULL OR crm_status = '')
			  AND (
				(last_remarks_date IS NOT NULL AND last_remarks_date <= %s)
				OR (last_remarks_date IS NULL AND DATE(creation) <= %s)
			  )
		""", (cutoff_date, cutoff_date))[0][0]
	else:
		subordinates = get_subordinates_from_hierarchy(user)
		team = list(set([user] + subordinates))
		escaped_team = ", ".join([frappe.db.escape(u) for u in team])
		count = frappe.db.sql(f"""
			SELECT COUNT(*) FROM `tabHbs Tally Renewal`
			WHERE (crm_status NOT IN ('SOLD', 'LOST', 'WON', 'Sold', 'Lost', 'Won') OR crm_status IS NULL OR crm_status = '')
			  AND (crm_ex_1 IN ({escaped_team}) OR owner IN ({escaped_team}))
			  AND (
				(last_remarks_date IS NOT NULL AND last_remarks_date <= %s)
				OR (last_remarks_date IS NULL AND DATE(creation) <= %s)
			  )
		""", (cutoff_date, cutoff_date))[0][0]

	return {
		"count": count or 0,
		"cutoff_date": cutoff_date,
		"is_admin_or_manager": is_admin_mgr
	}




def get_permission_query_conditions(user=None):
	"""Permission query hook for Hbs Tally Renewal based on User Hierarchy."""
	if not user:
		user = frappe.session.user

	if is_owner_or_admin(user):
		return ""

	# Managers and Owners in Hbs User Hierarchy can see all renewals
	role_type = frappe.db.get_value("Hbs User Hierarchy", {"user": user}, "role_type")
	if role_type in ("Manager", "Owner"):
		return ""

	subordinates = get_subordinates_from_hierarchy(user)
	team_members = list(set([user] + subordinates))
	team_escaped = ", ".join([frappe.db.escape(u) for u in team_members])

	return f"`tabHbs Tally Renewal`.`crm_ex_1` IN ({team_escaped})"


def has_permission(doc, ptype="read", user=None):
	"""Permission hook for Hbs Tally Renewal."""
	if not user:
		user = frappe.session.user

	if is_owner_or_admin(user):
		return True

	if ptype == "import":
		return False

	# Managers in Hbs User Hierarchy can view, edit, email, and print all renewals
	role_type = frappe.db.get_value("Hbs User Hierarchy", {"user": user}, "role_type")
	if role_type in ("Manager", "Owner") and ptype in ("read", "write", "save", "email", "print"):
		return True

	if getattr(frappe.flags, "in_takeover", False):
		return True

	if not doc:
		return True

	subordinates = get_subordinates_from_hierarchy(user)
	team_members = set([user] + subordinates)
	if isinstance(doc, str):
		if not frappe.db.exists("Hbs Tally Renewal", doc):
			return True
		doc_obj = frappe.get_doc("Hbs Tally Renewal", doc)
	else:
		doc_obj = doc

	if getattr(doc_obj, "flags", None) and getattr(doc_obj.flags, "in_takeover", False):
		return True

	# 1. Check in-memory doc values or new doc creation
	if (
		ptype == "create"
		or (hasattr(doc_obj, "is_new") and doc_obj.is_new())
		or doc_obj.get("crm_ex_1") in team_members
		or doc_obj.get("owner") in team_members
	):
		return True

	# 2. For write/save/delete permissions on an existing doc, check DB state before alteration
	if ptype in ("write", "save", "delete"):
		doc_name = getattr(doc_obj, "name", None)
		if doc_name and frappe.db.exists("Hbs Tally Renewal", doc_name):
			db_val = frappe.db.get_value("Hbs Tally Renewal", doc_name, "crm_ex_1")
			if db_val in team_members:
				return True

	return False


def has_data_import_permission(doc=None, ptype="read", user=None):
	"""Only Administrator, System Manager, or Hierarchy Owner can use Data Import."""
	try:
		from hbs_crm.importer_patch import apply_data_import_patch
		apply_data_import_patch()
	except Exception:
		pass
	if not user:
		user = frappe.session.user
	return is_owner_or_admin(user)


@frappe.whitelist()
def get_old_remarks_html(name):
	"""Endpoint to return rendered Old Remarks HTML."""
	if not name:
		return "<div style='color:#94a3b8; font-style:italic; padding:10px;'>No past remarks imported yet.</div>"
	doc = frappe.get_doc("Hbs Tally Renewal", name)
	doc.render_old_remarks_html()
	return doc.old_remarks_html




DEFAULT_RENEWAL_EMAIL_SUBJECT = "Quotation for Tally TSS Renewal - Serial: {{ doc.tss_tally_serial or doc.tally_serial or '' }} ({{ doc.cc_acc_name or doc.portal_acc_name or doc.cc_contact or doc.portal_contact or doc.tss_tally_serial or doc.tally_serial or 'Valued Client' }})"


DEFAULT_RENEWAL_EMAIL_BODY = """<p>Dear {{ doc.cc_contact or doc.portal_contact or doc.cc_acc_name or doc.portal_acc_name or ('Serial ' ~ (doc.tss_tally_serial or doc.tally_serial or '')) or 'Valued Client' }},</p>
<p>Greetings from HBS!</p>
<p>Please find below the quotation for the renewal of your Tally Software Services (TSS):</p>
<div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 12px 16px; margin: 12px 0; font-family: sans-serif;">
	<table style="width: 100%; border-collapse: collapse; font-size: 13px;">
		<tr>
			<td style="padding: 4px 0; color: #64748b; width: 160px;"><b>Company / Account:</b></td>
			<td style="padding: 4px 0; color: #1e293b;"><b>{{ doc.cc_acc_name or doc.portal_acc_name or doc.cc_contact or doc.portal_contact or doc.tss_tally_serial or doc.tally_serial or 'N/A' }}</b></td>
		</tr>
		<tr>
			<td style="padding: 4px 0; color: #64748b;"><b>Tally Serial Number:</b></td>
			<td style="padding: 4px 0; color: #1e293b;"><b>{{ doc.tss_tally_serial or doc.tally_serial or 'N/A' }}</b></td>
		</tr>
		<tr>
			<td style="padding: 4px 0; color: #64748b;"><b>License / Edition:</b></td>
			<td style="padding: 4px 0; color: #1e293b;">{{ doc.license or doc.edition or doc.flavour or 'TallyPrime' }}</td>
		</tr>
		<tr>
			<td style="padding: 4px 0; color: #64748b;"><b>TSS Expiry Date:</b></td>
			<td style="padding: 4px 0; color: #1e293b;">{{ doc.acc_expiry_date or doc.portal_expiry_date or 'N/A' }}</td>
		</tr>
		{% if doc.cc_amount or doc.final_total %}
		<tr>
			<td style="padding: 6px 0 4px 0; color: #059669; font-size: 14px;"><b>Renewal Amount:</b></td>
			<td style="padding: 6px 0 4px 0; color: #059669; font-size: 14px; font-weight: bold;">₹{{ doc.final_total or doc.cc_amount }}</td>
		</tr>
		{% endif %}
	</table>
</div>
<p><b>Benefits of Active Tally TSS:</b></p>
<ul style="margin-top: 4px; margin-bottom: 12px; padding-left: 20px; color: #334155; font-size: 13px;">
	<li>Access to latest TallyPrime releases, product upgrades &amp; feature enhancements.</li>
	<li>Seamless connected e-Invoicing and e-Way Bill generation directly from Tally.</li>
	<li>Automated banking features, payment reconciliations, and bank statement import.</li>
	<li>Anytime, anywhere secure remote access and web browser reports.</li>
	<li>Continuous compliance with latest statutory and tax changes.</li>
</ul>
<p>Please review and let us know your confirmation to proceed with the renewal.</p>
<p>Warm regards,<br>
<b>{{ executive.full_name or 'HBS Sales Team' }}</b>
{%- if executive.designation %}<br>{{ executive.designation }}{% endif -%}
{%- if executive.mobile_no %}<br>Mobile: {{ executive.mobile_no }}{% endif -%}
{%- if executive.email %}<br>Email: {{ executive.email }}{% endif -%}
</p>"""


def get_renewal_client_recipients(doc):
	"""Resolve recipient emails for Hbs Tally Renewal quotation.
	Checks Admin Email ID (doc.admin_id) and Portal Email (doc.portal_email).
	- If both exist and differ: returns both.
	- If both exist and match: returns single deduplicated email.
	- If either is blank: returns the non-blank one.
	- If both blank: falls back to doc.cc_email / doc.director_email.
	"""
	recipients = []
	for raw in [getattr(doc, "admin_id", None), getattr(doc, "portal_email", None)]:
		if raw and str(raw).strip():
			for e in str(raw).replace(";", ",").split(","):
				e = e.strip()
				if e and "@" in e and e.lower() not in [r.lower() for r in recipients]:
					recipients.append(e)

	if not recipients:
		for raw in [getattr(doc, "cc_email", None), getattr(doc, "director_email", None)]:
			if raw and str(raw).strip():
				for e in str(raw).replace(";", ",").split(","):
					e = e.strip()
					if e and "@" in e and e.lower() not in [r.lower() for r in recipients]:
						recipients.append(e)

	return recipients


def get_renewal_executive_context(doc):
	"""Resolve Executive 1 (crm_ex_1) contact details for renewal email templates.
	Strictly uses Executive 1 (crm_ex_1). Logged-in user is not used.
	"""
	exec_user = (getattr(doc, "crm_ex_1", None) or "").strip()
	if exec_user and frappe.db.exists("User", exec_user):
		return get_logged_in_user_context(exec_user)
	return {
		"full_name": "HBS Sales Team",
		"email": "",
		"mobile_no": "",
		"phone": "",
		"phone_number": "",
		"designation": ""
	}


def render_renewal_email_for_doc(doc, executive_dict=None):
	"""Render email subject and body using Jinja from settings or defaults."""
	if executive_dict is None:
		executive_dict = get_renewal_executive_context(doc)
	settings = frappe.get_single("Hbs CRM Email Settings") if frappe.db.exists("DocType", "Hbs CRM Email Settings") else frappe._dict()
	subject_template = (getattr(settings, "renewal_email_subject", None) or "").strip() or DEFAULT_RENEWAL_EMAIL_SUBJECT
	body_template = (getattr(settings, "renewal_email_body", None) or "").strip() or DEFAULT_RENEWAL_EMAIL_BODY

	context = {"doc": doc, "executive": executive_dict, "logged_in_user": executive_dict}
	subject = frappe.render_template(subject_template, context)
	message = frappe.render_template(body_template, context)
	return {"subject": subject, "message": message}


@frappe.whitelist()
def get_renewal_email_template_defaults():
	"""Fetch default renewal quotation email settings configured in Hbs CRM Email Settings."""
	settings = frappe.get_single("Hbs CRM Email Settings") if frappe.db.exists("DocType", "Hbs CRM Email Settings") else frappe._dict()
	subject = (getattr(settings, "renewal_email_subject", None) or "").strip() or DEFAULT_RENEWAL_EMAIL_SUBJECT
	message = (getattr(settings, "renewal_email_body", None) or "").strip() or DEFAULT_RENEWAL_EMAIL_BODY
	sender_name = getattr(settings, "sender_name", None) or "HBS Sales Team"
	from_email = getattr(settings, "email_id", None) or "tally@hbsmail.in"
	return {
		"subject": subject,
		"message": message,
		"sender_name": sender_name,
		"from_email": from_email,
	}


@frappe.whitelist()
def get_rendered_renewal_email_template(name):
	"""Render TSS quotation email subject and body using Hbs CRM Email Settings and doc fields."""
	doc = frappe.get_doc("Hbs Tally Renewal", name)
	user = frappe.session.user
	if not is_owner_or_admin(user) and not has_permission(doc, "read", user):
		frappe.throw(_("Permission Denied"), title=_("Permission Denied"))

	settings = frappe.get_single("Hbs CRM Email Settings") if frappe.db.exists("DocType", "Hbs CRM Email Settings") else frappe._dict()
	exec_dict = get_renewal_executive_context(doc)

	rendered = render_renewal_email_for_doc(doc, exec_dict)
	user_email = exec_dict.get("email") or (frappe.session.user if frappe.session and "@" in str(frappe.session.user) else "")
	recipients = get_renewal_client_recipients(doc)

	return {
		"subject": rendered["subject"],
		"message": rendered["message"],
		"to_email": ", ".join(recipients),
		"cc_email": user_email,
		"from_email": settings.email_id or "tally@hbsmail.in",
		"sender_name": settings.sender_name or "HBS Sales Team"
	}


def get_renewal_quotation_pdf_attachment(doc):
	"""Render the HBS Renewal Quotation print format to PDF and return an attachments list (or [] on failure)."""
	try:
		assign_renewal_pi_and_date(doc)
		pdf_content = frappe.get_print(
			doctype=doc.doctype,
			name=doc.name,
			print_format="HBS Renewal Quotation",
			as_pdf=True,
		)
		if pdf_content:
			fname = f"Quotation_{doc.tss_tally_serial or doc.tally_serial or doc.name}.pdf"
			return [{
				"fname": fname,
				"fcontent": pdf_content,
			}]
	except Exception as e:
		frappe.log_error(f"PDF generation error for Renewal {doc.name}: {str(e)}", "Quotation PDF Warning")
	return []


@frappe.whitelist()
def get_renewal_quotation_html(name):
	"""Render the HBS Renewal Quotation print format to HTML for preview inside modal."""
	doc = frappe.get_doc("Hbs Tally Renewal", name)
	user = frappe.session.user if frappe.session else "System"
	if not is_owner_or_admin(user) and not has_permission(doc, "read", user):
		frappe.throw(_("Permission Denied"), frappe.PermissionError)

	assign_renewal_pi_and_date(doc)
	raw_html = frappe.get_print(
		doctype="Hbs Tally Renewal",
		name=name,
		print_format="HBS Renewal Quotation",
		as_pdf=False
	)
	import re
	cleaned_html = re.sub(r'<div class="action-banner[^>]*>[\s\S]*?</div>', '', raw_html)
	return cleaned_html


@frappe.whitelist()
def send_manual_renewal_email(name, to_email, subject, message, cc_email=None, from_email=None, sender_name=None, extra_attachments=None, attach_print=1):
	"""Backend endpoint for sending interactive quotation email to client for Hbs Tally Renewal."""
	doc = frappe.get_doc("Hbs Tally Renewal", name)
	user = frappe.session.user
	if not is_owner_or_admin(user) and not has_permission(doc, "read", user):
		frappe.throw(_("You do not have permission to send quotation for this renewal."), title=_("Permission Denied"))

	if not to_email:
		frappe.throw(_("Recipient 'To' Email is required."))

	user_email = (frappe.session.user or "").strip().lower()
	recipients_list = [e.strip() for e in to_email.split(",") if e.strip()]
	if user_email and [e.lower() for e in recipients_list] == [user_email]:
		frappe.throw(_("The 'To' field cannot be your own executive email ({0}). Please enter the client's email address.").format(to_email))

	if not doc.cc_email and recipients_list:
		doc.db_set("cc_email", recipients_list[0], update_modified=False)
		doc.cc_email = recipients_list[0]

	display_name = sender_name or "HBS Sales Team"
	email_addr = from_email or "tally@hbsmail.in"

	if frappe.db.exists("Hbs CRM Email Settings"):
		settings = frappe.get_doc("Hbs CRM Email Settings")
		if not from_email and settings.email_id:
			email_addr = settings.email_id
		if not sender_name and settings.sender_name:
			display_name = settings.sender_name

	sender = f"{display_name} <{email_addr}>"

	assign_renewal_pi_and_date(doc)

	attachments = []
	if frappe.utils.cint(attach_print) == 1:
		attachments.extend(get_renewal_quotation_pdf_attachment(doc))
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
				frappe.log_error(f"Failed to attach file {file_url}: {str(e)}", "Email Attachment Error")

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

	return True


@frappe.whitelist()
def assign_renewal_pi_number(renewal_name):
	"""Explicitly assign renewal PI number and quotation date to an Hbs Tally Renewal."""
	doc = frappe.get_doc("Hbs Tally Renewal", renewal_name)
	user = frappe.session.user
	if not is_owner_or_admin(user) and not has_permission(doc, "write", user):
		frappe.throw(_("Permission Denied"), title=_("Permission Denied"))

	assign_renewal_pi_and_date(doc)
	return {"pi_number": doc.pi_number, "quotation_date": doc.quotation_date}


@frappe.whitelist()
def send_bulk_renewal_email(names, subject_template, message_template, cc_email=None, from_email=None, sender_name=None, attach_print=1):
	"""Send batch quotation emails to multiple selected Hbs Tally Renewal records with Jinja template rendering."""
	if isinstance(names, str):
		try:
			names = json.loads(names)
		except Exception:
			names = [n.strip() for n in names.split(",") if n.strip()]

	if not names or not isinstance(names, list):
		frappe.throw(_("No renewal records selected for bulk email."))

	display_name = sender_name or "HBS Sales Team"
	email_addr = from_email or "tally@hbsmail.in"

	if frappe.db.exists("Hbs CRM Email Settings"):
		settings = frappe.get_doc("Hbs CRM Email Settings")
		if not from_email and settings.email_id:
			email_addr = settings.email_id
		if not sender_name and settings.sender_name:
			display_name = settings.sender_name

	sender = f"{display_name} <{email_addr}>"
	logged_in_user_dict = get_logged_in_user_context()
	user_email = frappe.session.user if frappe.session and frappe.session.user else "System"
	default_exec_cc = cc_email or logged_in_user_dict.get("email") or (frappe.session.user if frappe.session and "@" in str(frappe.session.user) else None)

	# Managers, Owners, and Admins can send bulk quotation to any lead
	user_role = frappe.db.get_value("Hbs User Hierarchy", {"user": user_email}, "role_type")
	can_bulk_all = is_owner_or_admin(user_email) or user_role == "Manager"

	sent_records = []
	skipped_records = []
	failed_records = []

	for name in names:
		serial = "-"
		party = "-"
		try:
			doc = frappe.get_doc("Hbs Tally Renewal", name)
			serial = str(doc.tss_tally_serial or doc.tally_serial or doc.name or "-").strip()
			party = str(doc.cc_acc_name or doc.portal_acc_name or "-").strip()

			if not can_bulk_all and not has_permission(doc, "read", user_email):
				failed_records.append({
					"name": name,
					"serial": serial,
					"party": party,
					"email": "-",
					"error": _("Permission Denied")
				})
				continue

			recipients = get_renewal_client_recipients(doc)
			if not recipients:
				skipped_records.append({
					"name": name,
					"serial": serial,
					"party": party,
					"reason": _("No Email ID found")
				})
				continue

			assign_renewal_pi_and_date(doc)

			exec_dict = get_renewal_executive_context(doc)
			ctx = {"doc": doc, "executive": exec_dict, "logged_in_user": exec_dict}
			rendered_subject = frappe.render_template(subject_template, ctx)
			rendered_message = frappe.render_template(message_template, ctx)

			cc = [e.strip() for e in default_exec_cc.split(",") if e.strip()] if default_exec_cc else None

			pdf_attach = get_renewal_quotation_pdf_attachment(doc) if frappe.utils.cint(attach_print) == 1 else []

			frappe.sendmail(
				recipients=recipients,
				cc=cc,
				sender=sender,
				reply_to=email_addr,
				subject=rendered_subject,
				message=rendered_message,
				attachments=pdf_attach if pdf_attach else None,
				reference_doctype=doc.doctype,
				reference_name=doc.name,
				expose_recipients="header",
				now=True
			)

			sent_records.append({
				"name": name,
				"serial": serial,
				"party": party,
				"email": ", ".join(recipients)
			})
		except Exception as e:
			err_str = str(e)
			frappe.log_error(f"Bulk quotation email failed for {name}: {err_str}", "Bulk Renewal Email Error")
			failed_records.append({
				"name": name,
				"serial": serial,
				"party": party,
				"email": to_email if "to_email" in locals() and to_email else "-",
				"error": err_str
			})

	frappe.db.commit()

	return {
		"status": "success",
		"success_count": len(sent_records),
		"sent_records": sent_records,
		"skipped_records": skipped_records,
		"skipped_no_email": [r["name"] for r in skipped_records],
		"failed_records": failed_records
	}


@frappe.whitelist()
def import_past_remarks_from_file(file_url, overwrite=0):
	"""Upload and process past remarks Excel (.xlsx / .xls), grouping by serial number and updating records."""
	user = frappe.session.user if frappe.session else "System"
	if not is_owner_or_admin(user):
		frappe.throw(_("Only Owner and Administrator can import past remarks."), title=_("Permission Denied"))

	if not file_url:
		frappe.throw(_("Excel file is required."))

	file_name = frappe.db.get_value("File", {"file_url": file_url}, "name")
	if not file_name:
		frappe.throw(_("Uploaded file not found in system."))

	file_doc = frappe.get_doc("File", file_name)
	content = file_doc.get_content()
	if not content:
		frappe.throw(_("Uploaded file is empty or could not be read."))

	overwrite = frappe.utils.cint(overwrite) == 1

	if isinstance(content, str):
		content = content.encode("utf-8")

	import io
	import datetime
	rows = []

	if content.startswith(b"PK"):
		import openpyxl
		wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
		ws = wb.active
		raw_rows = list(ws.iter_rows(values_only=True))
		if raw_rows:
			headers = [str(c or "").strip().lower() for c in raw_rows[0]]
			for r in raw_rows[1:]:
				if not any(r):
					continue
				row_dict = {}
				for idx, h in enumerate(headers):
					val = r[idx] if idx < len(r) else ""
					if isinstance(val, (datetime.date, datetime.datetime)):
						val = val.strftime("%d-%b-%Y")
					row_dict[h] = str(val or "").strip()
				rows.append(row_dict)
	else:
		import xlrd
		wb = xlrd.open_workbook(file_contents=content)
		ws = wb.sheets()[0]
		headers = [str(ws.cell_value(0, c)).strip().lower() for c in range(ws.ncols)]
		for r in range(1, ws.nrows):
			row_dict = {}
			for c in range(ws.ncols):
				h = headers[c]
				val = str(ws.cell_value(r, c)).strip()
				row_dict[h] = val
			rows.append(row_dict)

	if not rows:
		return {"status": "error", "message": _("No data rows found in the uploaded Excel.")}

	sample = rows[0]
	serial_key = next((k for k in sample.keys() if "serial" in k), None)
	user_key = next((k for k in sample.keys() if "user" in k or "exec" in k), None)
	date_key = next((k for k in sample.keys() if "date" in k), None)
	time_key = next((k for k in sample.keys() if "time" in k), None)
	remark_key = next((k for k in sample.keys() if "remark" in k or "note" in k), None)

	if not serial_key or not remark_key:
		frappe.throw(_("Excel must contain at least 'Serial No' and 'Remarks' columns."))

	from collections import defaultdict
	by_serial = defaultdict(list)
	for row in rows:
		s = row.get(serial_key, "").strip()
		if s.endswith(".0"):
			s = s[:-2]
		rem = row.get(remark_key, "").strip()
		if s and rem:
			by_serial[s].append({
				"user": row.get(user_key, "") if user_key else "",
				"date": row.get(date_key, "") if date_key else "",
				"time": row.get(time_key, "") if time_key else "",
				"remark": rem
			})

	updated_count = 0
	skipped_count = 0
	not_found_count = 0

	for serial, entries in by_serial.items():
		doc_name = (
			frappe.db.get_value("Hbs Tally Renewal", {"tss_tally_serial": serial}, "name") or
			frappe.db.get_value("Hbs Tally Renewal", {"tally_serial": serial}, "name")
		)
		if not doc_name:
			not_found_count += 1
			continue

		existing = (frappe.db.get_value("Hbs Tally Renewal", doc_name, "old_remarks") or "").strip()
		if existing and not overwrite:
			skipped_count += 1
			continue

		lines = []
		for e in entries:
			prefix_parts = []
			if e["date"] or e["time"]:
				dt_str = f"{e['date']} {e['time']}".strip()
				prefix_parts.append(dt_str)
			if e["user"]:
				prefix_parts.append(e["user"])
			prefix = " | ".join(prefix_parts)
			if prefix:
				lines.append(f"[{prefix}] {e['remark']}")
			else:
				lines.append(e["remark"])

		text_block = "\n".join(lines)
		frappe.db.set_value("Hbs Tally Renewal", doc_name, "old_remarks", text_block, update_modified=False)
		updated_count += 1

	frappe.db.commit()

	msg = _(
		"<b>Past Remarks Import Complete!</b><br><br>"
		"• <b>{0}</b> records updated with compiled remarks.<br>"
		"• <b>{1}</b> records skipped (already had remarks).<br>"
		"• <b>{2}</b> serial numbers not found in current database."
	).format(updated_count, skipped_count, not_found_count)

	return {
		"status": "success",
		"message": msg,
		"updated_count": updated_count,
		"skipped_count": skipped_count,
		"not_found_count": not_found_count
	}


# --- CUSTOM EXCEL DATA IMPORT (Fallback when Frappe Data Import tool fails) ---
@frappe.whitelist()
def import_renewals_from_excel(file_url):
	"""
	Custom fallback Excel importer for Hbs Tally Renewal records.
	Handles Excel files (.xlsx / .xls), maps columns via hooks data_import_column_aliases
	and DocType fields (case-insensitively), resolves usernames (kps, dev, yogi, etc.),
	and creates or updates records matching by tally_serial or name.
	Publishes real-time progress and returns a detailed failure report with exact reasons.
	"""
	user = frappe.session.user if frappe.session else "System"
	if not is_owner_or_admin(user):
		frappe.throw(_("Only Owner and Administrator can import data."), title=_("Permission Denied"))

	if not file_url:
		frappe.throw(_("Excel file is required."))

	file_name = frappe.db.get_value("File", {"file_url": file_url}, "name")
	if not file_name:
		frappe.throw(_("Uploaded file not found in system."))

	file_doc = frappe.get_doc("File", file_name)
	content = file_doc.get_content()
	if not content:
		frappe.throw(_("Uploaded file is empty or could not be read."))

	if isinstance(content, str):
		content = content.encode("utf-8")

	import io
	import datetime

	raw_headers = []
	raw_data_rows = []

	if content.startswith(b"PK"):
		import openpyxl
		wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
		ws = wb.active
		raw_rows = list(ws.iter_rows(values_only=True))
		if raw_rows:
			raw_headers = [str(c or "").strip() for c in raw_rows[0]]
			raw_data_rows = raw_rows[1:]
	else:
		import xlrd
		wb = xlrd.open_workbook(file_contents=content)
		ws = wb.sheets()[0]
		raw_headers = [str(ws.cell_value(0, c)).strip() for c in range(ws.ncols)]
		for r in range(1, ws.nrows):
			raw_data_rows.append([ws.cell_value(r, c) for c in range(ws.ncols)])

	if not raw_headers or not raw_data_rows:
		return {"status": "error", "message": _("No data found in uploaded Excel.")}

	# Load aliases from hooks and doctype meta
	aliases_hooks = frappe.get_hooks("data_import_column_aliases") or {}
	aliases_dict = aliases_hooks.get("Hbs Tally Renewal", {})
	alias_map = {}
	if isinstance(aliases_dict, dict):
		for k, v in aliases_dict.items():
			fname = v[0] if isinstance(v, list) else v
			if fname:
				alias_map[str(k).strip().lower()] = fname

	meta = frappe.get_meta("Hbs Tally Renewal")
	field_types = {df.fieldname: df.fieldtype for df in meta.fields}

	# Mapping map: clean header -> DocField fieldname
	field_map = {}
	for df in meta.fields:
		field_map[df.fieldname.lower()] = df.fieldname
		if df.label:
			field_map[df.label.strip().lower()] = df.fieldname

	for k, v in alias_map.items():
		field_map[k] = v

	field_map["id"] = "name"
	field_map["name"] = "name"
	field_map["serial no"] = "tally_serial"
	field_map["serial"] = "tally_serial"
	field_map["serial number"] = "tally_serial"
	field_map["product version"] = "tally_version"
	field_map["product ver"] = "tally_version"
	field_map["number version"] = "release"
	field_map["number ver"] = "release"

	col_to_field = {}
	for idx, h in enumerate(raw_headers):
		clean_h = str(h or "").strip().lower()
		if clean_h in field_map:
			col_to_field[idx] = field_map[clean_h]

	if not any(f in ("tally_serial", "tss_tally_serial", "name") for f in col_to_field.values()):
		frappe.throw(_("Excel must contain a 'Serial No' or 'ID' column to identify renewal records."))

	user_map = {
		"kps": "kps@hbsmail.in",
		"dev": "dev@hbsmail.in",
		"yogi": "yogi@hbsmail.in",
		"yogendra": "yogi@hbsmail.in",
		"admin": "Administrator",
		"administrator": "Administrator",
	}

	user_resolve_cache = {}
	def resolve_user(val):
		if not val:
			return None
		val_clean = str(val).strip()
		if val_clean in user_resolve_cache:
			return user_resolve_cache[val_clean]
		if frappe.db.exists("User", val_clean, cache=True):
			user_resolve_cache[val_clean] = val_clean
			return val_clean
		if val_clean.lower() in user_map:
			target = user_map[val_clean.lower()]
			if frappe.db.exists("User", target, cache=True):
				user_resolve_cache[val_clean] = target
				return target
		resolved = (
			frappe.db.get_value("User", {"username": val_clean.lower()})
			or frappe.db.get_value("User", {"username": val_clean})
			or frappe.db.get_value("User", {"first_name": val_clean})
			or frappe.db.get_value("User", {"full_name": val_clean})
		)
		res = resolved or val_clean
		user_resolve_cache[val_clean] = res
		return res

	def safe_date(val):
		if not val:
			return None
		if isinstance(val, (datetime.date, datetime.datetime)):
			return val.strftime("%Y-%m-%d")
		try:
			return frappe.utils.data.getdate(val)
		except Exception:
			return None

	total_rows = len(raw_data_rows)
	created_count = 0
	updated_count = 0
	failed_rows = []

	for row_idx, r in enumerate(raw_data_rows, start=2):
		if not any(r):
			continue

		if total_rows > 0 and (row_idx % max(1, total_rows // 25) == 0 or row_idx == total_rows + 1):
			pct = min(100.0, float(row_idx - 1) / total_rows * 100)
			frappe.publish_progress(
				pct,
				title=_("Importing Renewal Data"),
				description=_("Processed {0} of {1} rows... (Created: {2}, Updated: {3}, Skipped: {4})").format(
					row_idx - 1, total_rows, created_count, updated_count, len(failed_rows)
				)
			)

		row_data = {}
		for idx, val in enumerate(r):
			if idx not in col_to_field:
				continue
			fname = col_to_field[idx]
			if val is None or val == "":
				continue

			ftype = field_types.get(fname, "Data")
			if ftype in ("Date", "Datetime"):
				parsed_d = safe_date(val)
				if parsed_d:
					row_data[fname] = parsed_d
			elif ftype == "Link" and getattr(meta.get_field(fname), "options", None) == "User":
				row_data[fname] = resolve_user(val)
			elif ftype in ("Int", "Check"):
				try:
					row_data[fname] = frappe.utils.cint(float(str(val).strip()))
				except Exception:
					pass
			elif ftype in ("Float", "Currency"):
				try:
					row_data[fname] = frappe.utils.flt(str(val).strip())
				except Exception:
					pass
			else:
				s_val = str(val).strip()
				if s_val.endswith(".0") and (fname in ("tally_serial", "tss_tally_serial", "pincode", "cc_pincode", "portal_phone", "cc_phone", "cc_mobile", "portal_mobile") or fname.endswith("_serial")):
					s_val = s_val[:-2]
				row_data[fname] = s_val

		serial = row_data.get("tally_serial") or row_data.get("tss_tally_serial")
		doc_name = row_data.get("name")
		party = row_data.get("cc_acc_name") or row_data.get("portal_acc_name") or row_data.get("cc_contact") or ""

		if not serial and not doc_name:
			failed_rows.append({
				"row": row_idx,
				"serial": "-",
				"party": party or "-",
				"reason": _("Missing Serial Number or ID in row")
			})
			continue

		if serial:
			raw_serial = str(serial).strip()
			if not is_genuine_tally_serial(raw_serial):
				failed_rows.append({
					"row": row_idx,
					"serial": raw_serial,
					"party": party or "-",
					"reason": _("Invalid Tally Serial (Must be 9 digits starting with 7, digital root 9)")
				})
				continue

		if not doc_name and serial:
			doc_name = (
				frappe.db.get_value("Hbs Tally Renewal", {"tally_serial": serial}, "name") or
				frappe.db.get_value("Hbs Tally Renewal", {"tss_tally_serial": serial}, "name")
			)

		try:
			if doc_name and frappe.db.exists("Hbs Tally Renewal", doc_name):
				doc = frappe.get_doc("Hbs Tally Renewal", doc_name)
				for k, v in row_data.items():
					if k != "name":
						doc.set(k, v)
				doc.flags.in_import = True
				doc.flags.ignore_permissions = True
				doc.save()
				updated_count += 1
			else:
				doc = frappe.new_doc("Hbs Tally Renewal")
				for k, v in row_data.items():
					if k != "name":
						doc.set(k, v)
				doc.flags.in_import = True
				doc.flags.ignore_permissions = True
				doc.insert()
				created_count += 1

			if (created_count + updated_count) % 50 == 0:
				frappe.db.commit()

		except Exception as e:
			err_msg = frappe.utils.strip_html(str(e)).strip()
			frappe.log_error(f"Error importing row {row_idx} ({serial}): {err_msg}", "Custom Excel Import")
			failed_rows.append({
				"row": row_idx,
				"serial": serial or doc_name or "-",
				"party": party or "-",
				"reason": err_msg or _("Database save error")
			})

	frappe.publish_progress(100, title=_("Importing Renewal Data"), description=_("Import completed!"))
	frappe.db.commit()

	return {
		"status": "success",
		"created_count": created_count,
		"updated_count": updated_count,
		"skipped_count": len(failed_rows),
		"failed_rows": failed_rows
	}


# --- UPDATE SECONDARY DATA (Excel: TSS Tally Serial, License, TSS Expiry Date, Portal Partner Name, crm stage) ---
@frappe.whitelist()
def update_secondary_data_from_excel(file_url):
	"""
	Update secondary data for Hbs Tally Renewal records from Excel.
	Columns expected: TSS Tally Serial, License, TSS Expiry Date, Portal Partner Name, crm stage.
	Matches existing records by TSS Tally Serial / tally_serial / name and updates fields directly.
	"""
	user = frappe.session.user if frappe.session else "System"
	if not is_owner_or_admin(user):
		frappe.throw(_("Only Owner and Administrator can update data."), title=_("Permission Denied"))

	if not file_url:
		frappe.throw(_("Excel file is required."))

	file_name = frappe.db.get_value("File", {"file_url": file_url}, "name")
	if not file_name:
		frappe.throw(_("Uploaded file not found in system."))

	file_doc = frappe.get_doc("File", file_name)
	content = file_doc.get_content()
	if not content:
		frappe.throw(_("Uploaded file is empty or could not be read."))

	if isinstance(content, str):
		content = content.encode("utf-8")

	import io
	import datetime
	import re

	raw_headers = []
	raw_data_rows = []

	if content.startswith(b"PK"):
		import openpyxl
		wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
		ws = wb.active
		raw_rows = list(ws.iter_rows(values_only=True))
		if raw_rows:
			raw_headers = [str(c or "").strip() for c in raw_rows[0]]
			raw_data_rows = raw_rows[1:]
	else:
		import xlrd
		wb = xlrd.open_workbook(file_contents=content)
		ws = wb.sheets()[0]
		raw_headers = [str(ws.cell_value(0, c)).strip() for c in range(ws.ncols)]
		for r in range(1, ws.nrows):
			raw_data_rows.append([ws.cell_value(r, c) for c in range(ws.ncols)])

	if not raw_headers or not raw_data_rows:
		return {"status": "error", "message": _("No data found in uploaded Excel.")}

	def norm_header(h):
		return re.sub(r"[^a-z0-9]", "", str(h or "").lower())

	col_serial = None
	col_license = None
	col_expiry = None
	col_partner = None
	col_ref = None
	col_stage = None

	for idx, h in enumerate(raw_headers):
		nh = norm_header(h)
		if nh in ("tsstallyserial", "tallyserial", "serialno", "serial", "serialnumber", "tssserial") and col_serial is None:
			col_serial = idx
		elif nh in ("license", "licensetype", "licence") and col_license is None:
			col_license = idx
		elif nh in ("tssexpirydate", "expirydate", "tssexpiry", "portalexpirydate", "accexpirydate") and col_expiry is None:
			col_expiry = idx
		elif nh in ("portalpartnername", "partnername", "portalpartner", "partner") and col_partner is None:
			col_partner = idx
		elif nh in ("referencestatus", "referencestate", "crmref", "refstatus", "reference", "ref") and col_ref is None:
			col_ref = idx
		elif nh in ("crmstage", "stage", "crm_stage") and col_stage is None:
			col_stage = idx

	if col_serial is None:
		frappe.throw(_("Excel must contain a 'TSS Tally Serial' column to identify renewal records."))

	# Pre-fetch existing renewals in memory for O(1) matching
	existing_records = frappe.db.sql(
		"""
		SELECT name, tally_serial, tss_tally_serial, cc_acc_name, portal_acc_name
		FROM `tabHbs Tally Renewal`
		""",
		as_dict=True
	)
	serial_map = {}
	for r in existing_records:
		if r.tally_serial:
			serial_map[str(r.tally_serial).strip()] = r
		if r.tss_tally_serial:
			serial_map[str(r.tss_tally_serial).strip()] = r
		if r.name:
			serial_map[str(r.name).strip()] = r

	def safe_date(val):
		if not val:
			return None
		if isinstance(val, (datetime.date, datetime.datetime)):
			return val.strftime("%Y-%m-%d")
		if isinstance(val, (int, float)):
			try:
				d = datetime.date(1899, 12, 30) + datetime.timedelta(days=int(val))
				return d.strftime("%Y-%m-%d")
			except Exception:
				pass
		s = str(val).strip()
		if not s or s.lower() in ("none", "nan", "null", "-", "nat"):
			return None
		for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d.%m.%Y", "%d-%b-%Y", "%d-%b-%y", "%d/%m/%y", "%d-%m-%y"):
			try:
				return datetime.datetime.strptime(s, fmt).date().strftime("%Y-%m-%d")
			except ValueError:
				continue
		try:
			return str(frappe.utils.data.getdate(s))
		except Exception:
			return None

	def clean_license(val):
		if not val:
			return None
		s = str(val).strip()
		upper = s.upper()
		if "AUDITOR" in upper:
			return "TALLY PRIME AUDITOR"
		elif "GOLD" in upper:
			return "TALLY PRIME GOLD"
		elif "SILVER" in upper:
			return "TALLY PRIME SILVER"
		elif "SERVER" in upper:
			return "TALLY PRIME SERVER"
		elif "RENTAL" in upper:
			return "RENTAL"
		elif "NEW CASE" in upper or "NEW" in upper:
			return "NEW CASE"
		return s

	def clean_ref_status(val):
		if not val:
			return None
		s = str(val).strip().upper()
		if "MOVE" in s or "OUT" in s:
			return "MOVED OUT"
		elif "ACTIVE" in s:
			return "ACTIVE"
		elif "COMP" in s:
			return "COMPETITION"
		return s

	total_rows = len(raw_data_rows)
	updated_count = 0
	failed_rows = []

	for row_idx, r in enumerate(raw_data_rows, start=2):
		if not any(r):
			continue

		if total_rows > 0 and (row_idx % max(1, total_rows // 20) == 0 or row_idx == total_rows + 1):
			pct = min(100.0, float(row_idx - 1) / total_rows * 100)
			frappe.publish_progress(
				pct,
				title=_("Updating Secondary Data"),
				description=_("Processed {0} of {1} rows... (Updated: {2}, Skipped: {3})").format(
					row_idx - 1, total_rows, updated_count, len(failed_rows)
				)
			)

		val_serial = r[col_serial] if col_serial < len(r) else None
		if val_serial is None or str(val_serial).strip() == "":
			failed_rows.append({
				"row": row_idx,
				"serial": "-",
				"party": "-",
				"reason": _("Missing TSS Tally Serial in row")
			})
			continue

		raw_serial = re.sub(r"\.0$", "", str(val_serial).strip())
		clean_serial = "".join(filter(str.isdigit, raw_serial))
		lookup_key = clean_serial if len(clean_serial) == 9 else raw_serial

		if not is_genuine_tally_serial(lookup_key):
			failed_rows.append({
				"row": row_idx,
				"serial": lookup_key,
				"party": "-",
				"reason": _("Invalid Tally Serial (Must be 9 digits starting with 7, digital root 9)")
			})
			continue

		target_rec = serial_map.get(lookup_key) or serial_map.get(raw_serial)
		if not target_rec:
			partner_display = str(r[col_partner]).strip() if (col_partner is not None and col_partner < len(r) and r[col_partner]) else "-"
			failed_rows.append({
				"row": row_idx,
				"serial": lookup_key,
				"party": partner_display,
				"reason": _("Serial Number not found in Hbs Tally Renewal")
			})
			continue

		doc_name = target_rec.name
		party_display = target_rec.cc_acc_name or target_rec.portal_acc_name or "-"

		updates = {}

		# 1. License
		if col_license is not None and col_license < len(r) and r[col_license]:
			lic = clean_license(r[col_license])
			if lic:
				updates["license"] = lic

		# 2. TSS Expiry Date
		if col_expiry is not None and col_expiry < len(r) and r[col_expiry]:
			parsed_exp = safe_date(r[col_expiry])
			if parsed_exp:
				updates["acc_expiry_date"] = parsed_exp
				updates["portal_expiry_date"] = parsed_exp
			else:
				failed_rows.append({
					"row": row_idx,
					"serial": lookup_key,
					"party": party_display,
					"reason": _("Invalid TSS Expiry Date: {0}").format(r[col_expiry])
				})
				continue

		# 3. Portal Partner Name
		if col_partner is not None and col_partner < len(r) and r[col_partner]:
			p_name = str(r[col_partner]).strip()
			if p_name:
				updates["portal_partner_name"] = p_name
				updates["partner_name"] = p_name

		# 4. Reference Status (crm_ref)
		if col_ref is not None and col_ref < len(r) and r[col_ref]:
			ref_val = clean_ref_status(r[col_ref])
			if ref_val:
				updates["crm_ref"] = ref_val

		# 5. crm stage / reference status fallback
		if col_stage is not None and col_stage < len(r) and r[col_stage]:
			raw_stage = str(r[col_stage]).strip()
			if raw_stage:
				if col_ref is None and any(k in raw_stage.upper() for k in ("MOVE", "OUT", "ACTIVE", "COMPETITION")):
					ref_val = clean_ref_status(raw_stage)
					if ref_val:
						updates["crm_ref"] = ref_val
				else:
					c_stage = raw_stage
					c_upper = c_stage.upper()
					if "FOLLOW" in c_upper:
						c_stage = "IN FOLLOW-UP"
					elif "RESPOND" in c_upper:
						c_stage = "CUSTOMER NOT RESPONDING"
					elif "DEMO" in c_upper or "MEETING" in c_upper:
						c_stage = "DEMO/MEETING DONE"
					elif "LEAD" in c_upper:
						c_stage = "LEAD"
					elif "QUOTE" in c_upper or "QUOTATION" in c_upper:
						c_stage = "QUOTATION SENT"
					updates["crm_stage"] = c_stage

		if not updates:
			failed_rows.append({
				"row": row_idx,
				"serial": lookup_key,
				"party": party_display,
				"reason": _("No values found to update in this row")
			})
			continue

		try:
			frappe.db.set_value("Hbs Tally Renewal", doc_name, updates, update_modified=True)
			updated_count += 1

			if updated_count % 100 == 0:
				frappe.db.commit()

		except Exception as e:
			err_msg = frappe.utils.strip_html(str(e)).strip()
			failed_rows.append({
				"row": row_idx,
				"serial": lookup_key,
				"party": party_display,
				"reason": err_msg or _("Database update error")
			})

	frappe.publish_progress(100, title=_("Updating Secondary Data"), description=_("Update completed!"))
	frappe.db.commit()

	return {
		"status": "success",
		"report_title": _("📊 Secondary Data Update Report"),
		"created_count": 0,
		"updated_count": updated_count,
		"skipped_count": len(failed_rows),
		"failed_rows": failed_rows
	}


# --- UPDATE MASTER DATA FROM CUSTOMER SERIALS REPORT (EXCEL) ---
@frappe.whitelist()
def update_master_data_from_excel(file_url):
	"""
	Update Master Data (Portal tab & metrics) for Hbs Tally Renewal records from Excel.
	Customer Serials Report columns matched by Customer Serial Name / Tally Serial.
	"""
	user = frappe.session.user if frappe.session else "System"
	if not is_owner_or_admin(user):
		frappe.throw(_("Only Owner and Administrator can update data."), title=_("Permission Denied"))

	if not file_url:
		frappe.throw(_("Excel file is required."))

	file_name = frappe.db.get_value("File", {"file_url": file_url}, "name")
	if not file_name:
		frappe.throw(_("Uploaded file not found in system."))

	file_doc = frappe.get_doc("File", file_name)
	content = file_doc.get_content()
	if not content:
		frappe.throw(_("Uploaded file is empty or could not be read."))

	if isinstance(content, str):
		content = content.encode("utf-8")

	import io
	import datetime
	import re

	raw_headers = []
	raw_data_rows = []

	if content.startswith(b"PK"):
		import openpyxl
		wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
		ws = wb.active
		raw_rows = list(ws.iter_rows(values_only=True))
		if raw_rows:
			raw_headers = [str(c or "").strip() for c in raw_rows[0]]
			raw_data_rows = raw_rows[1:]
	else:
		import xlrd
		wb = xlrd.open_workbook(file_contents=content)
		ws = wb.sheets()[0]
		raw_headers = [str(ws.cell_value(0, c)).strip() for c in range(ws.ncols)]
		for r in range(1, ws.nrows):
			raw_data_rows.append([ws.cell_value(r, c) for c in range(ws.ncols)])

	if not raw_headers or not raw_data_rows:
		return {"status": "error", "message": _("No data found in uploaded Excel.")}

	# Detect and skip annotation row (e.g. Row 2 with 'NO USE', 'NEW FIELD', 'QUESTION MARK')
	start_row_offset = 2
	if raw_data_rows:
		row2_str = " ".join([str(c or "").upper() for c in raw_data_rows[0]])
		if any(marker in row2_str for marker in ("NO USE", "NEW FIELD", "QUESTION MARK")):
			raw_data_rows = raw_data_rows[1:]
			start_row_offset = 3

	def norm(h):
		return re.sub(r"[^a-z0-9]", "", str(h or "").lower())

	# Map columns by normalized headers
	col_serial = None
	col_serial_alt = None
	col_expiry = None
	col_flavor = None
	col_release = None
	col_account = None
	col_email = None
	col_admin_email = None
	col_address = None
	col_city = None
	col_pincode = None
	col_tss_priority = None
	col_mau = None
	col_prod_family = None
	col_rfm = None
	col_qau = None
	col_mca = None
	col_actvn = None
	col_last_ping = None
	col_gstin = None
	col_e_invoice = None
	col_avail_storage = None
	col_used_storage = None
	col_ira_quota = None
	col_tss_status = None

	for idx, h in enumerate(raw_headers):
		n = norm(h)
		if n in ("customerserialcustomerserialname", "customerserialname", "tsstallyserial", "tallyserial", "serialno", "serialnumber") and col_serial is None:
			col_serial = idx
		elif n in ("tallyserialnumber", "customerserial") and col_serial_alt is None:
			col_serial_alt = idx
		elif n in ("tssrentalexpirydate", "tssexpirydate", "rentalexpirydate", "portalexpirydate") and col_expiry is None:
			col_expiry = idx
		elif n in ("flavor", "flavour", "tallyflavour") and col_flavor is None:
			col_flavor = idx
		elif (n in ("release", "version", "tallyrelease", "tallyversion", "releaseversion", "releaserversion", "tallyreleaseversion", "tallyreleaserversion", "productversion", "productver", "tallyprimerelease") or ("release" in n and "date" not in n) or ("version" in n and "turnover" not in n)) and col_release is None:
			col_release = idx
		elif n in ("account", "portalaccname", "accountname") and col_account is None:
			col_account = idx
		elif n in ("accountemailid", "accountemail", "portalemail") and col_email is None:
			col_email = idx
		elif n in ("customeraccountadminemailid", "customeraccountadminemail", "adminemailid", "adminid") and col_admin_email is None:
			col_admin_email = idx
		elif ("address" in n or n in ("customeraddress", "portaladdress")) and col_address is None:
			col_address = idx
		elif n in ("city", "customercity", "ledcity", "state", "customerstate", "portalstate") and col_city is None:
			col_city = idx
		elif n in ("pincode", "portalpincode", "pin") and col_pincode is None:
			col_pincode = idx
		elif n in ("tsspriority", "tssranking") and col_tss_priority is None:
			col_tss_priority = idx
		elif n in ("mau", "monthlyactiveusers") and col_mau is None:
			col_mau = idx
		elif n in ("productfamily",) and col_prod_family is None:
			col_prod_family = idx
		elif n in ("serialrfmsegmentation", "rfmsegmentation", "rfmsegment") and col_rfm is None:
			col_rfm = idx
		elif n in ("qau", "quarterlyactiveusers") and col_qau is None:
			col_qau = idx
		elif n in ("mcaflag",) and col_mca is None:
			col_mca = idx
		elif n in ("firstactvndatetime", "firstactivationdatetime", "firstactivationdate", "activationdate") and col_actvn is None:
			col_actvn = idx
		elif n in ("lastpingdate", "lastping") and col_last_ping is None:
			col_last_ping = idx
		elif n in ("primarygstinnumber", "primarygstin", "gstin", "gstinnumber") and col_gstin is None:
			col_gstin = idx
		elif n in ("gstineinvoiceenablementstatus", "gstineinvoicestatus", "einvoiceenablementstatus", "einvoicestatus") and col_e_invoice is None:
			col_e_invoice = idx
		elif n in ("availablestoragegb", "availablestorage") and col_avail_storage is None:
			col_avail_storage = idx
		elif n in ("usedstoragegb", "usedstorage") and col_used_storage is None:
			col_used_storage = idx
		elif n in ("docsbyiraquotaavailable", "docsbyiraquota") and col_ira_quota is None:
			col_ira_quota = idx
		elif n in ("tssstatus",) and col_tss_status is None:
			col_tss_status = idx

	if col_serial is None:
		frappe.throw(_("Excel must contain a 'Customer Serial Name' or 'Tally Serial' column to identify renewal records."))

	# Pre-fetch existing renewals in memory: PURELY MATCH ON TALLY SERIAL NUMBER
	existing_records = frappe.db.sql(
		"""
		SELECT `name`, `tally_serial`, `tss_tally_serial`, `cc_acc_name`, `portal_acc_name`, `acc_expiry_date`, `address`, `portal_address`, `release`, `tally_version`, `product_ver`, `state`
		FROM `tabHbs Tally Renewal`
		""",
		as_dict=True
	)
	serial_map = {}
	for r in existing_records:
		if r.tally_serial:
			serial_map[str(r.tally_serial).strip()] = r
		if r.tss_tally_serial:
			serial_map[str(r.tss_tally_serial).strip()] = r

	def safe_date(val):
		if not val:
			return None
		if isinstance(val, (datetime.date, datetime.datetime)):
			return val.strftime("%Y-%m-%d")
		if isinstance(val, (int, float)):
			try:
				d = datetime.date(1899, 12, 30) + datetime.timedelta(days=int(val))
				return d.strftime("%Y-%m-%d")
			except Exception:
				pass
		s = str(val).strip()
		if not s or s.lower() in ("none", "nan", "null", "-", "nat"):
			return None
		if "," in s:
			s = s.split(",")[0].strip()
		elif " " in s:
			s = s.split(" ")[0].strip()
		for fmt in ("%m/%d/%Y", "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%m-%d-%Y", "%d.%m.%Y", "%d-%b-%Y", "%d-%b-%y", "%d/%m/%y", "%d-%m-%y"):
			try:
				return datetime.datetime.strptime(s, fmt).date().strftime("%Y-%m-%d")
			except ValueError:
				continue
		try:
			return str(frappe.utils.data.getdate(s))
		except Exception:
			return None

	def clean_flavour(val):
		if not val:
			return None, None
		s = str(val).strip()
		u = s.upper()
		if "SILVER" in u:
			return "Tally Prime Silver", "TALLY PRIME SILVER"
		elif "GOLD" in u:
			return "Tally Prime Gold", "TALLY PRIME GOLD"
		elif "AUDITOR" in u:
			return "Tally Prime Auditor", "TALLY PRIME AUDITOR"
		elif "SERVER" in u:
			return "Tally Prime Server", "TALLY PRIME SERVER"
		elif "RENTAL" in u:
			return "Tally Prime Rental", "RENTAL"
		elif s.lower().startswith("tally prime"):
			return s, s.upper()
		elif s:
			return f"Tally Prime {s}", f"TALLY PRIME {s.upper()}"
		return s, s

	total_rows = len(raw_data_rows)
	updated_count = 0
	created_count = 0
	failed_rows = []

	untagged_user = (
		frappe.db.get_single_value("Hbs CRM Settings", "untagged_renewal_user")
		or "untagged@hbsmail.in"
	)
	if not frappe.db.exists("User", untagged_user):
		u = frappe.new_doc("User")
		u.email = untagged_user
		u.first_name = "Untagged"
		u.send_welcome_email = 0
		u.insert(ignore_permissions=True)

	for r_offset, r in enumerate(raw_data_rows):
		row_idx = start_row_offset + r_offset
		if not any(r):
			continue

		if total_rows > 0 and (r_offset % max(1, total_rows // 20) == 0 or r_offset == total_rows - 1):
			pct = min(100.0, float(r_offset + 1) / total_rows * 100)
			frappe.publish_progress(
				pct,
				title=_("Updating Master Data"),
				description=_("Processed {0} of {1} rows... (Created: {2}, Updated: {3}, Skipped: {4})").format(
					r_offset + 1, total_rows, created_count, updated_count, len(failed_rows)
				)
			)

		val_serial = r[col_serial] if col_serial is not None and col_serial < len(r) else None
		if (val_serial is None or str(val_serial).strip() == "") and col_serial_alt is not None and col_serial_alt < len(r):
			val_serial = r[col_serial_alt]

		if val_serial is None or str(val_serial).strip() == "":
			failed_rows.append({
				"row": row_idx,
				"serial": "-",
				"party": "-",
				"reason": _("Missing Tally Serial Number in row")
			})
			continue

		raw_serial = re.sub(r"\.0$", "", str(val_serial).strip())
		clean_serial = "".join(filter(str.isdigit, raw_serial))
		lookup_key = clean_serial if len(clean_serial) == 9 else raw_serial

		if not is_genuine_tally_serial(lookup_key):
			failed_rows.append({
				"row": row_idx,
				"serial": lookup_key,
				"party": "-",
				"reason": _("Invalid Tally Serial (Must be 9 digits starting with 7, digital root 9)")
			})
			continue

		target_rec = serial_map.get(lookup_key) or serial_map.get(raw_serial)
		acc_display = str(r[col_account]).strip() if (col_account is not None and col_account < len(r) and r[col_account]) else "-"
		if target_rec:
			doc_name = target_rec.name
			party_display = target_rec.cc_acc_name or target_rec.portal_acc_name or acc_display
		else:
			doc_name = None
			party_display = acc_display

		updates = {}

		# 1. Flavor & License
		if col_flavor is not None and col_flavor < len(r) and r[col_flavor]:
			f_val, lic_val = clean_flavour(r[col_flavor])
			if f_val:
				updates["flavour"] = f_val
			if lic_val:
				updates["license"] = lic_val

		# 2. TSS Expiry Date
		if col_expiry is not None and col_expiry < len(r) and r[col_expiry]:
			p_exp = safe_date(r[col_expiry])
			if p_exp:
				updates["portal_expiry_date"] = p_exp
				if not target_rec or not target_rec.acc_expiry_date:
					updates["acc_expiry_date"] = p_exp

		# 3. Release & Tally Version & Product Version
		if col_release is not None and col_release < len(r) and r[col_release]:
			rel = str(r[col_release]).strip()
			if rel and rel.lower() not in ("none", "nan", "null", "-"):
				updates["release"] = rel
				updates["tally_version"] = rel
				updates["product_ver"] = rel

		# 4. Account Name -> portal_acc_name ONLY
		if col_account is not None and col_account < len(r) and r[col_account]:
			acc = str(r[col_account]).strip()
			if acc and acc.lower() not in ("none", "nan", "null", "-"):
				updates["portal_acc_name"] = acc

		# 5. Account Email Id -> account_id (in License Details) & portal_email
		if col_email is not None and col_email < len(r) and r[col_email]:
			em = str(r[col_email]).strip()
			if em:
				updates["account_id"] = em
				updates["portal_email"] = em

		# 6. Customer Account Admin Email ID
		if col_admin_email is not None and col_admin_email < len(r) and r[col_admin_email]:
			adm = str(r[col_admin_email]).strip()
			if adm:
				updates["admin_id"] = adm

		# 7. Customer Address
		if col_address is not None and col_address < len(r) and r[col_address]:
			raw_addr = str(r[col_address]).strip()
			clean_addr = re.sub(r"^['\s,-]+|['\s,-]+$", "", raw_addr).strip()
			clean_addr = re.sub(r",\s*,+", ",", clean_addr).strip(" ,-")
			if clean_addr and clean_addr.lower() not in ("null", "none", "nan", "-"):
				updates["portal_address"] = clean_addr
				if not target_rec or not target_rec.address or str(target_rec.address).strip() in ("", "-", ", ,"):
					updates["address"] = clean_addr

		# 8. City / State -> state (Address details section of Portal Tab)
		if col_city is not None and col_city < len(r) and r[col_city]:
			city = str(r[col_city]).strip()
			if city and city.lower() not in ("none", "nan", "null", "-"):
				updates["state"] = city

		# 9. Pincode
		if col_pincode is not None and col_pincode < len(r) and r[col_pincode]:
			pin = re.sub(r"\.0$", "", str(r[col_pincode]).strip())
			if pin:
				updates["pincode"] = pin

		# 10. TSS Priority / Ranking
		if col_tss_priority is not None and col_tss_priority < len(r) and r[col_tss_priority]:
			prio = str(r[col_tss_priority]).strip()
			if prio:
				updates["tss_ranking"] = prio
				updates["crm_priority"] = prio

		# 11. MAU
		if col_mau is not None and col_mau < len(r) and r[col_mau] is not None:
			updates["mau"] = str(r[col_mau]).strip()

		# 12. Product Family
		if col_prod_family is not None and col_prod_family < len(r) and r[col_prod_family]:
			pf = str(r[col_prod_family]).strip()
			if pf:
				updates["product_family"] = pf

		# 13. Serial RFM Segmentation
		if col_rfm is not None and col_rfm < len(r) and r[col_rfm]:
			rfm = str(r[col_rfm]).strip()
			if rfm:
				updates["rfm_segment"] = rfm

		# 14. QAU
		if col_qau is not None and col_qau < len(r) and r[col_qau] is not None:
			updates["qau"] = str(r[col_qau]).strip()

		# 15. MCA Flag
		if col_mca is not None and col_mca < len(r) and r[col_mca] is not None:
			updates["mca_flag"] = str(r[col_mca]).strip()

		# 16. First actvn date time -> acc_start_date
		if col_actvn is not None and col_actvn < len(r) and r[col_actvn]:
			act_d = safe_date(r[col_actvn])
			if act_d:
				updates["acc_start_date"] = act_d

		# 17. Last Ping Date (text range)
		if col_last_ping is not None and col_last_ping < len(r) and r[col_last_ping]:
			lp = str(r[col_last_ping]).strip()
			if lp and lp.lower() not in ("none", "nan", "null"):
				updates["last_ping_date"] = lp

		# 18. Primary GSTIN Number -> gstin
		if col_gstin is not None and col_gstin < len(r) and r[col_gstin]:
			gst = str(r[col_gstin]).strip()
			if gst and gst.lower() not in ("none", "nan", "null"):
				updates["gstin"] = gst

		# 19. GSTIN E invoice enablement status -> gstin_e_invoice_status
		if col_e_invoice is not None and col_e_invoice < len(r) and r[col_e_invoice]:
			ei = str(r[col_e_invoice]).strip()
			if ei and ei.lower() not in ("none", "nan", "null"):
				updates["gstin_e_invoice_status"] = ei

		# 20. Available Storage(GB) -> available_storage_gb
		if col_avail_storage is not None and col_avail_storage < len(r) and r[col_avail_storage] is not None:
			try:
				s_val = str(r[col_avail_storage]).strip()
				if s_val and s_val.lower() not in ("none", "nan", "null"):
					updates["available_storage_gb"] = float(s_val)
			except (ValueError, TypeError):
				pass

		# 21. Used Storage(GB) -> used_storage_gb
		if col_used_storage is not None and col_used_storage < len(r) and r[col_used_storage] is not None:
			try:
				u_val = str(r[col_used_storage]).strip()
				if u_val and u_val.lower() not in ("none", "nan", "null"):
					updates["used_storage_gb"] = float(u_val)
			except (ValueError, TypeError):
				pass

		# 22. Docs By Ira Quota Available -> docs_by_ira_quota
		if col_ira_quota is not None and col_ira_quota < len(r) and r[col_ira_quota] is not None:
			iq = str(r[col_ira_quota]).strip()
			if iq and iq.lower() not in ("none", "nan", "null"):
				updates["docs_by_ira_quota"] = iq

		# 23. TSS Status -> tss_status
		if col_tss_status is not None and col_tss_status < len(r) and r[col_tss_status]:
			ts = str(r[col_tss_status]).strip()
			if ts and ts.lower() not in ("none", "nan", "null"):
				updates["tss_status"] = ts

		if not updates:
			failed_rows.append({
				"row": row_idx,
				"serial": lookup_key,
				"party": party_display,
				"reason": _("No values found to update in this row")
			})
			continue

		# Stamp last excel updated and set Reference Status to ACTIVE
		updates["last_updated"] = frappe.utils.today()
		updates["crm_ref"] = "ACTIVE"

		try:
			if doc_name:
				frappe.db.set_value("Hbs Tally Renewal", doc_name, updates, update_modified=True)
				updated_count += 1
			else:
				new_doc = frappe.new_doc("Hbs Tally Renewal")
				new_doc.flags.in_import = True
				new_doc.tally_serial = lookup_key
				new_doc.tss_tally_serial = lookup_key
				new_doc.customer_serial = lookup_key
				new_doc.crm_ex_1 = untagged_user
				new_doc.crm_executive = untagged_user
				new_doc.owner = untagged_user
				for k, v in updates.items():
					setattr(new_doc, k, v)
				if updates.get("portal_acc_name"):
					new_doc.cc_acc_name = updates["portal_acc_name"]
				new_doc.insert(ignore_permissions=True)
				created_count += 1

				target_dict = frappe._dict({
					"name": new_doc.name,
					"tally_serial": lookup_key,
					"tss_tally_serial": lookup_key,
					"cc_acc_name": getattr(new_doc, "cc_acc_name", None),
					"portal_acc_name": getattr(new_doc, "portal_acc_name", None),
					"acc_expiry_date": getattr(new_doc, "acc_expiry_date", None),
					"address": getattr(new_doc, "address", None),
					"portal_address": getattr(new_doc, "portal_address", None),
					"release": getattr(new_doc, "release", None),
					"tally_version": getattr(new_doc, "tally_version", None),
					"product_ver": getattr(new_doc, "product_ver", None),
					"state": getattr(new_doc, "state", None),
				})
				serial_map[lookup_key] = target_dict
				if raw_serial:
					serial_map[raw_serial] = target_dict

			if (updated_count + created_count) % 100 == 0:
				frappe.db.commit()

		except Exception as e:
			err_msg = frappe.utils.strip_html(str(e)).strip()
			failed_rows.append({
				"row": row_idx,
				"serial": lookup_key,
				"party": party_display,
				"reason": err_msg or _("Database save error")
			})

	frappe.publish_progress(100, title=_("Updating Master Data"), description=_("Update completed!"))
	frappe.db.commit()

	return {
		"status": "success",
		"report_title": _("📊 Master Data (Portal) Update Report"),
		"created_count": created_count,
		"updated_count": updated_count,
		"skipped_count": len(failed_rows),
		"failed_rows": failed_rows
	}


