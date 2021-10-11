odoo.define('udes_security.kanban_renderer', function (require) {
    "use strict";

    var KanbanRenderer = require('web.KanbanRenderer');

    KanbanRenderer.include({
        _renderGrouped: function (fragment) {
            this._super.apply(this, arguments);
    
            if (this.arch.attrs.draggable==="false"){
                this.$el.sortable("disable");
            }
    
        },
    });
});
