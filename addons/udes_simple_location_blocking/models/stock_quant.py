from odoo import models


class StockQuant(models.Model):
    _inherit = 'stock.quant'

    def _gather(self, product_id, location_id, **kwargs):
        """ Filter quants of blocked locations.
            It is done afterwards because location_id might
            an ancestor of the quants locations.
        """
        quants = super(StockQuant, self)._gather(product_id, location_id, **kwargs)
        return quants.filtered(lambda q: not q.location_id.u_blocked)
