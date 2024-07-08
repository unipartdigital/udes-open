odoo.define('udes_common.basic_fields', function (require) {
"use strict";

var core = require('web.core');
var _t = core._t;
var rpc = require('web.rpc');

var registry = require("web.field_registry");
var basicFields = require('web.basic_fields');
var datepicker = require('web.datepicker');
var FieldDate = basicFields.FieldDate;

var FieldPreciseDateTime = FieldDate.extend({
    supportedFieldTypes: ['precise_datetime'],

    init: function () {
        this._super.apply(this, arguments);
        if (this.value) {
            this.value = this._parseValue(this.value);
            var offset = this.getSession().getTZOffset(this.value);
            var displayedValue = this.value.clone().add(offset, 'minutes');
            this.datepickerOptions.defaultDate = displayedValue;
        }
    },

    // No to raise error in case precise datetime fields are editable. Not suggested to have editable precise datetime
    // fields as user cannot input milliseconds from datepicker.
    _makeDatePicker: function () {
        var parsed_value = this.value && this._parseValue(this.value);
        var value = parsed_value && parsed_value.add(this.getSession().getTZOffset(parsed_value), 'minutes');
        return new datepicker.DateTimeWidget(this, {defaultDate: value});
    },

});

registry.add("precise_datetime", FieldPreciseDateTime);

return {
    FieldPreciseDateTime: FieldPreciseDateTime,
};

});
