# -*- coding: utf-8 -*-

# @TODO: Tidy, forms field read-only

from odoo import models, fields, api, SUPERUSER_ID, _
import logging

_logger = logging.getLogger(__name__)


REDACTED_TXT = _('Redacted')
PII_RELATIONS = [
    'partner_id', 'res_partner_id', 'author_id', 'partner_address_id',
    'owner_id', 'partner_shipping_id', 'partner_invoice_id',
    'order_partner_id', 'customer_id'
]


@api.model
def _read(self, result):
    """Redact fields based on res.user.u_view_customers"""
    if self.env.uid == SUPERUSER_ID or self.env.user.u_view_customers:
        for record in result:
            for field in record:
                if (field in PII_RELATIONS
                        and isinstance(record[field], tuple)
                        and self.env['res.partner'].sudo().search_count([
                            ('id', '=', record[field][0]),
                            ('customer', '=', True)])):
                                # Log PII has been viewed
                                _logger.info("User %s viewed Customer %s via %s.%s",
                                             self.env.uid, record[field][0], self._name, field)
        return result

    for record in result:
        for field in record:
            if (field in PII_RELATIONS
                    and isinstance(record[field], tuple)
                    and self.env['res.partner'].sudo().search_count([
                        ('id', '=', record[field][0]),
                        ('customer', '=', True)])):
                # Record ID remains and string value redacted
                record[field] = (record[field][0], REDACTED_TXT)
                _logger.info("%s: %s.%s", REDACTED_TXT, self._name, field)

    return result


class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.multi
    def name_get(self):
        """We rely on the ACL to limit access to this model, but we
           still need to redact data retrieved via joined queries
        """
        result = super(ResPartner, self).name_get()

        if self.env.uid == SUPERUSER_ID or self.env.user.u_view_customers:
            for record in result:
                if (isinstance(record, tuple)
                        and self.sudo().search_count([('id', '=', record[0]),
                                                      ('customer', '=', True)])):
                    # Log PII viewed
                    _logger.info("User %s viewed Customer %s via res.partner", self.env.uid, record[0])
                    
            return result

        redacted_result = []

        for record in result:
            if (isinstance(record, tuple)
                    and self.sudo().search_count([('id', '=', record[0]),
                                                  ('customer', '=', True)])):
                # Record ID remains and string value redacted
                redacted_result.append((record[0], REDACTED_TXT))
                _logger.info(REDACTED_TXT + ": res.partner")
            else:
                redacted_result.append(record)

        return redacted_result


class SaleOrder(models.Model):
    _inherit = "sale.order"

    @api.multi
    def read(self, fields=None, load='_classic_read'):
        result = super(SaleOrder, self).read(fields=fields, load=load)
        return _read(self, result)


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    @api.multi
    def read(self, fields=None, load='_classic_read'):
        result = super(SaleOrderLine, self).read(fields=fields, load=load)
        return _read(self, result)


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    @api.multi
    def read(self, fields=None, load='_classic_read'):
        result = super(StockPicking, self).read(fields=fields, load=load)
        return _read(self, result)
