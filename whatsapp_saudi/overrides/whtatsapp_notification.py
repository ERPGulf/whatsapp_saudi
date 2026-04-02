import frappe
from frappe import _
from frappe.email.doctype.notification.notification import Notification
import json
import requests
from werkzeug.wrappers import Response
import io
import re
import base64
from frappe.utils import now, get_url
import os
from whatsapp_saudi.overrides.pdf_a3 import (
    embed_file_in_pdf,
    send_whatsapp_with_pdf_a3,
    embed_public_file_in_pdf,
    bevatel_create_pdf,
    _send_bevatel_whatsapp,
    normalize_phone_bavatel,
)
from frappe.core.doctype.role.role import get_info_based_on_role, get_user_info
from frappe.utils.jinja import render_template

ERROR_MESSAGE = "success: false, reason: API access prohibited or incorrect instanceid or token"
ERROR_MESSAGE1 = "Failed to close conversation"
ERROR_MESSAGE2 = "Failed to generate PDF/A-3 file!"
ERROR_MESSAGE3 = "WhatsApp File Message sent successfully"
ERROR_MESSAGE4 = "Bevatel Configuration Error"
ERROR_MESSAGE5 = "Document is cancelled"
ERROR_MESSAGE6 = "Configuration error occurred"
ERROR_MESSAGE7 = "application/x-www-form-urlencoded"
ERROR_MESSAGE8 = "Failed to send notification"
DOCNAME = "Whatsapp Saudi"
Tittle1 = "Message successfully sent"
file_upload_error = "File upload error"
Doctype_success_log = "whatsapp saudi success log"
Type = "application/json"
Type_pdf = "application/pdf"


def log_whatsapp_success(message, phone_number):
    """
    Insert a success record into the WhatsApp Saudi success log doctype.

    Args:
        message: The message content or conversation/message ID to log.
        phone_number: The recipient's phone number.
    """
    frappe.get_doc({
        "doctype": Doctype_success_log,
        "title": Tittle1,
        "message": message,
        "to_number": phone_number,
        "time": now(),
    }).insert(ignore_permissions=True)


def log_bevatel_response(response, response_data, phone_number,Tittle1, Doctype_success_log, results):
    """
    Log Bevatel WhatsApp API response and append result status.
    """
    if response.status_code in [200, 201]:
        log_whatsapp_success(json.dumps(response_data), phone_number)
        results.append({
            "status": "success",
            "phone": phone_number
        })
    else:
        frappe.log_error(
            title="Bevatel WhatsApp API Error",
            message=json.dumps(response_data),
        )
        results.append({
            "status": "failed",
            "phone": phone_number,
            "error": response_data
        })


def normalize_phone(number):
    phone_number = (number or "").replace("+", "").replace("-", "").replace(" ", "")
    if phone_number.startswith("00"):
        phone_number = phone_number[2:]
    elif phone_number.startswith("0"):
        if len(phone_number) == 10:
            phone_number = "966" + phone_number[1:]
        else:
            phone_number = "966" + phone_number
    if phone_number.startswith("0"):
        phone_number = phone_number[1:]
    return phone_number


def generate_pdf_base64_from_bytes(pdf_bytes: bytes) -> str:
    return f"data:application/pdf;base64,{base64.b64encode(pdf_bytes).decode()}"


def generate_pdf_base64(doctype, docname, print_format):
    file = frappe.get_print(doctype, docname, print_format, as_pdf=True)
    pdf_bytes = file if isinstance(file, (bytes, bytearray)) else io.BytesIO(file).getvalue()
    return generate_pdf_base64_from_bytes(pdf_bytes)


def decode_memory_url(memory_url):
    try:
        header, encoded = memory_url.split(",", 1)
        return base64.b64decode(encoded)
    except Exception:
        return None


def upload_file_common(url, token, memory_url, filename):
    if not memory_url:
        return {"error": "No file to upload"}
    file_content = decode_memory_url(memory_url)
    if file_content is None:
        return {"error": "Invalid memory_url/base64"}

    headers = {"Authorization": token}
    files = {"file": (filename, file_content, Type_pdf)}
    try:
        response = requests.post(url, headers=headers, files=files)
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "File upload request failed")
        return {"error": str(e)}

    try:
        return response.json()
    except Exception:
        return {"error": "Invalid JSON response", "raw": response.text}


def send_graphql(url, token, query, variables):
    headers = {"Authorization": token, "Content-Type": Type}
    payload = {"query": query, "variables": variables}
    try:
        resp = requests.post(url, headers=headers, json=payload)
        return resp
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "GraphQL request failed")
        raise


def close_conversation(conversation_id):
    try:
        ws_doc = frappe.get_doc(DOCNAME)
        query = """
            mutation ConversationSetState($input: ConversationSetStateInput!) {
                response: conversationSetState(input: $input) {
                    message { id }
                }
            }
        """
        variables = {"input": {"conversationId": conversation_id, "state": "CLOSED"}}
        send_graphql(ws_doc.raseyel_file_api, ws_doc.raseyel_authorization_token, query, variables)
    except Exception:
        frappe.log_error(frappe.get_traceback(), ERROR_MESSAGE1)


