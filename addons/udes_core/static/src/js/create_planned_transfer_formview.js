odoo.define('udes_core.CreatePlannedTransferFormview', function (require) {
  "use strict";

  var FormController = require('web.FormController');

  var udesFormController = FormController.extend({

    init: function () {
      this.replaceTransferButton();
    },

    replaceTransferButton: function () {

      FormController.include({

        renderButtons: function ($node) {
          this._super.apply(this, arguments)
          this.$buttons.find('.o_form_button_add_planned').click(this.proxy('treeViewAction'));
        },

        treeViewAction: function () {

          var hashDict = parseParms(window.location.hash);

          //Build the context string based on active_id
          var contextString =
              "{" +
              "'planned_picking': True," +
              "'contact_display': 'partner_address',";
          if ("active_id" in hashDict) {
            contextString +=
                "'default_picking_type_id': " + hashDict["active_id"];
          }
          contextString += "}";

          this.do_action({
            type: "ir.actions.act_window",
            name: "New Transfer",
            res_model: "stock.picking",
            views: [[false, 'form']],
            target: 'current',
            view_type: 'form',
            view_mode: 'form',
            context: contextString,
            flags: {'form': {'action_buttons': true, 'options': {'mode': 'edit'}}}
          });
          return {'type': 'ir.actions.client', 'tag': 'reload',}
        }

      })

    }

  });

  return udesFormController;

});

odoo.define('udes_core.createPlannedTransfeFormview', function (require) {
  "use strict";

  var UdesFormController = require('udes_core.CreatePlannedTransferFormview');
  new UdesFormController();
});

/**
 * Parse params from the location hash
 * @param str String to parse
 * @returns {Dictionary of hash values}
 */
function parseParms(str) {
  var pieces = str.split("&"), data = {}, i, parts;
  // process each query pair
  for (i = 0; i < pieces.length; i++) {
    parts = pieces[i].split("=");
    if (parts.length < 2) {
      parts.push("");
    }
    data[decodeURIComponent(parts[0])] = decodeURIComponent(parts[1]);
  }
  return data;
}