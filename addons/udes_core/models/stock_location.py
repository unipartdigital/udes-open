# -*- coding: utf-8 -*-

from odoo import fields, models,  _
from odoo.exceptions import ValidationError


class StockLocation(models.Model):
    _name = 'stock.location'
    # Add messages to locations.
    _inherit = ['stock.location', 'mail.thread']

    # Disable translation instead of renaming.
    name = fields.Char(translate=False)

    # Add tracking for archiving.
    active = fields.Boolean(track_visibility='onchange')

    def _prepare_info(self, extended=False, load_quants=False):
        """
            Prepares the following info of the location in self:
            - id: int
            - name: string
            - barcode: string

            When load_quants is True also return:
            - quant_ids: [{stock.quants}]
        """
        self.ensure_one()

        info = {"id": self.id,
                "name": self.name,
                "barcode": self.barcode,
                }
        if load_quants:
            info['quants_ids'] = self.quant_ids.get_info()

        return info

    def get_info(self, **kwargs):
        """ Return a list with the information of each location in self.
        """
        res = []
        for loc in self:
            res.append(loc._prepare_info(**kwargs))

        return res

    def get_location(self, location_identifier, no_results=False):
        """ Get locations from a name, barcode, or id.

            @param no_results: Boolean
                Allows to return empty recordset when the location is
                not found
        """
        if isinstance(location_identifier, int):
            domain = [('id', '=', location_identifier)]
        elif isinstance(location_identifier, str):
            domain = ['|', ('barcode', '=', location_identifier),
                           ('name', '=', location_identifier)]
        else:
            raise ValidationError(_('Unable to create domain for location search from identifier of type %s') % type(location_identifier))

        results = self.search(domain)
        if not results and not no_results:
            raise ValidationError(_('Location not found for identifier %s') % str(location_identifier))
        if  len(results) > 1:
            raise ValidationError(_('Too many locations found for identifier %s') % str(location_identifier))

        return results
