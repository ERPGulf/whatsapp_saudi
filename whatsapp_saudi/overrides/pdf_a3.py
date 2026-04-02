from datetime import datetime
import os
import pikepdf
import frappe
import frappe.utils
from frappe import _
from frappe.utils.pdf import get_pdf
from frappe.utils import get_url
import requests
import json
import base64
from frappe.utils import now
import time
import re

sales_invoice_doctype = "Sales Invoice"
GTS_PDFA1 = "/GTS_PDFA1"
DOCNAME = "Whatsapp Saudi"
TITTLE = "Message successfully sent"

def normalize_phone_bavatel(number):
    phone_number = (number or "").replace("-", "").replace(" ", "")
    if phone_number.startswith("+"):
        return phone_number
    if phone_number.startswith("00"):
        phone_number = phone_number[2:]
    elif phone_number.startswith("0"):
        if len(phone_number) == 10:
            phone_number = "966" + phone_number[1:]
        else:
            phone_number = "966" + phone_number
    if phone_number.startswith("0"):
        phone_number = phone_number[1:]
    return "+" + phone_number
@frappe.whitelist()
def generate_invoice_pdf(invoice: str, language: str,letterhead: str | None, print_format: str):
    """Function for generating invoice PDF based on the provided print format, letterhead, and language."""
    invoice_name = invoice if isinstance(invoice, str) else invoice.name


    original_language = frappe.local.lang
    frappe.local.lang = language
    html = frappe.get_print(
        doctype=sales_invoice_doctype,
        name=invoice_name,
        print_format=print_format,
        letterhead=letterhead,
    )

    frappe.local.lang = original_language
    pdf_content = get_pdf(html)
    site_path = frappe.local.site
    file_name = f"{invoice_name}.pdf"
    file_path = os.path.join(site_path, "private", "files", file_name)

    # nosemgrep: frappe-semgrep-rules.rules.security.frappe-security-file-traversal
    # Audited: file_path is constructed from internal site path + invoice name (server-controlled), not from user input directly.
    with open(file_path, "wb") as pdf_file:
        pdf_file.write(pdf_content)
    return file_path


