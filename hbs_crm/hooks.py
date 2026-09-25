app_name = "hbs_crm"
app_title = "HBS CRM"
app_publisher = "Hbs"
app_description = "HBS CRM Application"
app_email = "hbs@mail.in"
app_license = "mit"
app_home = "/app/hbs-crm"

from hbs_crm.importer_patch import apply_data_import_patch
apply_data_import_patch()

website_route_rules = [
	{"from_route": "/desk", "to_route": "app/hbs-crm"},
]

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
add_to_apps_screen = [
	{
		"name": "hbs_crm",
		"title": "HBS CRM",
		"route": "/app/hbs-crm",
		"has_permission": "hbs_crm.hbs_crm.utils.has_app_permission"
	}
]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/hbs_crm/css/hbs_crm.css"
# app_include_js = "/assets/hbs_crm/js/hbs_crm.js"

# include js, css files in header of web template
# web_include_css = "/assets/hbs_crm/css/hbs_crm.css"
# web_include_js = "/assets/hbs_crm/js/hbs_crm.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "hbs_crm/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "hbs_crm/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "hbs_crm.utils.jinja_methods",
# 	"filters": "hbs_crm.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "hbs_crm.install.before_install"
# after_install = "hbs_crm.install.after_install"
after_migrate = "hbs_crm.hbs_crm.doctype.hbs_crm_lead.hbs_crm_lead.backfill_last_remarks"

# Uninstallation
# ------------

# before_uninstall = "hbs_crm.uninstall.before_uninstall"
# after_uninstall = "hbs_crm.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "hbs_crm.utils.before_app_install"
# after_app_install = "hbs_crm.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "hbs_crm.utils.before_app_uninstall"
# after_app_uninstall = "hbs_crm.utils.after_app_uninstall"

# Build
# ------------------
# To hook into the build process

# after_build = "hbs_crm.build.after_build"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "hbs_crm.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

scheduler_events = {
	"daily": [
		"hbs_crm.hbs_crm.doctype.hbs_crm_lead.hbs_crm_lead.send_daily_pending_followup_digest"
	]
}

# Testing
# -------

# before_tests = "hbs_crm.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "hbs_crm.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "hbs_crm.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "hbs_crm.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["hbs_crm.utils.before_request"]
# after_request = ["hbs_crm.utils.after_request"]

# Job Events
# ----------
# before_job = ["hbs_crm.utils.before_job"]
# after_job = ["hbs_crm.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"hbs_crm.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []

permission_query_conditions = {
	"Hbs Crm Lead": "hbs_crm.hbs_crm.doctype.hbs_crm_lead.hbs_crm_lead.get_permission_query_conditions",
	"Hbs Tally Renewal": "hbs_crm.hbs_crm.doctype.hbs_tally_renewal.hbs_tally_renewal.get_permission_query_conditions",
}

has_permission = {
	"Hbs Crm Lead": "hbs_crm.hbs_crm.doctype.hbs_crm_lead.hbs_crm_lead.has_permission",
	"Hbs Tally Renewal": "hbs_crm.hbs_crm.doctype.hbs_tally_renewal.hbs_tally_renewal.has_permission",
	"Hbs User Hierarchy": "hbs_crm.hbs_crm.doctype.hbs_user_hierarchy.hbs_user_hierarchy.has_permission",
	"Data Import": "hbs_crm.hbs_crm.doctype.hbs_tally_renewal.hbs_tally_renewal.has_data_import_permission",
}

data_import_column_aliases = {
	"Hbs Tally Renewal": {
		"SERIAL NO": "tally_serial",
		"PARENT": "flavour",
		"CONTACT ON": "contact_on",
		"STATUS": "crm_status",
		"EXPIRY DATE": "acc_expiry_date",
		"CUSTOM NAME": "cc_acc_name",
		"Portal C Name": "portal_acc_name",
		"LAST UPDATED": "last_updated",
		"EXE": "crm_ex_1",
		"executive": "crm_ex_1",
		"Partner Name": "partner_name",
		"EMAIL": "portal_email",
		"MOBILE": "portal_mobile",
		"CRMREF": "crm_ref",
		"Crmref": "crm_ref",
		"Pp Name": "portal_partner_name",
		"PORTAL STATE": "state",
		"STATE": "state",
		"BILLLING CITY": "led_city",
		"CITY": "led_city",
		"PORTAL PINCODE": "pincode",
		"PINCODE": "pincode",
		"Portal Address": "portal_address",
		"Billing Address": "address",
		"CRMPRIORITY": "crm_priority",
		"Crm Priority": "crm_priority",
		"Admin Id": "admin_id",
		"Billing Contact": "cc_contact",
		"Billing Phone": "cc_phone",
		"Billing Mobile": "cc_mobile",
		"Billing Email": "cc_email",
		"Biilling Email Cc": "cc_email_cc",
		"Billing State": "cc_state",
		"Billing Pincode": "cc_pincode",
		"Product Version": "tally_version",
		"PRODUCT VERSION": "tally_version",
		"Product Ver": "tally_version",
		"PRODUCT VER": "tally_version",
		"MIGRATION": "migration_priority",
		"ENQLOSTDUETO": "crm_lost_remarks",
		"QAU": "qau",
		"MCA": "mca_registered",
		"RFM SEGMENT": "rfm_segment",
		"UPGRADE": "upgrade_priority",
		"Account Id": "account_id",
		"Crm Stage": "crm_stage",
		"Led Customer Name": "cc_acc_name",
		"CONTACT NO": "portal_phone",
		"last partner name": "portal_partner_name",
		"AREA": "led_city",
		"NUMBER VERSION": "release",
		"Number Version": "release",
		"NUMBER VER": "release",
		"Number Ver": "release",
		"Lastuser": "portal_owner",
		# "$$GetTssExpiryDate:$nAME": "acc_expiry_date",
		"EDITLOG": "edit_log",
		"Director Contact Person": "director_contact_person",
		"Director Type": "director_type",
		"Director Gst": "director_gst",
		"Director GST": "director_gst",
		"Director Nature": "director_nature",
		"Director Mobile": "director_mobile",
		"Director Email": "director_email",
		"Director Address": "director_address",
		"Director State": "director_state",
		"Director Pincode": "director_pincode",
		"Director Turnover Slab": "director_turnover_slab",
		"Director Turnover": "director_turnover",
		"LICENSE": "license",
		"License": "license",
		"TALLY VERSION": "tally_version",
		"Tally Version": "tally_version",
		"VERSION": "tally_version",
		"Version": "tally_version",
		"FLAVOUR": "flavour",
		"Flavour": "flavour",
		"Tally Flavour": "flavour",
		"RELEASE": "release",
		"Release": "release",
		"PORTAL EXPIRY DATE": "portal_expiry_date",
		"Portal Expiry Date": "portal_expiry_date",
		"TSS EXPIRY DATE": "acc_expiry_date",
		"TSS Expiry Date": "acc_expiry_date",
		"Old Remarks": "old_remarks",
		"OLD REMARKS": "old_remarks",
		"Old Remark": "old_remarks",
		"OLD REMARK": "old_remarks",
		"Past Remarks": "old_remarks",
		"PAST REMARKS": "old_remarks",
		"Previous Remarks": "old_remarks",
		"PREVIOUS REMARKS": "old_remarks",
		"Last 2 Years Remarks": "old_remarks",
		"LAST 2 YEARS REMARKS": "old_remarks",
		"Remarks History": "old_remarks",
		"REMARKS HISTORY": "old_remarks",
	}
}
