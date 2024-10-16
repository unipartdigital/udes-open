from collections import defaultdict
from datetime import datetime
import logging

from odoo import models, fields, api, _
from odoo.tools.float_utils import float_compare, float_round, float_is_zero
from itertools import groupby
from operator import itemgetter
from odoo.osv import expression
from odoo.exceptions import ValidationError, UserError

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
        return self.filtered(
            lambda ml: ml.qty_done > 0
            and float_compare(
                ml.qty_done, ml.product_uom_qty, precision_rounding=ml.product_uom_id.rounding
            )
            < 0
        )

    def get_lines_incomplete(self):
        """Return the move lines in self that are not completed,
        i.e., quantity done < quantity to do
        """
        return self.filtered(lambda ml: float_compare(ml.qty_done, ml.product_uom_qty, precision_rounding=ml.product_uom_id.rounding) < 0)

    def get_lines_done(self):
        """Return the move lines in self that are completed,
        i.e., quantity done >= quantity to do
        """
        return self.filtered(lambda ml: float_compare(ml.qty_done, ml.product_uom_qty, precision_rounding=ml.product_uom_id.rounding) >= 0)

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
            greater_equal_mls = sorted_mls.filtered(lambda ml: float_compare(ml.product_uom_qty, uom_qty, precision_rounding=ml.product_uom_id.rounding) >= 0)
            # last one will be at least equal
            mls = greater_equal_mls[-1] if greater_equal_mls else sorted_mls
        else:
            mls = self

        for ml in mls:
            result |= ml
            extra_qty = self._round_qty(ml.product_uom_qty - uom_qty)
            if extra_qty > 0:
                new_ml = ml._split(uom_qty=extra_qty)
                uom_qty = 0
            else:
                uom_qty -= ml.product_uom_qty
            if float_is_zero(uom_qty, precision_rounding=ml.product_uom_id.rounding):
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
        # Ensure float rounding is correctly handled. A series of subtractions by small units
        # could cause rounding errors when using "UP" rounding method. A concrete example:
        #   >>> split_qty = 1.2 - 0.1
        #   >>> split_qty
        #   1.0999999999999999
        #   >>> float_round(1.2 - split_qty, precision_rounding=0.01, rounding_method="DOWN")
        #   0.1
        #   >>> float_round(1.2 - split_qty, precision_rounding=0.01, rounding_method="HALF-UP")
        #   0.1
        #   >>> float_round(1.2 - split_qty, precision_rounding=0.01, rounding_method="UP")
        #   0.11
        return float_round(
            value, precision_rounding=self.product_uom_id.rounding, rounding_method="HALF-UP"
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
            move = self.move_id
            location_dest_id = (
                move.location_dest_id._get_putaway_strategy(move.product_id).id
                or move.location_dest_id.id
            )
            new_ml = self.copy(
                default={
                    "product_uom_qty": split_qty,
                    "qty_done": 0.0,
                    "result_package_id": False,
                    "lot_name": False,
                    "location_dest_id": location_dest_id,
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

    def _find_move_lines(self, uom_qty, product, package=None, lot_name=None, location=None, picking=None):
        """Find a subset of move lines from self matching the subset of the key:
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
            products_quantities = [[{"product":product, "uom_qty": uom_qty},],]
            if picking: 
                mls_fulfill |= picking.add_unexpected_parts(products_quantities)
            else:
                mls_fulfill |= self.picking_id.add_unexpected_parts(products_quantities)
        return mls_fulfill, new_ml

    def prepare(
        self, product_ids=None, package=None, location=None, result_package=None, location_dest=None
    ):
        """Prepare incomplete move lines in self into groups of mls to be updated with
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
                        _("All package %s move lines cannot be found in picking %s")
                        % (package.name, mls.picking_id.name)
                    )
                res[pack_mls] = vals
            else:
                res[mls] = vals
            # Set to empty list to bypass the for
            product_ids = []

        for prod in product_ids:
            product_barcode = prod["barcode"]
            product = Product.get_or_create(product_barcode)
            rounding = product.uom_id.rounding
            quantity = prod["uom_qty"]
            lot_names = prod.get("lot_names", [])
            lot_quantities = prod.get("lot_quantities", [])
            product_tracking = product.tracking
            is_trackable = product_tracking != "none"
            is_serial = product_tracking == "serial"
            is_lot = product_tracking == "lot"
            if is_lot and not lot_quantities:
                lot_quantities = [quantity]
            if is_serial and not lot_quantities:
                lot_quantities = [1] * quantity
            if (
                is_trackable
                and float_compare(sum(lot_quantities), quantity, precision_rounding=rounding) != 0
            ):
                raise ValidationError(
                    _("Total lot/serial quantities entered doesn't match to total quantity.")
                )
            elif is_trackable and len(lot_names) != len(lot_quantities):
                raise ValidationError(
                    _("Lot/Serial quantity doesn't correspond to every lot/serial number entered.")
                )
            qty_done = quantity
            if product_tracking != "none":
                quantity_fulfilled = 0
                res, lot_names = self._swap_tracked_items(
                    mls, quantity, product, location, is_serial, vals, res, lot_names
                )
                for idx, lot_name in enumerate(lot_names):
                    qty_done = lot_quantities[idx]
                    lot_name_val = lot_name
                    # If it is incoming we don't need to match the lot
                    if incoming:
                        lot_name = None
                    else:
                        lot_name_val = None
                    prod_mls, new_ml = mls._find_move_lines(
                        qty_done, product, package, lot_name, location
                    )
                    prod_dict = {"qty_done": qty_done, "lot_name": lot_name_val}
                    prod_dict.update(vals)
                    res[prod_mls] = prod_dict
                    quantity_fulfilled += qty_done
                    mls -= prod_mls
                    if new_ml:
                        mls |= new_ml
                    if float_compare(quantity_fulfilled, quantity, precision_rounding=rounding) == 0:
                        break
            else:
                prod_mls, new_ml = mls._find_move_lines(qty_done, product, package, None, location, picking=self.picking_id)
                prod_dict = {"qty_done": qty_done}
                prod_dict.update(vals)
                res[prod_mls] = prod_dict
                mls -= prod_mls
                if new_ml:
                    mls |= new_ml
        return dict(res)

    def _swap_tracked_items(
        self, mls, quantity, product, location, is_serial, vals, res, lot_names
    ):
        """
        This handles the tracked product swaps. A tracked product swap is when a different lot name, than what is on the move_lines,
        has been passed to prepare(). The swapped in lot name should be in the same location and of the same product, else no swaps
        will happen.This method will produce a dictionary of a dictionary containing
        update information on different movelines so that the tracked products can be swapped. An adjusted list of
        lot_names is also returned.
        Returns: dict(dict), list()
        """
        StockProductionLot = self.env["stock.production.lot"]
        StockMoveLine = self.env["stock.move.line"]
        Quant = self.env["stock.quant"]

        # Swapping the tracked products
        mls = mls.filtered(lambda m: m.qty_done < m.product_uom_qty)
        lot_names_on_picking = mls.lot_id.mapped("name")
        lot_names_swapped_in = list(set(lot_names) - set(lot_names_on_picking))
        # If there swapping tracked products are allowed and some lot_names have been swapped in
        if mls.u_picking_type_id.u_allow_swapping_tracked_products:
            mls_not_changing = mls.filtered(lambda mls: mls.lot_id.name in lot_names)

            # Needed for the special case where we overpick on a moveline on the pick and
            # want the overpicked quantity to be swapped in on the other movelines
            for ml in mls_not_changing:
                # Test that there are other movelines for the overpicking fulfillment
                # ml.product_uom_qty < quantity
                if (
                    not is_serial
                    and ml.product_uom_qty < quantity
                    and not lot_names_swapped_in
                    and len(mls) > 1
                ):
                    mls_not_changing = mls_not_changing - ml
                    lot_names_swapped_in.append(ml.lot_id.name)

            quantity_swapping = quantity - sum(mls_not_changing.mapped("product_uom_qty"))
            mls_need_changing = mls - mls_not_changing
            if quantity_swapping and lot_names_swapped_in:
                picking_mls, new_ml = mls._find_move_lines(
                    quantity_swapping, product, None, None, location
                )

                # Workout the lot_ids that were swapped in and store the ones that were swapped out
                lot_ids_swapped_in = StockProductionLot.search(
                    [("name", "in", lot_names_swapped_in)]
                )
                lot_ids_swapped_out = picking_mls.lot_id

                # If any of the lot_ids_swapped_in belong to another move_line
                swapped_lot_on_assigned_mls = StockMoveLine.search(
                    [
                        ("lot_id", "in", lot_ids_swapped_in.mapped("id")),
                        ("state", "=", "assigned"),
                        ("u_picking_type_id", "=", mls.u_picking_type_id.id),
                        ("qty_done", "=", 0.0),
                        ("picking_id", "!=", mls.picking_id.id),
                    ],
                    order="id",
                )

                # For the message thread to notify of the tracked product swapped out
                old_mls = mls_need_changing | swapped_lot_on_assigned_mls
                for picking, mls in old_mls.groupby("picking_id"):
                    picking_qty = quantity_swapping
                    swap_out_text = ""
                    for ml in mls:
                        picking_qty -= ml.product_uom_qty
                        swapped_qty = min([quantity_swapping, ml.product_uom_qty])
                        if is_serial:
                            swapped_qty = 1
                        swap_out_text += f"<li>Product: {ml.product_id.name}, Quantity: {float(swapped_qty)}, Lot/Serial Name: {ml.lot_id.name} </li>"
                        if picking_qty <= 0:
                            break
                    body = "Tracked Products Swapped Out: <ul>" + swap_out_text + "</ul>"
                    picking.message_post(body=body)

                # Check there is available quantity on the system
                domain = [
                    ("product_id", "=", product.id),
                    ("location_id", "child_of", location.ids),
                    ("lot_id", "in", [lot_id.id for lot_id in lot_ids_swapped_in]),
                ]
                quants = Quant.search(domain).with_context(prefetch_fields=False)
                quants.read(["quantity", "reserved_quantity"], load="_classic_write")
                if quantity_swapping > sum(quants.mapped("quantity")):
                    raise UserError(
                        "You have picked more stock than is available on the system. Speak to your manager."
                    )

                # Generator expressions to easily iterate over
                mls_need_changing = (ml for ml in mls_need_changing)
                lot_ids_swapped_in = (lot for lot in lot_ids_swapped_in)

                amount_to_be_swapped = quantity_swapping
                if is_serial:
                    # Want to update the movelines on each serial tracked product
                    # until all the quantity scanned in is zero
                    qty_done = 1
                    while quantity_swapping > 0:
                        ml, lot_id = next(mls_need_changing), next(lot_ids_swapped_in)
                        prod_dict = {
                            "product_uom_qty": qty_done,
                            "qty_done": qty_done,
                            "lot_name": lot_id.name,
                            "lot_id": lot_id.id,
                        }
                        prod_dict.update(vals)
                        res[ml] = prod_dict
                        quantity_swapping -= qty_done
                else:
                    qty_done = quantity_swapping
                    # Update the first lot with all scanned in lot information
                    ml, lot_id = next(mls_need_changing), next(lot_ids_swapped_in)
                    reserved_quantity = ml.product_uom_qty
                    prod_dict = {
                        "product_uom_qty": qty_done,
                        "qty_done": qty_done,
                        "lot_name": lot_id.name,
                        "lot_id": lot_id.id,
                    }
                    prod_dict.update(vals)
                    res[ml] = prod_dict
                    quantity_swapping -= reserved_quantity
                    # If the lot quantity covers multiple movelines then delete these movelines
                    # Unless it has partially picked some moveline then update the reserved qty on that moveline
                    while quantity_swapping > 0:
                        ml = next(mls_need_changing)
                        reserved_quantity = ml.product_uom_qty
                        quantity_swapping -= reserved_quantity
                        if quantity_swapping >= 0:
                            ml.unlink()
                        else:
                            prod_dict = {"product_uom_qty": abs(quantity), "qty_done": 0}
                            res[ml] = prod_dict

                # Remove swapped in lot from old move line and replace it with swapped out lot
                # Can zip as lot_ids_swapped_out will never have fewer item then swapped_lot_on_assigned_mls
                for old_lot, ml_to_change in zip(lot_ids_swapped_out, swapped_lot_on_assigned_mls):
                    # If we partially pick a lot that is reserved on another picking then we need to update the
                    # mls on that picking to have a new reserved quantity (old quantity - quantity swapped out) and create another moveline with
                    # for the lot that was swapped out.
                    if not is_serial and ml_to_change.product_uom_qty > amount_to_be_swapped:
                        prod_dict = {
                            "lot_name": ml_to_change.lot_id.name,
                            "lot_id": ml_to_change.lot_id.id,
                            "product_uom_qty": ml_to_change.product_uom_qty - amount_to_be_swapped,
                            "qty_done": 0.0,
                        }
                        ml_to_change.write(
                            {"product_uom_qty": ml_to_change.product_uom_qty - amount_to_be_swapped}
                        )
                        res[ml_to_change] = prod_dict
                        new_mls = ml_to_change.copy()
                        new_prod_dict = {
                            "lot_name": old_lot.name,
                            "lot_id": old_lot.id,
                            "product_uom_qty": amount_to_be_swapped,
                            "qty_done": 0.0,
                        }
                        res[new_mls] = new_prod_dict
                    else:
                        prod_dict = {
                            "lot_name": old_lot.name,
                            "lot_id": old_lot.id,
                            "product_uom_qty": 1.0 if is_serial else amount_to_be_swapped,
                            "qty_done": 0.0,
                        }
                        ml_to_change.write({"product_uom_qty": 0.0})
                        res[ml_to_change] = prod_dict

                # Remove lot names that have been processed so they are not called below
                lot_names = list(set(lot_names) - set(lot_names_swapped_in))

            # For the message thread to notify of the tracked products swapped in
            new_mls = StockMoveLine.browse()
            for ml, _mls_values in res.items():
                new_mls = new_mls | ml

            for picking, mls in new_mls.groupby("picking_id"):
                swap_in_text = ""
                for ml in mls:
                    mls_value = res[ml]
                    if mls_value["lot_name"] != ml.lot_id.name:
                        swap_in_text += f"<li>Product: {ml.product_id.name}, Quantity: {float(mls_value['product_uom_qty'])}, Lot/Serial Name: {mls_value['lot_name']} </li>"
                body = "Tracked Products Swapped In: <ul>" + swap_in_text + "</ul>"
                picking.message_post(body=body)

        return res, lot_names

    def mark_as_done(self, values=None):
        """Marks as done the move lines in self and updates them with the values provided.
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
            # A change of lot_id implies a change of quant so the old qty_done on
            # the moveline is not important
            elif new_uom_qty > current_uom_qty and not values.get("lot_id"):
                raise ValidationError(
                    _("Move line %i for product %s does not have enough quantity: %i vs %i")
                    % (ml.id, ml.product_id.name, new_uom_qty, current_uom_qty)
                )
            ml.write(ml_vals)

        return True

    def _split_and_group_mls_by_quantity(self, maximum_qty):
        """
        Split move lines into groups of up to a maximum quantity
        :param maximum_qty: float quantity to split and group move lines
        :returns: list of grouped move lines
        """
        grouped_mls = []

        # Group all (partially) done and cancelled moves first
        remaining_mls = self
        excluded_move_lines = self.filtered(lambda m: m.qty_done or m.state == "done")
        if excluded_move_lines:
            grouped_mls.append(excluded_move_lines)
            remaining_mls -= excluded_move_lines

        # See if any mls are equal to the maximum and add them as individual groups
        exact_mls = self.filtered(lambda l: l.product_uom_qty == maximum_qty)
        remaining_mls -= exact_mls
        for ml in exact_mls:
            grouped_mls.append(ml)

        # Splitting and grouping remaining move lines by using move_lines_for_qty method, where if
        # a move line is split we add the split move line to be split again and remove the move line
        # used from move lines to be split. Add the move lines to the grouped move lines.
        while remaining_mls:
            mls_used, new_ml, _uom_qty = remaining_mls.move_lines_for_qty(maximum_qty)
            if new_ml:
                remaining_mls |= new_ml
            remaining_mls -= mls_used
            grouped_mls.append(mls_used)
        return grouped_mls

    def _merge_move_lines(self):
        """This method will, for each move line in `self`, go up in their linked picking and try to
        find in their existing move line a candidate into which we can merge the move.
        :return: Recordset of move lines passed to this method.
            If some of passed move lines were merged into another existing one, return this one and
            not the (now unlinked) original.
        """
        MoveLine = self.env["stock.move.line"]
        distinct_fields = self._prepare_merge_move_lines_distinct_fields()

        candidate_move_line_list = [picking.move_line_ids for picking in self.picking_id]
        # Move removed after merge
        move_lines_to_unlink = MoveLine.browse()
        move_lines_to_merge = []
        for candidate_move_lines in candidate_move_line_list:
            # First step find move lines to merge.
            candidate_move_lines = candidate_move_lines.with_context(prefetch_fields=False)
            for k, g in groupby(
                sorted(candidate_move_lines, key=self._prepare_merge_move_line_sort_method),
                key=itemgetter(*distinct_fields),
            ):
                move_lines = MoveLine.concat(*g).filtered(
                    lambda m: m.state not in ("done", "cancel") and not m.qty_done
                )
                # If we have multiple records we will merge then in a single one.
                if len(move_lines) > 1:
                    move_lines_to_merge.append(move_lines)

        # second step merge its move lines, initial demand, ...
        move_lines_to_write = {}
        for move_lines in move_lines_to_merge:
            # built merge move line data, which will be used after unlink to write
            # to specific move lines.
            move_lines_to_write[move_lines[0]] = move_lines._merge_move_lines_fields()
            # update merged moves dicts
            move_lines_to_unlink |= move_lines[1:]
        # Unlinking move lines first will add the available quantity (
        # By removing already reserved quantity), when writing will reserve the merged quantity.
        # TODO Would be better to bypass reserving on both write and unlink, but the unlink core
        #  functionality doesnt have an option to by pass. Issue #4895
        if move_lines_to_unlink:
            move_lines_to_unlink.sudo().unlink()
        for move_line, value in move_lines_to_write.items():
            move_line.write(value)
        return (self | MoveLine.concat(*move_lines_to_merge)) - move_lines_to_unlink

    @api.model
    def _prepare_merge_move_lines_distinct_fields(self):
        """
        Prepare merge move lines distinct fields
        """
        return ["product_id", "location_id", "location_dest_id", "package_id", "lot_id", "move_id"]

    @api.model
    def _prepare_merge_move_line_sort_method(self, move_line):
        """
        Sort move lines depending on distinct fields prepared
        """
        move_line.ensure_one()

        return [
            move_line.product_id.id,
            move_line.location_id.id,
            move_line.location_dest_id.id,
            move_line.package_id.id,
            move_line.lot_id.id,
            move_line.move_id.id,
        ]

    def _merge_move_lines_fields(self):
        """This method will return a dict of stock move line’s values that represent the values of
        all move lines in `self` merged."""

        return {
            "product_uom_qty": sum(self.mapped("product_uom_qty")),
        }