class ERPGulfNotification(Notification):

    def get_receiver_list(self, doc, context):
        """return receiver list based on the doc field and role specified"""
        receiver_list = []
        for recipient in self.recipients:
            if recipient.condition and not frappe.safe_eval(recipient.condition, None, context):
                continue

            if recipient.receiver_by_document_field == "owner":
                receiver_list += get_user_info([dict(user_name=doc.get("owner"))], "mobile_no")
            elif recipient.receiver_by_document_field:
                receiver_list.append(doc.get(recipient.receiver_by_document_field))

            if recipient.receiver_by_role:
                receiver_list += get_info_based_on_role(recipient.receiver_by_role, "mobile_no")

        return receiver_list

    def get_receiver_phone_number(self, number):
        return normalize_phone(number)

    def bavatel_phone(self, number):
        return normalize_phone_bavatel(number)

    def parse_message_block(self, text):
        result = {}
        lines = (text or "").split("\n")
        for line in lines:
            line = line.strip().rstrip(",")
            if "=" in line:
                key, value = line.split("=", 1)
                result[key.strip()] = value.strip().strip('"')
        return result

    def create_pdf(self, doc):
        file = frappe.get_print(doc.doctype, doc.name, self.print_format, as_pdf=True)
        pdf_bytes = file if isinstance(file, (bytes, bytearray)) else io.BytesIO(file).getvalue()
        return generate_pdf_base64_from_bytes(pdf_bytes)

    def upload_file(self, doc, context):
        pdf_a3_path = embed_file_in_pdf(doc.name, self.print_format, letterhead=None, language="en")
        if not pdf_a3_path:
            frappe.throw(_(ERROR_MESSAGE2))

        # nosemgrep: frappe-semgrep-rules.rules.security.frappe-security-file-traversal
        # Audited: pdf_a3_path comes from embed_file_in_pdf which constructs path from
        # internal site path. replace() maps public URL back to local filesystem path.
        with open(pdf_a3_path.replace(get_url(), frappe.local.site), "rb") as pdf_file:
            pdf_base64 = base64.b64encode(pdf_file.read()).decode()

        memory_url = f"data:application/pdf;base64,{pdf_base64}"
        recipients = self.get_receiver_list(doc, context)

        for receipt in recipients:
            number = receipt
            phoneNumber = self.get_receiver_phone_number(number)
            # nosemgrep: frappe-semgrep-rules.rules.security.frappe-ssti
            # Audited: self.message is the Notification document's message field,
            # which is admin-controlled configuration, not direct user input.
            msg1 = frappe.render_template(self.message, context)
            try:
                doc1 = frappe.get_doc(DOCNAME)
                url = doc1.get("file_upload")
                token = doc1.get("raseyel_authorization_token")

                uploaded_file = memory_url
                if not uploaded_file:
                    return {"error": "No file uploaded"}

                return upload_file_common(url, token, memory_url, f"{doc.name}.pdf")

            except Exception:
                frappe.log_error(frappe.get_traceback(), file_upload_error)
                return {"error": "File upload exception"}

    def rasayel_whatsapp_file_message(self, doc, context):
        recipients = self.get_receiver_list(doc, context)

        for receipt in recipients:
            phoneNumber = self.get_receiver_phone_number(receipt)

            try:
                upload_response = self.upload_file(doc, context)
                if not upload_response or "error" in upload_response:
                    return upload_response

                blob_id = upload_response.get("attachment", {}).get("id")
                if not blob_id:
                    return {"error": "Failed to extract blob ID", "raw": upload_response}

                ws_doc = frappe.get_doc(DOCNAME)
                url = ws_doc.raseyel_file_api
                channel_id = int(ws_doc.channel_id)
                token = ws_doc.raseyel_authorization_token

                # nosemgrep: frappe-semgrep-rules.rules.security.frappe-ssti
                # Audited: self.message is the Notification document's message field,
                # which is admin-controlled configuration, not direct user input.
                msg_block = frappe.render_template(self.message, context)
                parsed = self.parse_message_block(msg_block)

                file_template_id = int(parsed.get("message_template_id"))

                body_params = []
                for key in sorted(parsed.keys()):
                    if key.startswith("var"):
                        body_params.append({"type": "TEXT", "text": parsed[key]})

                headers = {"Authorization": token, "Content-Type": Type}

                components_normal = [
                    {
                        "type": "HEADER",
                        "parameters": [{"type": "DOCUMENT", "blobOrAttachmentId": blob_id}],
                    }
                ]

                if body_params:
                    components_normal.append({"type": "BODY", "parameters": body_params})

                payload_normal = json.dumps({
                    "query": """
                        mutation TemplateProactiveMessageCreate($input: MessageProactiveTemplateCreateInput!) {
                            response: templateProactiveMessageCreate(input: $input) {
                                message {
                                    conversation { id }
                                }
                            }
                        }
                    """,
                    "variables": {
                        "input": {
                            "channelId": channel_id,
                            "receiver": phoneNumber,
                            "messageTemplateId": int(file_template_id),
                            "components": components_normal,
                        }
                    },
                })

                response = requests.post(url, headers=headers, data=payload_normal)
                response_json = response.text

                try:
                    response_dict = json.loads(response_json)
                except Exception:
                    frappe.log_error("Invalid JSON", response_json)
                    return {"error": "Invalid JSON response", "raw": response_json}

                validation_error = False
                if "errors" in response_dict:
                    for err in response_dict.get("errors", []):
                        if "Wrong Template Parameters" in err.get("message", ""):
                            validation_error = True

                if validation_error:
                    components_buttons = [
                        {
                            "type": "HEADER",
                            "parameters": [{"type": "DOCUMENT", "blobOrAttachmentId": blob_id}],
                        },
                        {"type": "BUTTONS", "parameters": body_params},
                    ]

                    payload_buttons = json.dumps({
                        "query": """
                            mutation TemplateProactiveMessageCreate($input: MessageProactiveTemplateCreateInput!) { response: templateProactiveMessageCreate(input: $input) { message { conversation { id } } }}
                        """,
                        "variables": {
                            "input": {
                                "channelId": channel_id,
                                "receiver": phoneNumber,
                                "messageTemplateId": int(file_template_id),
                                "components": components_buttons,
                            }
                        },
                    })

                    response = requests.post(url, headers=headers, data=payload_buttons)
                    response_json = response.text
                    response_dict = json.loads(response_json)

                conversation_id = (
                    response_dict.get("data", {})
                    .get("response", {})
                    .get("message", {})
                    .get("conversation", {})
                    .get("id")
                )

                if conversation_id:
                    log_whatsapp_success(conversation_id, phoneNumber)

                    try:
                        close_conversation(conversation_id)
                    except Exception:
                        frappe.log_error(frappe.get_traceback(), ERROR_MESSAGE1)

                    return {
                        "success": True,
                        "conversation_id": conversation_id,
                        "message": ERROR_MESSAGE3,
                    }

                return {"error": "Send failed", "raw": response_json}

            except Exception:
                frappe.log_error(
                    title="Rasayel API Error",
                    message=json.dumps({
                        "invoice": doc.name,
                        "response": response.text,
                        "text": frappe.get_traceback(),
                    }, indent=2),
                )
                return {"error": "Exception while sending file message"}

    def rasayel_whatsapp_message(self, doc, context):
        try:
            ws_doc = frappe.get_doc(DOCNAME)
            url = ws_doc.raseyel_message_api
            channel_id = int(ws_doc.channel_id)
            token = ws_doc.raseyel_authorization_token

            recipients = self.get_receiver_list(doc, context)
            results = []

            for recipient in recipients:
                phone_number = self.get_receiver_phone_number(recipient)
                # nosemgrep: frappe-semgrep-rules.rules.security.frappe-ssti
                # Audited: self.message is the Notification document's message field,
                # which is admin-controlled configuration, not direct user input.
                msg_block = frappe.render_template(self.message, context)
                parsed = self.parse_message_block(msg_block)
                message_template_id = parsed.get("message_template_id")

                body_params = []
                for key in sorted(parsed.keys()):
                    if key.startswith("var"):
                        body_params.append({"type": "TEXT", "text": parsed[key]})

                payload = json.dumps({
                    "phone": phone_number,
                    "channel_id": channel_id,
                    "type": "TEMPLATE",
                    "template": {
                        "message_template_id": int(message_template_id),
                        "components": [{"type": "BODY", "parameters": body_params}],
                    },
                })

                headers = {"Authorization": token, "Content-Type": Type}

                response = requests.post(url, headers=headers, data=payload)
                response_json = response.text

                if response.status_code in (200, 201):
                    try:
                        response_dict = json.loads(response_json)
                    except Exception:
                        frappe.log_error("Invalid JSON response", response_json)
                        results.append({
                            "phone": phone_number,
                            "success": False,
                            "error": "Invalid JSON",
                            "raw": response_json,
                        })
                        continue

                    message_id = response_dict.get("id") or response_dict.get("message", {}).get("id")
                    conversation_id = (
                        response_dict.get("conversation_id")
                        or response_dict.get("conversation", {}).get("id")
                        or response_dict.get("data", {}).get("conversation_id")
                    )

                    if message_id and conversation_id:
                        log_whatsapp_success(message_id, phone_number)

                        try:
                            close_conversation(conversation_id)
                        except Exception:
                            frappe.log_error(frappe.get_traceback(), ERROR_MESSAGE1)

                        results.append({
                            "phone": phone_number,
                            "success": True,
                            "message_id": message_id,
                            "conversation_id": conversation_id,
                        })
                    else:
                        frappe.log_error("Message send failed (missing IDs)", response_json)
                        results.append({
                            "phone": phone_number,
                            "success": False,
                            "error": "Incomplete success response",
                            "raw": response_json,
                        })
                else:
                    frappe.log_error(
                        title="Rasayel API Error",
                        message=json.dumps({"invoice": doc.name, "response": response_json}, indent=2),
                    )
                    results.append({
                        "phone": phone_number,
                        "success": False,
                        "status_code": response.status_code,
                        "raw": response_json,
                    })

            return results

        except Exception:
            frappe.log_error(title="Failed to send Rasayel Notification", message=frappe.get_traceback())
            return {"error": "Failed to send message"}

    def send_bevatel_file_template_message(self, doc, context):
        try:
            pdf_a3_url = embed_public_file_in_pdf(doc.name, self.print_format, letterhead=None, language="en")
            if not pdf_a3_url:
                frappe.throw(_(ERROR_MESSAGE2))

            ws_doc = frappe.get_single(DOCNAME)
            url = ws_doc.bavatel_file_url
            api_account_id = ws_doc.account_id
            api_access_token = ws_doc.access_token
            inbox_id = ws_doc.inbox_id

            recipients = self.get_receiver_list(doc, context)
            results = []

            message_content = self.message or ""

            template_match = re.search(r'message_template_id\s*=\s*"([^"]+)"', message_content)
            template_name = template_match.group(1) if template_match else None

            language_match = re.search(r'language\s*=\s*"([^"]+)"', message_content)
            language = language_match.group(1) if language_match else "ar"

            var_matches = re.findall(r'var\d+\s*=\s*"([^"]*)"', message_content)

            # nosemgrep: frappe-semgrep-rules.rules.security.frappe-ssti
            # Audited: var values are extracted from the Notification document's message field,
            # which is admin-controlled configuration, not direct user input.
            body_variables = []
            for var in var_matches:
                rendered_value = frappe.render_template(var.strip(), {"doc": doc})
                body_variables.append(rendered_value)

            for recipient in recipients:
                try:
                    phone_number = self.bavatel_phone(recipient)

                    parameters = {
                        "media": {
                            "link": pdf_a3_url,
                            "type": "DOCUMENT",
                            "filename": f"{doc.name}.pdf",
                        }
                    }

                    if body_variables:
                        parameters["body"] = body_variables

                    payload = {
                        "inbox_id": inbox_id,
                        "contact": {"phone_number": phone_number},
                        "message": {
                            "template": {
                                "name": template_name,
                                "language": language,
                                "parameters": parameters,
                            }
                        },
                    }

                    headers = {
                        "api_account_id": api_account_id,
                        "api_access_token": api_access_token,
                        "Content-Type": "application/json",
                    }

                    response = requests.post(url, headers=headers, json=payload, timeout=30)
                    response_data = response.json()

                    log_bevatel_response(
                        response=response,
                        response_data=response_data,
                        phone_number=phone_number,
                        title1=Tittle1,
                        Doctype_success_log=Doctype_success_log,
                        results=results
                    )

                except Exception:
                    frappe.log_error(
                        title="Bevatel WhatsApp Send Failed",
                        message=frappe.get_traceback(),
                    )

            frappe.db.commit()
            return results

        except Exception:
            frappe.log_error(title=ERROR_MESSAGE4, message=frappe.get_traceback())
            return {"status": "error", "message": ERROR_MESSAGE6}

    def send_bevatel_template_message(self, doc, context):
        try:
            ws_doc = frappe.get_single(DOCNAME)
            url = ws_doc.bavatel_file_url
            api_account_id = ws_doc.account_id
            api_access_token = ws_doc.access_token
            inbox_id = ws_doc.inbox_id
            default_template_name = ws_doc.template_name
            default_language = ws_doc.language or "en"

            recipients = self.get_receiver_list(doc, context)
            results = []

            message_content = self.message or ""

            template_id_match = re.search(r'message_template_id\s*=\s*"([^"]+)"', message_content)
            template_id = template_id_match.group(1) if template_id_match else default_template_name

            language_match = re.search(r'language\s*=\s*"([^"]+)"', message_content)
            language = language_match.group(1) if language_match else default_language

            var_matches = re.findall(r'var\d+\s*=\s*"([^"]*)"', message_content)

            # nosemgrep: frappe-semgrep-rules.rules.security.frappe-ssti
            # Audited: var values are extracted from the Notification document's message field,
            # which is admin-controlled configuration, not direct user input.
            variables = []
            for var in var_matches:
                rendered_value = frappe.render_template(var.strip(), {"doc": doc})
                variables.append(rendered_value)

            for recipient in recipients:
                try:
                    phone_number = self.bavatel_phone(recipient)

                    template_data = {
                        "name": template_id,
                        "language": language,
                        "parameters": {"body": variables if variables else []},
                    }

                    payload = {
                        "inbox_id": inbox_id,
                        "contact": {"phone_number": phone_number},
                        "message": {"template": template_data},
                    }

                    headers = {
                        "api_account_id": api_account_id,
                        "api_access_token": api_access_token,
                        "Content-Type": "application/json",
                    }

                    response = requests.post(url, headers=headers, json=payload, timeout=30)
                    response_data = response.json()

                    log_bevatel_response(
                        response=response,
                        response_data=response_data,
                        phone_number=phone_number,
                        title1=Tittle1,
                        Doctype_success_log=Doctype_success_log,
                        results=results
                    )
                except Exception:
                    frappe.log_error(
                        title="Bevatel WhatsApp Send Failed",
                        message=frappe.get_traceback(),
                    )

            frappe.db.commit()
            return results

        except Exception:
            frappe.log_error(title=ERROR_MESSAGE4, message=frappe.get_traceback())
            return {"status": "error", "message": "Configuration or unexpected error occurred. Check error logs."}

    @frappe.whitelist()
    def send_whatsapp_with_pdf(self, doc: object, context: dict):
        pdf_a3_path = embed_file_in_pdf(doc.name, self.print_format, letterhead=None, language="en")
        if not pdf_a3_path:
            frappe.throw(_(ERROR_MESSAGE2))

        # nosemgrep: frappe-semgrep-rules.rules.security.frappe-security-file-traversal
        # Audited: pdf_a3_path comes from embed_file_in_pdf which constructs path from
        # internal site path. replace() maps public URL back to local filesystem path.
        with open(pdf_a3_path.replace(get_url(), frappe.local.site), "rb") as pdf_file:
            pdf_base64 = base64.b64encode(pdf_file.read()).decode()

        memory_url = f"data:application/pdf;base64,{pdf_base64}"
        recipients = self.get_receiver_list(doc, context)

        for receipt in recipients:
            number = receipt
            phoneNumber = self.get_receiver_phone_number(number)
            url = frappe.get_doc(DOCNAME).get("file_url")
            instance = frappe.get_doc(DOCNAME).get("instance_id")
            # nosemgrep: frappe-semgrep-rules.rules.security.frappe-ssti
            # Audited: self.message is the Notification document's message field,
            # which is admin-controlled configuration, not direct user input.
            msg1 = frappe.render_template(self.message, context)
            token = frappe.get_doc(DOCNAME).get("token")
            payload = {
                "instanceid": instance,
                "token": token,
                "body": memory_url,
                "filename": f"{doc.name}.pdf",
                "caption": msg1,
                "phone": phoneNumber,
            }

            headers = {"content-type": ERROR_MESSAGE7}
            try:
                response = requests.post(url, headers=headers, data=payload, timeout=30)
                response_json = response.text
                if response.status_code == 200:
                    response_dict = json.loads(response_json)
                    if response_dict.get("sent") and response_dict.get("id"):
                        log_whatsapp_success(msg1, phoneNumber)
                    else:
                        frappe.log_error(
                            title="API Error",
                            message=json.dumps({"invoice": doc.name, "response": response_json}, indent=2),
                        )
                else:
                    frappe.log_error(
                        title="API Error",
                        message=json.dumps({"invoice": doc.name, "response": response_json}, indent=2),
                    )

                return response
            except requests.exceptions.RequestException:
                frappe.log_error(title=ERROR_MESSAGE8, message=frappe.get_traceback())

    def send_whatsapp_without_pdf(self, doc, context):
        url = frappe.get_doc(DOCNAME).get("message_url")
        instance = frappe.get_doc(DOCNAME).get("instance_id")
        # nosemgrep: frappe-semgrep-rules.rules.security.frappe-ssti
        # Audited: self.message is the Notification document's message field,
        # which is admin-controlled configuration, not direct user input.
        msg1 = frappe.render_template(self.message, context)
        token = frappe.get_doc(DOCNAME).get("token")
        recipients = self.get_receiver_list(doc, context)
        results = []
        for receipt in recipients:
            number = receipt
            phoneNumber = self.get_receiver_phone_number(number)
            querystring = {
                "instanceid": instance,
                "token": token,
                "phone": phoneNumber,
                "body": msg1,
            }
            try:
                response = requests.get(url, params=querystring)
                response_json = response.text
                if response.status_code == 200:
                    response_dict = json.loads(response_json)
                    if response_dict.get("sent") and response_dict.get("id"):
                        log_whatsapp_success(msg1, phoneNumber)
                        results.append({"phone": phoneNumber, "success": True})
                    else:
                        frappe.log_error(
                            title=ERROR_MESSAGE8,
                            message=json.dumps({"invoice": doc.name, "response": response_json}, indent=2),
                        )
                        results.append({"phone": phoneNumber, "success": False, "raw": response_json})
                else:
                    frappe.log_error("status code is not 200", frappe.get_traceback())
                    results.append({"phone": phoneNumber, "success": False, "status_code": response.status_code})
            except requests.exceptions.RequestException:
                frappe.log_error(
                    title=ERROR_MESSAGE8,
                    message=json.dumps({"invoice": doc.name, "response": response_json}, indent=2),
                )
                results.append({"phone": phoneNumber, "success": False, "error": "request exception"})
        return results

    def send(self, doc):
        context = {"doc": doc, "alert": self, "comments": None}
        if doc.get("_comments"):
            context["comments"] = json.loads(doc.get("_comments"))
        rasayel_api = frappe.get_doc(DOCNAME).whatsapp_provider
        if self.is_standard:
            self.load_standard_properties(context)

        if self.channel == DOCNAME:
            frappe.log_error(
                title="DEBUG STEP 3 - Channel Matched",
                message="Inside Whatsapp Saudi channel",
            )
            try:
                if self.attach_print and self.print_format:
                    if rasayel_api == "Rasayel":
                        frappe.enqueue(
                            self.rasayel_whatsapp_file_message,
                            queue="long",
                            timeout=600,
                            doc=doc,
                            context=context,
                        )
                    elif rasayel_api == "Bevatel":
                        frappe.enqueue(
                            self.send_bevatel_file_template_message,
                            queue="long",
                            timeout=600,
                            doc=doc,
                            context=context,
                        )
                    else:
                        frappe.enqueue(
                            self.send_whatsapp_with_pdf,
                            queue="long",
                            timeout=600,
                            doc=doc,
                            context=context,
                        )
                else:
                    if rasayel_api == "Rasayel":
                        frappe.enqueue(
                            self.rasayel_whatsapp_message,
                            queue="long",
                            timeout=600,
                            doc=doc,
                            context=context,
                        )
                    elif rasayel_api == "Bevatel":
                        frappe.enqueue(
                            self.send_bevatel_template_message,
                            queue="long",
                            timeout=600,
                            doc=doc,
                            context=context,
                        )
                    else:
                        frappe.enqueue(
                            self.send_whatsapp_without_pdf,
                            queue="long",
                            timeout=600,
                            doc=doc,
                            context=context,
                        )
            except Exception:
                frappe.log_error(
                    title="Failed to send WhatsApp notification", message=frappe.get_traceback()
                )
        else:
            try:
                super(ERPGulfNotification, self).send(doc)
            except Exception:
                frappe.log_error(
                    title="Failed to send standard notification", message=frappe.get_traceback()
                )


