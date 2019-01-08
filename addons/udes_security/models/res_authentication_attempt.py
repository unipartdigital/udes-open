from odoo import api, models


class ResAuthenticationAttempt(models.Model):
    _inherit = 'res.authentication.attempt'
    _name = 'res.authentication.attempt'

    @api.model
    def _hits_limit(self, limit, remote, login=None, *args, **kwargs):
        """ Override _hits_limit method to ignore non-user specific IP bans
         if configured to """
        check_by_ip = int(self.env["ir.config_parameter"].sudo()
                          .get_param("auth_brute_force.check_by_ip", 0))
        if not login and check_by_ip == 0:
            return False
        return super()._hits_limit(limit, remote, login, *args, **kwargs)
