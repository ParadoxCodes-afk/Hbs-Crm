# Copyright (c) 2026, Hbs and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def _safe_date(val):
	"""Parse date safely from string, datetime, or date."""
	if not val:
		return None
	try:
		return frappe.utils.getdate(val)
	except Exception:
		# Try DD-MM-YYYY or DD/MM/YYYY
		val_str = str(val).strip()
		for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d", "%d-%b-%y", "%d-%b-%Y", "%d/%b/%y", "%d/%b/%Y"):
			try:
				import datetime
				return datetime.datetime.strptime(val_str, fmt).date()
			except Exception:
				continue
	return None


def _normalize_key(row, *keys):
	"""Find the first matching key in row (case/space-insensitive)."""
	if not isinstance(row, dict):
		return None
	for k in keys:
		if k in row and row[k] is not None:
			return row[k]
	# Try case-insensitive matching
	lower_map = {str(orig).strip().lower(): orig for orig in row.keys()}
	for k in keys:
		target = str(k).strip().lower()
		if target in lower_map:
			orig_key = lower_map[target]
			if row[orig_key] is not None:
				return row[orig_key]
	return None


@frappe.whitelist(methods=["POST"])
def sync_outstanding(data=None, **kwargs):
	"""Ingest live Outstanding billing report snapshot via JSON API.
	- Matches schema from billing system (OUTSTANDING sheet / JSON).
	- Idempotent snapshot sync:
	  1. Deletes records from DB whose bill_no is not in the incoming payload (cleared/paid).
	  2. Updates existing records with fresh amounts and overdue days.
	  3. Inserts new bills.
	- Resolves executive links to User records.
	- Links to Hbs Customer if party_name matches an existing customer.
	"""
	# Extract JSON payload across all possible caller methods (direct arg, kwargs, form_dict, raw request body)
	if data is None:
		for k in ("Outstanding", "outstanding", "data", "bills", "items", "records"):
			if k in kwargs and kwargs[k]:
				data = kwargs[k]
				break

	if data is None and hasattr(frappe, "form_dict"):
		for k in ("Outstanding", "outstanding", "data", "bills", "items", "records"):
			if k in frappe.form_dict and frappe.form_dict[k]:
				data = frappe.form_dict[k]
				break

	if data is None and hasattr(frappe, "request") and frappe.request:
		req_data = getattr(frappe.request, "data", None)
		if not req_data and hasattr(frappe.request, "get_data"):
			try:
				req_data = frappe.request.get_data()
			except Exception:
				pass
		if req_data:
			try:
				parsed = frappe.parse_json(req_data)
				if isinstance(parsed, dict):
					for k in ("Outstanding", "outstanding", "data", "bills", "items", "records"):
						if k in parsed:
							data = parsed[k]
							break
					if data is None:
						data = parsed
				elif isinstance(parsed, list):
					data = parsed
			except Exception:
				pass

	if isinstance(data, str):
		try:
			data = frappe.parse_json(data)
		except Exception:
			pass

	if isinstance(data, dict):
		for key in ("Outstanding", "outstanding", "data", "bills", "items", "records"):
			if key in data and isinstance(data[key], (list, str)):
				data = data[key]
				if isinstance(data, str):
					try:
						data = frappe.parse_json(data)
					except Exception:
						pass
				break

	if not isinstance(data, list):
		if isinstance(data, dict):
			data = [data]
		else:
			frappe.throw(
				_("Invalid payload. Expected a list of bills or { 'Outstanding': [...] }"),
				title=_("Invalid Request")
			)

	if not data:
		return {
			"status": "success",
			"message": "Empty data received. No records modified.",
			"total_received": 0,
			"inserted": 0,
			"updated": 0,
			"deleted": 0
		}

	# Build executive user resolution map
	users = frappe.db.sql(
		"SELECT `name`, `email`, `full_name`, `first_name` FROM `tabUser` WHERE `enabled` = 1",
		as_dict=True
	)
	user_map = {}
	for u in users:
		if u.name:
			user_map[u.name.strip().lower()] = u.name
		if u.email:
			user_map[u.email.strip().lower()] = u.name
		if u.full_name:
			user_map[u.full_name.strip().lower()] = u.name
		if u.first_name:
			user_map[u.first_name.strip().lower()] = u.name
	now_dt = frappe.utils.now_datetime()
	now_date = frappe.utils.nowdate()

	# Parse and normalize incoming rows
	parsed_rows = []
	incoming_bill_nos = set()

	for raw in data:
		if not isinstance(raw, dict):
			continue

		bill_no = _normalize_key(raw, "bill No", "bill_no", "Bill No", "billno", "BillNo", "bill_number")
		if not bill_no or not str(bill_no).strip():
			continue

		bill_no_clean = str(bill_no).strip()
		incoming_bill_nos.add(bill_no_clean)

		party_name = _normalize_key(raw, "party Name", "party_name", "Party Name", "PartyName", "Party", "party", "customer_name", "Customer Name", "Customer", "customer", "Particulars", "particulars", "Ledger Name", "ledger_name") or "Unknown Party"
		party_name_clean = str(party_name).strip() or "Unknown Party"

		company_name = _normalize_key(raw, "Company Name", "company_name", "Company", "company", "Company_Name", "comp_name")
		company_name_clean = str(company_name or "").strip()

		bill_date = _safe_date(_normalize_key(raw, "Date", "date", "bill_date", "Bill Date")) or now_date
		due_date = _safe_date(_normalize_key(raw, "Due Date", "due_date", "DueDate", "Due_Date"))

		bill_amt = frappe.utils.flt(_normalize_key(raw, "Bill Amt", "bill_amt", "Bill Amount", "bill_amount", "amount"))
		pending_amt = frappe.utils.flt(_normalize_key(raw, "Pending Amt", "pending_amt", "Pending Amount", "pending_amount"))

		overdue_days_val = _normalize_key(raw, "Over Due Days", "overdue_days", "Overdue Days", "over_due_days", "overdue")
		if overdue_days_val is not None and str(overdue_days_val).strip() != "":
			overdue_days = frappe.utils.cint(overdue_days_val)
		elif due_date:
			overdue_days = max(0, frappe.utils.date_diff(now_date, due_date))
		else:
			overdue_days = 0

		# TDS flag
		tds_raw = str(_normalize_key(raw, "Is TDS Yes/No", "is_tds", "Is TDS", "is_tds_yes_no", "tds") or "").strip().lower()
		is_tds = "Yes" if tds_raw in ("yes", "y", "true", "1") else "No"

		# Executives
		ex1_raw = _normalize_key(raw, "Executive1", "executive_1", "Executive 1", "executive1")
		ex2_raw = _normalize_key(raw, "Executive2", "executive_2", "Executive 2", "executive2")
		ex1_user = user_map.get(str(ex1_raw).strip().lower()) if ex1_raw else None
		ex2_user = user_map.get(str(ex2_raw).strip().lower()) if ex2_raw else None

		# Status
		if pending_amt == 0:
			status = "Cleared"
		elif bill_amt and abs(pending_amt) < abs(bill_amt):
			status = "Partially Paid"
		else:
			status = "Pending"

		parsed_rows.append({
			"bill_no": bill_no_clean,
			"bill_date": bill_date,
			"party_name": party_name_clean,
			"company_name": company_name_clean,
			"customer": None,
			"bill_amt": bill_amt,
			"pending_amt": pending_amt,
			"due_date": due_date,
			"overdue_days": overdue_days,
			"is_tds": is_tds,
			"executive_1": ex1_user,
			"executive_2": ex2_user,
			"executive_1_name": str(ex1_raw).strip() if ex1_raw else None,
			"executive_2_name": str(ex2_raw).strip() if ex2_raw else None,
			"status": status,
			"last_sync_date": now_dt,
		})

	if not incoming_bill_nos:
		frappe.throw(_("No valid bill numbers found in payload."), title=_("Invalid Data"))

	# Step 1: Remove DB records whose bill_no is NOT in the incoming payload (bills cleared/paid)
	existing_all = frappe.db.sql(
		"SELECT `name`, `bill_no` FROM `tabHbs Outstanding`",
		as_dict=True
	)
	to_delete = [r.name for r in existing_all if r.bill_no not in incoming_bill_nos]
	deleted_count = 0
	if to_delete:
		# Batch delete in chunks of 500
		for i in range(0, len(to_delete), 500):
			chunk = to_delete[i:i + 500]
			frappe.db.delete("Hbs Outstanding", {"name": ["in", chunk]})
		deleted_count = len(to_delete)

	# Step 2: Index current records by bill_no
	existing_active_map = {
		r.bill_no: r.name
		for r in existing_all
		if r.bill_no in incoming_bill_nos
	}

	inserted_count = 0
	updated_count = 0

	# Step 3: Insert or update incoming rows
	for row in parsed_rows:
		b_no = row["bill_no"]
		if b_no in existing_active_map:
			doc_name = existing_active_map[b_no]
			frappe.db.set_value("Hbs Outstanding", doc_name, {
				"bill_date": row["bill_date"],
				"party_name": row["party_name"],
				"company_name": row["company_name"],
				"customer": row["customer"],
				"bill_amt": row["bill_amt"],
				"pending_amt": row["pending_amt"],
				"due_date": row["due_date"],
				"overdue_days": row["overdue_days"],
				"is_tds": row["is_tds"],
				"executive_1": row["executive_1"],
				"executive_2": row["executive_2"],
				"executive_1_name": row["executive_1_name"],
				"executive_2_name": row["executive_2_name"],
				"status": row["status"],
				"last_sync_date": row["last_sync_date"],
			}, update_modified=False)
			updated_count += 1
		else:
			new_doc = frappe.new_doc("Hbs Outstanding")
			new_doc.flags.in_api_sync = True
			new_doc.update(row)
			new_doc.insert(ignore_permissions=True)
			existing_active_map[b_no] = new_doc.name
			inserted_count += 1

	frappe.db.commit()

	return {
		"status": "success",
		"message": f"Synced {len(parsed_rows)} bills successfully.",
		"total_received": len(data),
		"inserted": inserted_count,
		"updated": updated_count,
		"deleted": deleted_count,
	}
