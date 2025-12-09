# Copyright (c) 2023, ERPGulf.com and contributors
# For license information, please see license.txt

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
def create_pdf(allow_guest=True):
    file = frappe.get_print("Global Defaults","default_company",as_pdf=True)
    pdf_bytes = io.BytesIO(file)
    pdf_base64 = base64.b64encode(pdf_bytes.getvalue()).decode()
    in_memory_url = f"data:application/pdf;base64,{pdf_base64}"
    return  in_memory_url

#api for send message
@frappe.whitelist(allow_guest=True)
def send_message(phone,url,instance,token):
    memory_url=create_pdf()

    phone_number = get_receiver_phone_number(number=phone)

    pdf_url=url
    payload = {
        'instanceid':instance,
        'token':token,
        'body':memory_url,
        'filename': 'Company',
        'caption':"this is a test message",
        'phone': phone_number
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
                frappe.log_error("success: false,reason: API access prohibited or incorrect instanceid or token", message=frappe.get_traceback())
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
            frappe.log_error("status code is not 200", message=frappe.get_traceback())
      return response
    except Exception as e:
        frappe.log_error(title='Failed to send notification', message=frappe.get_traceback())

#api for get receiver phone number

def get_receiver_phone_number(number):
    phone_number = number.replace("+","").replace("-","")
    if phone_number.startswith("+") == True:
        phone_number = phone_number[1:]
    elif phone_number.startswith("00") == True:
        phone_number = phone_number[2:]
    elif phone_number.startswith("0") == True:
        if len(phone_number) == 10:
            phone_number = "966" + phone_number[1:]
    else:
        if len(phone_number) < 10:
            phone_number ="966" + phone_number
    if phone_number.startswith("0") == True:
        phone_number = phone_number[1:]

    return phone_number


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






@frappe.whitelist(allow_guest=True)
def upload_file_pdf(docname):
    # 1. Generate PDF
    try:
        memory_url = create_pdf()
    except Exception as e:
        frappe.log_error(
            title="Error creating PDF",
            message=f"Error generating PDF for {docname} - {str(e)}"
        )
        return {"status": "error", "message": "PDF generation failed."}

    whatsapp_conf = frappe.get_doc("Whatsapp Saudi")


    try:
        url = whatsapp_conf.file_upload
        token = whatsapp_conf.raseyel_authorization_token

        if not memory_url:
            return {"error": "PDF not generated"}


        try:
            _, encoded = memory_url.split(",", 1)
            file_content = base64.b64decode(encoded)
        except Exception:
            return {"error": "PDF base64 decode failed"}

        file_name = f"{docname}.pdf"
        mime_type = "application/pdf"

        headers = {"Authorization": token}

        files = {
            'file': (file_name, file_content, mime_type)
        }


        response = requests.post(url, headers=headers, files=files)

        try:
            return response.json()
        except:
            return {"error": "Invalid JSON response", "raw": response.text}

    except Exception as e:
        frappe.log_error(title="File Upload Error", message=frappe.get_traceback())
        return {"error": str(e)}


@frappe.whitelist(allow_guest=True)
def rasayel_whatsapp_file_message_pdf(docname):
    try:
        # Step 1: Upload PDF to Rasayel
        upload_response = upload_file_pdf(docname)

        if not upload_response or "error" in upload_response:
            return upload_response

        if "error" in upload_response:
            return upload_response

        attachment = upload_response.get("attachment", {})
        blob_id = attachment.get("id")


        if not blob_id:
            return {
                "error": "Failed to extract blob ID from upload response",
                "upload_response": upload_response
            }


        if not blob_id:
            return {
                "error": "Failed to extract blob ID from upload response",
                "upload_response": upload_response
            }


        doc = frappe.get_doc('Whatsapp Saudi')
        url = doc.get('raseyel_file_api')
        channel_id = int(doc.get('channel_id'))
        file_template_id = int(doc.get('message_template_id'))
        token = doc.get('raseyel_authorization_token')
        phone = doc.get('to_number')


        phone_number = get_receiver_phone_number(phone)


        payload = json.dumps({
            "query": """
                mutation TemplateProactiveMessageCreate($input: MessageProactiveTemplateCreateInput!) {
                    data: templateProactiveMessageCreate(input: $input) {
                        message {
                            conversation { id }
                        }
                    }
                }
            """,
            "variables": {
                "input": {
                    "channelId": channel_id,
                    "receiver": phone_number,
                    "components": [
                        {
                            "type": "HEADER",
                            "parameters": [
                                {
                                    "type": "DOCUMENT",
                                    "blobOrAttachmentId": blob_id
                                }
                            ]
                        }
                    ],
                    "messageTemplateId": file_template_id
                }
            }
        })

        headers = {
            'Authorization': token,
            'Content-Type': 'application/json'
        }


        response = requests.post(url, headers=headers, data=payload)


        response_text = response.text


        if response.status_code != 200:
            frappe.log_error(
                title = "Rasayel API Error",
                message = response_text
            )
            return {
                "error": "WhatsApp API error",
                "status_code": response.status_code,
                "raw": response_text
            }


        try:
            response_dict = response.json()
        except Exception:
            frappe.log_error(
                title="Invalid JSON from Rasayel",
                message=response_text
            )
            return {"error": "Invalid JSON response", "raw": response_text}

        conversation_id = (
            response_dict.get("data", {})
                        .get("data", {})
                        .get("message", {})
                        .get("conversation", {})
                        .get("id")
        )

        if not conversation_id:
            frappe.log_error(
                title="No conversation ID in Rasayel response",
                message=json.dumps(response_dict, indent=2)
            )
            return {
                "error": "Failed to get conversation ID",
                "raw": response_dict
            }

        frappe.get_doc({
            "doctype": "whatsapp saudi success log",
            "title": "Message successfully sent",
            "message": conversation_id,
            "to_number": phone_number,
            "time": now()
        }).insert(ignore_permissions=True)

        return {
            "success": True,
            "conversation_id": conversation_id,
            "message": "WhatsApp File Message sent successfully"
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Rasayel File Message Error")
        return {"error": str(e)}