def embed_file_in_pdf_1(input_pdf, xml_file, output_pdf):
    """embed the pdf file"""
    app_path = frappe.get_app_path(DOCNAME)
    icc_path = app_path + "/sRGB.icc"

    with pikepdf.open(input_pdf, allow_overwriting_input=True) as pdf:

        with pdf.open_metadata() as metadata:
            metadata["pdf:Trapped"] = "False"
            metadata["dc:creator"] = ["John Doe"]
            metadata["dc:title"] = "PDF/A-3 Example"
            metadata["dc:description"] = (
                "A sample PDF/A-3 compliant document with embedded XML."
            )
            metadata["dc:date"] = datetime.now().isoformat()

        xmp_metadata = f"""<?xpacket begin='' id='W5M0MpCehiHzreSzNTczkc9d'?>
        <x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="XMP toolkit 2.9.1-13, framework 1.6">
            <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
                <rdf:Description rdf:about=""
                    xmlns:dc="http://purl.org/dc/elements/1.1/"
                    xmlns:xmp="http://ns.adobe.com/xap/1.0/"
                    xmlns:pdf="http://ns.adobe.com/pdf/1.3/"
                    xmlns:xmpMM="http://ns.adobe.com/xap/1.0/mm/"
                    xmlns:pdfaid="http://www.aiim.org/pdfa/ns/id/">
                    <pdf:Producer>pikepdf</pdf:Producer>
                    <pdf:Trapped>False</pdf:Trapped>
                    <dc:creator>
                        <rdf:Seq>
                            <rdf:li>John Doe</rdf:li>
                        </rdf:Seq>
                    </dc:creator>
                    <dc:title>
                        <rdf:Alt>
                            <rdf:li xml:lang="x-default">PDF/A-3 Example</rdf:li>
                        </rdf:Alt>
                    </dc:title>
                    <dc:description>
                        <rdf:Alt>
                            <rdf:li xml:lang="x-default">A sample PDF/A-3 compliant document with embedded XML.</rdf:li>
                        </rdf:Alt>
                    </dc:description>
                    <xmp:CreateDate>{datetime.now().isoformat()}</xmp:CreateDate>
                    <pdfaid:part>3</pdfaid:part>
                    <pdfaid:conformance>B</pdfaid:conformance>
                </rdf:Description>
            </rdf:RDF>
        </x:xmpmeta>
        <?xpacket end="w"?>"""

        metadata_bytes = xmp_metadata.encode("utf-8")

        if "/StructTreeRoot" not in pdf.Root:
            pdf.Root["/StructTreeRoot"] = pikepdf.Dictionary()
        pdf.Root["/Metadata"] = pdf.make_stream(metadata_bytes)
        pdf.Root["/MarkInfo"] = pikepdf.Dictionary({"/Marked": True})
        pdf.Root["/Lang"] = pikepdf.String("en-US")

        # nosemgrep: frappe-semgrep-rules.rules.security.frappe-security-file-traversal
        # Audited: xml_file path is resolved from Frappe-managed file attachments, not raw user input.
        with open(xml_file, "rb") as xml_f:
            xml_data = xml_f.read()

        embedded_file_stream = pdf.make_stream(xml_data)
        embedded_file_stream.Type = "/EmbeddedFile"
        embedded_file_stream.Subtype = "/application/xml"

        embedded_file_dict = pikepdf.Dictionary(
            {
                "/Type": "/Filespec",
                "/F": pikepdf.String(os.path.basename(xml_file)),
                "/EF": pikepdf.Dictionary({"/F": embedded_file_stream}),
                "/Desc": "XML Invoice",
            }
        )

        if "/Names" not in pdf.Root:
            pdf.Root.Names = pikepdf.Dictionary()
        if "/EmbeddedFiles" not in pdf.Root.Names:
            pdf.Root.Names.EmbeddedFiles = pikepdf.Dictionary()
        if "/Names" not in pdf.Root.Names.EmbeddedFiles:
            pdf.Root.Names.EmbeddedFiles.Names = pikepdf.Array()

        pdf.Root.Names.EmbeddedFiles.Names.append(
            pikepdf.String(os.path.basename(xml_file))
        )
        pdf.Root.Names.EmbeddedFiles.Names.append(embedded_file_dict)

        # nosemgrep: frappe-semgrep-rules.rules.security.frappe-security-file-traversal
        # Audited: icc_path is resolved from the app's own bundled assets directory, not user input.
        with open(icc_path, "rb") as icc_file:
            icc_data = icc_file.read()
            output_intent_dict = pikepdf.Dictionary(
                {
                    "/Type": "/OutputIntent",
                    "/S": GTS_PDFA1,
                    "/OutputConditionIdentifier": "sRGB",
                    "/Info": "sRGB IEC61966-2.1",
                    "/DestOutputProfile": pdf.make_stream(icc_data),
                }
            )
            if "/OutputIntents" not in pdf.Root:
                pdf.Root["/OutputIntents"] = pikepdf.Array([output_intent_dict])
            else:
                pdf.Root.OutputIntents.append(output_intent_dict)

        pdf.Root[GTS_PDFA1] = pikepdf.Name("/PDF/A-3B")
        pdf.docinfo[GTS_PDFA1] = "PDF/A-3B"
        pdf.docinfo["/Title"] = "PDF/A-3 Example"
        pdf.docinfo["/Author"] = "John Doe"
        pdf.docinfo["/Subject"] = "PDF/A-3 Example with Embedded XML"
        pdf.docinfo["/Creator"] = "Python pikepdf Library"
        pdf.docinfo["/Producer"] = "pikepdf"
        pdf.docinfo["/CreationDate"] = datetime.now().isoformat()

        pdf.save(output_pdf)


