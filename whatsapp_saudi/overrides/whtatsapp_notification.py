import frappe
from frappe import _
from frappe.email.doctype.notification.notification import Notification, get_context, json
from frappe.core.doctype.role.role import get_info_based_on_role, get_user_info
import requests
import json
import io
import base64
from frappe.utils import now
import time
from frappe import enqueue
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
          phoneNumber =self.get_receiver_phone_number(number)
        url =frappe.get_doc('Whatsapp Saudi').get('file_url')
        instance =frappe.get_doc('Whatsapp Saudi').get('instance_id')
        msg1 = frappe.render_template(self.message, context)
        token =frappe.get_doc('Whatsapp Saudi').get('token')


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
            response = requests.post(url, headers=headers, data=payload, files=files)
            response_json=response.text
            if response.status_code == 200:
                response_dict = json.loads(response_json)
                if response_dict.get("sent") and response_dict.get("id"):
                    current_time =now()# for geting current time
                     # If the message is sent successfully a success message response will be recorded in the WhatsApp Saudi success log.
                    frappe.get_doc({
                          "doctype": "whatsapp saudi success log",
                          "title": "Message successfully sent ",
                          "message": msg1,
                          "to_number":phoneNumber,
                          "time": current_time
                          }).insert()

                else:
                  frappe.log_error("success: false, reason: API access prohibited or incorrect instanceid or token", frappe.get_traceback())
            else:
              frappe.log_error("status code is not 200", frappe.get_traceback())
            return response
        except Exception as e:
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
            phoneNumber =self.get_receiver_phone_number(number)

        querystring = {
            "instanceid":instance,
            "token": token,
            "phone":phoneNumber,
            "body":msg1
          }
        try:
            response = requests.get(url, params=querystring)
            response_json=response.text
            if response.status_code == 200:
                response_dict = json.loads(response_json)
                if response_dict.get("sent") and response_dict.get("id"):
                  current_time =now()
                # If the message is sent successfully a success message response will be recorded in the WhatsApp Saudi success log."
                  frappe.get_doc({
                        "doctype": "whatsapp saudi success log",
                        "title": "Message successfully sent",
                        "message":msg1,
                        "to_number":number,
                        "time":current_time
                    }).insert()

                else:
                  frappe.log_error("success: false, reason: API access prohibited or incorrect instanceid or token", frappe.get_traceback())
            else:
                frappe.log_error("status code  is not 200", frappe.get_traceback())
            return response
        except Exception as e:
          frappe.log_error(title='Failed to send notification', message=frappe.get_traceback())


  # call the  send whatsapp with pdf function and send whatsapp without pdf function and it work with the help of condition
    def send(self, doc):
        context = {"doc":doc, "alert": self, "comments": None}
        if doc.get("_comments"):
          context["comments"] = json.loads(doc.get("_comments"))
        if self.is_standard:
          self.load_standard_properties(context)
        try:
            if self.channel == "Whatsapp Saudi":

        # if attach_print and print format both are enable then it send pdf with message
              if self.attach_print and  self.print_format:

                  frappe.enqueue(
                  self.send_whatsapp_with_pdf,
                  queue="short",
                  timeout=200,
                  doc=doc,
                  context=context
                  )

               # otherwise send only message
              else:
                  frappe.enqueue(
                  self.send_whatsapp_without_pdf,
                  queue="short",
          timeout=200,
          doc=doc,
          context=context
         )
        except:
            frappe.log_error(title='Failed to send notification', message=frappe.get_traceback())
            super(ERPGulfNotification, self).send(doc)


    def get_receiver_list(self, doc, context):
      """return receiver list based on the doc field and role specified"""
      receiver_list = []
      for recipient in self.recipients:
        if recipient.condition:
          if not frappe.safe_eval(recipient.condition, None, context):
            continue
			# For sending messages to the owner's mobile phone number
        if recipient.receiver_by_document_field == "owner":
            receiver_list += get_user_info([dict(user_name=doc.get("owner"))], "mobile_no")
			# For sending messages to the number specified in the receiver field
        elif recipient.receiver_by_document_field:
            receiver_list.append(doc.get(recipient.receiver_by_document_field))
			# For sending messages to specified role
        if recipient.receiver_by_role:
              receiver_list += get_info_based_on_role(recipient.receiver_by_role, "mobile_no")
        return receiver_list



    def get_receiver_phone_number(self,number):
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





import requests
import json
import io
import base64
# from your_module_path import create_pdf1, get_receiver_phone_number  # replace 'your_module_path' with the actual path
import time
@frappe.whitelist(allow_guest=True)
def create_pdf1(doctype,docname,print_format):
        file = frappe.get_print(doctype, docname,print_format, as_pdf=True)
        pdf_bytes = io.BytesIO(file)
        pdf_base64 = base64.b64encode(pdf_bytes.getvalue()).decode()
        in_memory_url = f"data:application/pdf;base64,{pdf_base64}"
        return in_memory_url
@frappe.whitelist(allow_guest=True)


def send_whatsapp_with_pdf1(message, docname, doctype, print_format):
    memory_url = create_pdf1(doctype, docname, print_format)

    # Get configuration values from 'Whatsapp Saudi' doctype
    # Get configuration values from 'Whatsapp Saudi' doctype
    whatsapp_config = frappe.get_doc('Whatsapp Saudi')
    sales_invoice=frappe.get_doc("Sales Invoice",docname)
    customer=sales_invoice.get("customer")
    customer_doc=frappe.get_doc("Customer", customer)

    url = whatsapp_config.get('file_url')
    instance = whatsapp_config.get('instance_id')
    token = whatsapp_config.get('token')
    phone=customer_doc.get("custom_whatsapp_number_")
    if not phone:
        frappe.throw("No WhatsApp number found for the customer")
    # Get receiver's phone number
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
        response = requests.post(url, headers=headers, data=payload, files=files)

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
                frappe.log_error("success: false, reason: API access prohibited or incorrect instanceid or token",
                                 frappe.get_traceback())
        else:
            frappe.log_error("Status code is not 200", frappe.get_traceback())
        # return response.text

    except Exception as e:
        frappe.log_error(title='Failed to send notification', message=frappe.get_traceback())
    return response_dict
def get_receiver_phone_number1(phone_number):
        phoneNumber = phone_number.replace("+","").replace("-","").replace(" ","")
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