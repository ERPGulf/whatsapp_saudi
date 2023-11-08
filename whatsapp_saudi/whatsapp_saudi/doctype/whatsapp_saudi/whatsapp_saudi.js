// Copyright (c) 2023, ERPGulf.com and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Whatsapp Saudi", {
// 	refresh(frm) {

// 	},
// });
frappe.ui.form.on("Whatsapp Saudi", {
  refresh: function(frm) {
      frm.add_custom_button(__("click"), function() {
          frm.call({
              method: "whatsapp_saudi.whatsapp_saudi.doctype.whatsapp_saudi.whatsapp_saudi.send_message",
              args: {
                

              },
              callback: function(response) {
                  if (response.message) {  
                      frappe.msgprint(response.message);
                     
                  }
              }
          });
      }, __("send"));
  }
});