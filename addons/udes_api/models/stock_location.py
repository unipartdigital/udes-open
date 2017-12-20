# -*- coding: utf-8 -*-

from odoo import api, models, fields

class StockLocation(models.Model):
    _inherit = "stock.location"


    @api.multi
    def _prepare_info(self, extended=False, load_quants=False):
        """ TODO: add docstring

            id: stock.location.id
            name: stock.location.name
            barcode: stock.location.barcode

            When extended is True also return:

            u_blocked   boolean     Whether the location has been blocked. If it has been blocked, stock should not be moved to/from this location.
            u_blocked_reason    string  A descriptive reason why the location has been blocked.
            quant_ids   [{stock.quants]}    A list of all the quants at the given location.
        """
        self.ensure_one()

        info = {"id": self.id,
                "name": self.name,
                "barcode": self.barcode,
               }
        if extended:
            info['u_blocked'] = self.u_blocked
            info['u_blocked_reason'] = self.u_blocked_reason
        if load_quants:
            info['quants_ids'] = self.quant_ids.get_info()

        return info 

    @api.multi
    def get_info(self, extended=False, load_quants=False):
        """ TODO: add docstring
        """
        res = []
        for loc in self:
            res.append(loc._prepare_info(extended=extended, load_quants=load_quants))

        return res


    def get_location(self, location_identifier):
        """ Get locations from a name, barcode, or id.
        """
        if isinstance(location_identifier, int):
            domain = [('id', '=', location_identifier)]
        elif isinstance(location_identifier, str):
            domain = ['|', ('barcode', '=', location_identifier),
                           ('name', '=', location_identifier)]
        else:
            raise ValidationError(_('Unable to create domain for location search from identifier of type %s') % type(location_identifier))

        results = self.search(domain)
        if not results:
            raise ValidationError(_('Location not found for identifier %s') % str(location_identifier))
        if  len(results) > 1:
            raise ValidationError(_('Too many locations found for identifier %s') % str(location_identifier))

        return results

