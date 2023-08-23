odoo.define("udes_security.mail_utils", function (require) {
  "use strict";

  var mail_utils = require("mail.utils");

  function udes_addLink(node, transformChildren) {
    if (node.nodeType === 3) {  // text node
	// Don't add automatic link to url text which happens in mail_utils.addLink
        return node.textContent;
    }
    if (node.tagName === "A") return node.outerHTML;
    transformChildren();
    return node.outerHTML;
  }

  // Override mail.utils function
  mail_utils.addLink = udes_addLink;

});
