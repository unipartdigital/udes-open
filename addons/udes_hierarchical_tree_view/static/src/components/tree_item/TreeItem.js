odoo.define(
  "udes_hierarchical_tree_view/static/src/components/tree_item/TreeItem.js",
  function (require) {
    "use strict";
    const { Component } = owl;
    const patchMixin = require("web.patchMixin");
    const { useState } = owl.hooks;

    class TreeItem extends Component {
      /**
       * @override
       */
      constructor(...args) {
        super(...args);
        this.state = useState({
          isDraggedOn: false,
        });
      }

      toggleChildren() {
        if (this.props.item.hasOwnProperty('child_id')) {
          if (this.props.item.child_id.length > 0) {
            this.trigger("tree_item_clicked", { data: this.props.item });
          }
        }
        if (this.props.item.hasOwnProperty('child_ids')) {
          if (this.props.item.child_ids.length > 0) {
            this.trigger("tree_item_clicked", { data: this.props.item });
          }
        }
      }

      openFormView() {
        this.trigger("open_form_view", { data: this.props.item });
      }

      onDragstart(event) {
        event.dataTransfer.setData("TreeItem", JSON.stringify(this.props.item));
      }

      onDragover() { }

      onDragenter() {
        Object.assign(this.state, { isDraggedOn: true });
      }

      onDragleave() {
        Object.assign(this.state, { isDraggedOn: false });
      }

      onDrop(event) {
        Object.assign(this.state, { isDraggedOn: false });
        let droppedItem = JSON.parse(event.dataTransfer.getData("TreeItem"));
        if (
          droppedItem.id == this.props.item.id ||
          droppedItem.parent_id[0] == this.props.item.id
        ) {
          console.log("Dropping a node inside itself or same parent has no effect");
          return;
        }
        if (this.props.item.parent_path.startsWith(droppedItem.parent_path)) {
          console.log("Dropping a node inside child of itself is invalid");
          return;
        }
        this.trigger("change_item_tree", {
          itemMoved: droppedItem,
          newParent: this.props.item,
        });
      }
    }

    Object.assign(TreeItem, {
      components: { TreeItem },
      props: {
        item: {},
        countField: "",
        disableDragDrop: "",
        startUnfolded: "",
        showFormButton: "",
      },
      template: "udes_hierarchical_tree_view.TreeItem",
    });

    return patchMixin(TreeItem);
  }
);
