function whatsapp_saudi_send_invoice_dialog(docname, with_phone) {
    const fields = [
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
    ];

    if (with_phone) {
        fields.push({
            fieldtype: 'Data',
            fieldname: 'phone',
            label: __('WhatsApp Number'),
            reqd: 1,
            description: __('Include country code, e.g. 9665XXXXXXXX')
        });
    }

    const dialog = new frappe.ui.Dialog({
        title: with_phone ? __('Send Invoice to Different Number') : __('Send Invoice to WhatsApp'),
        fields: fields,
        primary_action_label: __('Send'),
        primary_action() {
            const values = dialog.get_values();
            if (!values) {
                return;
            }

            frappe.call({
                method: 'whatsapp_saudi.overrides.whtatsapp_notification.get_whatsapp_pdf_a3',
                args: {
                    message: 'SALES INVOICE',
                    docname: docname,
                    doctype: 'Sales Invoice',
                    print_format: values.print_format,
                    letterhead: values.letterhead || null,
                    language: values.language,
                    phone: with_phone ? values.phone : null
                },
                freeze: true,
                freeze_message: __('Generating PDF & Sending WhatsApp message...'),
                callback: function (response) {
                    const res = response.message;
                    const is_success = res && (res.status === 'success' || res.success === true);
                    if (is_success) {
                        frappe.msgprint(__('WhatsApp message sent successfully!'));
                    } else {
                        frappe.msgprint((res && res.message) || __('Failed to send WhatsApp message.'));
                    }
                }
            });

            dialog.hide();
        }
    });

    dialog.show();
}

frappe.ui.form.on('Sales Invoice', {
    refresh(frm) {
        frm.add_custom_button(__('Send Invoice to WhatsApp'), () => {
            whatsapp_saudi_send_invoice_dialog(frm.doc.name, false);
        }, __('WhatsApp'));

        frm.add_custom_button(__('Send Invoice to Different Number'), () => {
            whatsapp_saudi_send_invoice_dialog(frm.doc.name, true);
        }, __('WhatsApp'));
    }
});

frappe.listview_settings = frappe.listview_settings || {};
frappe.listview_settings['Sales Invoice'] = frappe.listview_settings['Sales Invoice'] || {};

(function () {
    const existing_onload = frappe.listview_settings['Sales Invoice'].onload;
    frappe.listview_settings['Sales Invoice'].onload = function (listview) {
        if (existing_onload) {
            existing_onload(listview);
        }

        listview.page.add_action_item(__('Send Invoice to WhatsApp'), () => {
            whatsapp_saudi_list_send(listview, false);
        });

        listview.page.add_action_item(__('Send Invoice to Different Number'), () => {
            whatsapp_saudi_list_send(listview, true);
        });
    };
})();

function whatsapp_saudi_list_send(listview, with_phone) {
    const checked_items = listview.get_checked_items();
    if (checked_items.length !== 1) {
        frappe.msgprint(__('Please select exactly one Sales Invoice.'));
        return;
    }
    whatsapp_saudi_send_invoice_dialog(checked_items[0].name, with_phone);
}
