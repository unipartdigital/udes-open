odoo.define('udes_core.CreatePlannedTransferKanban', function (require) {
  "use strict";

  var KanbanController = require('web.KanbanController');

  var udesKanbanController = KanbanController.extend({

    init: function () {
      this.replaceTransferButton();
    },

    replaceTransferButton: function () {

      KanbanController.include({

        renderButtons: function ($node) {
          this._super.apply(this, arguments)
          if (this.$buttons) {
            this.$buttons.find('.o_list_button_add_planned').click(this.proxy('treeViewAction'));
          }
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

  return udesKanbanController;

});

odoo.define('udes_core.createPlannedTransferKanban', function (require) {
  "use strict";

  var KanbanController = require('udes_core.CreatePlannedTransferKanban');
  new KanbanController();
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