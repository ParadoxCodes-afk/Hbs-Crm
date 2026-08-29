import frappe

def execute():
	# Forcefully update the Desktop Icon value in the database
	if frappe.db.exists("Desktop Icon", "Hbs Crm"):
		frappe.db.set_value("Desktop Icon", "Hbs Crm", "link_type", "Workspace Sidebar")
		frappe.clear_cache(doctype="Desktop Icon")
		frappe.clear_cache()