# FIX: Added type hints to all arguments
@frappe.whitelist()
def create_pdf1(doctype: str, docname: str, print_format: str):
    try:
        file = frappe.get_print(doctype, docname, print_format)
        if isinstance(file, str) and "Uncaught Server Exception" in file:
            return Response(
                json.dumps({"error": "Uncaught Server Exception detected."}),
                status=500,
                mimetype=Type,
            )
        file = frappe.get_print(doctype, docname, print_format, as_pdf=True)
        pdf_bytes = file if isinstance(file, (bytes, bytearray)) else io.BytesIO(file).getvalue()
        pdf_base64 = base64.b64encode(pdf_bytes).decode()
        in_memory_url = f"data:application/pdf;base64,{pdf_base64}"
        return in_memory_url

    except frappe.PrintFormatError:
        frappe.local.response["http_status_code"] = 500
        return {"error": "An issue occurred while generating the PDF."}

    except (frappe.DoesNotExistError, frappe.PermissionError, frappe.ValidationError) as e:
        frappe.local.response["http_status_code"] = 500
        frappe.log_error(f"Error in create_pdf1: {str(e)}", "Custom Function Error")
        return {"error": "Something went wrong. Please try again later."}


# FIX: Added type hints to all arguments
@frappe.whitelist()
def send_whatsapp_with_pdf1(message: str, docname: str, doctype: str, print_format: str):
    try:
        memory_url = create_pdf1(doctype, docname, print_format)
    except (frappe.DoesNotExistError, frappe.PermissionError, frappe.ValidationError, frappe.PrintFormatError) as e:
        frappe.log_error(
            title="Error creating PDF",
            message=f"Error generating PDF for {docname} with format {print_format}. Error: {str(e)}",
        )
        return {
            "status": "error",
            "message": f"Error generating PDF for {docname} with format {print_format}. Please check the print format and try again.",
        }

    xml_file = None
    cleared_xml_file_name = "Cleared xml file " + docname + ".xml"
    reported_xml_file_name = "Reported xml file " + docname + ".xml"
    attachments = frappe.get_all("File", filters={"attached_to_name": docname}, fields=["file_name"])

    for attachment in attachments:
        file_name = attachment.get("file_name", None)
        file = os.path.join(frappe.local.site, "private", "files", file_name)
        if file_name in [cleared_xml_file_name, reported_xml_file_name]:
            xml_file = file

    if not xml_file:
        frappe.throw(
            _("No XML file found for the invoice {0}. Please ensure the XML file is attached.").format(docname)
        )

    whatsapp_config = frappe.get_doc(DOCNAME)
    sales_invoice = frappe.get_doc("Sales Invoice", docname)
    if sales_invoice.get("docstatus") == 2:
        frappe.throw(_(ERROR_MESSAGE5))
        return {"status": "error", "message": ERROR_MESSAGE5}

    customer = sales_invoice.get("customer")
    customer_doc = frappe.get_doc("Customer", customer)

    url = whatsapp_config.get("file_url")
    instance = whatsapp_config.get("instance_id")
    token = whatsapp_config.get("token")
    phone = customer_doc.get("custom_whatsapp_number_")

    if not phone:
        return {"status": "error", "message": "No WhatsApp number found for the customer"}

    phonenumber = normalize_phone(phone)

    payload = {
        "instanceid": instance,
        "token": token,
        "body": memory_url,
        "filename": docname,
        "caption": message,
        "phone": phonenumber,
    }

    files = []
    headers = {"content-type": ERROR_MESSAGE7}

    try:
        response = requests.post(url, headers=headers, data=payload, files=files, timeout=30)
        response_json = response.text
        if response.status_code == 200:
            response_dict = json.loads(response_json)
            if response_dict.get("sent") and response_dict.get("id"):
                log_whatsapp_success(message, phonenumber)
                response_dict["success"] = True
                response_dict["message"] = Tittle1
            else:
                frappe.log_error(ERROR_MESSAGE, frappe.get_traceback())
                return {"status": "error", "message": "Failed to send message, check API access."}
        else:
            frappe.log_error("Status code is not 200", frappe.get_traceback())
            return {"status": "error", "message": "Failed to send message, non-200 response."}
    except requests.exceptions.RequestException:
        frappe.log_error(title=ERROR_MESSAGE8, message=frappe.get_traceback())
        return {"status": "error", "message": "Error in sending WhatsApp message."}

    return {"status": "success", "message": "Message sent successfully."}


