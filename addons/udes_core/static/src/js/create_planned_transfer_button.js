odoo.define('udes_core.CreatePlannedTransferButton', function (require) {
  "use strict";

  var core = require('web.core');
  var ListView = require('web.ListView');
  var ListController = require('web.ListController');
  // var QWeb = require('core.qweb');
  //


  var BasicController = require('web.BasicController');
  var DataExport = require('web.DataExport');
  var pyeval = require('web.pyeval');
  var Sidebar = require('web.Sidebar');
  var _t = core._t;
  var qweb = core.qweb;

  var udesListController = ListController.extend({

    init: function () {
      alert('Called')
      this.replace_transfer_button();
    },

    replace_transfer_button: function () {

      ListController.include({

        renderButtons: function ($node) {
          console.log("=========================================1");
          var self = this;
          this._super($node);
          this.$buttons.find('.o_list_button_add_planned').click(this.proxy('tree_view_action'));
          // this.$buttons.find('.o_list_button_add_planned').click(function () {
          //   alert('Hello');
          // });
        },

        // this.do_action({
        //     type: "ir.actions.act_window",
        //     name: "New Transfer",
        //     res_model: "stock.picking",
        //     views: [[false, 'form']],
        //     target: 'current',
        //     view_type: 'form',
        //     view_mode: 'form',
        //     context: "{'search_default_picking_type_id': '" + this.action.context.active_id +
        //     "','default_picking_type_id': '" + this.action.context.active_id +
        //     "',contact_display': 'partner_address'," +
        //     "}",
        //     flags: {'form': {'action_buttons': true, 'options': {'mode': 'edit'}}}
        //   });

        tree_view_action: function () {

          console.log("=========================================2");
          // debugger
          // console.log("ActiveId:" + this.action.context.active_id);


          this.do_action({
            type: "ir.actions.act_window",
            name: "New Transfer",
            res_model: "stock.picking",
            views: [[false, 'form']],
            target: 'current',
            view_type: 'form',
            view_mode: 'form',
            context: "{'planned_picking': True," +
            " 'contact_display': 'partner_address'," +
            // " 'search_default_picking_type_id': '" + this.action.context.active_id + "'," +
            " 'default_picking_type_id': 9}",
            flags: {'form': {'action_buttons': true, 'options': {'mode': 'edit'}}}
          });
          return {'type': 'ir.actions.client', 'tag': 'reload',}
        }

      })

    },

  });

  return udesListController;

});

odoo.define('udes_core.createPlannedTransferButton', function (require) {
  "use strict";

  var UdesListController = require('udes_core.CreatePlannedTransferButton');
  new UdesListController();
});

// ListView = require('web.ListView')
//
//   ListView.include({
//     render_buttons: function () {
//       console.log("=========================================2");
//       // GET BUTTON REFERENCE
//       this._super.apply(this, arguments)
//       if (this.$buttons) {
//         var btn = this.$buttons.find('.o_list_button_add_2')
//       }
//
//       // PERFORM THE ACTION
//       btn.on('click', this.proxy('do_new_button'))
//
//     },
//     do_new_button: function () {
//
//       instance.web.Model('sale.order')
//           .call('update_sale_button', [[]])
//           .done(function (result) {
//
//           })
//     });
// });