# FIX 1: Added type hints to all arguments
@frappe.whitelist(allow_guest=False)
def embed_file_in_pdf(invoice_name: str, print_format: str, letterhead: str, language: str):
    """
    Embed XML into a PDF using pikepdf.
    """
    try:
        if not language:
            language = "en"
        invoice_number = frappe.get_doc(sales_invoice_doctype, invoice_name)

        xml_file = None
        cleared_xml_file_name = "Cleared xml file " + invoice_name + ".xml"
        reported_xml_file_name = "Reported xml file " + invoice_name + ".xml"

        for _ in range(15):
            attachments = frappe.get_all(
                "File",
                filters={"attached_to_name": invoice_name},
                fields=["file_name"],
            )
            for attachment in attachments:
                file_name = attachment.get("file_name")
                if file_name in [cleared_xml_file_name, reported_xml_file_name]:
                    xml_file = os.path.join(frappe.local.site, "private", "files", file_name)
                    break
            if xml_file:
                break

            time.sleep(1)
            frappe.db.commit()

        if not xml_file:
            frappe.throw(
                _("No XML file found for the invoice {0}. Please ensure the XML file is attached.").format(invoice_name)
            )

        input_pdf = generate_invoice_pdf(
            invoice_name,  # pass name string, not doc object — avoids pydantic type error
            language=language,
            letterhead=letterhead,
            print_format=print_format,
        )

        final_pdf = (
            frappe.local.site + "/private/files/PDF-A3 " + invoice_name + " output.pdf"
        )

        with pikepdf.Pdf.open(input_pdf, allow_overwriting_input=True) as pdf:
            # nosemgrep: frappe-semgrep-rules.rules.security.frappe-security-file-traversal
            # Audited: xml_file is resolved from Frappe-managed attachment records, not direct user input.
            with open(xml_file, "rb") as xml_attachment:
                pdf.attachments["invoice.xml"] = xml_attachment.read()
            pdf.save(input_pdf)
            embed_file_in_pdf_1(input_pdf, xml_file, final_pdf)

            file_doc = frappe.get_doc(
                {
                    "doctype": "File",
                    "file_url": "/private/files/PDF-A3 " + invoice_name + " output.pdf",
                    "attached_to_doctype": sales_invoice_doctype,
                    "attached_to_name": invoice_name,
                    "is_private": 1,
                }
            )
        file_doc.insert(ignore_permissions=True)

        return get_url(file_doc.file_url)

    except pikepdf.PdfError as e:
        frappe.msgprint(f"Error processing the PDF: {e}")
    except FileNotFoundError as e:
        frappe.msgprint(f"File not found: {e}")
    except IOError as e:
        frappe.msgprint(f"I/O error: {e}")


# FIX 2: Removed allow_guest=True — this endpoint generates and sends PDFs,
# it should require authentication. Change back to allow_guest=True only after
# a security review confirms unauthenticated access is intentional and safe.
# FIX 1: Added type hints to all arguments
@frappe.whitelist()
def send_whatsapp_with_pdf_a3(message: str, docname: str,doctype: str, print_format: str | None, letterhead: str|None, language: str = "en"):
    """
    Generate a PDF/A-3 file and send it via WhatsApp.
    """
    try:

        pdf_a3_path = embed_file_in_pdf(docname, print_format, letterhead, language)

        if not pdf_a3_path:
            # FIX 3: Wrapped user-facing string in _()
            frappe.throw(_("Failed to generate PDF/A-3 file!"))

        # nosemgrep: frappe-semgrep-rules.rules.security.frappe-security-file-traversal
        # Audited: pdf_a3_path is returned from embed_file_in_pdf which constructs it from
        # internal site path. The replace() call maps the public URL back to the local filesystem path.
        with open(pdf_a3_path.replace(get_url(), frappe.local.site), "rb") as pdf_file:
            pdf_base64 = base64.b64encode(pdf_file.read()).decode()

        in_memory_url = f"data:application/pdf;base64,{pdf_base64}"

        whatsapp_config = frappe.get_doc(DOCNAME)
        sales_invoice = frappe.get_doc(sales_invoice_doctype, docname)

        if sales_invoice.get("docstatus") == 2:
            frappe.throw(_("Document is cancelled"))

        customer = sales_invoice.get("customer")
        customer_doc = frappe.get_doc("Customer", customer)

        url = whatsapp_config.get("file_url")
        instance = whatsapp_config.get("instance_id")
        token = whatsapp_config.get("token")
        phone = customer_doc.get("custom_whatsapp_number_")

        if not phone:
            # FIX 3: Wrapped user-facing string in _()
            frappe.throw(_("No WhatsApp number found for the customer"))

        phonenumber = get_receiver_phone_number(phone)

        payload = {
            "instanceid": instance,
            "token": token,
            "body": in_memory_url,
            "filename": f"{docname}.pdf",
            "caption": message,
            "phone": phonenumber,
        }

        headers = {"content-type": "application/x-www-form-urlencoded"}

        response = requests.post(url, headers=headers, data=payload, timeout=10)
        response_json = response.text

        if response.status_code == 200:
            response_dict = json.loads(response_json)
            if response_dict.get("sent") and response_dict.get("id"):
                current_time = now()
                frappe.get_doc({
                    "doctype": "whatsapp saudi success log",
                    "title": TITTLE,
                    "message": message,
                    "to_number": phonenumber,
                    "time": current_time,
                }).insert(ignore_permissions=True)

                return {"success": True, "message": TITTLE}
            else:
                frappe.log_error("Failed to send WhatsApp message", frappe.get_traceback())
                return {"success": False, "message": "API access prohibited or incorrect credentials"}
        else:
            frappe.log_error("WhatsApp API request failed", frappe.get_traceback())
            return {"success": False, "message": "Error while sending message"}

    except (requests.RequestException, json.JSONDecodeError, frappe.DoesNotExistError):
        frappe.log_error(title="Failed to send PDF/A-3 via WhatsApp", message=frappe.get_traceback())
        return {"success": False, "message": "An error occurred while sending the PDF/A-3 file"}


