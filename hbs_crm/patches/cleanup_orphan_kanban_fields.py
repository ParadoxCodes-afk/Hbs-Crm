import frappe


def execute():
	"""
	Clean up orphan or colliding Kanban Board Field records to allow ERPNext sync to proceed cleanly.
	"""
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
