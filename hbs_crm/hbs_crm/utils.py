# Copyright (c) 2026, Hbs and contributors
# For license information, please see license.txt

import frappe

def has_app_permission():
	"""Check if current user has permission to access HBS CRM App Switcher card."""
	return True


# ==============================================================================
# UNUSED / LEGACY CODE (Commented out)
# ==============================================================================
# from typing import Literal
# import email.utils
# from cryptography.fernet import Fernet
# def logging(*args, **kwargs): pass
# import requests
# import json 
# import smtplib
# import ssl
# from email.message import EmailMessage
# import os
# import mimetypes
# import time
# import importlib
# import datetime
# from frappe.utils import now_datetime
# from frappe.email.doctype.email_account.email_account import pull_from_email_account



# def convert_ddmmyyyy_to_yyyymmdd(date_str):
# 	if not date_str or not isinstance(date_str, str):
# 		return date_str
# 	try:
# 		return datetime.datetime.strptime(date_str, "%d-%m-%Y").strftime("%Y-%m-%d")
# 	except Exception:
# 		return date_str  

# def excel_date_to_str(excel_serial):
# 	if not excel_serial:
# 		return ""
# 	try:
# 		return (datetime.datetime(1899, 12, 30) + datetime.timedelta(days=float(excel_serial))).strftime("%Y-%m-%d")
# 	except Exception:
# 		return str(excel_serial)

# def extract_emails_phones(obj, emails=None, phones=None):
# 	if emails is None: emails = set()
# 	if phones is None: phones = set()
# 	if isinstance(obj, dict):
# 		for k, v in obj.items():
# 			if isinstance(v, str):
# 				try:
# 					parsed = json.loads(v)
# 					extract_emails_phones(parsed, emails, phones)
# 				except (ValueError, TypeError):
# 					pass
# 			if 'email' in k.lower() and v and '@' in str(v) and v not in ('None', 'No', 'N/A', 'null'):
# 				emails.add(str(v))
# 			if ('phone' in k.lower() or 'mobile' in k.lower()) and v and v not in ('None', 'No', 'N/A', 'null'):
# 				phones.add(str(v))
# 			extract_emails_phones(v, emails, phones)
# 	elif isinstance(obj, list):
# 		for item in obj:
# 			extract_emails_phones(item, emails, phones)
# 	return list(emails), list(phones)

# def get_callable_from_string(func_path):
# 	"""Get a callable from a string like 'module.submodule.function'."""
# 	module_path, func_name = func_path.rsplit('.', 1)
# 	module = importlib.import_module(module_path)
# 	return getattr(module, func_name)

# def queue(type, names, single, user=None):
# 	try:
# 		single = get_callable_from_string(single)
# 		total = len(names)
# 		success = 0
# 		error = 0
# 		last_update = 0

# 		# frappe.publish_realtime(type, {"message": f"{type} started ({total})"}, user=user)

# 		for name in names:
# 			if not frappe.db.exists(type, name):
# 				error += 1
# 				logging(f"Missing doc: {name}", "error", type, name)
# 				continue

# 			# try:
# 			# 	ok = single(name)

# 			# 	if ok:
# 			# 		success += 1
# 			# 	else:
# 			# 		error += 1
# 			# 		logging(f"Convert exception: {str(e)}", "error", type, name)


# 			# except Exception as e:
# 			# 	error += 1
# 			# 	logging(f"Convert exception: {str(e)}", "error", type, name)

# 			try:
# 				frappe.enqueue(
# 					single,
# 					queue='long',
# 					timeout=60,
# 					name=name
# 				)
# 				success += 1
# 			except Exception as e:
# 				error += 1
# 				logging(f"Enqueue failed {name}: {str(e)}", "error", type, name)




# 			# # Throttle UI updates
# 			# now = time.time()
# 			# if now - last_update > 1:
# 			# 	frappe.publish_realtime(
# 			# 		type,
# 			# 		{"message": f"{success} success | {error} failed | {total - success - error} left"},
# 			# 		user=user,
# 			# 	)
# 			# 	last_update = now

# 		# frappe.publish_realtime(
# 		# 	type,
# 		# 	{"message": f"Completed {type}: {success} success, {error} failed"},
# 		# 	user=user,
# 		# )

# 		logging(f"queue created total:{total} error:{error} success:{success}", "error", type, name)

# 	except Exception as e:
# 		logging(f"QUEUE FATAL ERROR: {str(e)}", "error", type, names)

# # def queue(type, names, single ,user=None):
# # 	try:
# # 		single = get_callable_from_string(single)
	
# # 		now = time.time()
# # 		last_modified = 0

# # 		total = len(names)
# # 		success = 0
# # 		error = 0


# # 		message = f" {type} process started for {total} items"
# # 		frappe.publish_realtime(
# # 			type,
# # 			{"message": message, "timeout": 4},
# # 			user=user,
# # 		)

# # 		for idx, name in enumerate(names):
# # 			status = "success"

# # 			if not frappe.db.exists(type, name):
# # 				status = "error"
# # 				error += 1
# # 				error_message = f"Document {name} not present in {type} database"
# # 				logging(error_message, type, "error", name)
# # 				continue

# # 			try:
# # 				res = single(name)
# # 				success += 1

# # 			except Exception as e:
# # 				error += 1
# # 				status = "error"
# # 				error_message = f"Document {name} contains some error: {str(e)}"
# # 				logging(error_message, type, "error", name)

# # 			now = time.time()
# # 			if now - last_modified > 1:
# # 				message = f"{type} progress: {total} items, {success} success, {error} error, {total - success - error} remaining"
# # 				frappe.publish_realtime(
# # 					type,
# # 					{"message": message, "timeout": 4},
# # 					user=user,
# # 				)
# # 				last_modified = now
# # 		message = f"Completed {type} progress: {total} items, {success} success, {error} error"
# # 		frappe.publish_realtime(
# # 			type,
# # 			{"message": message, "timeout": 10},
# # 			user=user,
# # 		)
# # 	except Exception as e:
# # 		error_message = f"Document contains some error: {str(e)}"
# # 		logging(error_message, type, "error", names)
# # 	return 

# def encrypt_string(data):
# 	env = frappe.get_doc('gseven settings') # this is working perfectly
# 	key = env.decrypt_key
# 	try:
# 		fernet = Fernet(str(key))
# 		encrypted_data = fernet.encrypt(data.encode()).decode()
# 		return None, encrypted_data
# 	except Exception as e:
# 		frappe.logger().error(f"Encryption failed: {str(e)}")
# 		return str(e), None 

