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
def create_pdf():
    frappe.msgprint("pdff")
    file = frappe.get_print("Customer","Tata motors","tata motors", as_pdf=True)
    pdf_bytes = io.BytesIO(file)
    pdf_base64 = base64.b64encode(pdf_bytes.getvalue()).decode()
    in_memory_url = f"data:application/pdf;base64,{pdf_base64}"
    
  
    return  in_memory_url
    
    # return in_memory_url

@frappe.whitelist()
def send_message():
    memory_url=create_pdf()
    frappe.msgprint("return back")
    url = "https://api.4whats.net/sendFile"

    payload = {
        'instanceid': '133866',
        'token': 'f95b7d1e-b2f8-4b3c-aec4-ff5b93f0595a',
        'body':memory_url,
        'filename': '',
        'caption': 'null',
        'phone': '+919961343245'
    }
    
    files = []
    
    headers = {
        'content-type': 'application/x-www-form-urlencoded',
        'Cookie': 'PHPSESSID=e9603d8bdbea9f5bf851e36831b8ba16'
    }

    try:
      response = requests.post(url, headers=headers, data=payload, files=files)
      response_json=response.text
      if response.status_code == 200:
            response_dict = json.loads(response_json)
            if response_dict.get("sent") and response_dict.get("id"):
                current_time =now()# for geting current time
                frappe.get_doc({
                        "doctype": "whatsapp saudi success log",
                        "title": "sucess",
                        "message": "testing",
                        "time": current_time
                    }).insert()
            else:
                frappe.log( "success: false,reason: API access prohibited or incorrect instanceid or token" , message=frappe.get_traceback())
            
            #   frappe.log_error(title='Failed to send notification', message=frappe.get_traceback()) 
      else:
            
           frappe.log("status code  is not 200", message=frappe.get_traceback()) 
           
      return response
    except Exception as e:
        frappe.log_error(title='Failed to send notification', message=frappe.get_traceback())  
 

