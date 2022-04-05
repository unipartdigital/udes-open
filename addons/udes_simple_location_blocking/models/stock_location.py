from odoo import api, models, fields, _
from odoo.exceptions import ValidationError


class StockLocation(models.Model):
    _inherit = "stock.location"

    u_blocked = fields.Boolean(
        string="Is Blocked?",
        help=_("Check this box to prevent stock picks from this location"),
        index=True,
    )

    u_blocked_reason = fields.Char(string="Reason for Block:", required=False)

    def check_blocked(self, prefix="", extra=[]):
        """
        Checks if any of the locations in self are blocked and if blocked raise a ValidationError.

        :param prefix: string
        :param prefix: list: names of Boolean fields to use to filter blocked locations
        """
        if not isinstance(prefix, str):
            raise ValidationError(_("Prefix parameter for check_blocked should be string"))
        blocked_locations = self.filtered(lambda x: x.u_blocked)
        if not isinstance(extra, list):
            raise ValidationError(_("Extra parameter for check_blocked should be list"))
        for field in extra:
            blocked_locations = self.filtered(lambda x: getattr(x, field))
        if blocked_locations:
            raise ValidationError(
                _("%s %s Please speak to a team leader to resolve the issue.")
                % (prefix, "".join(blocked_locations._prepare_blocked_msg()))
            )

    def _prepare_blocked_msg(self):
        """
        Prepares a message for the locations depending on if it is blocked or not.
        """
        msg = []
        for location in self:
            if location.u_blocked:
                reason = _("(reason: no reason specified)")
                if location.u_blocked_reason:
                    reason = _("(reason: %s)") % (str(location.u_blocked_reason))
                msg.append(_("Location %s is blocked %s.") % (location.name, reason))
            else:
                msg.append(_("Location %s is not blocked.") % location.name)
        msg = " ".join(msg)
        return msg

    @api.onchange("u_blocked")
    def onchange_u_blocked(self):
        """Empty blocked reason when locations are unblocked"""
        if not self.u_blocked:
            self.u_blocked_reason = ""

    @api.constrains("u_blocked")
    def _check_reserved_quants_and_blocked_reason(self):
        """
        Check if there is any stock.quant already reserved for the locations trying to be blocked.
        Also check if a blocked reason is given when blocking the location.
        """
        Quant = self.env["stock.quant"]
        for record in self:
            if record.u_blocked:
                n_quants = Quant.search_count(
                    [
                        ("reserved_quantity", ">", 0),
                        ("location_id", "=", record.id),
                    ]
                )
                if n_quants > 0:
                    raise ValidationError(
                        _("Location cannot be blocked because it contains reserved stock.")
                    )
                if not record.u_blocked_reason:
                    raise ValidationError(
                        _("A reason for blocking the locations is required when attempting to block a location.")
                    )