# # complete the decrypt functoin , the key is taken from 
# def decrypt_string(data):
# 	try:
# 		env = frappe.get_doc('gseven settings')
# 		key = env.decrypt_key
# 		fernet = Fernet(key)
# 		decrypted_data = fernet.decrypt(data.encode()).decode()
# 		return None, decrypted_data

# 	except Exception as e:
# 		frappe.logger().error(f"Decryption failed: {str(e)}")
# 		return str(e), None    

# def get_base_url():
# 	env = frappe.get_doc('gseven settings')
# 	if env.is_production:
# 		return env.base_url_production
# 	else:
# 		return env.base_url_development

# def get_base_url():
# 	env = frappe.get_doc('gseven settings')
# 	if env.is_production:
# 		return env.base_url_production
# 	else:
# 		return env.base_url_development


# # fix this function for sendoing pessage through get request 

# def message_auto_sender_send_message(phone, text, file="", send_attachment=1):
# 	"""
# 	Sends a message using the Message Auto Sender API.

# 	Args:
# 		phone (str): The receiver's mobile phone number.
# 		text (str): The message text to be sent.
# 		file (str, optional): The file URL if an attachment is required. Defaults to an empty string.

# 	Returns:
# 		tuple: (bool, str, dict or None) - Returns error status, error message, and response body.
# 	"""
# 	env = frappe.get_doc('gseven settings')

# 	if not env.enable_whatsapp_message_auto_sender:
# 		# frappe.logger().error(f"Please enable WhatsApp Message Auto Sender in settings.")
# 		return "Please enable WhatsApp Message Auto Sender in settings.", None

# 	url = "https://app.messageautosender.com/api/v1/message/create"

# 	query = {
# 		"api_key": env.whatsapp_message_auto_sender_api,
# 		"receiverMobileNo": phone,
# 		"channelId": env.whatsapp_message_auto_sender_channel_id,
# 		"message": text
# 	}

# 	if file and env.is_production and int(send_attachment) == 1:
# 		query["filePathUrl"] = f"{file}"

# 	try:
# 		resp = requests.get(url, params=query)
# 		if resp.status_code == 200:
# 			body = resp.json()
# 			return None, body  
# 		else:
# 			error_message = f"Failed to send message: {resp.status_code}, {resp.text}"
# 			frappe.logger().error(error_message)
# 			return error_message, None
# 	except requests.exceptions.RequestException as e:
# 		error_message = f"Error while sending message: {str(e)}"
# 		frappe.logger().error(error_message)
# 		return error_message, 

# def red_lava(phone, text, file="", send_attachment=1):
# 	"""
# 	Sends a message using the redlava api.

# 	Args:
# 		phone (str): The receiver's mobile phone number.
# 		text (str): The message text to be sent.
# 		file (str, optional): The file URL if an attachment is required. Defaults to an empty string.

# 	Returns:
# 		tuple: (bool, str, dict or None) - Returns error status, error message, and response body.
# 	"""
# 	env = frappe.get_doc('gseven settings')
# 	# print(f"{env}====================>ENV")
# 	if not env.apikey: 
# 		return "Please add redlava whatsapp apiKey in gseven settings first", None

# 	if not env.phoneid:
# 		# frappe.logger().error(f"Please enable WhatsApp Message Auto Sender in settings.")
# 		return "Please add WhatsApp redlava phoneId.", None
# 	if not env.x_phone_id:
# 		# frappe.logger().error(f"Please enable WhatsApp Message Auto Sender in settings.")
# 		return "Please add WhatsApp redlava x-phone-id.", None

# 	url = "https://wa.redlava.in/api/v1/whatsapp/sendMessage"

# 	query = {
# 		"apiKey": env.apikey,
		
# 		"phoneId":env.phoneid
# 	}
# 	headers = {
# 		"x-phone-id":env.x_phone_id,
# 		"Content-Type": "application/json" 
# 	}
# 	body={
# 		"to":str(phone),
# 		"text":text
# 	}
# 	# print(f"{query}=================>query")
# 	# print(f"{body}================>body")
# 	# print(f"{headers}================>headers")
# 	if file and env.is_production and int(send_attachment) == 1:
# 		query["filePathUrl"] = f"{file}"

# 	try:
# 		resp = requests.post(url, params=query, headers=headers, json=body)
# 		message_id = resp.json().get("waMessageId", "")
# 		if resp.status_code == 200:
# 			result = resp.json()
# 			# return None, result  
# 			return {"status": "success", "message": "Message sent successfully", "data": result, "message_id": message_id}
# 		else:
# 			error_message = f"Failed to send message: {resp.status_code}, {resp.text}"
# 			frappe.logger().error(error_message)
# 			return {"status": "error", "message": error_message}
# 	except Exception as e:
# 		error_message = f"Error while sending message: {str(e)}{frappe.get_traceback()}"
# 		frappe.logger().error(error_message)
# 		return {"status": "error", "message": error_message}

# # sending schduled whatsapp
# def auto_whatsapp_sender():
# 	try:

# 		data = frappe.db.get_all(
# 			'gseven whatsapp unofficial',
# 			filters={
# 				'status': 'pending',
# 				'type': 'schedule',
# 				'to_be_sent_on': ['<', now_datetime()]
# 			},
# 			fields=['*']
# 		)

# 		# this will send for all 
# 		# data = frappe.db.get_all(
# 		# 	'gseven whatsapp unofficial',
# 		# 	filters={
# 		# 		'status': 'pending',
# 		# 		'type': 'schedule',
# 		# 	},
# 		# 	fields=['*']
# 		# )

		
# 		for d in data:
# 			if d:
# 				try:
# 					error, res = message_auto_sender_send_message(d.get('receiver'), d.get('message'), d.get('file_url'), d.get('send_attachment'))
# 					if res == None:
# 						update = frappe.get_doc("gseven whatsapp unofficial", d.get('name'))
# 						update.error_message = error
# 						update.status = "error"
# 						update.save()
# 						frappe.db.commit()
# 						continue
# 					else:
# 						update = frappe.get_doc("gseven whatsapp unofficial", d.get('name'))
# 						update.status = "completed"
# 						update.save()
# 						frappe.db.commit()
# 						continue
# 				except Exception as e:
# 					frappe.logger().error(f"Error sending WhatsApp message: {str(e)}")
# 					update = frappe.get_doc("gseven whatsapp unofficial", d.get('name'))
# 					update.error_message = str(e)
# 					update.status = "error"
# 					update.save()
# 					frappe.db.commit()
# 					continue
# 	except Exception as e:
# 		frappe.logger().error(f"Error sending email: {str(e)}")
# 		return str(e), None

# # method to get base url
# def get_base_url():
# 	env = frappe.get_doc('gseven settings')
# 	if env.is_production:
# 		return env.base_url_production
# 	else:
# 		return env.base_url_development


