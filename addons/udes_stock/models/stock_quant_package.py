# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from collections import defaultdict


class StockQuantPackage(models.Model):
    _name = 'stock.quant.package'
    _inherit = ['stock.quant.package', 'mixin.stock.model']
    _description = 'Package'

    # Enable create packages
    MSM_CREATE = True

    def get_quantities_by_key(self, get_key=lambda q: q.product_id):
        """ This function computes the product quantities for the given package grouped by a key
            :args:
                get_key: a callable which takes a quant and returns the key
        """
        return self._get_contained_quants().get_quantities_by_key(get_key=get_key)

    def mls_can_fulfil(self, mls):
        """ Returns mls which the package can fulfil. If the product_qty of the
            mls is larger than in the package (i.e. in self) the mls will be split.
            :args:
                mls: move lines to check against
            :returns: the move lines the package can fulfil, and those split out that it can't
        """
        MoveLines = self.env['stock.move.line']

        pack_quantities = self.get_quantities_by_key()
        can_fulfil_mls = MoveLines.browse()
        excess_mls = MoveLines.browse()
        for prod, mls_grp in mls.groupby('product_id'):
            pack_qty = pack_quantities.get(prod, 0)
            if pack_qty == 0:
                # just skip over
                continue
            fulfil_mls, excess_ml, _ = mls_grp.move_lines_for_qty(pack_qty)
            can_fulfil_mls |= fulfil_mls
            if excess_ml:
                excess_mls |= excess_ml
        return can_fulfil_mls, excess_mls

    def has_same_content(self, other, get_key=lambda q: q.product_id):
        """ Compare the content of current packages with the content of other packages
            :args:
                - other: Other package to compare with
            :kwargs:
                - get_key: what to compare, dictionary method
            :returns:
                - Boolean flag, true if packages in self are the same as the packages in other (based on comparison method)
        """
        return frozenset(self.get_quantities_by_key(get_key=get_key)) == frozenset(other.get_quantities_by_key(get_key=get_key))

    def find_move_lines(self, aux_domain=None):
        """ Find move lines related to the package.
            Expects a singleton package.
            :kwargs:
               - A further aux domain can be specified for searching
                 move lines, defaults to in progress
            :returns: a recordset with the move lines in progress.
        """
        MoveLine = self.env['stock.move.line']

        if aux_domain is None:
            aux_domain = [('state', 'not in', ['done', 'cancel'])]
        domain = [('package_id', 'in', self.ids)] + aux_domain
        move_lines = MoveLine.search(domain)
        return move_lines

    def get_reserved_quantity(self):
        """ Returns the quantity in package that is reserved """
        return sum(self._get_contained_quants().mapped('reserved_quantity'))
