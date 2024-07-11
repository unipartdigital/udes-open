odoo.define('udes_stock.basic_fields', function (require) {
"use strict";

var core = require('web.core');
var _t = core._t;
var rpc = require('web.rpc');

var registry = require("web.field_registry");
var basicFields = require('web.basic_fields');
var datepicker = require('web.datepicker');
var FieldDateTime = basicFields.FieldDateTime;

var FieldPreciseDateTime = FieldDateTime.extend({
    supportedFieldTypes: ['precise_datetime'],

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
