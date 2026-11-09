"""Corbit SMS gateway (https://api.corbit.sa) — POST /api/v1/send.

Settings live on the "Whatsapp Saudi" single doctype, "Corbit SMS" tab.
"""

import json
import time

import frappe
import requests
from frappe import _
from frappe.utils import cint, now, strip_html

SETTINGS_DOCTYPE = "Whatsapp Saudi"
SUCCESS_LOG_DOCTYPE = "whatsapp saudi success log"
DEFAULT_BASE_URL = "https://api.corbit.sa"
SEND_PATH = "/api/v1/send"
MAX_LENGTH = 1600
TIMEOUT = 30
RETRY_STATUSES = (429, 502, 503)
MAX_RETRY_WAIT = 10  # seconds; longer Retry-After values are not waited on


class CorbitSMSConfigError(Exception):
    pass


def get_corbit_config():
    settings = frappe.get_single(SETTINGS_DOCTYPE)
    if not cint(settings.get("corbit_enabled")):
        raise CorbitSMSConfigError(_("Corbit SMS is not enabled in Whatsapp Saudi settings"))

    token = settings.get_password("corbit_api_token", raise_exception=False)
    sender = (settings.get("corbit_sender_name") or "").strip()
    if not token or not sender:
        raise CorbitSMSConfigError(_("Corbit SMS API Token and Sender Name are required"))

    base_url = (settings.get("corbit_base_url") or DEFAULT_BASE_URL).strip().rstrip("/")
    return {"url": base_url + SEND_PATH, "token": token.strip(), "sender": sender}


def normalize_corbit_number(number):
    """International format, digits only, 8–15 digits (e.g. 9665XXXXXXXX)."""
    from whatsapp_saudi.overrides.whtatsapp_notification import normalize_phone

    digits = "".join(ch for ch in normalize_phone(str(number or "")) if ch.isdigit())
    return digits if 8 <= len(digits) <= 15 else None


def _result(success, phone, **extra):
    return {"success": success, "status": "success" if success else "error", "phone": phone, **extra}


def _post_with_retry(url, payload, headers):
    """POST once; retry once on 429/502/503 if Retry-After is short."""
    response = None
    for attempt in range(2):
        response = requests.post(url, json=payload, headers=headers, timeout=TIMEOUT)
        if response.status_code not in RETRY_STATUSES or attempt == 1:
            break
        wait = cint(response.headers.get("Retry-After")) or 1
        if wait > MAX_RETRY_WAIT:
            break
        time.sleep(wait)
    return response


def send_corbit_sms(phone, message, allow_duplicate=False, idempotency_key=None, config=None):
    """Send one SMS through Corbit.

    allow_duplicate: sends X-Allow-Duplicate: true (needed for OTP resends — Corbit
                     otherwise rejects the same text to the same number within 1 hour).
    idempotency_key: optional Idempotency-Key header for safe retries.
    Returns {success, status, phone, message_id | code, error}.
    """
    try:
        config = config or get_corbit_config()
    except CorbitSMSConfigError as e:
        frappe.log_error(title="Corbit SMS configuration error", message=str(e))
        return _result(False, phone, code="CONFIG", error=str(e))

    number = normalize_corbit_number(phone)
    if not number:
        return _result(False, phone, code="VALIDATION", error=_("Invalid mobile number: {0}").format(phone))

    text = (message or "").strip()
    if not text:
        return _result(False, number, code="VALIDATION", error=_("Message is empty"))
    if len(text) > MAX_LENGTH:
        frappe.log_error(
            title="Corbit SMS message truncated",
            message=f"Message to {number} was {len(text)} characters; truncated to {MAX_LENGTH}.",
        )
        text = text[:MAX_LENGTH]

    payload = {
        "senderName": config["sender"],
        "number": number,
        "messageBody": text,
        "sendAtOption": "NOW",
    }
    headers = {
        "Authorization": f"Bearer {config['token']}",
        "Content-Type": "application/json",
    }
    if allow_duplicate:
        headers["X-Allow-Duplicate"] = "true"
    if idempotency_key:
        headers["Idempotency-Key"] = str(idempotency_key)[:255]

    try:
        response = _post_with_retry(config["url"], payload, headers)
    except requests.exceptions.RequestException as e:
        frappe.log_error(title="Corbit SMS request failed", message=frappe.get_traceback())
        return _result(False, number, code="NETWORK", error=str(e))

    try:
        data = response.json()
    except ValueError:
        data = {}
    if not isinstance(data, dict):
        data = {}

    if response.status_code == 200 and str(data.get("status", "")).lower() == "success":
        msg = (data.get("data") or {}).get("message") or {}
        message_id = msg.get("id")
        frappe.get_doc({
            "doctype": SUCCESS_LOG_DOCTYPE,
            "title": "Corbit SMS sent",
            "message": f"{message_id} ({msg.get('status')}): {text}",
            "to_number": number,
            "time": now(),
        }).insert(ignore_permissions=True)
        return _result(True, number, message_id=message_id, delivery_status=msg.get("status"))

    code = data.get("code") or str(response.status_code)
    error = data.get("message") or response.text[:1000]
    frappe.log_error(
        title=f"Corbit SMS failed ({code})",
        message=json.dumps(
            {"phone": number, "http_status": response.status_code, "code": code, "response": data or response.text[:2000]},
            indent=2,
            ensure_ascii=False,
        ),
    )
    return _result(False, number, code=code, http_status=response.status_code, error=error)


def send_corbit_sms_bulk(phones, message, allow_duplicate=False):
    """Send the same text to several numbers (one /send call each, de-duplicated)."""
    try:
        config = get_corbit_config()
    except CorbitSMSConfigError as e:
        frappe.log_error(title="Corbit SMS configuration error", message=str(e))
        return [_result(False, None, code="CONFIG", error=str(e))]

    results, seen = [], set()
    for phone in phones or []:
        number = normalize_corbit_number(phone)
        if number in seen:
            continue
        seen.add(number)
        results.append(send_corbit_sms(phone, message, allow_duplicate=allow_duplicate, config=config))
    return results


def render_sms_text(template, context):
    # nosemgrep: frappe-semgrep-rules.rules.security.frappe-ssti
    return strip_html(frappe.render_template(template or "", context)).strip()


@frappe.whitelist()
def send_sms(phone: str, message: str):
    """API: send a plain SMS via Corbit."""
    return send_corbit_sms(phone, message)


@frappe.whitelist()
def test_corbit_sms():
    """Settings button: send a test SMS to 'To Number (for testing)'."""
    frappe.only_for("System Manager")
    settings = frappe.get_single(SETTINGS_DOCTYPE)
    if not settings.to_number:
        frappe.throw(_("Set 'To Number (for testing)' on the Setting tab first"))
    return send_corbit_sms(
        settings.to_number,
        _("Test SMS from {0} via Corbit").format(frappe.local.site),
        allow_duplicate=True,
    )
