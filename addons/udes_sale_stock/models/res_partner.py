import logging
from odoo import _, api, fields, models, SUPERUSER_ID
from odoo.exceptions import AccessError

_logger = logging.getLogger(__name__)

class Partner(models.Model):

    _inherit = "res.partner"

    @api.model
    def search(self, args, offset=0, limit=None, order=None, count=False):
        """ Rule does not apply to administrator, group_inbound_user do not see customers. """
        if self._uid != SUPERUSER_ID and self.env['res.users'].has_group('udes_stock.group_inbound_user'):
            args = ['&', ('customer', '=', False)] + list(args)
            _logger.info('udes_stock.group_inbound_user search limited to none customers in search')
        
        return super(Partner, self).search(args, offset, limit, order, count=count)

    @api.multi
    def read(self, fields=None, load='_classic_read'):
        """ Group_inbound_user do not see customers. """
        result = super(Partner, self).read(fields, load=load)
        if self._uid != SUPERUSER_ID and self.env['res.users'].has_group('udes_stock.group_inbound_user'):
            for record in result:                                
                if record.get('customer') and record['customer'] == True:
                    _logger.info('udes_stock.group_inbound_user search limited to none customers in read')
                    raise AccessError(_("Inbound User Group does not have access to customers"))

        return result