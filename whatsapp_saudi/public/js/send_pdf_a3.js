// frappe.ui.form.on('Sales Invoice', {
//     refresh: function(frm) {
//         frm.add_custom_button('Send_pdf_A3', function() {
//             frappe.call({
//                 method: 'whatsapp_saudi.overrides.pdf_a3.send_whatsapp_with_pdf_a3',
//                 args: {
//                     message: "SALES INVOICE",
//                     invoice_name: frm.doc.name,
//                     doctype: "Sales Invoice",
//                     print_format: "Claudion Invoice Format"
//                 },
//                 callback: function(response) {
//                     if (response.message) {
//                         frappe.msgprint('WhatsApp message sent successfully!');
//                     } else {
//                         frappe.msgprint('Failed to send WhatsApp message.');
//                     }
//                 },
//                 error: function(err) {
//                     frappe.msgprint('Error sending WhatsApp message.');
//                     console.log(err);
//                 },
//                 always: function() {
//                     console.log('WhatsApp message request completed.');
//                 },
//                 btn: this, // Reference to the button
//                 freeze: true, // Freezing the screen
//                 freeze_message: "Sending WhatsApp message...", // Message to show
//                 async: true
//             });
//         });
//     }
// });


frappe.ui.form.on("Sales Invoice", {
    refresh: function (frm) {

        frm.add_custom_button(__('Send PDF-A3 through WhatApp'), function () {

            const dialog = new frappe.ui.Dialog({
                title: __('Send PDF-A3 via WhatsApp'),
                fields: [
                    {
                        fieldtype: 'Link',
                        fieldname: 'print_format',
                        label: __('Print Format'),
                        options: 'Print Format',
                        reqd: 1,
                        get_query: function () {
                            return {
                                filters: {
                                    doc_type: 'Sales Invoice'
                                }
                            };
                        }
                    },
                    {
                        fieldtype: 'Link',
                        fieldname: 'letterhead',
                        label: __('Letterhead'),
                        options: 'Letter Head',
                        reqd: 0
                    },
                    {
                        fieldtype: 'Link',
                        fieldname: 'language',
                        label: __('Language'),
                        options: 'Language',
                        reqd: 1
                    }
                ],
                primary_action_label: __('Generate & Send'),
                primary_action: function () {
                    const values = dialog.get_values();
                    if (!values) {
                        frappe.msgprint(__('Please fill all required fields.'));
                        return;
                    }


                    frappe.call({
                        method: 'whatsapp_saudi.overrides.pdf_a3.send_whatsapp_with_pdf_a3',
                        args: {
                            message: "SALES INVOICE",
                            invoice_name: frm.doc.name,
                            doctype: "Sales Invoice",
                            print_format: values.print_format,
                            letterhead: values.letterhead,
                            language: values.language
                        },
                        callback: function (response) {
                            if (response.message) {
                                frappe.msgprint(__('PDF Generated & WhatsApp message sent successfully!'));
                            } else {
                                frappe.msgprint(__('Failed to send WhatsApp message.'));
                            }
                        },
                        error: function (err) {
                            frappe.msgprint(__('Error sending WhatsApp message.'));
                            console.log(err);
                        },
                        always: function () {
                            console.log('WhatsApp message request completed.');
                        },
                        btn: this,
                        freeze: true,
                        freeze_message: __("Generating PDF & Sending WhatsApp message..."),
                        async: true
                    });

                    dialog.hide();
                }
            });
            dialog.show();
        });
    }
});
