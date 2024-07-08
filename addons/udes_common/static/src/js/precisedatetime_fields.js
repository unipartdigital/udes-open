odoo.define('udes_common.basic_fields', function (require) {
"use strict";

var core = require('web.core');
var _t = core._t;
var _lt = core._lt;
var rpc = require('web.rpc');

var basicFields = require('web.basic_fields');
var FieldDate = basicFields.FieldDate;

var FieldPreciseDateTime = FieldDate.extend({
    description: _lt("Precise Date & Time"),
    supportedFieldTypes: ['precise_datetime'],

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * return the datepicker value
     *
     * @private
     */
    _getValue: function () {
        var value = this.datewidget.getValue();
        return value && value.add(-this.getSession().getTZOffset(value), 'minutes');
    },
    /**
     * @override
     * @private
     */
    _isSameValue: function (value) {
        if (value === false) {
            return this.value === false;
        }
        return value.isSame(this.value);
    },
    /**
     * Instantiates a new DateTimeWidget datepicker rather than DateWidget.
     *
     * @override
     * @private
     */
    _makeDatePicker: function () {
        var value = this.value && this.value.clone().add(this.getSession().getTZOffset(this.value), 'minutes');
        return new datepicker.DateTimeWidget(this, {defaultDate: value});
    },

    /**
     * Set the datepicker to the right value rather than the default one.
     *
     * @override
     * @private
     */
    _renderEdit: function () {
        var value = this.value && this.value.clone().add(this.getSession().getTZOffset(this.value), 'minutes');
        this.datewidget.setValue(value);
        this.$input = this.datewidget.$input;
    },
});


return {
    FieldPreciseDateTime: FieldPreciseDateTime,
};

});
