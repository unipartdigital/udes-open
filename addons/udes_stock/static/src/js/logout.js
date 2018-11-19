odoo.define('udes.stock.logout', function (require) {

  var core = require('web.core');
  var logout = core.action_registry.get("logout");
  var ajax = require('web.ajax');
  var Dialog = require('web.Dialog');

  error = function (msg) {
    Dialog.alert(self, _(msg), {title: _("Error")});
  };

  logout_override = function () {
    var errMsg = _("Failed to retrieve picking batches");

    ajax.jsonpRpc("/api/stock-picking-batch/check-user-batches/", "call"
    ).then(function (data) {
      if (data == null) {
        error(errMsg);
      } else if (data.error) {
        error(data.error);
      } else if (data === true) {
        // Ask user to confirm logout
        var confirmMsg =  _("You still have work assigned - are you sure you "
                            + "wish to logout?");
        Dialog.confirm(self, confirmMsg, {
          confirm_callback: logout,
          cancel_callback: function () {},
          title: _('Confirm logout'),
        });
      } else {
        // No batches, logout.
        logout();
      }
    }).fail(function (err) {
      error(errMsg + ": " + err.data.message);
    });
  };

  core.action_registry.add('logout', logout_override);
});