def get_receiver_phone_number1(number):
    return normalize_phone(number)


# FIX: Added type hints to all arguments
@frappe.whitelist()
def rasayel_whatsapp_message1(phone: str, message: str):
    try:
        doc = frappe.get_doc(DOCNAME)
        url = doc.get("raseyel_message_api")
        channel_id = int(doc.get("channel_id"))
        message_template_id = int(doc.get("message_template_id"))
        token = doc.get("raseyel_authorization_token")

        payload = json.dumps({
            "phone": phone,
            "channel_id": channel_id,
            "type": "TEMPLATE",
            "template": {
                "message_template_id": message_template_id,
                "components": [
                    {
                        "type": "BODY",
                        "parameters": [{"type": "TEXT", "text": message}],
                    }
                ],
            },
        })

        headers = {"Authorization": token, "Content-Type": Type}

        response = requests.post(url, headers=headers, data=payload)

        if response.status_code != 200:
            frappe.log_error(
                title="Rasayel WhatsApp API Error",
                message=f"Status: {response.status_code}\nResponse: {response.text}",
            )
            return frappe.Response(
                json.dumps({
                    "status": "error",
                    "message": "Failed to send WhatsApp message",
                    "response": response.text,
                }),
                status=500,
                mimetype=Type,
            )

        return frappe.Response(
            json.dumps({"status": "success", "response": json.loads(response.text)}),
            status=200,
            mimetype=Type,
        )

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Rasayel WhatsApp Message Exception")
        return frappe.Response(
            json.dumps({"status": "error", "message": str(e)}),
            status=500,
            mimetype=Type,
        )


