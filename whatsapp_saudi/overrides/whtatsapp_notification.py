import frappe
from frappe.email.doctype.notification.notification import Notification
import json
from frappe.core.doctype.role.role import get_info_based_on_role, get_user_info
import requests
from werkzeug.wrappers import Response
import io
import base64
from frappe.utils import now
import os

ERROR_MESSAGE = "success: false, reason: API access prohibited or incorrect instanceid or token"
# to send whatsapp message and document using ultramsg
class ERPGulfNotification(Notification):
    def create_pdf(self,doc):
        file = frappe.get_print(doc.doctype, doc.name, self.print_format, as_pdf=True)
        pdf_bytes = io.BytesIO(file)
        pdf_base64 = base64.b64encode(pdf_bytes.getvalue()).decode()
        in_memory_url = f"data:application/pdf;base64,{pdf_base64}"
        return in_memory_url


 # fetch pdf from the create_pdf function and send to whatsapp
    @frappe.whitelist()
    def send_whatsapp_with_pdf(self,doc,context):
        memory_url=self.create_pdf(doc)
        recipients = self.get_receiver_list(doc,context)
        for receipt in recipients:
            number = receipt
            phoneNumber = self.get_receiver_phone_number(number)
            url = frappe.get_doc('Whatsapp Saudi').get('file_url')
            instance = frappe.get_doc('Whatsapp Saudi').get('instance_id')
            msg1 = frappe.render_template(self.message, context)
            token = frappe.get_doc('Whatsapp Saudi').get('token')
        payload = {
          'instanceid':instance,
          'token': token,
          'body':memory_url,
          'filename':doc.name,
          'caption': msg1,
          'phone':phoneNumber
        }

        files = []
        headers = {
          'content-type': 'application/x-www-form-urlencoded',
          'Cookie': 'PHPSESSID=e9603d8bdbea9f5bf851e36831b8ba16'
        }

        try:
            response = requests.post(url, headers=headers, data=payload, files=files, timeout=30)
            response_json=response.text
            if response.status_code == 200:
                response_dict = json.loads(response_json)
                if response_dict.get("sent") and response_dict.get("id"):
                    current_time = now()
                    # If the message is sent successfully a success message response will be recorded in the WhatsApp Saudi success log.
                    frappe.get_doc({
                        "doctype": "whatsapp saudi success log",
                        "title": "Message successfully sent ",
                        "message": msg1,
                        "to_number": phoneNumber,
                        "time": current_time
                    }).insert()

                else:
                    frappe.log_error(ERROR_MESSAGE, frappe.get_traceback())
            else:
                frappe.log_error("status code is not 200", frappe.get_traceback())
            return response
        except requests.exceptions.RequestException:
            frappe.log_error(title='Failed to send notification', message=frappe.get_traceback())



  #send message without pdf
    def send_whatsapp_without_pdf(self,doc,context):
        url =frappe.get_doc('Whatsapp Saudi').get('message_url')
        instance =frappe.get_doc('Whatsapp Saudi').get('instance_id')
        msg1 = frappe.render_template(self.message, context)
        token =frappe.get_doc('Whatsapp Saudi').get('token')
        recipients = self.get_receiver_list(doc,context)
        for receipt in recipients:
            number = receipt
            frappe.log_error(number)
            phoneNumber =self.get_receiver_phone_number(number)
    
        querystring = {
            "instanceid":instance,
            "token": token,
            "phone":phoneNumber,
            "body":msg1
          }
        try:
            frappe.log_error("WhatsApp API Payload", f"Query: {frappe.as_json(querystring)}")
            response = requests.get(url, params=querystring)
            response_json=response.text
            if response.status_code == 200:
                response_dict = json.loads(response_json)
                if response_dict.get("sent") and response_dict.get("id"):
                    current_time = now()
                    # If the message is sent successfully a success message response will be recorded in the WhatsApp Saudi success log."
                    frappe.get_doc({
                        "doctype": "whatsapp saudi success log",
                        "title": "Message successfully sent",
                        "message": msg1,
                        "to_number": number,
                        "time": current_time
                    }).insert()

                else:
                    frappe.log_error(ERROR_MESSAGE, frappe.get_traceback())
            else:
                frappe.log_error("status code  is not 200", frappe.get_traceback())
            return response
        except requests.exceptions.RequestException:
            frappe.log_error(title='Failed to send notification', message=frappe.get_traceback())


    def send(self, doc):
        context = {"doc": doc, "alert": self, "comments": None}
        if doc.get("_comments"):
            context["comments"] = json.loads(doc.get("_comments"))

        if self.is_standard:
            self.load_standard_properties(context)

        # Handle custom WhatsApp channel only
        if self.channel == "Whatsapp Saudi":
            try:
                if self.attach_print and self.print_format:
                    frappe.enqueue(
                        self.send_whatsapp_with_pdf,
                        queue="short",
                        timeout=200,
                        doc=doc,
                        context=context
                    )
                else:
                    frappe.enqueue(
                        self.send_whatsapp_without_pdf,
                        queue="short",
                        timeout=200,
                        doc=doc,
                        context=context
                    )
            except Exception:
                frappe.log_error(title='Failed to send WhatsApp notification', message=frappe.get_traceback())

        else:
            # Call original Notification.send() for Email, Slack, SMS, System Notification
            try:
                super(ERPGulfNotification, self).send(doc)
            except Exception:
                frappe.log_error(title='Failed to send standard notification', message=frappe.get_traceback())
                       
    def get_receiver_list(self, doc, context):
        """return receiver list based on the doc field and role specified"""
        receiver_list = []
        for recipient in self.recipients:
            if recipient.condition:
                if not frappe.safe_eval(recipient.condition, None, context):
                    continue

            if recipient.receiver_by_document_field == "owner":
                receiver_list += get_user_info([dict(user_name=doc.get("owner"))], "mobile_no")

            elif recipient.receiver_by_document_field:
                receiver_list.append(doc.get(recipient.receiver_by_document_field))

            if recipient.receiver_by_role:
                receiver_list += get_info_based_on_role(recipient.receiver_by_role, "mobile_no")
        return receiver_list



    def get_receiver_phone_number(self,number):
        phone_number = number.replace("+", "").replace("-", "").replace(" ", "")
        if phone_number.startswith("00"):
            phone_number = phone_number[2:]
        elif phone_number.startswith("0"):
            if len(phone_number) == 10:
                phone_number = "966" + phone_number[1:]
            elif len(phone_number) < 10:
                phone_number = "966" + phone_number
        if phone_number.startswith("0"):
            phone_number = phone_number[1:]

        return phone_number


