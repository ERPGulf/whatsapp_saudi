
frappe.ui.form.on("Whatsapp Saudi", {
    refresh: function(frm) {
        frm.add_custom_button(__("Send "), function() {
            if (!areCredentialsValid(frm)) {
                frappe.msgprint(__("Please fill in all required fields with the correct format before sending a test message."));
                return;
            }

            frm.call({
                method: "whatsapp_saudi.whatsapp_saudi.doctype.whatsapp_saudi.whatsapp_saudi.send_message",
                args: {
                    url: frm.doc.file_url,
                    instance: frm.doc.instance_id,
                    token: frm.doc.token,
                    phone: frm.doc.to_number
                },
                callback: function(response) {
                    if (response.message) {
                        frappe.msgprint(response.message);
                    }
                }
            });
        }, __("Send a test message"));
    }
});

function areCredentialsValid(frm) {
    const expectedFormat = /^https:\/\/api\.4whats\.net\/sendFile$/;


      return (
        frm.doc.file_url &&
        expectedFormat.test(frm.doc.file_url) &&
        frm.doc.instance_id &&
        frm.doc.token &&
        frm.doc.to_number



    );
}


