odoo.define("udes_stock.FormController", function (require) {
  "use strict";

  var FormController = require("web.FormController");

  FormController.include({
    renderButtons: function () {
      this._super.apply(this, arguments);
      var hideCreateModels = ["stock.picking", "stock.inventory"];
      if (hideCreateModels.includes(this.modelName)) {
          this.$buttons.find("button.o_form_button_create").hide();
      }
    },
  });
});
