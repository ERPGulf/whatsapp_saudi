function generateAndSendPDF(frm, title, method) {
    const dialog = new frappe.ui.Dialog({
        title: __(title),
        fields: [
            {
                fieldtype: 'Link',
                fieldname: 'print_format',
                label: __('Print Format'),
                options: 'Print Format',
                reqd: 1,
                get_query: () => {
                    return { filters: { doc_type: 'Sales Invoice' } };
                }
            },
            {
                fieldtype: 'Link',
                fieldname: 'letterhead',
                label: __('Letterhead'),
                options: 'Letter Head'
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
        primary_action() {
            const values = dialog.get_values();
            if (!values) {
                frappe.msgprint(__('Please fill all required fields.'));
                return;
            }

            frappe.call({
                method: method,
                args: {
                    message: "SALES INVOICE",
                    docname: frm.doc.name,
                    doctype: "Sales Invoice",
                    print_format: values.print_format,
                    letterhead: values.letterhead,
                    language: values.language
                },
                freeze: true,
                freeze_message: __("Generating PDF & Sending WhatsApp message..."),
                callback: function (response) {
                    const res = response.message;
                    if (res && res.status === "success"){
                        frappe.msgprint(__('PDF Generated & WhatsApp message sent successfully!'));
                    } else {
                        frappe.msgprint(__('Failed to send WhatsApp message.'));
                    }
                }
            });

            dialog.hide();
        }
    });
    dialog.show();
}

frappe.ui.form.on("Sales Invoice", {
    refresh(frm) {

        // Add buttons to MENU
        frm.page.add_menu_item(__('Send Pdf through WhatsApp'), function () {
            generateAndSendPDF(frm, 'Send PDF via WhatsApp',
                'whatsapp_saudi.overrides.whtatsapp_notification.get_whatsapp_pdf');
        });

        frm.page.add_menu_item(__('Send PDF-A3 through WhatsApp'), function () {
            generateAndSendPDF(frm, 'Send PDF-A3 via WhatsApp',
                'whatsapp_saudi.overrides.whtatsapp_notification.get_whatsapp_pdf_a3');
        });

    }
});