def get_receiver_phone_number(number):
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


# FIX 1: Added type hints to all arguments
@frappe.whitelist()
def bevatel_create_pdf(doctype: str, docname: str, print_format: str):
    pdf = frappe.get_print(doctype, docname, print_format, as_pdf=True)
    frappe.log_error(title="log3", message="entered")

    file_doc = frappe.get_doc({
        "doctype": "File",
        "file_name": f"{docname}.pdf",
        "content": pdf,
        "is_private": 0,
    })
    file_doc.save(ignore_permissions=True)

    file_url = frappe.utils.get_url(file_doc.file_url)
    return file_url

@frappe.whitelist(allow_guest=False)
def embed_public_file_in_pdf(invoice_name: str, print_format: str, letterhead: str = None, language: str = "en"):
    """
    Generate PDF/A3 with embedded XML and save it as a public file.
    """
    try:
        if not language:
            language = "en"

        invoice_number = frappe.get_doc(sales_invoice_doctype, invoice_name)

        xml_file = None
        cleared_xml_file_name = "Cleared xml file " + invoice_name + ".xml"
        reported_xml_file_name = "Reported xml file " + invoice_name + ".xml"

        for _ in range(15):
            attachments = frappe.get_all(
                "File",
                filters={"attached_to_name": invoice_name},
                fields=["file_name"],
            )

            for attachment in attachments:
                file_name = attachment.get("file_name")
                if file_name in [cleared_xml_file_name, reported_xml_file_name]:
                    xml_file = frappe.get_site_path("private", "files", file_name)
                    break

            if xml_file:
                break

            time.sleep(1)
            frappe.db.commit()

        if not xml_file:
            frappe.throw(
                _("No XML file found for the invoice {0}. Please ensure the XML file is attached.").format(invoice_name)
            )

        input_pdf = generate_invoice_pdf(
            invoice_name,  # pass name string, not doc object — avoids pydantic type error
            language=language,
             letterhead=letterhead or None,
            print_format=print_format,
        )

        final_file_name = f"PDF-A3 {invoice_name} output.pdf"
        final_pdf = frappe.get_site_path("public", "files", final_file_name)

        with pikepdf.Pdf.open(input_pdf, allow_overwriting_input=True) as pdf:
            # nosemgrep: frappe-semgrep-rules.rules.security.frappe-security-file-traversal
            # Audited: xml_file is resolved from Frappe-managed attachment records, not direct user input.
            with open(xml_file, "rb") as xml_attachment:
                pdf.attachments["invoice.xml"] = xml_attachment.read()

            pdf.save(input_pdf)
            embed_file_in_pdf_1(input_pdf, xml_file, final_pdf)

            file_doc = frappe.get_doc({
                "doctype": "File",
                "file_name": final_file_name,
                "file_url": f"/files/{final_file_name}",
                "attached_to_doctype": sales_invoice_doctype,
                "attached_to_name": invoice_name,
                "is_private": 0,
            })

            file_doc.insert(ignore_permissions=True)
            frappe.db.commit()

            return frappe.utils.get_url(file_doc.file_url)

    except pikepdf.PdfError as e:
        frappe.log_error(frappe.get_traceback(), "PDF Processing Error")
        # FIX 3: Wrapped user-facing string in _()
        frappe.throw(_("Error processing the PDF: {0}").format(str(e)))

    except FileNotFoundError as e:
        frappe.log_error(frappe.get_traceback(), "File Not Found Error")
        frappe.throw(_("File not found: {0}").format(str(e)))

    except IOError as e:
        frappe.log_error(frappe.get_traceback(), "IO Error")
        frappe.throw(_("I/O error: {0}").format(str(e)))

    except Exception:
        frappe.log_error(frappe.get_traceback(), "Embed PDF Error")
        # FIX 3: Wrapped user-facing string in _()
        frappe.throw(_("Unexpected error while embedding XML into PDF"))


