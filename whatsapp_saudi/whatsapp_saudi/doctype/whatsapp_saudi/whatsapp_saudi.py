from frappe.model.document import Document
from whatsapp_saudi.overrides.whtatsapp_notification import normalize_phone
import requests
import frappe
import logging
import io
import base64
from frappe.utils import now
import json
import time
ERROR_MESSAGE="Invalid JSON"

class WhatsappSaudi(Document):
    pass







def create_pdf_base64():
    file = frappe.get_print("Global Defaults", "default_company", as_pdf=True)
    pdf_bytes = io.BytesIO(file)
    pdf_base64 = base64.b64encode(pdf_bytes.getvalue()).decode()
    return f"data:application/pdf;base64,{pdf_base64}"



# API – Create PDF


@frappe.whitelist()
def create_pdf(allow_guest=True):
    return create_pdf_base64()


# API – Send Message


@frappe.whitelist(allow_guest=True)
def send_message(phone, url, instance, token):
    memory_url = create_pdf()
    phone_number = get_receiver_phone_number(number=phone)

    payload = {
        'instanceid': instance,
        'token': token,
        'body': memory_url,
        'filename': 'Company',
        'caption': "this is a test message",
        'phone': phone_number
    }

    headers = {
        'content-type': 'application/x-www-form-urlencoded'
    }

    try:
        response = requests.post(url, headers=headers, data=payload)

        if response.status_code == 200:
            try:
                response_dict = response.json()
            except Exception:
                frappe.msgprint("Invalid JSON response")
                return

            if response_dict.get("sent") and response_dict.get("id"):
                frappe.get_doc({
                    "doctype": "whatsapp saudi success log",
                    "title": "success",
                    "message": "testing",
                    "time": now()
                }).insert(ignore_permissions=True)
                frappe.msgprint("Sent successfully")

            elif response_dict.get("success") is False:
                frappe.msgprint("API access prohibited or incorrect token")
                frappe.log_error("API access issue", frappe.get_traceback())

            else:
                frappe.msgprint("Invalid phone number format")
                frappe.log_error("Invalid phone format", frappe.get_traceback())

        else:
            frappe.log_error(f"HTTP Error: {response.status_code}", frappe.get_traceback())

        return response

    except Exception:
        frappe.log_error(title='Failed to send notification', message=frappe.get_traceback())


# API – Phone Formatter (Original Kept)


def get_receiver_phone_number(number):
    return normalize_phone(number)



# API – Receive Message


@frappe.whitelist(allow_guest=True)
def receive_whatsapp_message():
    data = frappe.request.get_data(as_text=True)

    try:
        json_data = json.loads(data)
    except Exception:
        frappe.log_error(ERROR_MESSAGE, data)
        return {"status": "error", "message": ERROR_MESSAGE}

    try:
        instance_id = json_data.get("instanceId", "Unknown Instance")

        doc = frappe.get_doc({
            "doctype": "Whatsapp responses",
            "title": "Message Received",
            "response": json.dumps(json_data, indent=2),
            "instance_id": instance_id
        })
        doc.insert(ignore_permissions=True)

        frappe.log_error("Message Received", json.dumps(json_data, indent=2))

        return {"status": "success", "message": "Message received", "docname": doc.name}

    except Exception as e:
        frappe.log_error(title="Failed", message=str(e))
        return {"status": "error", "message": str(e)}



# API – Upload PDF to Rasayel


@frappe.whitelist(allow_guest=True)
def upload_file_pdf(docname):
    try:
        memory_url = create_pdf()
    except Exception as e:
        frappe.log_error("PDF generation failed", str(e))
        return {"status": "error", "message": "PDF generation failed"}

    whatsapp_conf = frappe.get_doc("Whatsapp Saudi")
    url = whatsapp_conf.file_upload
    token = whatsapp_conf.raseyel_authorization_token

    if not memory_url:
        return {"error": "PDF not generated"}

    try:
        _, encoded = memory_url.split(",", 1)
        file_content = base64.b64decode(encoded)
    except Exception:
        return {"error": "PDF decode failed"}

    files = {
        'file': (f"{docname}.pdf", file_content, "application/pdf")
    }

    try:
        response = requests.post(url, headers={"Authorization": token}, files=files)
        try:
            return response.json()
        except:
            return {"error": "Invalid JSON response", "raw": response.text}
    except Exception:
        frappe.log_error("File upload failed", frappe.get_traceback())
        return {"error": "Upload failed"}


# API – Send Rasayel File Message

@frappe.whitelist(allow_guest=True)
def rasayel_whatsapp_file_message_pdf(docname):
    try:
        upload_response = upload_file_pdf(docname)
        if not upload_response or "error" in upload_response:
            return upload_response

        blob_id = upload_response.get("attachment", {}).get("id")
        if not blob_id:
            return {"error": "Blob ID not found", "upload_response": upload_response}

        doc = frappe.get_doc('Whatsapp Saudi')
        url = doc.raseyel_file_api
        channel_id = int(doc.channel_id)
        file_template_id = int(doc.message_template_id)
        token = doc.raseyel_authorization_token

        phone_number = get_receiver_phone_number(doc.to_number)

        payload = {
            "query": """
                mutation TemplateProactiveMessageCreate($input: MessageProactiveTemplateCreateInput!) {
                    data: templateProactiveMessageCreate(input: $input) {
                        message { conversation { id } }
                    }
                }
            """,
            "variables": {
                "input": {
                    "channelId": channel_id,
                    "receiver": phone_number,
                    "messageTemplateId": file_template_id,
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
                    ]
                }
            }
        }

        response = requests.post(
            url,
            headers={
                "Authorization": token,
                "Content-Type": "application/json"
            },
            data=json.dumps(payload)
        )

        if response.status_code != 200:
            frappe.log_error("Rasayel error", response.text)
            return {"error": "API error", "raw": response.text}

        try:
            response_dict = response.json()
        except Exception:
            return {"error": ERROR_MESSAGE, "raw": response.text}

        conversation_id = (
            response_dict.get("data", {})
                .get("data", {})
                .get("message", {})
                .get("conversation", {})
                .get("id")
        )

        if not conversation_id:
            frappe.log_error("Conversation ID missing", json.dumps(response_dict, indent=2))
            return {"error": "Conversation ID missing", "raw": response_dict}

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
        frappe.log_error("Rasayel send failed", frappe.get_traceback())
        return {"error": str(e)}




@frappe.whitelist(allow_guest=True)
def send_bevatel_message(phone):
    import requests

    doc = frappe.get_doc("Whatsapp Saudi", frappe.form_dict.docname)

    url = "https://chat.bevatel.com/developer/api/v1/messages"

    payload = {
        "inbox_id": doc.inbox_id,
        "contact": {
            "phone_number": phone
        },
        "message": {
            "template": {
                "name": "opening_message",
                "language": "ar"
            }
        }
    }

    headers = {
        "api_account_id": doc.account_id,
        "api_access_token": doc.access_token,
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(url, headers=headers, json=payload)

        if response.status_code != 200:
            frappe.log_error(
                title="Bevatel API Error",
                message=response.text
            )

        return response.json()

    except Exception as e:
        frappe.log_error(
            title="Bevatel Exception",
            message=frappe.get_traceback()
        )
        frappe.throw("Failed to send message via Bevatel.")