# FIX: Added type hints to all arguments
@frappe.whitelist()
def upload_file_pdf(doctype: str, docname: str, print_format: str):
    try:
        memory_url = create_pdf1(doctype, docname, print_format)
    except Exception as e:
        frappe.log_error(
            title="Error creating PDF",
            message=f"Error generating PDF for {docname} - {str(e)}",
        )
        return {"status": "error", "message": "PDF generation failed."}

    cleared_xml = f"Cleared xml file {docname}.xml"
    reported_xml = f"Reported xml file {docname}.xml"
    xml_file = None
    attachments = frappe.get_all("File", filters={"attached_to_name": docname}, fields=["file_name"])

    for att in attachments:
        if att.file_name in [cleared_xml, reported_xml]:
            xml_file = os.path.join(frappe.local.site_path, "private", "files", att.file_name)
            break

    if not xml_file:
        frappe.throw(_("No XML file found for {0}").format(docname))

    invoice = frappe.get_doc("Sales Invoice", docname)
    if invoice.docstatus == 2:
        frappe.throw(_(ERROR_MESSAGE5))

    whatsapp_conf = frappe.get_doc(DOCNAME)
    try:
        url = whatsapp_conf.file_upload
        token = whatsapp_conf.raseyel_authorization_token
        if not memory_url:
            return {"error": "PDF not generated"}

        try:
            header, encoded = memory_url.split(",", 1)
            file_content = base64.b64decode(encoded)
        except Exception:
            return {"error": "PDF base64 decode failed"}

        file_name = f"{docname}.pdf"
        mime_type = Type_pdf
        headers = {
            "Authorization": f"Basic {token}"
        }
        files = {"file": (file_name, file_content, mime_type)}

        response = requests.post(url, headers=headers, files=files)
        try:
            return response.json()
        except Exception:
            return {"error": "Invalid JSON response", "raw": response.text}
    except Exception:
        frappe.log_error(title=file_upload_error, message=frappe.get_traceback())
        return {"error": "File upload exception"}


