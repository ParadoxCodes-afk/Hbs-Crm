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

	top_dict = {}
	if isinstance(data, dict):
		top_dict = data
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

		# Overdue days calculated strictly from current date - due_date (not from api sync)
		if due_date:
			overdue_days = max(0, frappe.utils.date_diff(now_date, due_date))
		else:
			overdue_days = 0

		# TDS flag
		tds_raw = str(_normalize_key(raw, "Is TDS Yes/No", "is_tds", "Is TDS", "is_tds_yes_no", "tds") or "").strip().lower()
		is_tds = "Yes" if tds_raw in ("yes", "y", "true", "1") else "No"

		# Executives
		ex1_raw = _normalize_key(raw, "Executive1", "executive_1", "Executive 1", "executive1")
		ex2_raw = _normalize_key(raw, "Executive2", "executive_2", "Executive 2", "executive2")
		ex1_code = str(ex1_raw or "").strip().upper().replace(".", "").replace(" ", "")
		if ex1_code == "JS":
			ex1_user = user_map.get("jyoti@hbsmail.in", "jyoti@hbsmail.in")
			ex2_user = user_map.get("saniya@hbsmail.in", "saniya@hbsmail.in")
		elif ex1_code == "AA":
			ex1_user = user_map.get("amrit@hbsmail.in", "amrit@hbsmail.in")
			ex2_user = user_map.get("aarti@hbsmail.in", "aarti@hbsmail.in")
		else:
			ex1_user = user_map.get(str(ex1_raw).strip().lower(), ex1_raw) if ex1_raw else None
			ex2_user = user_map.get(str(ex2_raw).strip().lower(), ex2_raw) if ex2_raw else None

		# Status: all active records in incoming outstanding sync are Pending
		status = "Pending"

		parsed_rows.append({
			"bill_no": bill_no_clean,
			"bill_date": bill_date,
			"party_name": party_name_clean,
			"company_name": company_name_clean,
			"bill_amt": bill_amt,
			"pending_amt": pending_amt,
			"due_date": due_date,
			"overdue_days": overdue_days,
			"is_tds": is_tds,
			"executive_1": ex1_user,
			"executive_2": ex2_user,
			"status": status,
			"last_sync_date": now_dt,
		})

	if not incoming_bill_nos:
		frappe.throw(_("No valid bill numbers found in payload."), title=_("Invalid Data"))

	# Determine company scope from incoming data and request parameters
	incoming_companies = set()
	param_company = (
		kwargs.get("company")
		or kwargs.get("company_name")
		or top_dict.get("company")
		or top_dict.get("company_name")
		or (frappe.form_dict.get("company") if hasattr(frappe, "form_dict") else None)
	)
	if param_company and str(param_company).strip():
		incoming_companies.add(str(param_company).strip())

	param_companies = (
		kwargs.get("companies")
		or top_dict.get("companies")
		or (frappe.form_dict.get("companies") if hasattr(frappe, "form_dict") else None)
	)
	if param_companies:
		if isinstance(param_companies, str):
			try:
				param_companies = frappe.parse_json(param_companies)
			except Exception:
				param_companies = [c.strip() for c in param_companies.split(",") if c.strip()]
		if isinstance(param_companies, (list, tuple, set)):
			for c in param_companies:
				if c and str(c).strip():
					incoming_companies.add(str(c).strip())

	for r in parsed_rows:
		c = r.get("company_name")
		if c and str(c).strip():
			incoming_companies.add(str(c).strip())

	# Determine whether to mark missing bills Complete (default: True, unless intermediate batch is specified)
	def _to_bool(val, default=True):
		if val is None:
			return default
		if isinstance(val, bool):
			return val
		s = str(val).strip().lower()
		return s in ("1", "true", "yes", "y", "t")

	del_param = kwargs.get("delete_missing")
	if del_param is None and hasattr(frappe, "form_dict"):
		del_param = frappe.form_dict.get("delete_missing")
	if del_param is None:
		del_param = kwargs.get("clear_unmatched") or (frappe.form_dict.get("clear_unmatched") if hasattr(frappe, "form_dict") else None)

	is_batch_param = kwargs.get("is_batch") or (frappe.form_dict.get("is_batch") if hasattr(frappe, "form_dict") else None)
	is_last_batch_param = kwargs.get("is_last_batch") or (frappe.form_dict.get("is_last_batch") if hasattr(frappe, "form_dict") else None)

	should_delete = True
	if is_batch_param is not None and _to_bool(is_batch_param, False):
		should_delete = False
	if is_last_batch_param is not None and _to_bool(is_last_batch_param, False):
		should_delete = True
	if del_param is not None:
		should_delete = _to_bool(del_param, True)

	completed_count = 0
	# Step 1: Update DB records for THIS COMPANY ONLY whose bill_no is NOT in the incoming payload to 'Complete'
	if should_delete:
		if incoming_companies:
			existing_company_records = frappe.db.sql(
				"SELECT `name`, `bill_no`, `status` FROM `tabHbs Outstanding` WHERE `company_name` IN %s",
				[tuple(incoming_companies)],
				as_dict=True
			)
		else:
			existing_company_records = frappe.db.sql(
				"SELECT `name`, `bill_no`, `status` FROM `tabHbs Outstanding` WHERE (`company_name` IS NULL OR `company_name` = '')",
				as_dict=True
			)

		to_complete = [r.name for r in existing_company_records if r.bill_no not in incoming_bill_nos and r.status != "Complete"]
		if to_complete:
			for i in range(0, len(to_complete), 50):
				chunk = to_complete[i:i + 50]
				frappe.db.sql(
					"UPDATE `tabHbs Outstanding` SET `status` = 'Complete', `modified` = %s WHERE `name` IN %s",
					[now_dt, tuple(chunk)]
				)
			completed_count = len(to_complete)
			frappe.db.commit()

	# Step 2: Index current records by bill_no
	bill_no_list = list(incoming_bill_nos)
	existing_active_map = {}
	for i in range(0, len(bill_no_list), 500):
		chunk = bill_no_list[i:i + 500]
		active_rows = frappe.db.sql(
			"SELECT `name`, `bill_no` FROM `tabHbs Outstanding` WHERE `bill_no` IN %s",
			[tuple(chunk)],
			as_dict=True
		)
		for r in active_rows:
			existing_active_map[r.bill_no] = r.name

	rows_to_update = []
	rows_to_insert = []
	for row in parsed_rows:
		if row["bill_no"] in existing_active_map:
			rows_to_update.append((existing_active_map[row["bill_no"]], row))
		else:
			rows_to_insert.append(row)

	inserted_count = 0
	updated_count = 0
	BATCH_SIZE = 50

	# Step 3: Fast batch update existing rows (in batches of 50)
	for i in range(0, len(rows_to_update), BATCH_SIZE):
		batch = rows_to_update[i:i + BATCH_SIZE]
		for doc_name, r in batch:
			frappe.db.sql("""
				UPDATE `tabHbs Outstanding`
				SET `bill_date` = %(bill_date)s,
					`party_name` = %(party_name)s,
					`company_name` = %(company_name)s,
					`bill_amt` = %(bill_amt)s,
					`pending_amt` = %(pending_amt)s,
					`due_date` = %(due_date)s,
					`overdue_days` = %(overdue_days)s,
					`is_tds` = %(is_tds)s,
					`executive_1` = %(executive_1)s,
					`executive_2` = %(executive_2)s,
					`status` = %(status)s,
					`last_sync_date` = %(last_sync_date)s,
					`modified` = %(modified)s
				WHERE `name` = %(name)s
			""", {
				**r,
				"name": doc_name,
				"modified": now_dt
			})
		updated_count += len(batch)
		frappe.db.commit()

	# Step 4: Fast batch insert new rows (in batches of 50)
	for i in range(0, len(rows_to_insert), BATCH_SIZE):
		batch = rows_to_insert[i:i + BATCH_SIZE]
		val_tuples = []
		for r in batch:
			seq_val = frappe.db.get_next_sequence_val("Hbs Outstanding")
			val_tuples.append((
				seq_val,
				r["bill_no"],
				r["party_name"],
				r["company_name"],
				r["bill_date"],
				r["due_date"],
				r["bill_amt"],
				r["pending_amt"],
				r["overdue_days"],
				r["is_tds"],
				r["executive_1"],
				r["executive_2"],
				r["status"],
				r["last_sync_date"],
				now_dt,
				now_dt,
				"Administrator",
				"Administrator",
				0
			))
		if val_tuples:
			placeholders = ", ".join(["(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"] * len(val_tuples))
			flat_vals = [item for sub in val_tuples for item in sub]
			frappe.db.sql(f"""
				INSERT INTO `tabHbs Outstanding` (
					`name`, `bill_no`, `party_name`, `company_name`, `bill_date`, `due_date`,
					`bill_amt`, `pending_amt`, `overdue_days`, `is_tds`, `executive_1`,
					`executive_2`, `status`, `last_sync_date`, `creation`, `modified`,
					`owner`, `modified_by`, `docstatus`
				) VALUES {placeholders}
			""", flat_vals)
		inserted_count += len(batch)
		frappe.db.commit()

	return {
		"status": "success",
		"message": f"Synced {len(parsed_rows)} bills successfully in batches of 50.",
		"total_received": len(data),
		"inserted": inserted_count,
		"updated": updated_count,
		"completed": completed_count,
		"deleted": 0,
		"companies": list(incoming_companies)
	}
