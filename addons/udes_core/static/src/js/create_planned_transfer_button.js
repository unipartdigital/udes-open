odoo.define('udes_core.CreatePlannedTransferButton', function (require) {
  "use strict";

  var ListController = require('web.ListController');

  var udesListController = ListController.extend({

    init: function () {
      this.replace_transfer_button();
    },

    replace_transfer_button: function () {

      ListController.include({

        renderButtons: function ($node) {
          this._super.apply(this, arguments)
          this.$buttons.find('.o_list_button_add_planned').click(this.proxy('tree_view_action'));
        },

        tree_view_action: function () {

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

  return udesListController;

});

odoo.define('udes_core.createPlannedTransferButton', function (require) {
  "use strict";

  var UdesListController = require('udes_core.CreatePlannedTransferButton');
  new UdesListController();
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