# FIX: Added type hints to all arguments
@frappe.whitelist()
def rasayel_whatsapp_file_message_pdf(doctype: str, docname: str, print_format: str):
    try:
        upload_response = upload_file_pdf(doctype, docname, print_format)

        if not upload_response or "error" in upload_response:
            return upload_response

        attachment = upload_response.get("attachment", {})
        blob_id = attachment.get("id")

        if not blob_id:
            return {"error": "Failed to extract blob ID from upload response", "upload_response": upload_response}

        doc = frappe.get_doc(DOCNAME)
        url = doc.get("raseyel_file_api")
        channel_id = int(doc.get("channel_id"))
        file_template_id = int(doc.get("message_template_id"))
        token = doc.get("raseyel_authorization_token")

        sales_invoice = frappe.get_doc("Sales Invoice", docname)
        if sales_invoice.docstatus == 2:
            frappe.throw(_(ERROR_MESSAGE5))

        customer = sales_invoice.customer
        customer_doc = frappe.get_doc("Customer", customer)
        phone = customer_doc.get("custom_whatsapp_number_")
        if not phone:
            return {"status": "error", "message": "No WhatsApp number found for the customer"}
        phone_number = normalize_phone(phone)

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
                            "parameters": [{"type": "DOCUMENT", "blobOrAttachmentId": blob_id}],
                        }
                    ],
                    "messageTemplateId": file_template_id,
                }
            },
        })

        headers = {"Authorization": token, "Content-Type": Type}

        response = requests.post(url, headers=headers, data=payload)
        response_text = response.text

        if response.status_code != 200:
            frappe.log_error(title="Rasayel API Error", message=response_text)
            return {"error": "WhatsApp API error", "status_code": response.status_code, "raw": response_text}

        try:
            response_dict = response.json()
        except Exception:
            frappe.log_error(title="Invalid JSON from Rasayel", message=response_text)
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
                message=json.dumps(response_dict, indent=2),
            )
            return {"error": "Failed to get conversation ID", "raw": response_dict}

        log_whatsapp_success(conversation_id, phone_number)

        try:
            close_conversation(conversation_id)
        except Exception:
            frappe.log_error(frappe.get_traceback(), ERROR_MESSAGE1)

        return {"status": "success", "conversation_id": conversation_id, "message": ERROR_MESSAGE3}

    except Exception:
        frappe.log_error(
            title="Rasayel API Error",
            message=json.dumps({
                "invoice": docname,
                "status_code": response.status_code,
                "response": response_text,
            }, indent=2),
        )
        return {"error": "Exception while sending file message"}


