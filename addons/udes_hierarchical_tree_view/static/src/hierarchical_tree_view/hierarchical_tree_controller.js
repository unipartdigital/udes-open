odoo.define("udes_hierarchical_tree_view.HierarchicalTreeController", function (require) {
  "use strict";

  var AbstractController = require("web.AbstractController");

  var HierarchicalTreeController = AbstractController.extend({
    custom_events: _.extend({}, AbstractController.prototype.custom_events, {
      tree_item_clicked: "_onTreeItemClicked",
      change_item_tree: "_onChangeItemTree",
      open_form_view: "_onOpenFormView",
    }),

    /**
     * @override
     * @param parent
     * @param model
     * @param renderer
     * @param {Object} params
     */
    init: function (parent, model, renderer, params) {
      this._super.apply(this, arguments);
    },

    /**
     * @param {Object} ev
     * @param {Object} ev.data contains the payload
     */
    _onTreeItemClicked: async function (ev) {
      ev.stopPropagation();
      if (ev.data.data.children === undefined) {
        await this.model.expandChildrenOf(
          ev.data.data.id,
          ev.data.data.parent_path
        );
      } else {
        this.model.toggleChildrenVisibleForItem(ev.data.data);
      }
      this.update({}, { reload: false });
    },

    /**
     * @param {Object} ev
     * @param {Object} ev.data contains the payload
     */
    _onOpenFormView: async function (ev) {
      ev.stopPropagation();
      if (ev.data.data.id !== undefined) {
        let form_views = this.actionViews.filter(function (view) { return view.type == "form" });
        if (form_views.length == 1) {
          await this.model.do_action({
            "res_id": ev.data.data.id,
            "res_model": this.model.modelName,
            "type": "ir.actions.act_window",
            "views": [[form_views[0].viewID, "form"]],
            'context': this.model.loadParams.context,
          })
        } else {
          await this.model.do_warn("Could not find a suitable form view for this model")
        }
      }
    },

    /**
     * @param {Object} ev
     * @param {Object} ev.data.itemMoved is the item that has been dragged
     * @param {Object} ev.data.newParent is the new target parent of the dropped item
     */
    _onChangeItemTree: async function (ev) {
      ev.stopPropagation();
      let itemMoved = ev.data.itemMoved;
      let newParent = ev.data.newParent;
      await this.model.changeParent(itemMoved.id, newParent.id);

      // Refresh old parent
      let oldParent = await this.model.refreshNode(itemMoved.parent_id[0]);
      await this.model.expandChildrenOf(oldParent.id, oldParent.parent_path);

      // Refresh new parent
      await this.model.expandChildrenOf(
        ev.data.newParent.id,
        ev.data.newParent.parent_path
      );
      this.update({}, { reload: false });
    },
  });

  return HierarchicalTreeController;
});