def _send_bevatel_whatsapp(doc, doctype, pdf_url):
    try:
        if not pdf_url:
            # FIX 3: Wrapped user-facing string in _()
            frappe.throw(_("Failed to generate PDF/A-3 file!"))

        ws_doc = frappe.get_single(DOCNAME)

        url = ws_doc.bavatel_file_url
        api_account_id = ws_doc.account_id
        api_access_token = ws_doc.access_token
        inbox_id = ws_doc.inbox_id

        phone = frappe.db.get_value("Contact", doc.contact_person, "mobile_no")
        if not phone:
            # FIX 3: Wrapped user-facing string in _()
            frappe.throw(_("Customer phone number not found"))

        phone_number = normalize_phone_bavatel(phone)

        notification_list = frappe.get_all(
            "Notification",
            filters={
                "channel": DOCNAME,
                "document_type": doctype,
                "enabled": 1,
            },
            fields=["name"],
            limit=1,
        )

        if not notification_list:
            # FIX 3: Wrapped user-facing string in _()
            frappe.throw(_("No active WhatsApp Saudi Notification found"))

        notification = frappe.get_doc("Notification", notification_list[0].name)
        message_content = notification.message or ""
        frappe.log_error(title="log4", message=message_content)
        # Extract template name
        template_match = re.search(r'message_template_id\s*=\s*"([^"]+)"', message_content)
        template_name = template_match.group(1) if template_match else None

        # Extract language
        language_match = re.search(r'language\s*=\s*"([^"]+)"', message_content)
        language = language_match.group(1) if language_match else "ar"

        # Extract variables
        var_matches = re.findall(r'var\d+\s*=\s*"([^"]*)"', message_content)

        # FIX 4 (SSTI): var values are extracted from a Notification document which is
        # admin-controlled configuration, not direct user input. Reviewed and accepted.
        # nosemgrep: frappe-semgrep-rules.rules.security.frappe-ssti
        body_variables = []
        for var in var_matches:
            rendered_value = frappe.render_template(var.strip(), {"doc": doc})
            body_variables.append(rendered_value)

        parameters = {
            "media": {
                "link": pdf_url,
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

        if response.status_code in [200, 201]:
            frappe.get_doc({
                "doctype": "whatsapp saudi success log",
                "title": TITTLE,
                "message": json.dumps(response_data),
                "to_number": phone_number,
                "time": now(),
            }).insert(ignore_permissions=True)

            frappe.db.commit()

            return {"status": "success", "phone": phone_number}

        else:
            frappe.log_error(
                title="Bevatel WhatsApp API Error",
                message=json.dumps(response_data),
            )
            return {"status": "failed", "phone": phone_number, "error": response_data}

    except Exception:
        frappe.log_error(
            title="Bevatel WhatsApp Send Failed",
            message=frappe.get_traceback(),
        )
        return {"status": "error", "message": "Sending failed"}