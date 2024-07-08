odoo.define('udes_stock.field_utils', function (require) {
"use strict";

/**
 * Field Utils
 *
 * This file contains two types of functions: formatting functions and parsing
 * functions.
 * A date
 * (or datetime) value is always stored as a Moment.js object, but displayed as
 * a string.  This file contains all sort of functions necessary to perform the
 * conversions.
 */

var core = require('web.core');
var dom = require('web.dom');
var session = require('web.session');
var time = require('web.time');
var field_utils = require('web.field_utils');
var utils = require('web.utils');

var _t = core._t;

//------------------------------------------------------------------------------
// Formatting
//------------------------------------------------------------------------------
/**
 * Returns a string representing a precise datetime.  If the value is false, then we
 * return an empty string.  Note that this is dependant on the localization
 * settings
 *
 * @params {Moment|false}
 * @param {Object} [field]
 *        a description of the field (note: this parameter is ignored)
 * @param {Object} [options] additional options
 * @param {boolean} [options.timezone=true] use the user timezone when formatting the
 *        date
 * @returns {string}
 */
function formatPreciseDateTime(value, field, options) {
    if (value === false) {
        return "";
    }
    value = field_utils.parse["precise_datetime"](value, field, options);
    if (!options || !('timezone' in options) || options.timezone) {
        value = value.clone().add(session.getTZOffset(value), 'minutes');
    }
    return value.format(time.getLangPreciseDatetimeFormat());
}

////////////////////////////////////////////////////////////////////////////////
// Parse
////////////////////////////////////////////////////////////////////////////////


/**
 * Create a Precise Datetime object
 * The method toJSON return the formatted value to send value server side
 *
 * @param {string} value
 * @param {Object} [field]
 *        a description of the field (note: this parameter is ignored)
 * @param {Object} [options] additional options
 * @param {boolean} [options.isUTC] the formatted date is utc
 * @param {boolean} [options.timezone=false] format the date after apply the timezone
 *        offset
 * @returns {Moment|false} Moment date object
 */
function parsePreciseDateTime(value, field, options) {
    if (!value) {
        return false;
    }
    var datePattern = time.getLangDateFormat(),
        timePattern = time.getLangTimeFormat();
    var datePatternWoZero = datePattern.replace('MM','M').replace('DD','D'),
        timePatternWoZero = timePattern.replace('HH','H').replace('mm','m').replace('ss','s');
    var pattern1 = datePattern + ' ' + timePattern;
    var pattern2 = datePatternWoZero + ' ' + timePatternWoZero;
    var precise_datetime;
    if (options && options.isUTC) {
        // phatomjs crash if we don't use this format
        precise_datetime = moment.utc(value.replace(' ', 'T') + 'Z');
    } else {
        precise_datetime = moment.utc(value, [pattern1, pattern2, moment.ISO_8601], true);
        if (options && options.timezone) {
            precise_datetime.add(-session.getTZOffset(precise_datetime), 'minutes');
        }
    }
    if (precise_datetime.isValid()) {
        if (precise_datetime.year() === 0) {
            precise_datetime.year(moment.utc().year());
        }
        if (precise_datetime.year() >= 1000) {
            precise_datetime.toJSON = function () {
                return this.clone().locale('en').format('YYYY-MM-DD HH:mm:ss.SSS');
            };
            return precise_datetime;
        }
    }
    throw new Error(_.str.sprintf(core._t("'%s' is not a correct precise datetime"), value));
}

field_utils.format.precise_datetime = formatPreciseDateTime;
field_utils.parse.precise_datetime = parsePreciseDateTime;

});
