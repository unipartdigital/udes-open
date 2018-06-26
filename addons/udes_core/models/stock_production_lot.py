# -*- coding: utf-8 -*-

from odoo import models, _
from odoo.exceptions import ValidationError


class StockProductionLot(models.Model):
    _inherit = 'stock.production.lot'
    _name = 'stock.production.lot'

    def get_lot(self, lot_identifier, product_id,
                create=False, no_results=False):
        """
        Get or create a lot specified by the related product and a
        reference that can be the name or id (respectively, string or
        integer arguments - the dispatch will be made on the arg type).

        Raise a ValidationError in case:
         - of unexpected 'lot_identifier' type;
         - no lot is found nor created;
         - multiple lots are found.

        @param lot_identifier: Lot identifier (string or integer)
        @param product_id: Relevant product id (integer)
        @param create: Boolean
            When it is True and lot_identifier is a name,
            a lot will be created if it does not exist
        @param no_results: Boolean
            Return empty recordset when the lot is not found;
            prevents the creation of a new lot
        """
        name = None
        domain = [('product_id', '=', product_id)]

        if isinstance(lot_identifier, int):
            domain.append(('id', '=', lot_identifier))
        elif isinstance(lot_identifier, str):
            domain.append(('name', '=', lot_identifier))
            name = lot_identifier
        else:
            raise ValidationError(
                _('Unable to create domain for lot search from identifier '
                  'of type %s') % type(lot_identifier))

        results = self.search(domain)

        if not results and not no_results:
            if not create or not name:
                # if `create` was flagged, `name` was not provided
                # or an empty string was passed
                raise ValidationError(_('Lot not found for identifier %s')
                                      % str(lot_identifier))

            results = self.create({'name': name,
                                   'product_id': product_id})

        if len(results) > 1:
            raise ValidationError(
                _('Too many lot instances found for identifier %s')
                % str(lot_identifier))

        return results

    def _prepare_info(self):
        """
            Prepares the following info of the lot in self:
            - id: int
            - name: string
        """
        self.ensure_one()

        res = {"id": self.id,
               "name": self.name,
               }

        return res

    def get_info(self):
        """ Return a list with the information of each lot in self.
        """
        res = []
        for lot in self:
            res.append(lot._prepare_info())

        return res
