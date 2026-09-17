# Copyright (c) 2026, Hbs and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import cstr, escape_html


def apply_data_import_patch():
	"""
	Monkey patch frappe.core.doctype.data_import.importer to support:
	1. Custom column header aliases from hooks (data_import_column_aliases).
	2. Case-insensitive header matching.
	3. Matching / resolving User names, usernames, and initials (kps, dev, yogi, etc.).
	4. Updating records by Tally Serial when doc ID / name is omitted.
	"""
	try:
		import frappe.core.doctype.data_import.importer as imp_mod

		if getattr(imp_mod, "_hbs_crm_patched", False):
			return
		imp_mod._hbs_crm_patched = True

		# 1. Patch build_fields_dict_for_column_matching for aliases
		orig_build_fields_dict = imp_mod.build_fields_dict_for_column_matching

		def patched_build_fields_dict(parent_doctype):
			out = orig_build_fields_dict(parent_doctype)
			aliases_hooks = frappe.get_hooks("data_import_column_aliases") or {}
			aliases_dict = aliases_hooks.get(parent_doctype, {})
			parent_meta = frappe.get_meta(parent_doctype)
			if isinstance(aliases_dict, dict):
				for alias_header, target_fieldnames in aliases_dict.items():
					if isinstance(target_fieldnames, list):
						fname = target_fieldnames[0] if target_fieldnames else None
					else:
						fname = target_fieldnames
					if fname and isinstance(fname, str):
						target_df = parent_meta.get_field(fname)
						if target_df:
							out[alias_header] = target_df
							out[alias_header.strip()] = target_df
							out[alias_header.lower()] = target_df
							out[alias_header.upper()] = target_df
			return out

		imp_mod.build_fields_dict_for_column_matching = patched_build_fields_dict

		# 2. Patch get_df_for_column_header for case-insensitive lookup
		def patched_get_df_for_column_header(doctype, header):
			if not header:
				return None

			def build_fields_dict_for_doctype():
				return imp_mod.build_fields_dict_for_column_matching(doctype)

			df_by_labels_and_fieldname = frappe.cache.hget(
				"data_import_column_header_map", doctype, generator=build_fields_dict_for_doctype
			) or {}

			res = df_by_labels_and_fieldname.get(header)
			if res:
				return res

			clean_header = str(header).strip().lower()
			for k, v in df_by_labels_and_fieldname.items():
				if str(k).strip().lower() == clean_header:
					return v
			return None

		imp_mod.get_df_for_column_header = patched_get_df_for_column_header

		# 3. Helper: resolve_user_link
		def resolve_user_link(value):
			if not value:
				return value
			val_clean = cstr(value).strip()
			if frappe.db.exists("User", val_clean, cache=True):
				return val_clean

			user_map = {
				"kps": "kps@hbsmail.in",
				"dev": "dev@hbsmail.in",
				"yogi": "yogi@hbsmail.in",
				"yogendra": "yogi@hbsmail.in",
				"admin": "Administrator",
				"administrator": "Administrator",
			}
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

		# 4. Patch Row.link_exists & Row.parse_value
		orig_row_link_exists = imp_mod.Row.link_exists
		def patched_row_link_exists(self, value, df):
			if df.options == "User" and value:
				value = resolve_user_link(value)
			return orig_row_link_exists(self, value, df)
		imp_mod.Row.link_exists = patched_row_link_exists

		orig_row_parse_value = imp_mod.Row.parse_value
		def patched_row_parse_value(self, value, col):
			val = orig_row_parse_value(self, value, col)
			if col and col.df and col.df.fieldtype == "Link" and col.df.options == "User" and val:
				val = resolve_user_link(val)
			return val
		imp_mod.Row.parse_value = patched_row_parse_value

		# 5. Patch Column.validate_values for User link validation
		orig_col_validate_values = imp_mod.Column.validate_values
		def patched_col_validate_values(self):
			if self.df and self.df.fieldtype == "Link" and self.df.options == "User":
				original_values = self.column_values
				values = set(original_values.values())
				exists = [
					d.name for d in frappe.get_all("User", filters={"name": ("in", list(values))})
				]
				for val in list(values):
					if val not in exists:
						resolved = resolve_user_link(val)
						if resolved and frappe.db.exists("User", resolved, cache=True):
							exists.append(val)
				not_exists = list(set(values) - set(exists))
				if not_exists:
					missing_values = ", ".join(escape_html(cstr(original_values[v])) for v in not_exists)
					self.warnings.append(
						{
							"message": _("Value {0} missing for {1}").format(
								frappe.bold(missing_values), frappe.bold(self.df.label or self.df.fieldname)
							),
							"type": "warning",
						}
					)
				return
			return orig_col_validate_values(self)
		imp_mod.Column.validate_values = patched_col_validate_values

		# 6. Patch Importer.update_record to support lookup by serial
		orig_update_record = imp_mod.Importer.update_record
		def patched_update_record(self, doc):
			id_field = imp_mod.get_id_field(self.doctype)
			doc_id = doc.get(id_field.fieldname) if id_field else None

			if not doc_id:
				serial = doc.get("tally_serial") or doc.get("tss_tally_serial")
				if serial:
					doc_id = frappe.db.get_value(self.doctype, {"tally_serial": str(serial).strip()}, "name")

			if not doc_id or not frappe.db.exists(self.doctype, doc_id):
				return self.insert_record(doc)

			existing_doc = frappe.get_doc(self.doctype, doc_id)
			updated_doc = frappe.get_doc(self.doctype, doc_id)
			updated_doc.update(doc)

			if imp_mod.get_diff(existing_doc, updated_doc):
				updated_doc.flags.updater_reference = {
					"doctype": self.data_import.doctype,
					"docname": self.data_import.name,
					"label": _("via Data Import"),
				}
				updated_doc.save()
				return updated_doc
			else:
				return existing_doc

		imp_mod.Importer.update_record = patched_update_record

	except Exception as e:
		frappe.log_error(f"Error applying Data Import patch: {str(e)}", "Data Import Patch Error")