# #custome bulk edit action
# def custom_bulk_edit_action(doctype, docnames, action, data, task_id=None):
# 	if data:
# 		data = frappe.parse_json(data)

# 	failed = []
# 	num_documents = len(docnames)

# 	for idx, docname in enumerate(docnames, 1):
# 		doc = frappe.get_doc(doctype, docname, ignore_permissions=True)
# 		try:
# 			if action == "update" and not doc.docstatus.is_cancelled():
# 				doc.update(data)
# 				doc.save()
# 				frappe.db.commit()

# 		except Exception as e:
# 			frappe.logger().error(f"Error while bulk editing document {docname}: {str(e)}")
# 			frappe.db.rollback()
# 			failed.append({"docname": docname, "error": str(e)})

# 	if failed:
# 		return f"Failed to update {len(failed)} out of {num_documents} documents.", None
# 	else:
# 		return None, f"Successfully updated {num_documents} documents."

# #get whatsapp
# def get_comments_fn(docname,doctype):
# 	try:
# 		# filters={'reference_doctype': doctype, 'reference_name': docname}, fields=['*']
# 		# print(f"Fetching comments for - {docname}")
# 		comments = frappe.get_all('Comment',filters={ 'reference_name': docname,'reference_doctype':doctype}, fields=['*'])
# 		# print(f"Comments fetched: {comments}")
# 		return comments
# 	except Exception as e:
# 		frappe.logger().error(f"Error fetching comments for - {docname}: {str(e)}")
# 		return {"status": "error", "message": str(e)}

# @frappe.whitelist(allow_guest=True)
# def get_whatsapp_messages(phoneArray):
# 	try:
# 		if isinstance(phoneArray, str):
# 			phoneArray = frappe.parse_json(phoneArray) 	
			
# 		if  isinstance(phoneArray, list) and len(phoneArray) == 0:
# 			return {"status": "error", "message": ("Phone array is empty")}
		
# 		conditions = []
# 		params = []
# 		for phone in phoneArray:
# 			# print(f"{phone} is the phone number")
# 			conditions.append("(receiver LIKE %s)")
# 			params.append(f"%{phone}%")
# 			conditions.append("(sender LIKE %s)")
# 			params.append(f"%{phone}%")

# 		condition_str = " OR ".join(conditions)
# 		query = f"""
# 			SELECT
# 				sender,
# 				receiver,
# 				file_url,
# 				message,
# 				creation,
				
# 				CASE
# 					WHEN { ' OR '.join(["receiver LIKE %s" for _ in phoneArray]) } THEN 'out'
# 					WHEN { ' OR '.join(["sender LIKE %s" for _ in phoneArray]) } THEN 'in'
# 					ELSE ''
# 				END as type
# 			FROM `tabgseven whatsapp unofficial`
# 			WHERE ({condition_str}) AND status = 'completed' AND sent_by = 'webhook'
# 			ORDER BY creation DESC
# 			LIMIT 100
# 		"""
# 		case_params = [f"%{phone}%" for phone in phoneArray] + [f"%{phone}%" for phone in phoneArray] + params
# 		result = frappe.db.sql(query, as_dict=True, values=case_params)
		
# 		return result
# 		# print(f"amsdlsam")
# 	except Exception as e:
# 		return {"status": "error", "message": str(e)}


# # official whatsapp function
# @frappe.whitelist(allow_guest = True)
# def get_whatsapp_official_response(to, text):
# 	try:

# 		settings = frappe.db.get_value(
# 			"gseven settings", None, ["apikey", "phoneid", "x_phone_id","webhook_url"], as_dict=True
# 		)
	
# 		headers = {
# 			"Content-Type": "application/json",
# 			"x-phone-id": settings["x_phone_id"],
			
# 		}
# 		url = f"https://wa.redlava.in/api/v1/whatsapp/sendMessage"
# 		params = {
# 				"apiKey": settings["apikey"],
# 				"phoneId": settings["phoneid"]
# 				}   
# 		payload = {
# 		"to":to,
# 		"text":text
# 		}
# 		response = requests.post(url, params=params, json=payload, headers=headers)
# 		# webhook url - https://webhook.site/f2b3fb73-c7f8-4afa-97f8-0e36b1c25e4d

# 		if response.status_code == 200:
# 			result = response.json()
# 			# print("WhatsApp API Success:", result)
# 			webhook_response = response.get(settings['webhook_url'])
# 			# print(f"=====================>webhook url==================={webhook_response}")
# 			return result
		
# 		print("WhatsApp API Failed:", response.text)
# 		frappe.throw(f"WhatsApp API Error: {response.text}")

# 	except Exception as e:
# 		frappe.db.rollback()
# 		print(f"Error in get_whatsapp_official_response: {str(e)}")
# 		frappe.throw(f"Error in WhatsApp API call: {str(e)}")




# def get_emails(docname,doctype):
# 	try:
# 		if not docname:
# 			frappe.local.response.http_status_code = 401
# 			return {"status": "error", "message": "Document name is required"}
		
# 		# baseUrl = frappe.base_url()
# 		baseUrl = frappe.utils.get_url()

# 		# Fetch emails related to the document
# 		# emails = frappe.get_all('Communication', filters={'reference_name': docname,'reference_doctype':doctype}, fields=['*'],order_by='creation desc')
# 		emails = frappe.db.sql("""
# 			SELECT 
# 				tc.*, 
# 				CONCAT(
# 					'[',
# 					GROUP_CONCAT(CONCAT('"', %s, tf.file_url, '"')),
# 					']'
# 				) AS attachments
# 			FROM `tabCommunication` AS tc
# 			LEFT JOIN `tabFile` AS tf 
# 				ON tf.attached_to_doctype = 'Communication'
# 			AND tf.attached_to_name = tc.name
# 			WHERE tc.reference_name = %s
# 			AND tc.reference_doctype = %s
# 			GROUP BY tc.name
# 			ORDER BY tc.creation DESC
# 		""", (baseUrl, docname, doctype), as_dict=True)

# 		return emails
		
# 	except Exception as e:
# 		return {"status": "error", "message": str(e)}
		
# #custom bulk delete action
# def custom_bulk_delete_action(doctype, docnames, task_id=None):
# 	failed = []
# 	num_documents = len(docnames)
	
# 	for idx, docname in enumerate(docnames, 1):
# 		try:
# 			frappe.delete_doc(doctype, docname, ignore_permissions=True)
# 			frappe.db.commit()
# 		except Exception as e:
# 			frappe.logger().error(f"Error while deleting document {docname}: {str(e)}")
# 			frappe.db.rollback()
# 			failed.append({"docname": docname, "error": str(e)})

