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


@frappe.whitelist(methods=["POST"])
def sync_incentives(data=None, **kwargs):
	"""Ingest Sales, Credit Notes & Incentives from billing system.
	- Schema matches 'Hbs Incentive Sheet' flat DocType.
	- Expands each executive in 'incentive' list into an individual record.
	- Ignores 'Serial Numbers' loop.
	- Links 'executive' field to User account.
	- Idempotent upsert by master_id.
	"""
	import json
	from frappe.utils import flt, now_datetime

	if data is None:
		for k in ("Incentive", "incentive", "incentives", "data", "records", "sales", "items"):
			if k in kwargs and kwargs[k]:
				data = kwargs[k]
				break

	if data is None and hasattr(frappe, "request") and frappe.request:
		try:
			raw_body = frappe.request.get_data(as_text=True)
			if raw_body:
				parsed = json.loads(raw_body)
				if isinstance(parsed, dict):
					data = parsed.get("data") or parsed.get("records") or parsed.get("incentives") or [parsed]
				elif isinstance(parsed, list):
					data = parsed
		except Exception:
			pass

	if data is None and hasattr(frappe, "form_dict") and frappe.form_dict:
		for k in ("data", "records", "incentives", "sales", "items"):
			if k in frappe.form_dict and frappe.form_dict[k]:
				val = frappe.form_dict[k]
				if isinstance(val, str):
					try:
						data = json.loads(val)
					except Exception:
						pass
				else:
					data = val
				break

	if isinstance(data, str):
		try:
			data = json.loads(data)
		except Exception:
			frappe.throw(_("Invalid JSON payload passed to sync_incentives."), title=_("Invalid Data"))

	if isinstance(data, dict):
		data = data.get("data") or data.get("records") or [data]

	if not data or not isinstance(data, list):
		frappe.throw(_("Payload must be a list of records or {'data': [...]}."), title=_("Invalid Data"))

	# Build active user lookup map
	users = frappe.db.sql(
		"SELECT name, email, first_name, last_name, full_name FROM `tabUser` WHERE enabled = 1",
		as_dict=True
	)
	user_map = {}
	for u in users:
		if u.name:
			user_map[u.name.strip().lower()] = u.name
		if u.email:
			user_map[u.email.strip().lower()] = u.name
		if u.first_name:
			user_map[u.first_name.strip().lower()] = u.name
		if u.full_name:
			user_map[u.full_name.strip().lower()] = u.name

	def _clean_amt(val):
		if val is None:
			return 0.0
		s = str(val).strip().replace(",", "")
		return flt(s)

	now_dt = now_datetime()
	parsed_rows = []
	incoming_master_ids = set()

	for voucher in data:
		if not isinstance(voucher, dict):
			continue

		master_id = _normalize_key(voucher, "Master Id", "Master ID", "master_id", "Master_Id", "id")
		company_name = _normalize_key(voucher, "COMPANY NAME", "Company Name", "company_name", "Company")
		voucher_date = _safe_date(_normalize_key(voucher, "DATE", "Date", "voucher_date", "date"))
		voucher_type = _normalize_key(voucher, "VCH TYPE", "Voucher Type", "vch_type", "voucher_type", "type")
		vch_no = _normalize_key(voucher, "VCHNO", "vch no", "vch_no", "voucher_no", "Vch No")
		party_name = _normalize_key(voucher, "PARTY NAME", "Party Name", "party_name", "Party") or company_name
		mobile_no = _normalize_key(voucher, "MOBILE", "Mobile No", "Mobile", "mobile_no", "mobile", "phone")
		email = _normalize_key(voucher, "EMAIL", "Email", "email", "email_id")
		state = _normalize_key(voucher, "State", "state")
		pincode = _normalize_key(voucher, "Pincode", "pincode", "Pin Code")

		if master_id is not None:
			incoming_master_ids.add(str(master_id).strip())

		v_header = {
			"master_id": str(master_id).strip() if master_id is not None else None,
			"company_name": str(company_name).strip() if company_name else None,
			"voucher_date": voucher_date,
			"voucher_type": str(voucher_type).strip() if voucher_type else None,
			"vch_no": str(vch_no).strip() if vch_no is not None else None,
			"party_name": str(party_name).strip() if party_name else None,
			"mobile_no": str(mobile_no).strip() if mobile_no else None,
			"email": str(email).strip() if email else None,
			"state": str(state).strip() if state else None,
			"pincode": str(pincode).strip() if pincode else None,
		}

		items = voucher.get("Items") or voucher.get("items")
		if not items or not isinstance(items, list):
			# If voucher itself has flat item/incentive keys (e.g. from single row)
			item_name = _normalize_key(voucher, "Item Name", "item_name")
			serial_no = _normalize_key(voucher, "Serial No", "serial_no")
			qty = flt(_normalize_key(voucher, "Qty", "qty") or 0)
			rate = _clean_amt(_normalize_key(voucher, "Rate", "rate"))
			amount = _clean_amt(_normalize_key(voucher, "Amount", "amount"))
			period = _normalize_key(voucher, "period", "Period")
			from_date = _safe_date(_normalize_key(voucher, "from date", "from_date", "From Date"))
			to_date = _safe_date(_normalize_key(voucher, "To Date", "to_date", "To Date"))
			roll_type = _normalize_key(voucher, "Roll Type", "roll_type")
			exec_raw = _normalize_key(voucher, "Executive", "executive")
			exec_user = user_map.get(str(exec_raw).strip().lower()) if exec_raw else None
			actual_amt = _clean_amt(_normalize_key(voucher, "Actual Amt", "actual_amt"))
			incentive = _clean_amt(_normalize_key(voucher, "Incentive", "incentive"))

			parsed_rows.append({
				**v_header,
				"item_name": str(item_name).strip() if item_name else None,
				"serial_no": str(serial_no).strip() if serial_no else None,
				"qty": qty,
				"rate": rate,
				"amount": amount,
				"period": str(period).strip() if period else None,
				"from_date": from_date,
				"to_date": to_date,
				"roll_type": str(roll_type).strip() if roll_type else None,
				"executive": exec_user,
				"executive_name": str(exec_raw).strip() if exec_raw else None,
				"actual_amt": actual_amt,
				"incentive": incentive,
				"last_sync_date": now_dt
			})
			continue

		for it in items:
			if not isinstance(it, dict):
				continue

			it_name = _normalize_key(it, "item_name", "Item Name")
			it_serial = _normalize_key(it, "serial_no", "Serial No")
			it_qty = flt(_normalize_key(it, "qty", "Qty") or 0)
			it_rate = _clean_amt(_normalize_key(it, "rate", "Rate"))
			it_amount = _clean_amt(_normalize_key(it, "amount", "Amount"))
			it_period = _normalize_key(it, "Period", "period")
			it_from = _safe_date(_normalize_key(it, "from_date", "from date", "From Date"))
			it_to = _safe_date(_normalize_key(it, "to_date", "To Date", "to_date"))

			it_base = {
				**v_header,
				"item_name": str(it_name).strip() if it_name else None,
				"serial_no": str(it_serial).strip() if it_serial else None,
				"qty": it_qty,
				"rate": it_rate,
				"amount": it_amount,
				"period": str(it_period).strip() if it_period else None,
				"from_date": it_from,
				"to_date": it_to,
			}

			incentives = it.get("incentive") or it.get("Incentive")
			if incentives and isinstance(incentives, list):
				for inc in incentives:
					if not isinstance(inc, dict):
						continue
					roll_type = _normalize_key(inc, "roll_type", "Roll Type")
					exec_raw = _normalize_key(inc, "executive", "Executive")
					exec_user = user_map.get(str(exec_raw).strip().lower()) if exec_raw else None
					actual_amt = _clean_amt(_normalize_key(inc, "actual_amt", "Actual Amt"))
					inc_val = _clean_amt(_normalize_key(inc, "incentive", "Incentive"))

					parsed_rows.append({
						**it_base,
						"roll_type": str(roll_type).strip() if roll_type else None,
						"executive": exec_user,
						"executive_name": str(exec_raw).strip() if exec_raw else None,
						"actual_amt": actual_amt,
						"incentive": inc_val,
						"last_sync_date": now_dt
					})
			else:
				# 1 row even if no incentive list
				parsed_rows.append({
					**it_base,
					"roll_type": None,
					"executive": None,
					"executive_name": None,
					"actual_amt": 0.0,
					"incentive": 0.0,
					"last_sync_date": now_dt
				})

	if not parsed_rows:
		frappe.throw(_("No valid records found in payload."), title=_("Invalid Data"))

	# Delete existing records for the incoming master_ids to ensure clean, idempotent snapshot
	if incoming_master_ids:
		master_id_list = list(incoming_master_ids)
		for i in range(0, len(master_id_list), 500):
			chunk = master_id_list[i:i + 500]
			frappe.db.sql(
				"DELETE FROM `tabHbs Incentive Sheet` WHERE `master_id` IN %s",
				[tuple(chunk)]
			)
		frappe.db.commit()

	# Batch insert into tabHbs Incentive Sheet
	BATCH_SIZE = 50
	inserted_count = 0
	for i in range(0, len(parsed_rows), BATCH_SIZE):
		batch = parsed_rows[i:i + BATCH_SIZE]
		val_tuples = []
		for r in batch:
			seq_val = frappe.db.get_next_sequence_val("Hbs Incentive Sheet")
			val_tuples.append((
				seq_val,
				r["master_id"],
				r["company_name"],
				r["voucher_date"],
				r["voucher_type"],
				r["vch_no"],
				r["party_name"],
				r["mobile_no"],
				r["email"],
				r["state"],
				r["pincode"],
				r["item_name"],
				r["serial_no"],
				r["qty"],
				r["rate"],
				r["amount"],
				r["period"],
				r["from_date"],
				r["to_date"],
				r["roll_type"],
				r["executive"],
				r["executive_name"],
				r["actual_amt"],
				r["incentive"],
				r["last_sync_date"],
				now_dt,
				now_dt,
				"Administrator",
				"Administrator",
				0
			))

		if val_tuples:
			placeholders = ", ".join(["(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"] * len(val_tuples))
			flat_vals = [item for sub in val_tuples for item in sub]
			frappe.db.sql(f"""
				INSERT INTO `tabHbs Incentive Sheet` (
					`name`, `master_id`, `company_name`, `voucher_date`, `voucher_type`, `vch_no`,
					`party_name`, `mobile_no`, `email`, `state`, `pincode`,
					`item_name`, `serial_no`, `qty`, `rate`, `amount`, `period`,
					`from_date`, `to_date`, `roll_type`, `executive`, `executive_name`,
					`actual_amt`, `incentive`, `last_sync_date`, `creation`, `modified`,
					`owner`, `modified_by`, `docstatus`
				) VALUES {placeholders}
			""", flat_vals)
		inserted_count += len(batch)
		frappe.db.commit()

	return {
		"status": "success",
		"message": f"Synced {len(parsed_rows)} incentive lines successfully.",
		"total_vouchers": len(data),
		"inserted_records": inserted_count,
		"master_ids": list(incoming_master_ids)
	}


# Alias for sync_sales_cr
@frappe.whitelist(methods=["POST"])
def sync_sales_cr(data=None, **kwargs):
	return sync_incentives(data=data, **kwargs)
