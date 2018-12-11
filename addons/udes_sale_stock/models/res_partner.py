import logging
from odoo import api, fields, models, SUPERUSER_ID

_logger = logging.getLogger(__name__)

class Partner(models.Model):

    _inherit = "res.partner"

    @api.model
    def search(self, args, offset=0, limit=None, order=None, count=False):

        # Rule does not apply to administrator, group_inbound_user do not see customers
        if self._uid != SUPERUSER_ID and self.env['res.users'].has_group('udes_stock.group_inbound_user'):
            args = ['&', ('customer', '=', False)] + list(args)

            _logger.info('udes_stock.group_inbound_user search limited to none customers')
        
        return super(Partner, self).search(args, offset, limit, order, count=count)