# 	if failed:
# 		return f"Failed to delete {len(failed)} out of {num_documents} documents.", None
# 	else:
# 		return None, f"Successfully deleted {num_documents} documents."

# #checking button visibility
# @frappe.whitelist()
# def check_button_visibility():
# 	try:
# 		res = frappe.db.get_single_value("gseven settings","is_production")
		
# 		return {"status": "success", "message": f"You have permission to perform action", "is_production": res}
		
# 	except Exception as e:
# 		frappe.logger().error(f"Check button permission failed: {str(e)}")
# 		return {"status": "error", "message": f"{e}"}

# @frappe.whitelist()
# def tally_portal_serial_check_all(serial):
# 	if not serial:
# 		frappe.throw("Serial is required", frappe.ValidationError)
	
# 	isDelhi = False 
# 	isNoida = False 
# 	delhiResponse = None
# 	noidaResponse = None

# 	try: 
# 		if isDelhi == False:
# 			delhiResponse = tally_portal_serial("delhi", serial)
# 			if delhiResponse and delhiResponse.get("expiry_details", {}).get("serial_status") == 1:
# 				isDelhi = True
# 			else:
# 				isDelhi = False 
		
# 		if isDelhi == False and isNoida == False:
# 			noidaResponse = tally_portal_serial("noida", serial)
# 			if noidaResponse and noidaResponse.get("expiry_details", {}).get("serial_status") == 1:
# 				isNoida = True
# 			else:
# 				isNoida = False

# 		if isDelhi == True:
# 			serial_data = delhiResponse.get("expiry_details", {}).get("serial_data", {})
# 			data = {
# 				"acc_expiry_date": convert_ddmmyyyy_to_yyyymmdd(serial_data.get("expiry", None)),  # acc_expiry_date
# 				"flavour": serial_data.get("flavour", ""),  # flavour
# 				"edition": serial_data.get("edition", ""),  # edition
# 				"portal_acc_name": serial_data.get("org_name", ""),  # portal_acc_name
# 				"portal_contact": serial_data.get("contact_name", ""),  # portal_contact

# 				"portal_email": serial_data.get("contact_email", ""),  # portal_email
# 				"portal_mobile": serial_data.get("contact_mobile", ""),  # portal_mobile
# 				"crm_priority": serial_data.get("tss_priority", ""),  # crm_priority
# 				"business_segment": serial_data.get("business_segment", ""),  # business_segment
# 				"product_ver": serial_data.get("release", ""),  # product_ver

# 				"account_id": serial_data.get("account_id", ""),  # account_id
# 				"admin_id": serial_data.get("account_admin_email_id", ""),  # admin_id
# 				"acc_start_date": convert_ddmmyyyy_to_yyyymmdd(serial_data.get("activation_date", None)),  # acc_start_date
# 				"mau": serial_data.get("mau", ""),  # mau
# 				"qau": serial_data.get("qau", ""),  # qau

# 				"rfm_segment": serial_data.get("rfm_segment", ""),  # rfm_segment
# 				"status": "done",  # status
# 				"error": "",  # error
# 				"gseven_branch": "delhi",  # gseven_branch
# 				"last_updated_api": time.strftime("%Y-%m-%d"),
# 			}
# 			return data
# 		elif isNoida == True:
# 			serial_data = noidaResponse.get("expiry_details", {}).get("serial_data", {})
# 			data = {
# 				"acc_expiry_date": convert_ddmmyyyy_to_yyyymmdd(serial_data.get("expiry", None)),  # acc_expiry_date
# 				"flavour": serial_data.get("flavour", ""),  # flavour
# 				"edition": serial_data.get("edition", ""),  # edition
# 				"portal_acc_name": serial_data.get("org_name", ""),  # portal_acc_name
# 				"portal_contact": serial_data.get("contact_name", ""),  # portal_contact

# 				"portal_email": serial_data.get("contact_email", ""),  # portal_email
# 				"portal_mobile": serial_data.get("contact_mobile", ""),  # portal_mobile
# 				"crm_priority": serial_data.get("tss_priority", ""),  # crm_priority
# 				"business_segment": serial_data.get("business_segment", ""),  # business_segment
# 				"product_ver": serial_data.get("release", ""),  # product_ver

# 				"account_id": serial_data.get("account_id", ""),  # account_id
# 				"admin_id": serial_data.get("account_admin_email_id", ""),  # admin_id
# 				"acc_start_date": convert_ddmmyyyy_to_yyyymmdd(serial_data.get("activation_date", None)),  # acc_start_date
# 				"mau": serial_data.get("mau", ""),  # mau
# 				"qau": serial_data.get("qau", ""),  # qau

# 				"rfm_segment": serial_data.get("rfm_segment", ""),  # rfm_segment
# 				"status": "done",  # status
# 				"error": "",  # error
# 				"gseven_branch": "noida",  # gseven_branch
# 				"last_updated_api": time.strftime("%Y-%m-%d"),
# 			}
# 			return data
# 		else:
# 			notmapped = {
# 				"gseven_branch":"not_gseven",
# 				"last_updated_api": time.strftime("%Y-%m-%d"),
# 				"status": "done", # status 
# 				"error": "" #error 
# 			}
# 			return notmapped

# 	except Exception as e:
# 		frappe.logger().error(f"Error in tally_portal_serial: {str(e)}")
# 		frappe.throw(str(e))

# @frappe.whitelist(allow_guest=True)
# def pull_email(name):
# 	try: 
# 		email_account = frappe.get_doc("Email Account", name)
# 		email_account.receive()
# 		return {"message": "success"}

# 	except Exception as e:
# 		frappe.throw(str(e))

# @frappe.whitelist()
# def pull_email_cron():
# 	try: 
# 		# Get ticket email from custom settings
# 		ticket_email = frappe.db.get_single_value('gseven settings', 'ticket_email')
# 		if ticket_email:
# 			email_account_name = frappe.db.get_value("Email Account", {"email_id": ticket_email}, "name")
# 			if email_account_name:
# 				email_account = frappe.get_doc("Email Account", email_account_name)
# 				email_account.receive()

# 		# Get automation email from custom settings
# 		# automation_email = frappe.db.get_single_value('gseven settings', 'ticket_email')
# 		# if automation_email: 
# 		# 	email_account_name = frappe.db.get_value("Email Account", {"email_id": automation_email}, "name")
# 		# 	if email_account_name:
# 		# 		email_account = frappe.get_doc("Email Account", email_account_name)
# 		# 		email_account.receive()

# 	except Exception as e:
# 		logging(f"Error while pulling emails: {str(e)}", "error")

