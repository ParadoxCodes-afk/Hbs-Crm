# Copyright (c) 2026, Hbs and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import now_datetime, getdate, nowtime, cstr


def log_executive_activity(
	reference_doctype,
	reference_name,
	activity_type,
	details="",
	party_name=None,
	user=None,
	user_name=None,
	contact_person=None,
	contact_phone=None,
	follow_up_date=None,
	status_before=None,
	status_after=None,
	timestamp=None
):
	"""Standard, robust logger for executive daily actions."""
	try:
		if not user:
			user = frappe.session.user

		# Skip Guest or automated syncs without a user
		if user in ("Guest",):
			return

		if not user_name:
			if user and user != "Administrator":
				user_name = frappe.get_cached_value("User", user, "full_name") or user
			else:
				user_name = "Administrator"

		dt = timestamp or now_datetime()
		act_date = getdate(dt)
		act_time = nowtime() if not timestamp else str(dt.time())[:8]

		# Prevent duplicate logs for the same document and action within 5 seconds (sargable index lookup)
		from datetime import timedelta
		cutoff = now_datetime() - timedelta(seconds=5)
		recent_dup = frappe.db.sql("""
			SELECT name FROM `tabHbs Executive Activity Log`
			WHERE reference_doctype = %s AND reference_name = %s
			  AND activity_type = %s AND user = %s
			  AND creation >= %s
			LIMIT 1
		""", (reference_doctype, cstr(reference_name), activity_type, user, cutoff))

		if recent_dup:
			return

		log_doc = frappe.get_doc({
			"doctype": "Hbs Executive Activity Log",
			"user": user,
			"user_name": user_name,
			"activity_date": act_date,
			"activity_time": act_time,
			"activity_type": activity_type,
			"reference_doctype": reference_doctype,
			"reference_name": cstr(reference_name),
			"party_name": cstr(party_name),
			"contact_person": cstr(contact_person),
			"contact_phone": cstr(contact_phone),
			"follow_up_date": follow_up_date,
			"status_before": cstr(status_before),
			"status_after": cstr(status_after),
			"details": cstr(details)
		})
		log_doc.insert(ignore_permissions=True)
	except Exception:
		# Fail-safe: activity logging must never crash primary business workflows
		frappe.log_error(title="Failed to log executive activity")


def backfill_historical_activities():
	"""Backfill historical remarks from tabHbs Lead Activity into tabHbs Executive Activity Log."""
	# Delete previous sample or test rows
	frappe.db.sql("DELETE FROM `tabHbs Executive Activity Log`")
	frappe.db.commit()

	imported_count = 0

	# 1. Backfill from Leads
	lead_activities = frappe.db.sql("""
		SELECT 
			a.user, a.date_time, a.remark,
			l.name as ref_name, l.company_name as party_name, l.contact_name, l.contact_phone,
			l.status, l.follow_up_date, l.executive_1
		FROM `tabHbs Lead Activity` a
		INNER JOIN `tabHbs Crm Lead` l ON a.parent = l.name AND a.parenttype = 'Hbs Crm Lead'
		ORDER BY a.date_time ASC
	""", as_dict=True)

	for act in lead_activities:
		user = act["user"] or act["executive_1"] or "Administrator"
		user_name = frappe.db.get_value("User", user, "full_name") or user
		dt = act["date_time"] or now_datetime()

		log_executive_activity(
			reference_doctype="Hbs Crm Lead",
			reference_name=act["ref_name"],
			activity_type="Follow-up Remark",
			details=act["remark"],
			party_name=act["party_name"],
			user=user,
			user_name=user_name,
			contact_person=act["contact_name"],
			contact_phone=act["contact_phone"],
			follow_up_date=act["follow_up_date"],
			timestamp=dt
		)
		imported_count += 1

	# 2. Backfill from Tally Renewals
	renewal_activities = frappe.db.sql("""
		SELECT 
			a.user, a.date_time, a.remark,
			r.name as ref_name, r.cc_acc_name as party_name, r.cc_contact as contact_name,
			COALESCE(NULLIF(r.cc_mobile, ''), r.cc_phone) as contact_phone,
			r.crm_status as status, r.follow_up_date, r.crm_ex_1
		FROM `tabHbs Lead Activity` a
		INNER JOIN `tabHbs Tally Renewal` r ON a.parent = r.name AND a.parenttype = 'Hbs Tally Renewal'
		ORDER BY a.date_time ASC
	""", as_dict=True)

	for act in renewal_activities:
		user = act["user"] or act["crm_ex_1"] or "Administrator"
		user_name = frappe.db.get_value("User", user, "full_name") or user
		dt = act["date_time"] or now_datetime()

		log_executive_activity(
			reference_doctype="Hbs Tally Renewal",
			reference_name=act["ref_name"],
			activity_type="Follow-up Remark",
			details=act["remark"],
			party_name=act["party_name"],
			user=user,
			user_name=user_name,
			contact_person=act["contact_name"],
			contact_phone=act["contact_phone"],
			follow_up_date=act["follow_up_date"],
			timestamp=dt
		)
		imported_count += 1

	# 3. Backfill from Outstanding
	out_activities = frappe.db.sql("""
		SELECT 
			a.user, a.date_time, a.remark,
			o.bill_no as ref_name, o.party_name, o.contact_person, o.contact_number as contact_phone,
			o.status, o.due_date as follow_up_date, o.executive_1
		FROM `tabHbs Lead Activity` a
		INNER JOIN `tabHbs Outstanding` o ON a.parent = o.name AND a.parenttype = 'Hbs Outstanding'
		ORDER BY a.date_time ASC
	""", as_dict=True)

	for act in out_activities:
		user = act["user"] or act["executive_1"] or "Administrator"
		user_name = frappe.db.get_value("User", user, "full_name") or user
		dt = act["date_time"] or now_datetime()

		log_executive_activity(
			reference_doctype="Hbs Outstanding",
			reference_name=act["ref_name"],
			activity_type="Payment Remark",
			details=act["remark"],
			party_name=act["party_name"],
			user=user,
			user_name=user_name,
			contact_person=act["contact_person"],
			contact_phone=act["contact_phone"],
			follow_up_date=act["follow_up_date"],
			timestamp=dt
		)
		imported_count += 1

	frappe.db.commit()
	return f"Successfully backfilled {imported_count} activities into Hbs Executive Activity Log."
