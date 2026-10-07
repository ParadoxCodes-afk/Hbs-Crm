import frappe


def execute():
	"""
	Ensure Workspace Sidebar and Sidebar titles match the module name to avoid v16 migration conflict.
	Also fixes any docfield/doctype module casing discrepancy.
	"""
	if frappe.db.table_exists("Workspace Sidebar"):
		frappe.db.sql("""
			UPDATE `tabWorkspace Sidebar`
			SET title = 'Hbs Crm', name = 'Hbs Crm'
			WHERE (name = 'HBS CRM' OR title = 'HBS CRM') AND module = 'Hbs Crm'
		""")

	if frappe.db.table_exists("Sidebar"):
		frappe.db.sql("""
			UPDATE `tabSidebar`
			SET title = 'Hbs Crm', name = 'Hbs Crm'
			WHERE (name = 'HBS CRM' OR title = 'HBS CRM') AND module = 'Hbs Crm'
		""")

	if frappe.db.table_exists("DocType"):
		frappe.db.sql("""
			UPDATE `tabDocType`
			SET module = 'Hbs Crm'
			WHERE name = 'Hbs Tally Renewal' AND module = 'hbs_crm'
		""")

	if frappe.db.table_exists("Kanban Board Field"):
		frappe.db.sql("""
			DELETE FROM `tabKanban Board Field`
			WHERE name = '2qjupsj5er'
		""")
		if frappe.db.table_exists("Kanban Board"):
			frappe.db.sql("""
				DELETE FROM `tabKanban Board Field`
				WHERE parent NOT IN (SELECT name FROM `tabKanban Board`)
			""")
