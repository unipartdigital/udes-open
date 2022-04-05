# -*- coding: utf-8 -*-

from odoo import api, models, _


class StockInventoryLine(models.Model):
    _inherit = 'stock.inventory.line'

    @api.constrains('location_id')
    def _check_location_not_blocked(self):
        """
        Check if any of the inventory line locations are blocked
        """
        self.location_id.check_blocked(prefix=_('Cannot create inventory adjustment line.'))


class StockInventory(models.Model):
    _inherit = "stock.inventory"

    @api.constrains('location_ids')
    def _check_location_not_blocked(self):
        """
        Check if any of the locations are blocked
        """
        self.location_ids.check_blocked(prefix=_('Cannot create inventory adjustment.'))

    def _action_done(self):
        """
        Check if any of the inventory or inventory line locations are blocked
        """
        self.location_ids.check_blocked(prefix=_('Cannot validate inventory adjustment.'))
        self.line_ids.location_id.check_blocked(prefix=_('Cannot validate inventory adjustment line.'))

        return super(StockInventory, self)._action_done()
