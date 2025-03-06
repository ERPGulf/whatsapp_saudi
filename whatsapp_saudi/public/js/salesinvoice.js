frappe.ui.form.on("Sales Invoice", {
    refresh: function (frm) {  // Use refresh to ensure the button is added every time the form is loaded
        frm.page.add_menu_item(__('Print PDF-A3'), function () {

            const dialog = new frappe.ui.Dialog({
                title: __('Generate PDF-A3'),
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
                        options: 'Language', // Options should be the 'Language' doctype
                        reqd: 1
                    }
                ],
                primary_action_label: __('Generate PDF-A3'),
                primary_action: function () {
                    const values = dialog.get_values();
                    if (!values) {
                        frappe.msgprint(__('Please fill all required fields.'));
                        return;
                    }

                    frappe.call({
                        method: 'whatsapp_saudi.whatsapp_saudi.pdf a3.embed_file_in_pdf',
                        args: {
                            invoice_name: frm.doc.name,
                            print_format: values.print_format,
                            letterhead: values.letterhead || '', // Ensure letterhead is handled if not selected
                            language: values.language
                        },
                        callback: function (r) {
                            if (r.message) {
                                console.log("Generated PDF URL:", r.message);
                                window.open(r.message, '_blank'); // Open the generated PDF in a new tab
                                frm.reload_doc();
                            } else {
                                frappe.msgprint(__('Failed to generate PDF-A3'));
                            }
                        }
                    });

                    dialog.hide();
                }
            });
            dialog.show();
        });
    }
});
