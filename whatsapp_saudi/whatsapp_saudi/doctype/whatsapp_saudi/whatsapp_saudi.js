frappe.ui.form.on("Whatsapp Saudi", {
    refresh(frm) {
        frm.add_custom_button(__("Send Test Message"), function () {

            // ✅ Firebase only (ignore WhatsApp provider completely)
            if (frm.doc.firebase_notification) {

                if (!frm.doc.client_token) {
                    frappe.msgprint(__("Please enter Client Token for Firebase Notification."));
                    return;
                }

                frm.call({
                    method: "whatsapp_saudi.whatsapp_saudi.doctype.whatsapp_saudi.whatsapp_saudi.test_firebase_push",
                    args: {
                        client_token: frm.doc.client_token
                    },
                    freeze: true,
                    freeze_message: __("Sending Firebase Test Notification..."),
                    callback: function (r) {
                        if (r.message) {
                            if (r.message.status === "success") {
                                frappe.msgprint({
                                    title: __("Firebase Success"),
                                    indicator: "green",
                                    message: __("Firebase test notification sent successfully.")
                                });
                            } else {
                                frappe.msgprint({
                                    title: __("Firebase Failed"),
                                    indicator: "red",
                                    message: __(r.message.error || "Firebase notification failed.")
                                });
                            }
                        }
                    }
                });

                return; // ✅ stop here, do NOT validate WhatsApp provider
            }

            // ✅ Only check provider if Firebase is OFF
            if (!frm.doc.whatsapp_provider) {
                frappe.msgprint(__("Please select a WhatsApp Provider."));
                return;
            }

            // ✅ Provider credential validation
            if (!areCredentialsValid(frm)) {
                frappe.msgprint(__("Please fill all required details correctly."));
                return;
            }

            // ✅ Rasayel
            if (frm.doc.whatsapp_provider === "Rasayel") {

                frm.call({
                    method: "whatsapp_saudi.whatsapp_saudi.doctype.whatsapp_saudi.whatsapp_saudi.rasayel_whatsapp_file_message_pdf",
                    args: {
                        docname: frm.doc.name
                    },
                    freeze: true,
                    freeze_message: __("Sending via Rasayel...")
                });

            }

            // ✅ WhatsApp.net
            else if (frm.doc.whatsapp_provider === "Whats.net") {

                frm.call({
                    method: "whatsapp_saudi.whatsapp_saudi.doctype.whatsapp_saudi.whatsapp_saudi.send_message",
                    args: {
                        provider: "whatsapp_net",
                        url: frm.doc.file_url,
                        instance: frm.doc.instance_id,
                        token: frm.doc.token,
                        phone: frm.doc.to_number
                    },
                    freeze: true,
                    freeze_message: __("Sending via WhatsApp.net...")
                });

            }

            // ✅ Bevatel
            else if (frm.doc.whatsapp_provider === "Bevatel") {

                frm.call({
                    method: "whatsapp_saudi.whatsapp_saudi.doctype.whatsapp_saudi.whatsapp_saudi.send_bevatel_message",
                    args: {
                        phone: frm.doc.to_number
                    },
                    freeze: true,
                    freeze_message: __("Sending via Bevatel...")
                });

            }

        });
    }
});


function areCredentialsValid(frm) {

    // ✅ Firebase enabled = skip all provider checks
    if (frm.doc.firebase_notification) {
        return !!frm.doc.client_token;
    }

    // ✅ Rasayel
    if (frm.doc.whatsapp_provider === "Rasayel") {
        return !!(
            frm.doc.file_upload &&
            frm.doc.raseyel_file_api &&
            frm.doc.raseyel_authorization_token &&
            frm.doc.to_number
        );
    }

    // ✅ WhatsApp.net
    if (frm.doc.whatsapp_provider === "Whats.net") {
        const expectedFormat = /^https:\/\/api\.4whats\.net\/sendFile$/;

        return !!(
            frm.doc.file_url &&
            expectedFormat.test(frm.doc.file_url) &&
            frm.doc.instance_id &&
            frm.doc.token &&
            frm.doc.to_number
        );
    }

    // ✅ Bevatel
    if (frm.doc.whatsapp_provider === "Bevatel") {
        return !!frm.doc.to_number;
    }

    return false;
}