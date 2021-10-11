odoo.define('udes_security.calendar_view', function (require) {
    "use strict";

    var CalendarView = require('web.CalendarView');

    CalendarView.include({
        init: function (viewInfo, params) {
            this._super.apply(this, arguments);

            if (viewInfo.hasOwnProperty('readonly_desktop_user')){
                let canEdit = !viewInfo.readonly_desktop_user;
                this.loadParams.editable = canEdit;
                this.loadParams.creatable = canEdit;
            }
        },
    });
});
