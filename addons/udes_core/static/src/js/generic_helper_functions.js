odoo.define('udes_core.GenericHelperFunctions', function (require) {
  "use strict";

  return {

    /**
     * Parse params from the location hash
     * @param str String to parse
     * @returns {Dictionary of hash values}
     */
    parseUrlParams: function (str) {
      var pieces = str.split("&"), data = {}, i, parts;
      // process each query pair
      for (i = 0; i < pieces.length; i++) {
        parts = pieces[i].split("=");
        if (parts.length < 2) {
          parts.push("");
        }
        data[decodeURIComponent(parts[0])] = decodeURIComponent(parts[1]);
      }
      return data;
    }

  }

});