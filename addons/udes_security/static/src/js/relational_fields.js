odoo.define("udes_security.relational_fields", function (require) {
  "use strict";

    var relational_fields = require('web.relational_fields');
    var Dialog = require('web.Dialog');
    var core = require('web.core');

    var _t = core._t;
    var FieldMany2One = relational_fields.FieldMany2One;

    // Creating a new M2ODialog class variable which is same as the one created in web module with
    // the change the Create button is removed. The one created in web module can not be overridden
    // as it is not returned.
    var udesM2ODialog = Dialog.extend({
        template: "M2ODialog",
        init: function (parent, name, value) {
            this.name = name;
            this.value = value;
            this._super(parent, {
                title: _.str.sprintf(_t("Create a %s"), this.name),
                size: 'medium',
                buttons: [{
                    text: _t('Create and edit'),
                    classes: 'btn-primary',
                    close: true,
                    click: function () {
                        this.trigger_up('search_create_popup', {
                            view_type: 'form',
                            value: this.$('input').val(),
                        });
                    },
                }, {
                    text: _t('Cancel'),
                    close: true,
                }],
            });
        },
        start: function () {
            this.$("p").text(_.str.sprintf(_t("You are creating a new %s, are you sure it does not exist yet?"), this.name));
            this.$("input").val(this.value);
        },
        /**
         * @override
         * @param {boolean} isSet
         */
        close: function (isSet) {
            this.isSet = isSet;
            this._super.apply(this, arguments);
        },
        /**
         * @override
         */
        destroy: function () {
            if (!this.isSet) {
                this.trigger_up('closed_unset');
            }
            this._super.apply(this, arguments);
        },
    });

    // Override Many2One field to change core behaviours.
    FieldMany2One.include({
        init: function () {
            this._super.apply(this, arguments);

            var no_quick_create = this.nodeOptions.no_quick_create;

            // If no_quick_create option is not specified then disable quick create by default
            if (no_quick_create == null) {
                this.nodeOptions.no_quick_create = true;
            }
        },

        // Override without super, in this way only the udesM2ODialog
        // will show not M2ODialog which is in web module
        _onInputFocusout: function () {
            if (this.can_create && this.floating) {
                new udesM2ODialog(this, this.string, this.$input.val()).open();
            }
        },
    })

});
