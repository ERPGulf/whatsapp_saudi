function generatePDFDialog(frm, title, method) {
    const dialog = new frappe.ui.Dialog({
        title: __(title),
        fields: [
            {
                fieldtype: 'Link',
                fieldname: 'print_format',
                label: __('Print Format'),
                options: 'Print Format',
                reqd: 1,
                get_query: function () {
                    return { filters: { doc_type: frm.doctype } };
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
        primary_action_label: __('Generate PDF'),
        primary_action: function () {
            const values = dialog.get_values();
            if (!values) {
                frappe.msgprint(__('Please fill all required fields.'));
                return;
            }
            generatePDF(frm, values, method);
            dialog.hide();
        }
    });
    dialog.show();
}

function generatePDF(frm, values, method) {
    frappe.call({
        method: method,
        args: {
            invoice_name: frm.doc.name,
            print_format: values.print_format,
            letterhead: values.letterhead || '',
            language: values.language
        },
        callback: function (r) {
            if (r.message) {
                console.log("Generated PDF URL:", r.message);
                window.open(r.message, '_blank');
                frm.reload_doc();
            } else {
                frappe.msgprint(__('Failed to generate PDF'));
            }
        }
    });
}


frappe.ui.form.on("Sales Invoice", {
    refresh: function (frm) {
        frm.page.add_menu_item(__('Print PDF-A3'), function () {
            generatePDFDialog(frm, 'Generate PDF-A3', 'whatsapp_saudi.overrides.pdf_a3.embed_file_in_pdf');
        });
    }
});
