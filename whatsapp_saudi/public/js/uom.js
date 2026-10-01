const child_doctypes = [
    "Sales Invoice Item",
    "Delivery Note Item",
    "Sales Order Item",
    "Purchase Invoice Item",
    "Purchase Order Item",
    "Purchase Receipt Item",
    "Quotation Item",
    "Stock Entry Detail"
];

function apply_uom_filter(frm, cdt, cdn) {
    let row = locals[cdt][cdn];

    if (!row.item_code) return;

    frappe.db.get_doc("Item", row.item_code).then(item => {

        let allowed_uoms = [];

        if (item.stock_uom) {
            allowed_uoms.push(item.stock_uom);
        }

        (item.uoms || []).forEach(u => {
            if (u.uom && !allowed_uoms.includes(u.uom)) {
                allowed_uoms.push(u.uom);
            }
        });

        frm.fields_dict.items.grid.get_field("uom").get_query = function () {
            return {
                filters: [
                    ["UOM", "name", "in", allowed_uoms]
                ]
            };
        };
    });
}

child_doctypes.forEach(dt => {
    frappe.ui.form.on(dt, {
        item_code(frm, cdt, cdn) {
            apply_uom_filter(frm, cdt, cdn);
        }
    });
});