odoo.define("udes_hierarchical_tree_view.HierarchicalTree", function (require) {
  "use strict";

  const HierarchicalTreeController = require("udes_hierarchical_tree_view.HierarchicalTreeController");
  const HierarchicalTreeModel = require("udes_hierarchical_tree_view.HierarchicalTreeModel");
  const HierarchicalTreeRenderer = require("udes_hierarchical_tree_view.HierarchicalTreeRenderer");
  const AbstractView = require("web.AbstractView");
  const core = require("web.core");
  const RendererWrapper = require("web.RendererWrapper");
  const view_registry = require("web.view_registry");

  const _lt = core._lt;

  const HierarchicalTree = AbstractView.extend({
    accesskey: "m",
    display_name: _lt("HierarchicalTree"),
    icon: "fa-indent",
    config: _.extend({}, AbstractView.prototype.config, {
      Controller: HierarchicalTreeController,
      Model: HierarchicalTreeModel,
      Renderer: HierarchicalTreeRenderer,
    }),
    viewType: "hierarchical_tree",
    searchMenuTypes: ["filter", "favorite"],

    /**
     * @override
     */
    init: function () {
      this._super.apply(this, arguments);
    },

    getRenderer(parent, state) {
      state = Object.assign(state || {}, this.rendererParams);
      return new RendererWrapper(parent, this.config.Renderer, state);
    },
  });

  view_registry.add("hierarchical_tree", HierarchicalTree);

  return HierarchicalTree;
});
