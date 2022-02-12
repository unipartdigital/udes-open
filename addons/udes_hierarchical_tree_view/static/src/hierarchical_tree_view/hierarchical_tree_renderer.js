odoo.define("udes_hierarchical_tree_view.HierarchicalTreeRenderer", function (require) {
  "use strict";

  const AbstractRendererOwl = require("web.AbstractRendererOwl");
  const patchMixin = require("web.patchMixin");
  const QWeb = require("web.QWeb");
  const session = require("web.session");

  const { useState } = owl.hooks;

  class HierarchicalTreeRenderer extends AbstractRendererOwl {
    constructor(parent, props) {
      super(...arguments);
      this.qweb = new QWeb(this.env.isDebug(), { _s: session.origin });
      this.state = useState({
        localItems: props.items || [],
        countField: "",
        disableDragDrop: "",
        startUnfolded: "",
        showFormButton: ""
      });
      if (this.props.arch.attrs.count_field) {
        Object.assign(this.state, {
          countField: this.props.arch.attrs.count_field,
        });
      }
      if (this.props.arch.attrs.disable_drag_drop) {
        Object.assign(this.state, {
          disableDragDrop: this.props.arch.attrs.disable_drag_drop,
        });
      }
      if (this.props.arch.attrs.start_unfolded) {
        Object.assign(this.state, {
          startUnfolded: this.props.arch.attrs.start_unfolded,
        });
      }
      if (this.props.arch.attrs.show_form_button) {
        Object.assign(this.state, {
          showFormButton: this.props.arch.attrs.show_form_button,
        });
      }
    }
  }

  const components = {
    TreeItem: require("udes_hierarchical_tree_view/static/src/components/tree_item/TreeItem.js"),
  };
  Object.assign(HierarchicalTreeRenderer, {
    components,
    defaultProps: {
      items: [],
    },
    props: {
      arch: {
        type: Object,
        optional: true,
      },
      items: {
        type: Array,
      },
      isEmbedded: {
        type: Boolean,
        optional: true,
      },
      noContentHelp: {
        type: String,
        optional: true,
      },
    },
    template: "udes_hierarchical_tree_view.HierarchicalTreeRenderer",
  });

  return patchMixin(HierarchicalTreeRenderer);
});
