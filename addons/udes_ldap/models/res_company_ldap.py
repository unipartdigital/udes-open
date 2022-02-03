"""
UDES LDAP configuration model.

In this model we override the standard authentication approach by using the
credentials of the logging-in user to search for themselves on the LDAP
server.  This removes the need for a service account to perform the search.
"""

from ldap.dn import escape_dn_chars
from odoo import models, fields


class CompanyLDAP(models.Model):
    """LDAP configuration model."""

    _inherit = "res.company.ldap"

    u_ldap_binddn_fmt = fields.Char(
        string="LDAP Binddn Format",
        help="A format string for the Distinguished Name used to bind to the "
        "LDAP server.  The user's uid will be formatted into this string.",
        default="",
        required=True,
    )

    def get_ldap_dicts(self):
        """Add our custom field to the conf dict and removed unused fields."""
        res = super().get_ldap_dicts()
        fields_to_remove = ["ldap_binddn", "ldap_password"]
        for rec in res:
            ldap = self.sudo().browse(rec["id"])
            rec["u_ldap_binddn_fmt"] = ldap.u_ldap_binddn_fmt
            for field in fields_to_remove:
                rec.pop(field, None)
        return res

    def authenticate(self, conf, login, password):
        """
        Set the login credentials before the superclass authenticates.

        We use the login credentials provided by the user to bind to the LDAP
        server.
        """
        # The login name is untrusted and must be escaped to prevent
        # LDAP-injection attacks.
        escaped_login = escape_dn_chars(login)
        # Use %-formatting to be consistent with ldap_filter, as we don't
        # want to change python-ldap.
        binddn = conf["u_ldap_binddn_fmt"] % escaped_login
        conf["ldap_binddn"] = binddn
        conf["ldap_password"] = password
        # We don't pass the escaped login because it gets escaped when the
        # filter is created.
        # TODO Does user creation work if login contains exotic characters?
        return super().authenticate(conf, login, password)