# @frappe.whitelist()
# def tally_portal_serial(location, serial):
# 	# Validate inputs
# 	if not location:
# 		frappe.throw("Location is required", frappe.ValidationError)
# 	if not serial:
# 		frappe.throw("Serial is required", frappe.ValidationError)
# 	if location not in ('noida', 'delhi'):
# 		frappe.throw("Location can only be 'noida' or 'delhi'", frappe.ValidationError)

# 	try:
# 		env = frappe.get_doc('gseven settings')
# 		if location == 'noida':
# 			apikey = env.tally_portal_noida
# 		else: 
# 			apikey = env.tally_portal_delhi

# 		url = (
# 			f"https://tallysolutions.com/api/v1/serialexpiry"
# 			f"?apikey={apikey}&slnum={serial}"
# 		)
# 		response = requests.get(url, timeout=10)
# 		response.raise_for_status()
# 		return response.json()
# 	except Exception as e:
# 		frappe.logger().error(f"Error in tally_portal_serial: {str(e)}")
# 		frappe.throw(str(e), frappe.SessionBootFailed)


# # @frappe


# @frappe.whitelist()
# def get_details(search):
# 	try:
# 		# if not search:
# 		#     frappe.throw("Search term is required", frappe.ValidationError)

# 		# Define which fields to search for each DocType
# 		gst_fields = [
# 			"gstin",
# 			"constitution_of_business",
# 			"legal_name_of_business",
# 			"trade_name_of_business",
# 			"registration_date",
# 			"taxpayer_type",
# 			"gstin_status",
# 			"nature_of_business_activities",
# 			"director_names",
# 			"principle_email_id",
# 			"principle_address",
# 			"principle_nature_of_business",
# 			"principle_mobile",
# 			"turnover_min",
# 			"turnover_max",
# 			"total_income",
# 			"email_list",
# 			"phone_list",
# 			"status"
# 		]
# 		gst_search_fields = [
# 			"gstin",
# 			"constitution_of_business",
# 			"legal_name_of_business",
# 			"trade_name_of_business",
# 			"registration_date",
# 			"taxpayer_type",
# 			"gstin_status",
# 			"nature_of_business_activities",
# 			"director_names",
# 			"principle_email_id",
# 			"principle_address",
# 			"principle_nature_of_business",
# 			"principle_mobile",
# 			"turnover_min",
# 			"turnover_max",
# 			"total_income",
# 			"email_list",
# 			"phone_list",
# 			"status"
# 		]
		
# 		ledger_fields = [
# 			"name",
# 			"guid",
# 			"email",
# 			"parent1",
# 			"alterid",
# 			"isdeleted",
# 			"ledgerphone",
# 			"ledgercontact",
# 			"division",
# 			"namelist",
# 			"gstregistrationtype",
# 			"gstin",
# 			"executive",
# 			"address",
# 			"email_list",
# 			"phone_list"
# 		]
# 		ledger_search_fields = [
# 			"name",
# 			"guid",
# 			"email",
# 			"parent1",
# 			"alterid",
# 			"isdeleted",
# 			"ledgerphone",
# 			"ledgercontact",
# 			"division",
# 			"namelist",
# 			"gstregistrationtype",
# 			"gstin",
# 			"executive",
# 			"address",
# 			"email_list",
# 			"phone_list"
# 		]
# 		crm_lead_fields = [
# 			"contact_name",
# 			"contact_phone",
# 			"contact_email",
# 			"contact_designation",
# 			"company_name",
# 			"company_gst",
# 			"company_pan",
# 			"company_address",
# 			"referred_by",
# 			"lead_source",
# 			"lead_source_id",
# 			"follow_up_date",
# 			"follow_up_time",
# 			"status",
# 			"requirement_received",
# 			"proposal_sent",
# 			"demo_done",
# 			"additional_discount",
# 			"payment_terms",
# 			"total_before_tax",
# 			"total_tax",
# 			"contains_tally_product",
# 			"total_after_tax",
# 			"final_total",
# 			"type",
# 			"latest_remark",
# 			"lead_type",
# 			"final_lead_type",
# 			"executive_one",
# 			"executive_two",
# 			"display_name",
# 			"expiry_date",
# 			"tally_serial",
# 			"flavor",
# 			"link_doctype",
# 			"link_doctype_id",
# 			"won_remark",
# 			"lost_remark",
# 			"parent_company",
# 			"gvla"
# 		]
# 		crm_lead_search_fields = [
# 			"contact_name",
# 			"contact_phone",
# 			"contact_email",
# 			"contact_designation",
# 			"company_name",
# 			"company_gst",
# 			"company_pan",
# 			"company_address"
# 		]

# 		def build_or_filters(search_fields, search):
# 			# Returns a filter that matches if any field contains the search term
# 			return [
# 				[field, "like", f"%{search}%"] for field in search_fields
# 			]

# 		gst_filters = build_or_filters(gst_search_fields, search)
# 		ledger_filters = build_or_filters(ledger_search_fields, search)
# 		crm_lead_filters = build_or_filters(crm_lead_search_fields, search)

# 		gst_data = frappe.db.get_all(
# 			"gseven gstin",
# 			fields=gst_search_fields,
# 			filters=gst_filters,
# 			order_by="modified desc",
# 			limit=10
# 		)

# 		ledger_data = frappe.db.get_all(
# 			"gseven tally ledger",
# 			fields=ledger_search_fields,
# 			filters=ledger_filters,
# 			order_by="modified desc",
# 			limit=10
# 		)

# 		crm_lead_data = frappe.db.get_all(
# 			"gseven crm lead",
# 			fields=crm_lead_search_fields,
# 			filters=crm_lead_filters,
# 			order_by="modified desc",
# 			limit=10
# 		)

# 		return {
# 			"gst_data": gst_data,
# 			"ledger_data": ledger_data,
# 			"crm_lead_data": crm_lead_data
# 		}

# 	except Exception as e:
# 		frappe.logger().error(f"Error in get details: {str(e)}")
# 		frappe.throw(str(e), frappe.SessionBootFailed)


# # add comment , used in the log activites tab 
# @frappe.whitelist()
# def addcomment(doctype, name, user, content):
# 	comment = frappe.new_doc("Comment")
# 	comment.update(
# 		{
# 			"comment_type": "Comment",
# 			"reference_doctype": doctype,
# 			"reference_name": name,
# 			"comment_by": user,
# 			"content": content,
# 		}
# 	)
# 	comment.insert(ignore_permissions=True)


# def validate_origin():

# 	allowed_url = frappe.get_single("gseven settings").base_url_production

# 	if not allowed_url:
# 		frappe.throw("You have to setup production url in gseven setting")

	
# 	ALLOWED_ORIGINS = [
# 		allowed_url
# 	]
	
# 	if frappe.request and hasattr(frappe.request, 'headers'):
	
