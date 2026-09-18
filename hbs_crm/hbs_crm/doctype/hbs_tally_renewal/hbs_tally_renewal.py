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
		if not doc.is_new():
			doc.db_set("quotation_date", today)
		doc.quotation_date = today

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
			doc.db_set("pi_number", full_pi_number)
		doc.pi_number = full_pi_number

		# Only update last_generated_renewal_pi_number; preserve admin's base order in renewal_pi_number_order
		frappe.db.set_single_value("Hbs CRM Settings", "last_generated_renewal_pi_number", full_pi_number)


class HbsTallyRenewal(Document):
	def validate(self):
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
		if getattr(self, "items", None) and len(self.items) > 0 and not getattr(self.flags, "in_import", False):
			if not getattr(self, "quotation_date", None):
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
		"""Calculate totals and taxes taking additional discount into account first."""
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
			discount = frappe.utils.flt(row.discount_amount) or 0
			row_subtotal = (qty * rate) - discount
			row_subtotals.append(row_subtotal)
			total_before_tax += row_subtotal

		additional_discount = frappe.utils.flt(self.additional_discount) or 0
		total_tax = 0
		total_after_tax = 0

		for row, row_subtotal in zip(self.items, row_subtotals):
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
		if self.final_total > 0 and not getattr(self.flags, "in_import", False):
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
				"tss_tally_serial", "license", "tally_version", "acc_expiry_date",
				"cc_acc_name", "cc_contact", "cc_phone", "cc_email"
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
			("cc_acc_name", "Account / Company Name"),
			("cc_phone", "Phone Number"),
		]

		for fn, label in locked_fields:
			old_val = str(old_doc.get(fn) or "").strip()
			new_val = str(self.get(fn) or "").strip()
			if old_val != new_val and old_val:
				frappe.throw(
					_("<b>Field Locked ({0})!</b><br>Only Mobile Number, Email ID, and Contact Person can be modified on saved records.").format(label),
					title=_("Alteration Restricted")
				)

		# Enforce quote items and rate lock for normal users
		old_discount = frappe.db.get_value("Hbs Tally Renewal", self.name, "additional_discount") or 0
		if frappe.utils.flt(self.additional_discount) != frappe.utils.flt(old_discount):
			frappe.throw(
				_("<b>Quote Locked!</b><br>Only Admin/Owner can change additional discount."),
				title=_("Alteration Restricted")
			)

		old_items = frappe.get_all(
			"hbs crm items",
			filters={"parent": self.name, "parenttype": "Hbs Tally Renewal"},
			fields=["item_name", "qty", "rate", "discount_amount"],
			order_by="idx asc"
		)
		new_items = [
			{
				"item_name": str(r.item_name or "").strip(),
				"qty": frappe.utils.flt(r.qty),
				"rate": frappe.utils.flt(r.rate),
				"discount_amount": frappe.utils.flt(r.discount_amount),
			}
			for r in getattr(self, "items", [])
		]
		old_items_clean = [
			{
				"item_name": str(r.item_name or "").strip(),
				"qty": frappe.utils.flt(r.qty),
				"rate": frappe.utils.flt(r.rate),
				"discount_amount": frappe.utils.flt(r.discount_amount),
			}
			for r in old_items
		]
		if old_items_clean and new_items != old_items_clean:
			frappe.throw(
				_("<b>Quote Locked!</b><br>Only Admin/Owner can modify quotation items or rates."),
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
			if not is_genuine_tally_serial(raw_serial):
				frappe.throw(_("Invalid Serial Number"), title=_("Invalid Serial Number"))

			serial = "".join(filter(str.isdigit, raw_serial))
			self.tally_serial = serial
			self.tss_tally_serial = serial

	def validate_no_duplicate_serial(self):
		"""Block saving if an active renewal (<= 15 days without remarks) for the same Tally serial exists."""
		serial = self.tally_serial or self.tss_tally_serial
		if not serial:
			return

		dup = check_duplicate_renewal(serial, current_renewal_name=self.name)
		if dup:
			# Inactive (> 15 days without remarks): allow saving/takeover
			if dup.get("is_inactive"):
				return

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
		"""Ensure contact person, mobile, and email populate into All Contacts history."""
		name = (self.cc_contact or "").strip()
		mobile = (self.cc_mobile or self.cc_phone or "").strip()
		email = (self.cc_email or "").strip()

		if not name and not mobile and not email:
			return

		if not getattr(self, "all_contacts", None):
			self.all_contacts = []

		matched_row = None
		for row in self.all_contacts:
			r_name = (row.contact_name or "").strip()
			r_phone = (row.contact_phone or "").strip()
			r_email = (row.contact_email or "").strip()

			if mobile and r_phone == mobile:
				matched_row = row
				break
			if email and r_email == email:
				matched_row = row
				break
			if not mobile and not email and name and r_name == name:
				matched_row = row
				break

		if matched_row:
			if name and not matched_row.contact_name:
				matched_row.contact_name = name
			if mobile and not matched_row.contact_phone:
				matched_row.contact_phone = mobile
			if email and not matched_row.contact_email:
				matched_row.contact_email = email
		else:
			self.append("all_contacts", {
				"contact_name": name,
				"contact_phone": mobile,
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
	"""Check if an active renewal already exists for the given Tally serial number."""
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
	where += " AND LOWER(IFNULL(crm_status, '')) != 'sold' AND LOWER(IFNULL(crm_stage, '')) != 'sold'"

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

	if is_lost:
		# If CRM status is lost, other person can overtake that lead without any checking
		dup["days_inactive"] = 0
		dup["is_inactive"] = True
	else:
		last_date = dup.get("last_remarks_date") or dup.get("contact_on") or dup.get("creation")
		if last_date:
			today = frappe.utils.getdate()
			last_d = frappe.utils.getdate(last_date)
			days_diff = frappe.utils.date_diff(today, last_d)
			dup["days_inactive"] = max(0, days_diff)
			dup["last_remarks_date_formatted"] = frappe.utils.formatdate(last_d, "dd/MM/yyyy")
			dup["is_inactive"] = days_diff > 15
		else:
			dup["days_inactive"] = 0
			dup["is_inactive"] = False

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
def check_portal(name):
	"""Check Tally Portal API using credentials from Hbs CRM Settings and populate fields."""
	doc = frappe.get_doc("Hbs Tally Renewal", name)
	user = frappe.session.user if frappe.session else "System"
	if not is_owner_or_admin(user) and not has_permission(doc, "read", user):
		frappe.throw(_("You do not have permission to sync this renewal."), title=_("Permission Denied"))

	serial = str(doc.tally_serial or "").strip()
	if not serial:
		frappe.throw(_("Tally Serial Number is required."), title=_("Serial Number Missing"))

	base_url, keys_to_try = get_tally_portal_credentials()

	res = None
	last_err = "Serial not mapped or invalid."

	try:
		for apikey in keys_to_try:
			url = build_tally_portal_url(base_url, apikey, serial)
			resp = requests.get(url, timeout=15).json()
			if resp and resp.get("expiry_details", {}).get("serial_status") == 1:
				res = resp
				break
			else:
				if resp:
					last_err = resp.get("expiry_details", {}).get("message") or resp.get("status_message") or last_err

		doc.response = json.dumps(res or resp, indent=2)

		if res:
			data = res.get("expiry_details", {}).get("serial_data", {})
			synced_fields = []
			unsynced_fields = []

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

			# 16. Portal Expiry Date
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

			# Activation Date
			act_str = data.get("activation_date")
			if act_str:
				parsed_act = safe_parse_portal_date(act_str)
				if parsed_act:
					doc.acc_start_date = parsed_act
					synced_fields.append("Activation Date")

			doc.status = "success"
			doc.error = None
			doc.crm_ref = "Mapped"
			if len(synced_fields) > 0:
				doc.last_updated_api = frappe.utils.nowdate()
			doc.flags.in_api_sync = True
			doc.save(ignore_permissions=True)
			frappe.db.commit()

			return {
				"status": "success",
				"message": _("Portal details fetched successfully!"),
				"synced_count": len(synced_fields),
				"unsynced_count": len(unsynced_fields),
				"synced_fields": synced_fields,
				"unsynced_fields": unsynced_fields
			}
		else:
			doc.crm_ref = "Moved Out"
			doc.status = "error"
			doc.error = str(last_err)
			doc.flags.in_api_sync = True
			doc.save(ignore_permissions=True)
			frappe.db.commit()
			return {"status": "error", "message": last_err}
	except Exception as e:
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
def bulk_update_renewal_fields(names, updates=None, remark=None):
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
				"follow_up_date", "last_remarks_date"
			}
			for k, v in updates.items():
				if k in allowed_fields and v is not None and str(v).strip() != "":
					update_dict[k] = v

	remark_text = str(remark).strip() if remark else ""
	if not update_dict and not remark_text:
		frappe.throw(_("Please provide at least one field value or remark to update."))

	for name in target_names:
		if remark_text:
			doc = frappe.get_doc("Hbs Tally Renewal", name)
			for k, v in update_dict.items():
				setattr(doc, k, v)
			if doc.crm_status == "Lost":
				doc.crm_lost_remarks = remark_text

			if "last_remarks_date" not in update_dict:
				doc.last_remarks_date = frappe.utils.nowdate()
				doc.contact_on = doc.last_remarks_date
			else:
				doc.contact_on = doc.last_remarks_date

			doc.last_updated = frappe.utils.nowdate()
			user_email = frappe.session.user if frappe.session and frappe.session.user else "System"
			doc.append("custom_activities", {
				"user": user_email,
				"date_time": frappe.utils.now_datetime(),
				"remark": remark_text
			})
			doc.last_remark = remark_text
			doc.render_activity_html()
			if hasattr(doc, "render_old_remarks_html"):
				doc.render_old_remarks_html()
			doc.flags.in_follow_up = True
			doc.save(ignore_permissions=True)
		else:
			doc_updates = dict(update_dict)
			if "last_remarks_date" in doc_updates:
				doc_updates["contact_on"] = doc_updates["last_remarks_date"]
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

	base_url, keys_to_try = get_tally_portal_credentials()
	if isinstance(names, str):
		names = json.loads(names)
	
	success = 0
	failed = 0
	total_fields_updated = 0
	for name in names:
		try:
			res = check_portal(name)
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


def is_owner_or_admin(user=None):
	"""True if user is Administrator/System, has System Manager role, or has role_type 'Owner' in Hbs User Hierarchy."""
	if not user:
		user = frappe.session.user if frappe.session else "Administrator"
	if user in ("Administrator", "System"):
		return True
	if "System Manager" in frappe.get_roles(user):
		return True
	role_type = frappe.db.get_value("Hbs User Hierarchy", {"user": user}, "role_type")
	return role_type == "Owner"


def get_subordinates_from_hierarchy(user, visited=None, is_root=True):
	"""Recursively get all subordinates reporting directly or indirectly to user."""
	if not hasattr(frappe.local, "subordinates_cache"):
		frappe.local.subordinates_cache = {}

	if is_root and user in frappe.local.subordinates_cache:
		return frappe.local.subordinates_cache[user]

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
			subordinates.extend(get_subordinates_from_hierarchy(report, visited, is_root=False))

	result = list(set(subordinates))
	if is_root:
		frappe.local.subordinates_cache[user] = result
	return result


def get_permission_query_conditions(user=None):
	"""Permission query hook for Hbs Tally Renewal based on User Hierarchy."""
	if not user:
		user = frappe.session.user

	if is_owner_or_admin(user):
		return ""

	# Managers in Hbs User Hierarchy can see all leads
	role_type = frappe.db.get_value("Hbs User Hierarchy", {"user": user}, "role_type")
	if role_type == "Manager":
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

	# Managers in Hbs User Hierarchy can view, email, and print all leads
	role_type = frappe.db.get_value("Hbs User Hierarchy", {"user": user}, "role_type")
	if role_type == "Manager" and ptype in ("read", "email", "print"):
		return True

	if getattr(frappe.flags, "in_takeover", False):
		return True

	if not doc:
		return True

	subordinates = get_subordinates_from_hierarchy(user)
	team_members = set([user] + subordinates)

	doc_obj = doc if hasattr(doc, "get") else frappe.get_doc("Hbs Tally Renewal", doc)

	if getattr(doc_obj, "flags", None) and getattr(doc_obj.flags, "in_takeover", False):
		return True

	# 1. Check in-memory doc values
	if doc_obj.get("crm_ex_1") in team_members:
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


def get_logged_in_user_context(user=None):
	user_name = user or (frappe.session.user if frappe.session else "Administrator")
	user_doc = frappe.get_doc("User", user_name) if user_name and user_name != "Guest" and frappe.db.exists("User", user_name) else None
	full_name = (user_doc.get("full_name") or user_doc.get("first_name") or "Executive") if user_doc else "Executive"
	mobile_no = (user_doc.get("mobile_no") or user_doc.get("phone") or user_doc.get("phone_number") or "") if user_doc else ""
	email = (user_doc.get("email") or "") if user_doc else ""
	designation = (user_doc.get("designation") or "") if user_doc else ""

	return {
		"full_name": full_name,
		"email": email,
		"mobile_no": mobile_no,
		"phone": mobile_no,
		"phone_number": mobile_no,
		"designation": designation
	}


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
<b>{{ logged_in_user.full_name or 'HBS Sales Team' }}</b><br>
{% if logged_in_user.designation %}{{ logged_in_user.designation }}<br>{% endif %}
{% if logged_in_user.mobile_no %}Mobile: {{ logged_in_user.mobile_no }}<br>{% endif %}
{% if logged_in_user.email %}Email: {{ logged_in_user.email }}{% endif %}
</p>"""


def render_renewal_email_for_doc(doc, logged_in_user_dict=None):
	"""Render email subject and body using Jinja from settings or defaults."""
	if logged_in_user_dict is None:
		logged_in_user_dict = get_logged_in_user_context()
	settings = frappe.get_single("Hbs CRM Email Settings") if frappe.db.exists("DocType", "Hbs CRM Email Settings") else frappe._dict()
	subject_template = (getattr(settings, "renewal_email_subject", None) or "").strip() or DEFAULT_RENEWAL_EMAIL_SUBJECT
	body_template = (getattr(settings, "renewal_email_body", None) or "").strip() or DEFAULT_RENEWAL_EMAIL_BODY

	context = {"doc": doc, "logged_in_user": logged_in_user_dict}
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
	logged_in_user_dict = get_logged_in_user_context()

	rendered = render_renewal_email_for_doc(doc, logged_in_user_dict)
	user_email = logged_in_user_dict.get("email") or (frappe.session.user if frappe.session and "@" in str(frappe.session.user) else "")

	return {
		"subject": rendered["subject"],
		"message": rendered["message"],
		"to_email": doc.cc_email or doc.portal_email or "",
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
		doc.db_set("cc_email", recipients_list[0])
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

	user_email = frappe.session.user if frappe.session and frappe.session.user else "System"
	clean_rem = f"Sent TSS Quotation to {to_email} | Subject: {subject}"
	doc.append("custom_activities", {
		"user": user_email,
		"date_time": frappe.utils.now_datetime(),
		"remark": clean_rem
	})
	doc.last_remark = clean_rem
	doc.last_remarks_date = frappe.utils.nowdate()
	doc.contact_on = doc.last_remarks_date
	doc.last_updated = frappe.utils.nowdate()
	doc.render_activity_html()
	doc.flags.in_follow_up = True
	doc.save(ignore_permissions=True)
	frappe.db.commit()

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

	success_count = 0
	skipped_no_email = []
	failed_records = []

	for name in names:
		try:
			doc = frappe.get_doc("Hbs Tally Renewal", name)
			if not can_bulk_all and not has_permission(doc, "read", user_email):
				failed_records.append({"name": name, "error": "Permission Denied"})
				continue

			to_email = (doc.cc_email or doc.portal_email or "").strip()
			if not to_email:
				skipped_no_email.append(doc.name)
				continue

			assign_renewal_pi_and_date(doc)

			ctx = {"doc": doc, "logged_in_user": logged_in_user_dict}
			rendered_subject = frappe.render_template(subject_template, ctx)
			rendered_message = frappe.render_template(message_template, ctx)

			recipients = [e.strip() for e in to_email.split(",") if e.strip()]
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
				now=True
			)

			clean_rem = f"Bulk TSS Quotation sent to {to_email} | Subject: {rendered_subject}"
			doc.append("custom_activities", {
				"user": user_email,
				"date_time": frappe.utils.now_datetime(),
				"remark": clean_rem
			})
			doc.last_remark = clean_rem
			doc.last_remarks_date = frappe.utils.nowdate()
			doc.contact_on = doc.last_remarks_date
			doc.last_updated = frappe.utils.nowdate()
			doc.render_activity_html()
			doc.flags.in_follow_up = True
			doc.save(ignore_permissions=True)
			success_count += 1
		except Exception as e:
			frappe.log_error(f"Bulk quotation email failed for {name}: {str(e)}", "Bulk Renewal Email Error")
			failed_records.append({"name": name, "error": str(e)})

	frappe.db.commit()

	return {
		"status": "success",
		"success_count": success_count,
		"skipped_no_email": skipped_no_email,
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

	def resolve_user(val):
		if not val:
			return None
		val_clean = str(val).strip()
		if frappe.db.exists("User", val_clean, cache=True):
			return val_clean
		if val_clean.lower() in user_map:
			target = user_map[val_clean.lower()]
			if frappe.db.exists("User", target, cache=True):
				return target
		resolved = (
			frappe.db.get_value("User", {"username": val_clean.lower()})
			or frappe.db.get_value("User", {"username": val_clean})
			or frappe.db.get_value("User", {"first_name": val_clean})
			or frappe.db.get_value("User", {"full_name": val_clean})
		)
		return resolved or val_clean

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


