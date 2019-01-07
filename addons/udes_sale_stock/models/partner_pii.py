# -*- coding: utf-8 -*-

# @TODO: EDI, testing, tidy

from odoo import models, fields, api, SUPERUSER_ID, _
import logging

_logger = logging.getLogger(__name__)

PII_FIELDS = [
    'name', 'display_name', 'title', 'phone', 'mobile', 'email', 'street', 'street2', 'city', 'zip'
]

@api.model
def _read(self, result, fields=None):
    """Redact fields based on res.user.u_view_customers"""

    if self.env.uid == SUPERUSER_ID or self.env.user.u_view_customers:
        return result
    
    redacted = _('Redacted')
    
    if fields is None:
        fields = ['partner_id']
        redacted = False

    for record in result:          
        for field in record:
            if field in fields:
                _logger.info("Field redacted: %s", field)
                record[field] = redacted

    return result


class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.multi
    def read(self, fields=None, load='_classic_read'):

        result = super(ResPartner, self).read(fields=fields, load=load)
        return _read(self, result, PII_FIELDS)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    @api.multi
    def read(self, fields=None, load='_classic_read'):

        result = super(SaleOrder, self).read(fields=fields, load=load)
        return _read(self, result)


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    @api.multi
    def read(self, fields=None, load='_classic_read'):

        result = super(StockPicking, self).read(fields=fields, load=load)
        return _read(self, result)