# 		isProduction = frappe.get_single("gseven settings").is_production
# 		if not isProduction:
# 			return True

# 		origin = frappe.request.headers.get('Origin')
# 		referer = frappe.request.headers.get('Referer')
				
# 		if origin and origin in ALLOWED_ORIGINS:
# 			return True
			
# 		if referer:
# 			for allowed_origin in ALLOWED_ORIGINS:
# 				if referer.startswith(allowed_origin):
# 					return True		
		
# 	return False



# @frappe.whitelist()
# def get_doctype_fields(doctype):
# 	try:
# 		# Get the doctype meta
# 		meta = frappe.get_meta(doctype)
		
# 		# Get all fields and filter them
# 		fields = []
# 		for field in meta.fields:
# 			# Skip unwanted field types
# 			if (field.hidden or 
# 				field.read_only or 
# 				field.fieldtype in ['Section Break', 'Column Break', 'HTML', 'Button', 'Table', 'Tab Break']):
# 				continue
			
# 			# Map field type for value input
# 			mapped_fieldtype = map_field_type(field.fieldtype)
			
# 			fields.append({
# 				'fieldname': field.fieldname,
# 				'label': field.label,
# 				'fieldtype': field.fieldtype,
# 				'mapped_fieldtype': mapped_fieldtype,
# 				'options': field.options,
# 				'reqd': field.reqd,
# 				'hidden': field.hidden,
# 				'read_only': field.read_only,
# 				'default': field.default,
# 				'description': field.description,
# 				'in_list_view': field.in_list_view,
# 				'in_standard_filter': field.in_standard_filter,
# 				'precision': field.precision if hasattr(field, 'precision') else None,
# 				'length': field.length if hasattr(field, 'length') else None
# 			})
		
# 		return fields
		
# 	except Exception as e:
# 		frappe.throw(f"Error fetching doctype fields: {str(e)}")

# def map_field_type(fieldtype):
# 	"""
# 	Map original field type to appropriate input field type
# 	"""
# 	field_type_mapping = {
# 		'Link': 'Link',
# 		'Select': 'Select',
# 		'Date': 'Date',
# 		'Datetime': 'Datetime',
# 		'Time': 'Time',
# 		'Check': 'Check',
# 		'Int': 'Int',
# 		'Float': 'Float',
# 		'Currency': 'Float',
# 		'Percent': 'Float',
# 		'Text': 'Text',
# 		'Small Text': 'Small Text',
# 		'Long Text': 'Long Text',
# 		'Password': 'Password',
# 		'Table': 'JSON'
# 	}
	
# 	return field_type_mapping.get(fieldtype, 'Data')


# #custome notification
# @frappe.whitelist()
# def send_notification_new(self, subject, to_emails=None, cc_emails=None, message="", for_what=""):
# 	if not to_emails:
# 		frappe.throw("User is required to send notification")

# 	doc = self.as_dict()
# 	doc.task_link = f"{frappe.utils.get_url()}/app/gerp-task/{self.name}"
# 	doc.username = ",".join(to_emails)
# 	doc.due_date = frappe.utils.formatdate(self.pending_date, "dd-MM-yyyy")

# 	try:
# 		# Fetch email template only if for_what is provided
# 		if for_what:
# 			template = frappe.get_all(
# 				"gerp task notification template",
# 				filters={"for_what": for_what, "is_active": 1, "type": "email"},
# 				fields=["email_template", "subject"]
# 			)

# 			if template and template[0].email_template:
# 				message = frappe.render_template(template[0].email_template, doc)
# 				message = message.replace("{{ task_link }}", doc.task_link)
# 				subject = frappe.render_template(template[0].subject, doc)

# 		# Pick sender email from gseven settings
# 		env = frappe.get_doc('gseven settings')
# 		if not env:
# 			frappe.throw("Please configure gseven Settings to send email notifications")
		
# 		if not env.task_notification_email:
# 			frappe.throw("Please configure Task Notification Email in gseven Settings to send email notifications")

# 		if not frappe.db.exists("Email Account", {"email_id": env.task_notification_email}):
# 			frappe.throw(f"Email account with email {env.task_notification_email} does not exist. Please configure it in Email Accounts.")
	
# 		reply_email = f"{env.task_notification_email.split('@')[0]}+gerp%20task-{self.name}@{env.task_notification_email.split('@')[1]}"

# 		latestCommunicationObject = frappe.get_all(
# 			"Communication",
# 			filters={
# 				"reference_doctype": "gerp task",     
# 				"reference_name": self.name,          
# 				"sent_or_received": "Sent"            
# 			},
# 			fields=["name"],
# 			order_by="creation desc",
# 			limit=1
# 		)
# 		latest_comm_id = latestCommunicationObject[0].name if latestCommunicationObject else None
		
# 		# Message chain setup
# 		reference_doctype = ""
# 		reference_name = ""
# 		if for_what != "reminder_for_assigned":
# 			reference_doctype = self.doctype
# 			reference_name = self.name

# 		# Send email notification
# 		send_email_with_communication_link(
# 			recipients=",".join(to_emails),
# 			cc=",".join(cc_emails) if cc_emails else None,
# 			subject=subject,
# 			content=message or f"{self.name} has been updated.",
# 			doctype=self.doctype,
# 			name=self.name,
# 			send_priority=1,
# 			sender=env.task_notification_email,
# 			reply_to=reply_email,
# 			reference_doctype=reference_doctype,
# 			reference_name=reference_name,
# 			delayed=True,
# 			expose_recipients='header',
# 			in_reply_to=latest_comm_id,
# 		)

# 	except Exception as e:
# 		frappe.log_error(title="Error sending custom notification", message=frappe.get_traceback())
# 		frappe.throw(f"Failed to send notification: {str(e)}")


# @frappe.whitelist()
# def send_notification(self, subject, for_user, message="", for_what=""):
# 	if not for_user:
# 		frappe.throw("User is required to send notification")

# 	doc = self.as_dict()
# 	doc.task_link = f"{frappe.utils.get_url()}/app/gerp-task/{self.name}"
# 	doc.username = for_user
# 	doc.due_date = frappe.utils.formatdate(self.pending_date, "dd-MM-yyyy")

# 	try:
# 		# Fetch email template only if for_what is provided
# 		if for_what:
# 			template = frappe.get_all(
# 				"gerp task notification template",
# 				filters={"for_what": for_what, "is_active": 1, "type": "email"},
# 				fields=["email_template", "subject"]
# 			)

# 			if template and template[0].email_template:
# 				message = frappe.render_template(template[0].email_template, doc)
# 				message = message.replace("{{ task_link }}", doc.task_link)
# 				subject = frappe.render_template(template[0].subject, doc)