@frappe.whitelist(allow_guest=True)
def create_pdf1(doctype, docname, print_format):
    try:
        file = frappe.get_print(doctype, docname, print_format)
        if isinstance(file, str) and "Uncaught Server Exception" in file:

            return Response(
            json.dumps(
                {"error":"Uncaught Server Exception detected."}
            ),
            status=500,
            mimetype="application/json",
        )
        file = frappe.get_print(doctype, docname, print_format,as_pdf=True)
        pdf_bytes = io.BytesIO(file)
        pdf_base64 = base64.b64encode(pdf_bytes.getvalue()).decode()
        in_memory_url = f"data:application/pdf;base64,{pdf_base64}"
        return in_memory_url

    except frappe.PrintFormatError:
        frappe.local.response["http_status_code"] = 500
        return {"error": "An issue occurred while generating the PDF."}

    except (frappe.DoesNotExistError, frappe.PermissionError, frappe.ValidationError) as e:
        frappe.local.response["http_status_code"] = 500
        frappe.log_error(f"Error in create_pdf1: {str(e)}", "Custom Function Error")
        return {"error": "Something went wrong. Please try again later."}



@frappe.whitelist(allow_guest=True)
def send_whatsapp_with_pdf1(message, docname, doctype, print_format):
    try:
        memory_url = create_pdf1(doctype, docname, print_format)
    except (frappe.DoesNotExistError, frappe.PermissionError, frappe.ValidationError, frappe.PrintFormatError) as e:
        frappe.log_error(title="Error creating PDF", message=f"Error generating PDF for {docname} with format {print_format}. Error: {str(e)}")
        return {"status": "error", "message": f"Error generating PDF for {docname} with format {print_format}. Please check the print format and try again."}

    xml_file = None
    cleared_xml_file_name = "Cleared xml file " + docname + ".xml"

    reported_xml_file_name = "Reported xml file " + docname + ".xml"
    attachments = frappe.get_all(
        "File", filters={"attached_to_name": docname}, fields=["file_name"]
    )

    for attachment in attachments:
        file_name = attachment.get("file_name", None)
        file=os.path.join(frappe.local.site, "private", "files", file_name)
        if file_name in [cleared_xml_file_name, reported_xml_file_name]:
            xml_file = file



    if not xml_file:
        frappe.throw(f"No XML file found for the invoice {docname}. Please ensure the XML file is attached.")
    whatsapp_config = frappe.get_doc('Whatsapp Saudi')
    sales_invoice = frappe.get_doc("Sales Invoice", docname)
    if sales_invoice.get("docstatus") == 2:
        frappe.throw("Document is cancelled")
        return {"status": "error", "message": "Document is cancelled."}

    customer = sales_invoice.get("customer")
    customer_doc = frappe.get_doc("Customer", customer)

    url = whatsapp_config.get('file_url')
    instance = whatsapp_config.get('instance_id')
    token = whatsapp_config.get('token')
    phone = customer_doc.get("custom_whatsapp_number_")

    if not phone:
        return {"status": "error", "message": "No WhatsApp number found for the customer"}

    phonenumber = get_receiver_phone_number1(phone)

    payload = {
        'instanceid': instance,
        'token': token,
        'body': memory_url,
        'filename': docname,
        'caption': message,
        'phone': phonenumber
    }

    files = []
    headers = {
        'content-type': 'application/x-www-form-urlencoded',
        'Cookie': 'PHPSESSID=e9603d8bdbea9f5bf851e36831b8ba16'  # Replace with the actual cookie value
    }

    try:
        response = requests.post(url, headers=headers, data=payload, files=files, timeout=30)
        response_json = response.text
        if response.status_code == 200:
            response_dict = json.loads(response_json)
            if response_dict.get("sent") and response_dict.get("id"):
                current_time = now()
                frappe.get_doc({
                    "doctype": "whatsapp saudi success log",
                    "title": "Message successfully sent",
                    "message": message,
                    "to_number": phonenumber,
                    "time": current_time
                }).insert(ignore_permissions=True)
                response_dict["success"] = True
                response_dict["message"] = "Message successfully sent"
            else:
                frappe.log_error(ERROR_MESSAGE, frappe.get_traceback())
                return {"status": "error", "message": "Failed to send message, check API access."}
        else:
            frappe.log_error("Status code is not 200", frappe.get_traceback())
            return {"status": "error", "message": "Failed to send message, non-200 response."}
    except requests.exceptions.RequestException:
        frappe.log_error(title='Failed to send notification', message=frappe.get_traceback())
        return {"status": "error", "message": "Error in sending WhatsApp message."}

    return {"status": "success", "message": "Message sent successfully."}



def get_receiver_phone_number1(number):
    phone_number = number.replace("+", "").replace("-", "").replace(" ", "")
    if phone_number.startswith("00"):
        phone_number = phone_number[2:]
    elif phone_number.startswith("0"):
        if len(phone_number) == 10:
            phone_number = "966" + phone_number[1:]
        elif len(phone_number) < 10:
            phone_number = "966" + phone_number
    if phone_number.startswith("0"):
        phone_number = phone_number[1:]

    return phone_number