frappe.ui.form.on('Sales Invoice', {
    refresh: function(frm) {
        frm.add_custom_button('Send_pdf_A3', function() {
            frappe.call({
                method: 'whatsapp_saudi.overrides.pdf_a3.send_whatsapp_with_pdf_a3',
                args: {
                    message: "SALES INVOICE",
                    invoice_name: frm.doc.name,
                    doctype: "Sales Invoice",
                    print_format: "Claudion Invoice Format"
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