def upload_file_pdfa3(doctype, docname, print_format):
    pdf_a3_path = embed_file_in_pdf(docname, print_format, letterhead=None, language="en")

    if not pdf_a3_path:
        frappe.throw(_(ERROR_MESSAGE2))

    # nosemgrep: frappe-semgrep-rules.rules.security.frappe-security-file-traversal
    # Audited: pdf_a3_path comes from embed_file_in_pdf which constructs path from
    # internal site path. replace() maps public URL back to local filesystem path.
    with open(pdf_a3_path.replace(get_url(), frappe.local.site), "rb") as pdf_file:
        pdf_base64 = base64.b64encode(pdf_file.read()).decode()

    memory_url = f"data:application/pdf;base64,{pdf_base64}"

    cleared_xml = f"Cleared xml file {docname}.xml"
    reported_xml = f"Reported xml file {docname}.xml"

    xml_file = None
    attachments = frappe.get_all("File", filters={"attached_to_name": docname}, fields=["file_name"])

    for att in attachments:
        if att.file_name in [cleared_xml, reported_xml]:
            xml_file = os.path.join(frappe.local.site_path, "private", "files", att.file_name)
            break

    if not xml_file:
        frappe.throw(_("No XML file found for {0}").format(docname))

    invoice = frappe.get_doc("Sales Invoice", docname)
    if invoice.docstatus == 2:
        frappe.throw(_(ERROR_MESSAGE5))

    whatsapp_conf = frappe.get_doc(DOCNAME)

    try:
        url = whatsapp_conf.file_upload
        token = whatsapp_conf.raseyel_authorization_token

        if not memory_url:
            return {"error": "PDF not generated"}

        try:
            header, encoded = memory_url.split(",", 1)
            file_content = base64.b64decode(encoded)
        except Exception:
            return {"error": "PDF base64 decode failed"}

        file_name = f"{docname}.pdf"
        mime_type = Type_pdf
        headers = {"Authorization": token}
        files = {"file": (file_name, file_content, mime_type)}

        response = requests.post(url, headers=headers, files=files)

        try:
            return response.json()
        except Exception:
            return {"error": "Invalid JSON response", "raw": response.text}

    except Exception as e:
        frappe.log_error(title=file_upload_error, message=frappe.get_traceback())
        return {"error": str(e)}


