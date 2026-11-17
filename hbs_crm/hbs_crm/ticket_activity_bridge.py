# Copyright (c) 2026, Hbs and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import cstr, getdate, now_datetime


def on_ticket_insert(doc, method=None):
	"""Log support ticket creation to Hbs Executive Activity Log."""
	from hbs_crm.hbs_crm.activity_logger import log_executive_activity

	user = (
		(frappe.session.user if frappe.session and frappe.session.user else None)
		or doc.executive
		or "Administrator"
	)
	remark = (getattr(doc, "remarks", None) or "").strip()
	amc_tag = " • AMC" if getattr(doc, "amc_status", None) == "YES" else ""
	details = f"Ticket Created • {doc.call_type or 'Support'} ({doc.priority or 'P2'}){amc_tag}"
	if remark:
		details += f" — {remark}"

	log_executive_activity(
		reference_doctype="support_ticket",
		reference_name=cstr(doc.name),
		activity_type="Ticket Created",
		details=details,
		party_name=doc.party_name,
		user=user,
		contact_person=doc.contact_name,
		contact_phone=doc.contact_phone,
		follow_up_date=doc.followup_date,
		status_after=doc.status,
	)


def on_ticket_update(doc, method=None):
	"""Log support ticket follow-up remarks and resolutions (1 row per action)."""
	from hbs_crm.hbs_crm.activity_logger import log_executive_activity

	prev = doc.get_doc_before_save()
	if not prev:
		return
	prev_rows = prev.get("followup_history") or []
	curr_rows = doc.get("followup_history") or []

	prev_names = {r.name for r in prev_rows if getattr(r, "name", None)}
	if prev_names:
		new_rows = [r for r in curr_rows if getattr(r, "name", None) not in prev_names]
	elif len(curr_rows) > len(prev_rows):
		new_rows = curr_rows[len(prev_rows):]
	else:
		new_rows = []

	for r in new_rows:
		row_status = (getattr(r, "status", None) or doc.status or "").strip().upper()
		act_type = "Ticket Resolved" if row_status == "COMPLETED" else "Follow-up Remark"
		actor = (
			getattr(r, "updated_by", None)
			or (frappe.session.user if frappe.session and frappe.session.user else None)
			or doc.executive2
			or doc.executive
			or "Administrator"
		)
		sub_info = " / ".join(filter(None, [getattr(r, "sub_status", None), getattr(r, "sub_sub_status", None)]))
		remark_txt = (getattr(r, "remarks", None) or "").strip()
		if sub_info and remark_txt:
			details = f"[{sub_info}] {remark_txt}"
		elif remark_txt:
			details = remark_txt
		else:
			details = f"Status: {row_status}" + (f" ({sub_info})" if sub_info else "")

		log_executive_activity(
			reference_doctype="support_ticket",
			reference_name=cstr(doc.name),
			activity_type=act_type,
			details=details,
			party_name=doc.party_name,
			user=actor,
			contact_person=doc.contact_name,
			contact_phone=doc.contact_phone,
			follow_up_date=getattr(r, "followup_date", None) or doc.followup_date,
			status_before=prev.status if prev else "",
			status_after=getattr(r, "status", None) or doc.status,
		)

	# Status changed without adding a followup row
	if not new_rows and prev and doc.has_value_changed("status"):
		new_st = (doc.status or "").strip().upper()
		act_type = "Ticket Resolved" if new_st == "COMPLETED" else "Status Change"
		actor = (
			(frappe.session.user if frappe.session and frappe.session.user else None)
			or doc.executive2
			or doc.executive
			or "Administrator"
		)
		log_executive_activity(
			reference_doctype="support_ticket",
			reference_name=cstr(doc.name),
			activity_type=act_type,
			details=f"Ticket status changed: {prev.status} ➔ {doc.status}",
			party_name=doc.party_name,
			user=actor,
			contact_person=doc.contact_name,
			contact_phone=doc.contact_phone,
			follow_up_date=doc.followup_date,
			status_before=prev.status,
			status_after=doc.status,
		)


def backfill_support_ticket_activities():
	"""Idempotently backfill historical support_ticket_followup rows into Hbs Executive Activity Log."""
	existing = frappe.db.sql(
		"""
		SELECT reference_name, activity_date, activity_time, activity_type
		FROM `tabHbs Executive Activity Log`
		WHERE reference_doctype = 'support_ticket'
		""",
		as_dict=True,
	)
	seen = {
		(r["reference_name"], str(r["activity_date"]), str(r["activity_time"])[:8], r["activity_type"])
		for r in existing
	}

	rows = frappe.db.sql(
		"""
		SELECT
			f.parent as ticket_name, f.updated_by, f.updated_on, f.remarks,
			f.status as row_status, f.sub_status, f.sub_sub_status, f.followup_date as row_fu_date,
			t.party_name, t.contact_name, t.contact_phone, t.executive, t.executive2,
			t.call_type, t.priority, t.amc_status, t.creation
		FROM `tabsupport_ticket_followup` f
		INNER JOIN `tabsupport_ticket` t ON t.name = f.parent
		WHERE f.parenttype = 'support_ticket'
		ORDER BY COALESCE(f.updated_on, t.creation) ASC, f.idx ASC
		""",
		as_dict=True,
	)

	user_names = {}
	inserted = 0

	for r in rows:
		dt = r["updated_on"] or r["creation"] or now_datetime()
		act_date = str(getdate(dt))
		act_time = str(dt.time())[:8] if hasattr(dt, "time") else str(dt)[11:19]
		row_st = (r["row_status"] or "").strip().upper()

		if row_st == "COMPLETED":
			act_type = "Ticket Resolved"
		elif row_st == "NEW" and not (r["remarks"] or "").strip():
			act_type = "Ticket Created"
		else:
			act_type = "Follow-up Remark"

		key = (cstr(r["ticket_name"]), act_date, act_time, act_type)
		if key in seen:
			continue
		seen.add(key)

		actor = r["updated_by"] or r["executive2"] or r["executive"] or "Administrator"
		if actor == "Guest":
			continue
		if actor not in user_names:
			user_names[actor] = (
				"Administrator"
				if actor == "Administrator"
				else (frappe.db.get_value("User", actor, "full_name") or actor)
			)

		sub_info = " / ".join(filter(None, [r["sub_status"], r["sub_sub_status"]]))
		remark_txt = (r["remarks"] or "").strip()
		if sub_info and remark_txt:
			details = f"[{sub_info}] {remark_txt}"
		elif remark_txt:
			details = remark_txt
		elif act_type == "Ticket Created":
			amc_tag = " • AMC" if r["amc_status"] == "YES" else ""
			details = f"Ticket Created • {r['call_type'] or 'Support'} ({r['priority'] or 'P2'}){amc_tag}"
		else:
			details = f"Status: {row_st}" + (f" ({sub_info})" if sub_info else "")

		doc = frappe.get_doc(
			{
				"doctype": "Hbs Executive Activity Log",
				"user": actor,
				"user_name": user_names[actor],
				"activity_date": act_date,
				"activity_time": act_time,
				"activity_type": act_type,
				"reference_doctype": "support_ticket",
				"reference_name": cstr(r["ticket_name"]),
				"party_name": cstr(r["party_name"]),
				"contact_person": cstr(r["contact_name"]),
				"contact_phone": cstr(r["contact_phone"]),
				"follow_up_date": r["row_fu_date"],
				"status_after": r["row_status"] or "",
				"details": details,
			}
		)
		doc.insert(ignore_permissions=True)
		inserted += 1

	if inserted:
		frappe.db.commit()
	return inserted
