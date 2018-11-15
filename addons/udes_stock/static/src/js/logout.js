odoo.define('udes.stock.logout', function (require) {

  var core = require('web.core');
  var logout = core.action_registry.get("logout");
  var ajax = require('web.ajax');
  var Dialog = require('web.Dialog');

  error = function (msg) {
    Dialog.alert(self, _(msg), {title: _("Error")});
  };

  logout_override = function () {
    test = ajax.jsonRpc("/api/stock-picking-batch/check-user-batches/", 'call').then(function (data) {
      if (data.error) {
        error(data.error);
      } else {
        if (data != false) {
          // Ask user to confirm logout
          Dialog.confirm(self, _("You still have work assigned - are you sure you wish to logout?"),{
            confirm_callback: function () { logout(); },
            cancel_callback: function () {},
            title: _('Confirm logout'),
          });
        } else {
          // No batches, logout.
          logout();
        }
      }
    });
  };

  core.action_registry.add('logout', logout_override);
});
