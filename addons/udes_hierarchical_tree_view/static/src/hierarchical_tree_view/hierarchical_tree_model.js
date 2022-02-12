odoo.define("udes_hierarchical_tree_view.HierarchicalTreeModel", function (require) {
  "use strict";

  var AbstractModel = require("web.AbstractModel");

  const HierarchicalTreeModel = AbstractModel.extend({
    /**
     * Make an RPC 'write' method call to update the parent_id of
     * an existing record.
     *
     * @param {integer} id ID Of the item we want to update
     * @param {integer} parent_id The parent item ID
     */
    changeParent: async function (id, parent_id) {
      await this._rpc({
        model: this.modelName,
        method: "write",
        args: [
          [id],
          {
            parent_id: parent_id,
          },
        ],
      });
    },

    /**
     * Refresh a node get fresh data from the server for a given item.
     * A search_read is executed via RPC Call and then the item is modified
     * in place in the hierarchical tree structure.
     *
     * @param {integer} id ID Of the item we want to refresh
     */
    refreshNode: async function (id) {
      var self = this;
      var result = null;
      await this._rpc({
        model: this.modelName,
        method: "read",
        args: [[id], []],
      }).then(function (itemUpdated) {
        let path = itemUpdated[0].parent_path;
        let target_node = self.__target_parent_node_with_path(
          path.split("/").filter((i) => i),
          self.data.items
        );
        target_node = itemUpdated[0];
        result = itemUpdated[0];
      });
      return result;
    },

    /**
     * Make an RPC call to get the child of the target itm then navigates
     * the nodes to the target the item and assign its "children" property
     * to the result of the RPC call.
     *
     * @param {integer} parentId Category we will "open/expand"
     * @param {string} path The parent_path represents the parents ids like "1/3/32/123/"
     */
    expandChildrenOf: async function (parentId, path) {
      var self = this;
      await this._rpc({
        model: this.modelName,
        method: "search_read",
        kwargs: {
          domain: [["parent_id", "=", parentId]],
        },
      }).then(function (children) {
        var target_node = self.__target_parent_node_with_path(
          path.split("/").filter((i) => i),
          self.data.items
        );
        target_node.children = children;
        if (target_node.hasOwnProperty("child_id")) {
          target_node.child_id = children.map((i) => i.id);
        }
        if (target_node.hasOwnProperty("child_ids")) {
          target_node.child_ids = children.map((i) => i.id);
        }
        target_node.childrenVisible = true;
      });
    },

    toggleChildrenVisibleForItem: async function (item) {
      var target_node = this.__target_parent_node_with_path(
        item.parent_path.split("/").filter((i) => i),
        this.data.items
      );
      target_node.childrenVisible = !target_node.childrenVisible;
    },

    recursivelyOpenParents: async function (item) {
      var self = this;
      await this._rpc({
        model: this.modelName,
        method: "read",
        args: [[item.parent_id[0]], []],
      }).then(async function (parent) {
        if (parent[0] && parent[0].id) {
          const directParent = parent[0];
          directParent.children = [item];
          directParent.childrenVisible = true;
          return await self.recursivelyOpenParents(directParent);
        } else {
          self.data.items = [item];
          return true;
        }
      });
    },
    /**
     * Search for the Node corresponding to the given path.
     * Paths are present in the property `parent_path` of any nested item they are
     * in the form "1/3/32/123/" we have to split the string to manipulate an Array.
     * Each item in the Array will correspond to an item ID in the tree, each one
     * level deeper than the last.
     *
     * @private
     * @param {Array} path for example ["1", "3", "32", "123"]
     * @param {Array} items the items to search in
     * @param {integer} n The current index of deep inside the tree
     * @returns {Object|undefined} the tree Node corresponding to the path
     **/
    __target_parent_node_with_path: function (path, items, n = 0) {
      for (const item of items) {
        if (item.id == parseInt(path[n])) {
          if (n < path.length - 1) {
            return this.__target_parent_node_with_path(
              path,
              item.children,
              n + 1
            );
          } else {
            return item;
          }
        }
      }
      return undefined;
    },

    __get: function () {
      return this.data;
    },

    __load: function (params) {
      this.modelName = params.modelName;
      this.domain = [["parent_id", "=", false]];
      this.data = {};
      return this._fetchData();
    },

    __reload: function (handle, params) {
      this.domain = [["parent_id", "=", false]];
      if (params && params.domain && params.domain.length > 0) {
        return this._fetchFilteredData(params.domain);
      } else {
        return this._fetchData();
      }
    },

    _fetchData: function () {
      var self = this;
      return this._rpc({
        model: this.modelName,
        method: "search_read",
        kwargs: {
          domain: this.domain,
        },
      }).then(function (result) {
        self.data.items = result;
      });
    },

    _fetchFilteredData: async function (domain) {
      var self = this;
      await this._rpc({
        model: this.modelName,
        method: "search_read",
        kwargs: {
          domain: domain,
        },
      }).then(async function (result) {
        for (const item of result) {
          return await self.recursivelyOpenParents(item);
        }
      });
    },
  });

  return HierarchicalTreeModel;
});
