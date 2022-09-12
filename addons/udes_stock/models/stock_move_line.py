from collections import defaultdict
from datetime import datetime
import logging

from odoo import models, fields, api, _
from odoo.tools.float_utils import float_compare, float_round
from odoo.osv import expression
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    u_done_by_id = fields.Many2one(
        "res.users",
        "Scanned By",
        help="User who completed the product move",
        index=True,
        copy=False,
    )

    u_done_datetime = fields.Datetime(
        "Completion Datetime",
        help="Date and time the operation was completed.",
        index=True,
        copy=False,
    )

    u_picking_type_id = fields.Many2one(
        "stock.picking.type",
        "Operation Type",
        related="move_id.picking_type_id",
        store=True,
        readonly=True,
    )

    @staticmethod
    def _now_for_tracking_data():
        """Override to change the tracking resolution"""
        return datetime.now()

    @api.model
    def _add_user_tracking_data(self, vals):
        """Inject/overwrite user tracking data into vals"""
        if vals.get("qty_done", 0) > 0:
            vals["u_done_by_id"] = self.env.uid
            vals["u_done_datetime"] = self._now_for_tracking_data()
        return vals

    @api.model
    def create(self, vals):
        """Extend to track the requester user"""
        vals = self._add_user_tracking_data(vals)
        return super().create(vals)

    @api.model
    def write(self, vals):
        """Extend to track the requester user"""
        vals = self._add_user_tracking_data(vals)
        return super().write(vals)

    def _log_message(self, record, move, template, vals):
        """
        Extend _log_message to stop messages being created
        when bypass_zero_qty_log_message context is set.
        """
        if self.env.context.get("bypass_zero_qty_log_message"):
            if "product_uom_qty" in vals and not vals["product_uom_qty"]:
                return
        return super()._log_message(record, move, template, vals)

    def get_lines_partially_complete(self):
        """Return the move lines in self that are not completed,
        i.e., 0 < quantity done < quantity to do
        """
        return self.filtered(lambda ml: 0 < ml.qty_done < ml.product_uom_qty)

    def get_lines_incomplete(self):
        """Return the move lines in self that are not completed,
        i.e., quantity done < quantity to do
        """
        return self.filtered(lambda ml: ml.qty_done < ml.product_uom_qty)

    def get_lines_done(self):
        """Return the move lines in self that are completed,
        i.e., quantity done >= quantity to do
        """
        return self.filtered(lambda ml: ml.qty_done >= ml.product_uom_qty)

    def move_lines_for_qty(self, uom_qty, sort=True):
        """
        Return a subset of move lines from self where their sum of the uom quantity
        to do is equal to parameter uom quantity.
        In case that a move line needs to be split, the new move line is
        also returned (this happens when total quantity in the move lines is
        greater than quantity parameter).
        If there is not enough quantity to do in the move lines,
        also return the remaining quantity.
        """
        MoveLine = self.env["stock.move.line"]
        new_ml = None
        result = MoveLine.browse()
        if uom_qty == 0:
            return result, new_ml, uom_qty

        if sort:
            sorted_mls = self.sorted(lambda ml: ml.product_uom_qty, reverse=True)
            greater_equal_mls = sorted_mls.filtered(lambda ml: ml.product_uom_qty >= uom_qty)
            # last one will be at least equal
            mls = greater_equal_mls[-1] if greater_equal_mls else sorted_mls
        else:
            mls = self

        for ml in mls:
            result |= ml
            extra_qty = ml.product_uom_qty - uom_qty
            if extra_qty > 0:
                new_ml = ml._split(uom_qty=extra_qty)
                uom_qty = 0
            else:
                uom_qty -= ml.product_uom_qty
            if uom_qty == 0:
                break

        return result, new_ml, uom_qty

    def _get_search_domain(self, strict=False):
        """Generate search domain for a given move line"""
        self.ensure_one()

        product = self.product_id
        lot = self.lot_id
        package = self.package_id
        owner = self.owner_id
        location = self.location_id
        domain = [("product_id", "=", product.id)]
        if not strict:
            if lot:
                domain = expression.AND([[("lot_id", "=", lot.id)], domain])
            if package:
                domain = expression.AND([[("package_id", "=", package.id)], domain])
            if owner:
                domain = expression.AND([[("owner_id", "=", owner.id)], domain])
            domain = expression.AND([[("location_id", "child_of", location.id)], domain])
        else:
            domain = expression.AND([[("lot_id", "=", lot and lot.id or False)], domain])
            domain = expression.AND(
                [[("package_id", "=", package and package.id or False)], domain]
            )
            domain = expression.AND([[("owner_id", "=", owner and owner.id or False)], domain])
            domain = expression.AND([[("location_id", "=", location.id)], domain])

        return domain

    def get_quants(self):
        """Returns the quants related to move lines in self"""
        Quant = self.env["stock.quant"]

        quants = Quant.browse()
        for ml in self:
            domain = ml._get_search_domain(strict=True)
            quants |= Quant.search(domain)

        return quants

    def get_quantities_by_key(self, get_key=lambda ml: ml.product_id):
        """This function computes the different product quantities for the given move lines
        :kwargs:
            - get_key: a callable which takes a move line and returns the key
        """
        res = defaultdict(int)
        for move_line in self:
            res[get_key(move_line)] += move_line.product_uom_qty
        return res

    def sort_by_key(self, sort_key=lambda ml: (ml.location_id.name, ml.product_id.id)):
        """Return the move lines sorted by location and product
        :kwargs:
            - sort_key: a callable lambda to determine the way of ordering
        """
        return self.sorted(key=sort_key)

    def _round_qty(self, value):
        return float_round(
            value, precision_rounding=self.product_uom_id.rounding, rounding_method="UP"
        )

    def _split(self, uom_qty=None):
        """Splits the move line by
        - uom_qty if uom_qty is set and (qty_done == 0 or uom_qty == qty_not_done)
        - qty_not_done if uom_qty is not set
        As cannot split by uom_qty if some already done!

        :kwargs:
            - uom_qty: int
                UoM quantity to split the move line by unless it has quantity done.
        :returns:
            either self (when the line is not split) or
            a new move line with the split quantity,
            where split quantity = qty or qty_not_done
        """
        self.ensure_one()
        res = self
        qty_done = self.qty_done
        qty_not_done = self._round_qty(self.product_uom_qty - self.qty_done)
        # Not allowed to split by qty parameter when quantity done > 0 unless
        # it is equal to quantity not done
        if uom_qty is not None and qty_done != 0 and uom_qty != qty_not_done:
            raise ValidationError(
                _("Trying to split a move line with quantity done at picking %s")
                % self.picking_id.name
            )
        split_qty = uom_qty or qty_not_done
        if (
            split_qty > 0
            and float_compare(
                split_qty, self.product_uom_qty, precision_rounding=self.product_uom_id.rounding
            )
            < 0
        ):
            # create new move line
            new_ml = self.copy(
                default={
                    "product_uom_qty": split_qty,
                    "qty_done": 0.0,
                    "result_package_id": False,
                    "lot_name": False,
                }
            )
            # Quantity to keep in self
            qty_to_keep = self._round_qty(self.product_uom_qty - split_qty)
            # update self move line quantity to do
            # - bypass_reservation_update:
            #   avoids to execute code specific for Odoo UI at stock.move.line.write()
            self.with_context(bypass_reservation_update=True).write(
                {"product_uom_qty": qty_to_keep, "qty_done": qty_done}
            )
            res = new_ml
        return res

    def get_move_lines_ordered_by(self, domain, aux_domain=None, order="id"):
        """Get move lines with a search order by id instead of ordering by model _order attribute
        Args:
            domain (list):  Default domain to search move lines
            aux_domain (list): Optional domain to extend the default domain
            order (Char): Optional order
        """
        StockMoveLine = self.env["stock.move.line"]

        if aux_domain is not None:
            domain += aux_domain
        return StockMoveLine.search(domain, order=order)

    def _find_move_lines(self, uom_qty, product, package=None, lot_name=None, location=None):
        """ Find a subset of move lines from self matching the subset of the key:
            product, package, lot and location.
        """
        funcs = [lambda ml: ml.product_id == product]
        if package:
            funcs.append(lambda ml: ml.package_id == package)
        if location:
            funcs.append(lambda ml: ml.location_id == location)
        if lot_name:
            funcs.append(lambda ml: (ml.lot_name == lot_name or ml.lot_id.name == lot_name))
        func = lambda ml: all(f(ml) for f in funcs)

        # Find move lines
        mls = self.filtered(func)
        mls_fulfill, new_ml, uom_qty = mls.move_lines_for_qty(uom_qty)
        if uom_qty > 0:
            # TODO: when implementing add_unexpected_parts() review if this is the best place
            mls_fulfill |= self.picking_id.add_unexpected_parts(uom_qty)
        return mls_fulfill, new_ml

    def prepare(
        self, product_ids=None, package=None, location=None, result_package=None, location_dest=None
    ):
        """ Prepare incomplete move lines in self into groups of mls to be updated with
            the same values. It will split move lines if required.
            Product_ids is a list of dictionaries with the following keys:
            * barcode: string
            * qty: integer
            * lot_names: list of strings (optional)
            Example: [{"barcode": "PROD01", "uom_qty":1}]

        """
        Product = self.env["product.product"]
        vals = {}
        if result_package:
            vals["result_package_id"] = result_package.id
        if location_dest:
            vals["location_dest_id"] = location_dest.id
        mls = self.get_lines_incomplete()
        incoming = mls.u_picking_type_id.code == "incoming"
        res = defaultdict(dict)
        if not product_ids:
            if package:
                pack_mls = package._get_current_move_lines()
                # TODO: this is probably where swap package should go
                if (pack_mls & mls) != pack_mls:
                    raise ValidationError(
                        _("All package %s move lines cannot be found in picking %s") %
                        (package.name, mls.picking_id.name)
                    )
                res[pack_mls] = vals
            else:
                res[mls] = vals
            # Set to empty list to bypass the for
            product_ids = []

        for prod in product_ids:
            product_barcode = prod["barcode"]
            product = Product.get_or_create(product_barcode)
            quantity = prod["uom_qty"]
            lot_names = prod.get("lot_names", [])
            product_tracking = product.tracking
            is_serial = product_tracking == "serial"
            is_lot = product_tracking == "lot"
            if is_serial and len(lot_names) != quantity:
                raise ValidationError(
                    _("Not enough serial numbers provided.")
                )
            elif is_lot and len(lot_names) != 1:
                raise ValidationError(
                    _("Too many lots provided.")
                )
            qty_done = quantity
            if product_tracking != "none":

                quantity_fulfilled = 0
                if is_serial:
                    qty_done = 1

                # Swapping the tracked products
                if mls.u_picking_type_id.u_allow_swapping_tracked_products:
                    # Find movelines in picking for location scanned in
                    picking_mls, new_ml = mls._find_move_lines(quantity, product, package, None, location)
                    picking_mls = picking_mls[:len(lot_names)]
                    # Find movelines that have lot_names that were not entered
                    mls_need_changing = picking_mls.filtered(lambda mls: mls.lot_id.name not in lot_names)
                    # Workout the lot_names that were swapped in
                    lot_names_on_picking = self.lot_id.mapped("name")
                    lot_names_swapped_in = list(set(lot_names) - set(lot_names_on_picking))
                    lot_ids_swapped_in = self.env["stock.production.lot"].search([("name", "in", lot_names_swapped_in)])
                    lot_ids_swapped_out = picking_mls.lot_id
                    # Update the reserved_quantity on quants that have not been scanned in (unreserve that quantity)
                    # Reserve quantity on the quant and for each move_line attach the new lot_id 
                    for picking_mls, lot_id in zip(mls_need_changing, lot_ids_swapped_in):
                        prod_dict = {
                        "product_uom_qty": qty_done,
                        "qty_done": qty_done,
                        "lot_name": lot_id.name,
                        "lot_id": lot_id.id
                        }
                        prod_dict.update(vals)
                        res[picking_mls] = prod_dict
                    
                    # If any of the lot_ids_swapped_in belong to another move_line
                    swapped_lot_on_assigned_mls = self.env["stock.move.line"].search([("lot_id", "in", lot_ids_swapped_in.mapped("id"))])
                    # Can zip as lot_ids_swapped_out will never have fewer item then swapped_lot_on_assigned_mls
                    for old_lot, mls in zip(lot_ids_swapped_out,swapped_lot_on_assigned_mls): 
                        prod_dict = {
                        "lot_name": old_lot.name,
                        "lot_id": old_lot.id,
                        "qty_done": 0.0
                        }
                        res[mls] = prod_dict

                    # Remove lot names that have been processed so they are not called below
                    lot_names = list(set(lot_names) - set(lot_names_swapped_in))
                
                # This won't find any move_lines for the swapped in products 
                for lot_name in lot_names:
                    lot_name_val = lot_name
                    # If it is incoming we don't need to match the lot
                    if incoming:
                        lot_name = None
                    else:
                        lot_name_val = None
                    prod_mls, new_ml = mls._find_move_lines(
                        qty_done, product, package, lot_name, location
                    )
                    prod_dict = {
                        "qty_done": qty_done,
                        "lot_name": lot_name_val
                    }
                    prod_dict.update(vals)
                    res[prod_mls] = prod_dict
                    quantity_fulfilled += qty_done
                    mls -= prod_mls
                    if new_ml:
                        mls |= new_ml
                    if quantity_fulfilled == quantity:
                        break
            else:
                prod_mls, new_ml = mls._find_move_lines(
                    qty_done, product, package, None, location
                )
                prod_dict = {"qty_done": qty_done}
                prod_dict.update(vals)
                res[prod_mls] = prod_dict
                mls -= prod_mls
                if new_ml:
                    mls |= new_ml
        return dict(res)

    def mark_as_done(self, values=None):
        """ Marks as done the move lines in self and updates them with the values provided.
            When no quantity is passed, it will mark the full line as done.
            Move lines should always have enough quantity.
        """
        if values is None:
            values = {}
        for ml in self:
            ml_vals = values.copy()
            new_uom_qty = ml_vals.get("qty_done", None)
            current_uom_qty = ml.product_uom_qty
            if new_uom_qty is None:
                ml_vals["qty_done"] = current_uom_qty
            elif new_uom_qty > current_uom_qty:
                raise ValidationError(
                    _("Move line %i for product %s does not have enough quantity: %i vs %i")
                    % (ml.id, ml.product_id.name, new_uom_qty, current_uom_qty)
                )
            ml.write(ml_vals)

        return True
