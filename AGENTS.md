# HBS CRM — Project Architecture & Quality Rules

This repository contains the **HBS CRM** Frappe app (`apps/hbs_crm`).
Follow these architecture, style, and verification rules for all code changes.

---

## 1. 🏗️ Code Organization & DRY (Don't Repeat Yourself)

1. **Shared Helpers & Utilities**:
   - All shared functions (e.g. `is_owner_or_admin`, `clean_indian_phone`, hierarchy traversal helpers) **must reside in `hbs_crm/hbs_crm/utils.py`**.
   - **Never** re-implement or duplicate these helper functions across individual DocType controllers (`hbs_crm_lead.py`, `hbs_tally_renewal.py`). Import them from `hbs_crm.hbs_crm.utils`.

2. **Schema & Select Field Synchronization**:
   - When updating Select field options in a parent DocType (e.g. `contact_designation` in `Hbs Crm Lead`), always synchronize the corresponding child table DocType (e.g. `Hbs Lead Contact`) to prevent validation failures.

3. **Client-Side Scripting & Desk CSS**:
   - Prefer clean CSS rules in injected `<style>` blocks over repetitive jQuery DOM traversal loops for styling.
   - For view-only fields that must remain visible when empty, keep `read_only: 0` in DocType JSON and enforce read-only properties via client-side JS (`setup_field_permissions`).

---

## 2. 🛡️ Permissions & Security

1. **User Hierarchy Scoping**:
   - Use `Hbs User Hierarchy` as the single source of truth for organizational hierarchy and visibility.
   - Implement record scoping via `get_permission_query_conditions` and `has_permission` hooks in `hooks.py`.
   - Use whitelist helper `@frappe.whitelist() def check_user_hierarchy_role` when checking permissions from client scripts to avoid table-level permission errors for non-admin users.

2. **Server-Side Mutation Guards**:
   - Always enforce critical business logic and field mutation locks in python controller `validate()` methods. Do not rely solely on client-side JS locks.

---

## 3. 🔄 Verification & Build Checklist

After modifying any DocType schemas, controllers, or client-side assets, always execute:

```bash
# 1. Compile check
python3 -m compileall apps/hbs_crm -q

# 2. Schema sync & cache clear
bench --site mysite.local migrate
bench --site mysite.local clear-cache

# 3. Asset bundling
bench build --app hbs_crm
```

---

## 4. 📦 Git & Commit Practices

- Write conventional, clear commit messages (`feat:`, `fix:`, `refactor:`).
- Commit only completed and verified features.
- Avoid pushing incomplete or in-progress experimental DocTypes to the remote `main` branch.
