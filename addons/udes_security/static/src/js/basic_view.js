odoo.define('udes_security.basic_vew', function (require) {
    "use strict";

    var BasicView = require('web.BasicView');

    BasicView.include({
        init: function (viewInfo, params) {
            this._super.apply(this, arguments);
            
            if (viewInfo.hasOwnProperty('readonly_desktop_user')){
                this.controllerParams.archiveEnabled = !viewInfo.readonly_desktop_user;
            }
        },
    });
});