# 		# Pick sender email from gseven settings
# 		env = frappe.get_doc('gseven settings')
# 		if not env:
# 			frappe.throw("Please configure gseven Settings to send email notifications")
		
# 		if not env.task_notification_email:
# 			frappe.throw("Please configure Task Notification Email in gseven Settings to send email notifications")

# 		if not frappe.db.exists("Email Account", {"email_id": env.task_notification_email}):
# 			frappe.throw(f"Email account with email {env.task_notification_email} does not exist. Please configure it in Email Accounts.")
	
# 		# Reply-to email for automatic linking
# 		reply_email = f"{env.task_notification_email.split('@')[0]}+gerp%20task-{self.name}@{env.task_notification_email.split('@')[1]}"


# 		latestCommunicationObject = frappe.get_all(
# 			"Communication",
# 			filters={
# 				"reference_doctype": "gerp task",     
# 				"reference_name": self.name,          
# 				"sent_or_received": "Sent"            
# 			},
# 			fields=["name"],
# 			order_by="creation desc",
# 			limit=1
# 		)
# 		latest_comm_id = latestCommunicationObject[0].name if latestCommunicationObject else None
		
# 		# Message chain setup

# 		msg_id = ""
# 		reference_doctype = ""
# 		reference_name = ""
# 		if latest_comm_id and for_what != "reminder_for_assigned":
# 			msg_id = latest_comm_id
		
# 		if for_what != "reminder_for_assigned":
# 			reference_doctype = self.doctype
# 			reference_name = self.name

# 		# Send email notification
# 		if for_user.lower() != "administrator":
# 			send_email_with_communication_link(
# 				recipients=for_user,
# 				subject=subject,
# 				content=message or f"{self.name} has been updated.",
# 				doctype=self.doctype,
# 				name=self.name,
# 				send_priority=1,
# 				sender=env.task_notification_email,
# 				reply_to=reply_email,
# 				reference_doctype=reference_doctype,
# 				reference_name=reference_name,
# 				delayed=False,
# 				expose_recipients='header',
# 				in_reply_to=msg_id,
# 			)

# 	except Exception as e:
# 		frappe.log_error(title="Error sending custom notification", message=frappe.get_traceback())
# 		frappe.throw(f"Failed to send notification: {str(e)}")





# @frappe.whitelist()
# def has_gerp_bulk_edit_permission(permission_type):
# 	alowed = frappe.db.get_value("gerp permission", {"user": frappe.session.user, "type": permission_type})
# 	return bool(alowed)


# #custom function to send email and link to communication doc
# import frappe
# from typing import Literal

# @frappe.whitelist()
# def send_email_with_communication_link(
# 	recipients=None,
# 	sender="",
# 	subject="No Subject",
# 	message="No Message",
# 	as_markdown=False,
# 	delayed=True,
# 	reference_doctype=None,
# 	reference_name=None,
# 	unsubscribe_method=None,
# 	unsubscribe_params=None,
# 	unsubscribe_message=None,
# 	add_unsubscribe_link=1,
# 	attachments=None,
# 	content=None,
# 	doctype=None,
# 	name=None,
# 	reply_to=None,
# 	queue_separately=False,
# 	cc=None,
# 	bcc=None,
# 	message_id=None,
# 	in_reply_to=None,
# 	send_after=None,
# 	expose_recipients=None,
# 	send_priority=1,
# 	communication=None,
# 	retry=1,
# 	now=None,
# 	read_receipt=None,
# 	is_notification=False,
# 	inline_images=None,
# 	template=None,
# 	args=None,
# 	header=None,
# 	print_letterhead=False,
# 	with_container=False,
# 	email_read_tracker_url=None,
# 	x_priority: Literal[1, 3, 5] = 3,
# ):
# 	try:
		
# 		# Send the email (returns None, not an object)
# 		res = frappe.sendmail(
# 			recipients=recipients,
# 			sender=sender,
# 			subject=subject,
# 			message=message,
# 			as_markdown=as_markdown,
# 			delayed=delayed,
# 			reference_doctype=reference_doctype,
# 			reference_name=reference_name,
# 			unsubscribe_method=unsubscribe_method,
# 			unsubscribe_params=unsubscribe_params,
# 			unsubscribe_message=unsubscribe_message,
# 			add_unsubscribe_link=add_unsubscribe_link,
# 			attachments=attachments,
# 			content=content,
# 			doctype=doctype,
# 			name=name,
# 			reply_to=reply_to,
# 			queue_separately=queue_separately,
# 			cc=cc,
# 			bcc=bcc,
# 			message_id=message_id,
# 			in_reply_to=in_reply_to,
# 			send_after=send_after,
# 			expose_recipients=expose_recipients,
# 			send_priority=send_priority,
# 			communication=communication,
# 			retry=retry,
# 			now=now,
# 			read_receipt=read_receipt,
# 			is_notification=is_notification,
# 			inline_images=inline_images,
# 			template=template,
# 			args=args,
# 			header=header,
# 			print_letterhead=print_letterhead,
# 			with_container=with_container,
# 			email_read_tracker_url=email_read_tracker_url,
# 			x_priority=x_priority
# 		)

# 		# If reference is provided, create Communication
# 		if reference_doctype and reference_name:
# 			comm = frappe.get_doc({
# 				"doctype": "Communication",
# 				"subject": subject,
# 				"content": content or message,
# 				"sent_or_received": "Sent",
# 				"reference_doctype": reference_doctype,
# 				"reference_name": reference_name,
# 				"status": "Linked",
# 				"sender": sender,
# 				"recipients": recipients,
# 				"cc": cc,
# 				"bcc": bcc,
# 				"communication_medium": "Email",
# 				"message_id": res.get("message_id") if res else None,
# 			})
# 			comm.insert(ignore_permissions=True)
# 			frappe.db.commit()

# 		return True

# 	except Exception:
# 		frappe.log_error(frappe.get_traceback(), "Error sending email with communication link")
# 		return False


# def get_communication_id(refrence_name,reference_doctype):
# 	try:
# 		latestCommunicationObject = frappe.get_all(
# 			"Communication",
# 			filters={
# 				"reference_doctype": reference_doctype,     
# 				"reference_name": refrence_name,          
# 				"sent_or_received": "Sent"            
# 			},
# 			fields=["name"],
# 			order_by="creation desc",
# 			limit=1
# 		)
# 		latest_comm_id = latestCommunicationObject[0].name if latestCommunicationObject else None

# 		return latest_comm_id
# 	except Exception as e:
# 		frappe.log_error(frappe.get_traceback(), "Error fetching automatic linking email setting")
# 		return None



# #custom get message id
# def get_message_id_custom():
# 	"""Returns Message ID created from doctype and name"""
# 	return email.utils.make_msgid(domain="gseven.in")

