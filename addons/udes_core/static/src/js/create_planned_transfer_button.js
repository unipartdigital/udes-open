odoo.define('udes_core.CreatePlannedTransferButton', function (require) {
  "use strict";

  var ListController = require('web.ListController');
  var GenericHelperFunctions = require('udes_core.GenericHelperFunctions');

  var udesListController = ListController.extend({

    init: function () {
      this.replaceTransferButton();
    },

    replaceTransferButton: function () {

      ListController.include({

        renderButtons: function ($node) {
          this._super.apply(this, arguments);
          if(this.$buttons){
            this.$buttons.find('.o_list_button_add_planned').click(this.proxy('treeViewAction'));
          }
        },

        treeViewAction: function () {

          var hashDict = GenericHelperFunctions.parseUrlParams(window.location.hash);

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
