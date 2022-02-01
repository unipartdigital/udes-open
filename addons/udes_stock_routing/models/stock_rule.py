from odoo import api, fields, models


class StockRule(models.Model):
    _inherit = "stock.rule"

    u_push_on_drop = fields.Boolean(
        "Push on Drop-off",
        default=False,
        help="When stock is dropped in the "
        "from_location of this path, "
        "automatically push it onwards.",
    )

    @api.model
    def get_path_from_location(self, location):
        """
        Find a single stock.rule for which the given location is
        a valid starting location. If one not found return an empty recordset. 
        Search for the stock.rules attached to the parent locations of location. If there is more than one stock.rule in the location hierarchy,
        sort them by choosing the parent_path with the largest integer at the end of its path. This is the closest parent location to the input
        location and hence the most relevant stock.rule. 
        Note: If there is more than one stock.rule defined on the closest location, the newest stock.rule on that location will be chosen. 
        """
        Rule = self.env["stock.rule"]
        push_steps = Rule.search(
            [
                (
                    "location_src_id",
                    "parent_of",
                    [
                        location.id,
                    ],
                ),
                ("u_push_on_drop", "=", True),
            ]
        )
        if push_steps:
            return push_steps.sorted(key=lambda p: p.location_src_id.parent_path.strip("/").split("/")[-1], reverse=True)[0]
        return self.browse()

    def _run_push(self, move):
        """
        Odoo has default behaviour to create another picking after a move is confirmed. Don't want this functionality
        if u_push_on_drop is turned on.    
        """
        if self.u_push_on_drop:
            return 
        return super()._run_push(move)