# def set_in_reply_to_custom(self, in_reply_to):
# 		"""Used to send the Message-Id of a received email back as In-Reply-To"""
# 		self.set_header("In-Reply-To", f"<{in_reply_to}>")
# 		self.set_header("References", f"<{in_reply_to}>")


# #send comment notification
# @frappe.whitelist()
# def send_comment_notification(doc, method):
# 	try:
# 		#sending email to assigned to user and watcher if notify to assgined and watcher is checked
# 		if doc.reference_doctype == "gerp task" and doc.reference_name and doc.comment_type == "Comment":
# 			task = frappe.get_doc("gerp task", doc.reference_name)
# 			to_emails = []
# 			cc_emails = []

# 			if task.assigned_user:
# 				for user in task.assigned_user:
# 					if user.type == "assigned" and user.user != "Administrator":
# 						to_emails.append(user.user)
# 					elif user.type == "watcher" and user.user != "Administrator":
# 						cc_emails.append(user.user)

# 			comm_id = get_communication_id(doc.reference_name, doc.reference_doctype)

# 			env = frappe.get_doc("gseven settings")

# 			if int(task.notify_to_watcher_and_assigned_everything) == 1:
# 				send_email_with_communication_link(
# 					recipients=",".join(to_emails),
# 					cc=",".join(cc_emails) if cc_emails else None,
# 					subject=f"Task : {task.name}",
# 					content=f"A new comment has been added to the task '{task.name}':<br>{doc.content}<br>View Task: <a href='{frappe.utils.get_url()}/app/gerp-task/{task.name}'>Click Here</a>",
# 					doctype=doc.reference_doctype,
# 					name=doc.reference_name,
# 					sender=env.task_notification_email,
# 					reply_to=env.task_notification_email,
# 					delayed=False,
# 					expose_recipients='header',
# 					in_reply_to=comm_id,
# 				)

# 	except Exception as e:
# 		frappe.log_error(frappe.get_traceback(), "Error sending comment notification")
# 		frappe.throw(f"Failed to send comment notification: {str(e)}")



# def get_copying_fields(doctype):
# 	try:

# 		#main object 
# 		main_object={
# 			"gerp task": [
# 				"task_description",
# 				"priority",
# 				"group",
# 				"set_by_user",
# 				"task_approval",
# 				"is_task_shift_weekly",
# 				"status_not_editable",
# 				"notify_all_changes_to_watcher",
# 				"notify_all_changes_to_watcher_on_whatsapp",
# 				"notify_to_watcher_when_task_done",
# 				"notify_to_watcher_when_task_done_on_whatsapp",
# 				"notify_to_creator_when_task_done",
# 				"notify_to_approver_when_task_is_done",
# 				"notify_to_assigned_when_task_created",
# 				"notify_to_assigned_when_task_created_on_whatsapp",
# 				"notify_all_changes_to_assigned",
# 				"notify_all_changes_to_assigned_on_whatsapp",
# 				"notify_to_watcher_and_assigned_everything",
# 				"reminder_for_assigned",
# 				"reminder_for_assigned_on_whatsapp",
# 				"reminder_for_watcher_and_assigned",
# 				"reminder_before_hours",
# 				"reminder_interval_hours",
# 				"fms_name",
# 				"linked_fms_doctype",
# 				"linked_fms_doctype_id",
# 				"linked_form_name",
# 				"linked_form_id",
# 				"linked_display_name",
# 				"linked_display_id",
# 				"recurring_task_config_id"
# 			]
# 		}
		
# 		if doctype in main_object:
# 			fields = main_object[doctype]
# 			return fields
# 		else:
# 			return []

# 	except Exception as e:
# 		frappe.log_error(frappe.get_traceback(), "Error fetching copying fields")
# 		return []


# @frappe.whitelist()
# def get_base_url():
# 	settings = frappe.get_single("gseven settings")

# 	if not settings.base_url_production:
# 		frappe.throw("Base URL not configured in GSeven Settings")

# 	return settings.base_url_production.rstrip('/')


# @frappe.whitelist()
# def get_customer_phones(customer_name=None, gst_number=None, tally_serial=None):
# 	try:
# 		phone_set = set()
		
# 		# Try to find customer from gst if provided
# 		if not customer_name and gst_number:
# 			gst_number = gst_number.strip().upper()
# 			customer_name = frappe.db.get_value("Customer", {"tax_id": gst_number}, "name")
		
# 		# If customer exists, get phone numbers from customer and contacts
# 		if customer_name and frappe.db.exists("Customer", customer_name):

# 			# Get all contacts linked to this customer
# 			contact_links = frappe.get_all(
# 				"Dynamic Link",
# 				filters={
# 					"link_doctype": "Customer",
# 					"link_name": customer_name,
# 					"parenttype": "Contact"
# 				},
# 				fields=["parent"]
# 			)
			
# 			# Get phone numbers from each contact
# 			for link in contact_links:
# 				contact_name = link.parent
# 				contact_doc = frappe.get_doc("Contact", contact_name)
				
# 				# Get mobile number
# 				if contact_doc.mobile_no:
# 					phone_set.add(contact_doc.mobile_no)
				
# 				# Get phone number
# 				if contact_doc.phone:
# 					phone_set.add(contact_doc.phone)
				
# 				# Get all phone numbers from phone child table
# 				if hasattr(contact_doc, 'phone_nos') and contact_doc.phone_nos:
# 					for phone in contact_doc.phone_nos:
# 						if phone.phone:
# 							phone_set.add(phone.phone)
		
# 		# Add phone numbers from tally serial if provided
# 		if tally_serial:
# 			tally_doc = frappe.get_doc("gseven tally serial", tally_serial)
			
# 			# Add contact_phone
# 			if tally_doc.contact_phone:
# 				phone_set.add(tally_doc.contact_phone)
			
# 			# Add all_contacts phones
# 			if hasattr(tally_doc, 'all_contacts') and tally_doc.all_contacts:
# 				for contact in tally_doc.all_contacts:
# 					if contact.contact_phone:
# 						phone_set.add(contact.contact_phone)
		
# 		# If no phone numbers found at all, return error
# 		if not phone_set:
# 			return {"status": "error", "message": "No phone numbers found"}
		
# 		# Convert set to comma-separated string
# 		phone_list = list(phone_set)
# 		phone_string = ", ".join(phone_list)
		
# 		return {
# 			"status": "success", 
# 			"data": phone_string,
# 			"count": len(phone_list),
# 			"customer": customer_name or ""
# 		}
		
# 	except Exception as e:
# 		frappe.log_error(f"Error in get_customer_phones: {str(e)}", "get_customer_phones")
# 		return {"status": "error", "message": str(e)}