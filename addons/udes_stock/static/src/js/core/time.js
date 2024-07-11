odoo.define('udes_stock.time', function (require) {
"use strict";

var translation = require('web.translation');
const time = require('web.time');

var _t = translation._t;

/**
 * Get precise date time format of the user's language
 */
function getLangPreciseDatetimeFormat() {
    // TODO can be improved to take the milliseconds format from database parameters
    return time.strftime_to_moment_format(_t.database.parameters.date_format + " " + _t.database.parameters.time_format) + ".SSS";
}

time.getLangPreciseDatetimeFormat = getLangPreciseDatetimeFormat;

return time;

});
