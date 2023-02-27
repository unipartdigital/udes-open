from odoo import fields, models


class Route(models.Model):
    _inherit = "stock.location.route"

    # Disable translation instead of renaming.
    name = fields.Char(translate=False)

    def write(self, values):
        """
        When in a route active field is changed, set the context with active_test = False which will
        ensure that will search even the inactive records and activate/inactivate them where needed.
        """

        if "active" in values and "active_test" not in self._context:
            self = self.with_context(active_test=False)
        return super(Route, self).write(values)
