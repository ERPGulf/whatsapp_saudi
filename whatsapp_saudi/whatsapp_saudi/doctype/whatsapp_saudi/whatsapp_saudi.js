frappe.ui.form.on("Whatsapp Saudi", {
    refresh(frm) {
        frm.add_custom_button(__("Send Test Message"), function () {

            if (!areCredentialsValid(frm)) {
                frappe.msgprint(__("Please fill all required details correctly."));
                return;  // ✅ important
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

            // ✅ NEW: Bevatel
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

    if (frm.doc.whatsapp_provider === "Rasayel") {
        return frm.doc.file_upload &&
               frm.doc.raseyel_file_api &&
               frm.doc.raseyel_authorization_token &&
               frm.doc.to_number;
    }

    if (frm.doc.whatsapp_provider === "Whats.net") {
        const expectedFormat = /^https:\/\/api\.4whats\.net\/sendFile$/;

        return (
            frm.doc.file_url &&
            expectedFormat.test(frm.doc.file_url) &&
            frm.doc.instance_id &&
            frm.doc.token &&
            frm.doc.to_number
        );
    }

    // ✅ Bevatel validation
    if (frm.doc.whatsapp_provider === "Bevatel") {
        return (
            frm.doc.to_number
        );
    }

    return false;
}
