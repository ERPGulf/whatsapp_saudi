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

#api for create pdf
@frappe.whitelist()
# creating pdf
def create_pdf():
    file = frappe.get_print("Global Defaults","default_company",as_pdf=True)
    pdf_bytes = io.BytesIO(file)
    pdf_base64 = base64.b64encode(pdf_bytes.getvalue()).decode()
    in_memory_url = f"data:application/pdf;base64,{pdf_base64}"
    return  in_memory_url

#api for send message
@frappe.whitelist()
def send_message(phone,url,instance,token):
    memory_url=create_pdf()

    phoneNumber =get_receiver_phone_number(number=phone)

    pdf_url=url
    payload = {
        'instanceid':instance,
        'token':token,
        'body':memory_url,
        'filename': 'Company',
        'caption':"this is a test message",
        'phone':phoneNumber
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

#api for get receiver phone number

def get_receiver_phone_number(number):
        phoneNumber = number.replace("+","").replace("-","")
        if phoneNumber.startswith("+") == True:
            phoneNumber = phoneNumber[1:]
        elif phoneNumber.startswith("00") == True:
            phoneNumber = phoneNumber[2:]
        elif phoneNumber.startswith("0") == True:
            if len(phoneNumber) == 10:
                phoneNumber = "966" + phoneNumber[1:]
        else:
            if len(phoneNumber) < 10:
                phoneNumber ="966" + phoneNumber
        if phoneNumber.startswith("0") == True:
            phoneNumber = phoneNumber[1:]

        return phoneNumber


#api for receive message and store in database

@frappe.whitelist(allow_guest=True)
def receive_whatsapp_message():
    data = frappe.request.get_data(as_text=True)
    json_data = json.loads(data)
    try:
        instance_id = json_data.get("instanceId", "Unknown Instance")
        frappe.log_error(title="Success", message=json.dumps(json_data, indent=2))
        doc = frappe.get_doc({
            "doctype": "Whatsapp responses",
            "title": "Message Received",
            "response":json.dumps(json_data, indent=2),
            "instance_id": instance_id,
        })
        doc.insert(ignore_permissions=True)
        return {
            "status": "success",
            "message": "Message received",
            "docname": doc.name
        }

    except Exception as e:
        frappe.log_error(title="failed", message=json.dumps(json_data, indent=2))
        return {"status": "error", "message": str(e)}



