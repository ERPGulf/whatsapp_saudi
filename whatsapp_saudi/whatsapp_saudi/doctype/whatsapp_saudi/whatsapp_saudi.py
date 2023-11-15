# Copyright (c) 2023, ERPGulf.com and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document

import requests
import frappe
import io
import base64
from frappe.utils import now
import json
import time
class WhatsappSaudi(Document):
	pass
@frappe.whitelist()
# creating pdf
def create_pdf():
    file = frappe.get_print("Global Defaults","default_company",as_pdf=True)
    pdf_bytes = io.BytesIO(file)
    pdf_base64 = base64.b64encode(pdf_bytes.getvalue()).decode()
    in_memory_url = f"data:application/pdf;base64,{pdf_base64}"
    return  in_memory_url
    

@frappe.whitelist()
def send_message(url,instance,token,phone):
    memory_url=create_pdf()
    pdf_url=url
    payload = {
        'instanceid':instance,
        'token':token,
        'body':memory_url,
        'filename': 'Company',
        'caption':"this is a test message",
        'phone':phone
    }
    
    files = []
    headers = {
        'content-type': 'application/x-www-form-urlencoded',
        'Cookie': 'PHPSESSID=e9603d8bdbea9f5bf851e36831b8ba16'
    }

    try:
      response = requests.post(pdf_url, headers=headers, data=payload, files=files)
      response_json=response.text
      if response.status_code == 200:
            if not response_json: 
                frappe.msgprint("Empty response. Enter correct URL.")
                return
            response_dict = json.loads(response_json)
            if response_dict.get("sent") and response_dict.get("id"):
                current_time =now()# for geting current time
                # If the message is sent successfully, a success message response will be recorded in the WhatsApp Saudi success log."
                frappe.get_doc({
                        "doctype": "whatsapp saudi success log",
                        "title": "sucess",
                        "message": "testing",
                        "time": current_time
                    }).insert()
                frappe.msgprint("sent")
            elif response_dict.get("success") is False and response_dict.get("reason"):
                frappe.msgprint("API access prohibited or incorrect instanceid or token")
                frappe.log( "success: false,reason: API access prohibited or incorrect instanceid or token" , message=frappe.get_traceback())
            else:
                response1=str(response_dict)
                response2=json.dumps(response1)
                frappe.msgprint(response2)
                frappe.msgprint("invalid phone number.Enter phone number with country code")
                frappe.log_error( title="invalid number" , message=frappe.get_traceback())
      else:
            response1=str(response_dict)
            response2=json.dumps(response1)
            frappe.msgprint(response2)
            frappe.log("status code  is not 200", message=frappe.get_traceback()) 
      return response
    except Exception as e:
        frappe.log_error(title='Failed to send notification', message=frappe.get_traceback())  
 