def _rasayel_send_pdfa3(doctype: str, docname: str, print_format: str):
    """Shared logic for rasayel_whatsapp_file_message_pdfa3 — deduplicated."""
    upload_response = upload_file_pdfa3(doctype, docname, print_format)

    if not upload_response or "error" in upload_response:
        return upload_response

    attachment = upload_response.get("attachment", {})
    blob_id = attachment.get("id")

    if not blob_id:
        return {"error": "Failed to extract blob ID from upload response", "upload_response": upload_response}

    doc = frappe.get_doc(DOCNAME)
    url = doc.get("raseyel_file_api")
    channel_id = int(doc.get("channel_id"))
    file_template_id = int(doc.get("message_template_id"))
    token = doc.get("raseyel_authorization_token")

    sales_invoice = frappe.get_doc("Sales Invoice", docname)
    if sales_invoice.docstatus == 2:
        frappe.throw(_(ERROR_MESSAGE5))

    customer = sales_invoice.customer
    customer_doc = frappe.get_doc("Customer", customer)
    phone = customer_doc.get("custom_whatsapp_number_")
    if not phone:
        return {"status": "error", "message": "No WhatsApp number found for the customer"}

    phone_number = get_receiver_phone_number1(phone)

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
                        "parameters": [{"type": "DOCUMENT", "blobOrAttachmentId": blob_id}],
                    }
                ],
                "messageTemplateId": file_template_id,
            }
        },
    })

    headers = {"Authorization": token, "Content-Type": Type}
    response = requests.post(url, headers=headers, data=payload)
    response_text = response.text

    if response.status_code != 200:
        frappe.log_error(title="Rasayel API Error", message=response_text)
        return {"error": "WhatsApp API error", "status_code": response.status_code, "raw": response_text}

    try:
        response_dict = response.json()
    except Exception:
        frappe.log_error(title="Invalid JSON from Rasayel", message=response_text)
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
            message=json.dumps(response_dict, indent=2),
        )
        return {"error": "Failed to get conversation ID", "raw": response_dict}

    log_whatsapp_success(conversation_id, phone_number)

    try:
        close_conversation(conversation_id)
    except Exception:
        frappe.log_error(frappe.get_traceback(), ERROR_MESSAGE1)

    return {"status": "success", "conversation_id": conversation_id, "message": ERROR_MESSAGE3}


def parse_notification_message(message):
    """Parse key="value" pairs from Notification Message field"""
    config = {}
    if not message:
        return config
    for line in message.split("\n"):
        match = re.match(r'(\w+)\s*=\s*"(.*)"', line.strip())
        if match:
            key, value = match.groups()
            config[key] = value
    return config


# FIX: Deduplicated — was defined twice identically. Now delegates to _rasayel_send_pdfa3.
# FIX: Added type hints to all arguments
@frappe.whitelist()
def rasayel_whatsapp_file_message_pdfa3(doctype: str, docname: str, print_format: str):
    try:
        return _rasayel_send_pdfa3(doctype, docname, print_format)
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Rasayel File Message Error")
        return {"error": str(e)}


# FIX: Added type hints to all arguments
@frappe.whitelist()
def send_bevatel_file_template_message_pdf(doctype: str, docname: str, print_format: str):
    try:
        doc = frappe.get_doc(doctype, docname)
        frappe.log_error(title="log2", message="entered")
        pdf_url = bevatel_create_pdf(doctype, docname, print_format)
        return _send_bevatel_whatsapp(doc, doctype, pdf_url)

    except Exception:
        frappe.log_error(title=ERROR_MESSAGE4, message=frappe.get_traceback())
        return {"status": "error", "message": ERROR_MESSAGE6}


# FIX: Added type hints to all arguments
@frappe.whitelist()
def send_bevatel_file_template_message_pdf_a3(doctype: str, docname: str, print_format: str):
    try:
        doc = frappe.get_doc(doctype, docname)
        pdf_url = embed_public_file_in_pdf(docname, print_format, letterhead=None, language="en")
        return _send_bevatel_whatsapp(doc, doctype, pdf_url)
    except Exception:
        frappe.log_error(title=ERROR_MESSAGE4, message=frappe.get_traceback())
        return {"status": "error", "message": ERROR_MESSAGE6}


@frappe.whitelist()
def get_whatsapp_pdf(message: str, docname: str, doctype: str, print_format: str):
    try:
        provider = frappe.get_doc(DOCNAME).whatsapp_provider

        if provider == "Rasayel":
            return rasayel_whatsapp_file_message_pdf(doctype, docname, print_format)
        elif provider == "Bevatel":
            frappe.log_error(title="log1", message="entered")
            return send_bevatel_file_template_message_pdf(doctype, docname, print_format)
        else:
            return send_whatsapp_with_pdf1(message, docname, doctype, print_format)

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Rasayel File Message Error")
        return {"error": str(e)}


# FIX: Added type hints to all arguments
@frappe.whitelist()
def get_whatsapp_pdf_a3(message: str, docname: str, doctype: str, print_format: str, letterhead: str | None):
    try:
        provider = frappe.get_doc(DOCNAME).whatsapp_provider

        if provider == "Rasayel":
            return rasayel_whatsapp_file_message_pdfa3(doctype, docname, print_format)
        elif provider == "Bevatel":
            return send_bevatel_file_template_message_pdf_a3(doctype, docname, print_format)
        else:
            return send_whatsapp_with_pdf_a3(message, docname, doctype, print_format, letterhead)

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Rasayel File Message Error")
        return {"error": str(e)}


# FIX: Added type hints to all arguments
@frappe.whitelist()
def send_whatsapp_text(message: str, phone: str):
    try:
        doc = frappe.get_doc(DOCNAME)
        phone = normalize_phone(phone)

        if not phone:
            return {"success": False, "message": "Phone number is required"}

        if not message:
            return {"success": False, "message": "Message is required"}

        url = doc.message_url

        payload = {
            "instanceid": doc.instance_id,
            "token": doc.token,
            "phone": phone,
            "body": message,
        }

        headers = {"Content-Type": ERROR_MESSAGE7}

        response = requests.post(url, data=payload, headers=headers, timeout=30)

        if response.status_code == 200:
            response_dict = json.loads(response.text)

            if response_dict.get("sent"):
                log_whatsapp_success(message, phone)
                return {"status": "success"}

        return {"status": "error"}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "WhatsApp Send Error")
        return {"success": False, "error": str(e)}