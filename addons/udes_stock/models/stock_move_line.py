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
        return self.filtered(lambda ml: 0 <  ml.qty_done < ml.product_uom_qty)

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
