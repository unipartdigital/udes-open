# -*- coding: utf-8 -*-

from odoo import models, _
from odoo.exceptions import ValidationError

from collections import defaultdict

import logging
_logger = logging.getLogger(__name__)


def _update_move_lines_and_log_swap(move_lines, pack, other_pack):
    """ Set the package ids of the specified move lines to the one
        of the other package and signal the package swap by posting
        a message to the picking instance of the first move line.

        Assumes that both packages are singletons and that the
        specified move lines are a non empty recordset.
    """
    move_lines.with_context(bypass_reservation_update=True)\
              .write({"package_id": other_pack.id,
                      "result_package_id": other_pack.id})
    msg = _("Package %s swapped for package %s.") % (pack.name, other_pack.name)
    move_lines[0].picking_id.message_post(body=msg)
    _logger.info(msg)


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def add_unexpected_parts(self, product_quantities):
        """ Extend function to check if the picking_type of the picking
            is allowed to overreceive, otherwise raise an error.
        """
        Product = self.env['product.product']
        self.ensure_one()

        if self.picking_type_id.u_over_receive:
            new_move_lines = super(StockPicking, self).add_unexpected_parts(product_quantities)
        else:
            overreceived_qtys = ["%s: %s" % (Product.get_product(id).name, qty)
                                 for id, qty in product_quantities.items()]
            raise ValidationError(
                    _("We are not expecting these extra quantities of"
                      " these parts:\n%s\nPlease either receive the right"
                      " amount and move the rest to probres, or if they"
                      " cannot be split, move all to probres.") %
                    '\n'.join(overreceived_qtys))

        return new_move_lines

    def _get_package_search_domain(self, package):
        """ Override to handle multiple levels of packages
        """
        return ['|', ('move_line_ids.package_id', 'child_of', package.id),
                '|', ('move_line_ids.result_package_id', 'child_of', package.id),
                ('move_line_ids.u_result_parent_package_id', '=', package.id)]

    def is_compatible_package(self, package_name):
        """ The package with name package_name is compatible
            with the picking in self if:
            - The package does not exist
            - The package is not in stock
            - The package has not been used in any other picking
        """
        Picking = self.env['stock.picking']
        Package = self.env['stock.quant.package']

        self.ensure_one()
        self.assert_valid_state()

        res = True
        pickings = Picking.get_pickings(package_name=package_name)
        if len(pickings) == 0:
            package = Package.get_package(package_name, no_results=True)
            if package and package.quant_ids or package.children_ids:
                # the package exists and it contains stock or other packages
                res = False
        elif len(pickings) > 1 or (len(pickings) == 1 and self != pickings):
            # the package has been used
            res = False

        return res

    def update_picking(self, **kwargs):
        """ Extend update_picking to process a new parameter
            'expected_package_name' that may be included among the
            keyword args. If such parameter is included, it will be
            propagated within the environment context to the parent
            method.

            Expects a singleton.

            Also include the 'validate_real_time' flag to the keyword
            args.

        """
        # If transport data has been sent in kwargs, add it to picking_info
        if 'u_transport_id' in kwargs:
            # retrieve transport info changes, and then remove them from kwargs
            u_transport_id = kwargs.pop('u_transport_id')
            # if picking_info already exists in kwargs, update with trailer info
            if 'picking_info' in kwargs:
                kwargs['picking_info'].update(u_transport_id)
            # else add picking_info to kwargs with the trailer info
            else:
                kwargs['picking_info'] = u_transport_id

        kwargs.update(
            {'validate_real_time': self.picking_type_id.u_validate_real_time})

        if 'expected_package_name' in kwargs:
            expected_package_name = kwargs.pop('expected_package_name')
            # NB: super().with_context() would return the current
            # instance and, as a result, concatenating update_picking()
            # would result in invoking this very method instead of
            # the parent from udes_core...
            self_with_context = self.with_context(
                expected_package_name=expected_package_name)
            res = super(StockPicking, self_with_context).update_picking(**kwargs)
        else:
            res = super(StockPicking, self).update_picking(**kwargs)

        return res

    def maybe_swap(self, scanned_package, expected_package):
        """ Validate the conditions for performing a swap of the
            specified packages by considering the picking instance
            (expects a singleton picking) and relevant move lines.

            Return the move lines related to the expected package,
            in case a swap is performed, or the ones related to the
            scanned package, if both packages belong to the same
            batch.

            Raise a ValidationError in case packages cannot be found
            in the picking or if the conditions for swapping are not
            met.

        """
        self.ensure_one()

        if not self.picking_type_id.u_allow_swapping_packages:
            raise ValidationError(
                _("Cannot swap packages of picking type '%s'")
                % self.picking_type_id.name)

        exp_pack_mls = self.move_line_ids.filtered(
            lambda ml: ml.package_id == expected_package)


        if not exp_pack_mls:
            raise ValidationError(
                _("Expected package cannot be found in picking %s") %
                self.name)

        if not scanned_package.has_same_content(expected_package):
            raise ValidationError(
                _("The contents of %s does not match what you have been "
                  "asked to pick.") % expected_package.name)

        if scanned_package.location_id != expected_package.location_id:
            raise ValidationError(
                _("Packages are in different locations and cannot be swapped"))

        scanned_pack_mls = None

        if scanned_package.is_reserved():
            scanned_pack_mls = scanned_package.find_move_lines(
                [('qty_done', '=', 0)])

            if scanned_pack_mls:
                # We know that all the move lines have the same picking id
                mls_picking = scanned_pack_mls[0].picking_id

                if mls_picking.picking_type_id != self.picking_type_id:
                    raise ValidationError(
                        _("Packages have different picking types and cannot "
                          "be swapped"))

                if self.batch_id \
                   and mls_picking.batch_id == self.batch_id:
                    # The scanned package and the expected are in
                    # the same batch; don't need to be swapped -
                    # simply return the move lines of the scanned
                    # package
                    return scanned_pack_mls
                else:
                    # We should swap the packages...
                    pass

        return self._swap_package(scanned_package, expected_package,
                                  scanned_pack_mls, exp_pack_mls)

    def _swap_package(self, scanned_package, expected_package,
                      scanned_pack_mls, exp_pack_mls):
        """ Performs the swap. """
        if scanned_pack_mls and exp_pack_mls:
            # Both packages are in move lines; we simply change
            # the package ids of both scanned and expected move lines
            _update_move_lines_and_log_swap(scanned_pack_mls,
                                            scanned_package,
                                            expected_package)
            _update_move_lines_and_log_swap(exp_pack_mls,
                                            expected_package,
                                            scanned_package)
        else:
            assert exp_pack_mls is not None, \
                "Expected package move lines empty"

            # We know that scanned_pack_mls is empty; we should now
            # 1) unreserve quants of the expected one, 2) reserve quants
            # of the scanned package, and 3) change the package ids of
            # the expected move lines
            expected_package._get_contained_quants()\
                            .write({'reserved_quantity': 0})

            for q in scanned_package._get_contained_quants():
                q.write({'reserved_quantity': q.quantity})

            _update_move_lines_and_log_swap(exp_pack_mls,
                                            expected_package,
                                            scanned_package)

        return exp_pack_mls

    def action_assign(self):
        """
            Override action_assign to reserve full packages if applicable
        """
        super(StockPicking, self).action_assign()
        self._reserve_full_packages()

    def _check_entire_pack(self):
        """
            Override to avoid values at result_package_id when
            user scans products
        """
        pickings = self.filtered(lambda p: p.picking_type_id.u_user_scans != 'product')
        super(StockPicking, pickings)._check_entire_pack()

    def _reserve_full_packages(self):
        """
            If the picking type of the picking in self has full package
            reservation enabled, partially reserved packages are
            completed.
        """
        Quant = self.env['stock.quant']
        MoveLine = self.env['stock.move.line']

        # do not reserve full packages when bypass_reserve_full packages
        # is set in the context as True
        if not self.env.context.get('bypass_reserve_full_packages'):
            for picking in self:
                # Check if the picking type requires full package reservation
                if picking.picking_type_id.u_reserve_as_packages:
                    all_quants = Quant.browse()
                    remaining_qtys = defaultdict(int)

                    # get all packages
                    packages = self.mapped('move_line_ids.package_id')
                    for package in packages:
                        move_lines = self.mapped('move_line_ids').filtered(lambda ml: ml.package_id == package)
                        # TODO: merge with assert_reserved_full_package
                        pack_products = frozenset(package._get_all_products_quantities().items())
                        mls_products = frozenset(move_lines._get_all_products_quantities().items())
                        if pack_products != mls_products:
                            # move_lines do not match the quants
                            pack_mls = MoveLine.search([('package_id', 'child_of', package.id),
                                                        ('state', 'not in', ['done', 'cancel'])
                                                        ])
                            other_pickings = pack_mls.mapped('picking_id') - picking
                            if other_pickings:
                                raise ValidationError(
                                    _('The package is reserved in other pickings: %s')
                                    % ','.join(other_pickings.mapped('name')))

                            quants = package._get_contained_quants()
                            all_quants |= quants
                            for product, qty in quants.group_quantity_by_product(only_available=True).items():
                                remaining_qtys[product] += qty
                    if remaining_qtys:
                        # Context variables:
                        # - filter the quants used in _create_moves() to be
                        # the ones of the packages to be completed
                        # - add bypass_reserve_full_packages at the context
                        # to avoid to be called again inside _create_moves()
                        picking.with_context(
                            bypass_reserve_full_packages=True,
                            quant_ids=all_quants.ids)._create_moves(remaining_qtys,
                                                                confirm=True,
                                                                assign=True)
