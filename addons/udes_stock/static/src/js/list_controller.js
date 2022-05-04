odoo.define('udes_stock.ListController', function (require) {
"use strict";

var ListController = require('web.ListController');
var Dialog = require('web.Dialog');
var core = require('web.core');

var _t = core._t;

ListController.include({

    _onToggleArchiveState: function (archive) {
        //Override the method in order to add a confirm dialog before archiving or unarchiving the selected records
        var self = this;
        function archiveThem() {
            return self._archive(self.selectedRecords, archive);
        }
        if (archive) {
            Dialog.confirm(this, _t("Are you sure you want to archive these records? They will become unavailable and hidden from searches."), {
                confirm_callback: archiveThem,
            });
        } else {
            Dialog.confirm(this, _t("Are you sure you want to unarchive these records?"), {
                confirm_callback: archiveThem,
            });
        }
    },

});

});
