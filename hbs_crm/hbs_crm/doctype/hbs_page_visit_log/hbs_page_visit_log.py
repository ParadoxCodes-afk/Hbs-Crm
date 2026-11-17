# Copyright (c) 2026, Hbs and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import cint, nowdate, nowtime


class HbsPageVisitLog(Document):
	pass


def on_doctype_update():
	"""Create composite indexes for lock-free daily summary upserts and dashboard reads."""
	frappe.db.add_unique("Hbs Page Visit Log", ["user", "visit_date", "page_name"], constraint_name="uniq_user_date_page")
	frappe.db.add_index("Hbs Page Visit Log", ["visit_date", "user"], index_name="idx_visit_date_user")


@frappe.whitelist()
def log_page_visit(page_name=None, page_route="", active_seconds=0, is_new_visit=0):
	"""Atomically accumulate active focused screen time per (user, date, page_name).

	Bypasses full Document lifecycle, hooks, and realtime broadcasts for minimal RAM/CPU overhead.
	"""
	user = frappe.session.user if frappe.session else None
	if not user or user in ("Guest", "Administrator"):
		return {"ok": False}

	clean_name = str(page_name or "").strip()[:140]
	if not clean_name:
		return {"ok": False}

	secs = max(0, min(cint(active_seconds), 300))
	visits = 1 if cint(is_new_visit) else 0
	if secs == 0 and visits == 0:
		return {"ok": True}

	clean_route = str(page_route or "").strip()[:140]
	today = nowdate()
	now_t = nowtime()[:8]
	params = {
		"user": user,
		"visit_date": today,
		"page_name": clean_name,
		"page_route": clean_route,
		"secs": secs,
		"visits": visits,
		"now_t": now_t,
	}

	# Fast path: single indexed UPDATE (avoids sequence overhead on heartbeats/revisits)
	frappe.db.sql(
		"""
		UPDATE `tabHbs Page Visit Log`
		SET `active_seconds` = `active_seconds` + %(secs)s,
			`visit_count` = `visit_count` + %(visits)s,
			`page_route` = COALESCE(NULLIF(%(page_route)s, ''), `page_route`),
			`last_visit_time` = %(now_t)s,
			`modified` = NOW(6)
		WHERE `user` = %(user)s AND `visit_date` = %(visit_date)s AND `page_name` = %(page_name)s
		""",
		params,
	)

	if frappe.db._cursor.rowcount == 0:
		params["name"] = frappe.db.get_next_sequence_val("Hbs Page Visit Log")
		frappe.db.sql(
			"""
			INSERT INTO `tabHbs Page Visit Log`
				(`name`, `creation`, `modified`, `modified_by`, `owner`, `docstatus`, `idx`,
				 `user`, `visit_date`, `page_name`, `page_route`,
				 `active_seconds`, `visit_count`, `first_visit_time`, `last_visit_time`)
			VALUES
				(%(name)s, NOW(6), NOW(6), %(user)s, %(user)s, 0, 0,
				 %(user)s, %(visit_date)s, %(page_name)s, %(page_route)s,
				 %(secs)s, %(visits)s, %(now_t)s, %(now_t)s)
			ON DUPLICATE KEY UPDATE
				`active_seconds` = `active_seconds` + VALUES(`active_seconds`),
				`visit_count` = `visit_count` + VALUES(`visit_count`),
				`page_route` = COALESCE(NULLIF(VALUES(`page_route`), ''), `page_route`),
				`last_visit_time` = VALUES(`last_visit_time`),
				`modified` = NOW(6)
			""",
			params,
		)
	return {"ok": True}
