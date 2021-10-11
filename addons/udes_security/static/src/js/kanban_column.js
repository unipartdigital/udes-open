odoo.define('udes_security.kanban_column', function (require) {
    "use strict";

    var KanbanColumn = require('web.KanbanColumn');

    KanbanColumn.include({
        init: function (parent, data, options, recordOptions) {
            this._super(parent, data, options, recordOptions);

            if (this.has_active_field && parent.arch.attrs.hasOwnProperty('readonly_desktop_user')){
                let canEdit = !parent.arch.attrs.readonly_desktop_user;
                this.has_active_field = canEdit;
            }
        },
        start: function () {
            this._super.apply(this, arguments);

            if (this.draggable==false){
                this.$el.sortable("disable");
            }
    
        },
    });
});
