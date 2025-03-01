frappe.ui.form.on('Sales Invoice', {
    refresh: function(frm) {
        frm.add_custom_button('Send WhatsApp', function() {
            frappe.call({
                method: 'whatsapp_saudi.overrides.whtatsapp_notification.send_whatsapp_with_pdf1',
                args: {
                    message: "hello",
                    docname: frm.doc.name,
                    doctype: "Sales Invoice",
                    print_format: "walkthrough"
                },
                callback: function(response) {
                    if (response.message) {
                        frappe.msgprint('WhatsApp message sent successfully!');
                    } else {
                        frappe.msgprint('Failed to send WhatsApp message.');
                    }
                },
                error: function(err) {
                    frappe.msgprint('Error sending WhatsApp message.');
                    console.log(err);
                },
                always: function() {
                    console.log('WhatsApp message request completed.');
                },
                btn: this, // Reference to the button
                freeze: true, // Freezing the screen
                freeze_message: "Sending WhatsApp message...", // Message to show
                async: true
            });
        });
    }
});
