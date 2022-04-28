"""UDES core picking functionality."""
import logging

from odoo import api, models, fields, _
from odoo.exceptions import ValidationError, UserError
from .common import get_next_name

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    sequence = fields.Integer(
        "Sequence", default=0, help="Used to order the 'All Operations' kanban view"
    )

    # Related pickings computed fields

    u_first_picking_ids = fields.One2many(
        "stock.picking",
        string="First Pickings",
        compute="_compute_first_picking_ids",
        help="First pickings in the chain",
    )
    u_prev_picking_ids = fields.One2many(
        "stock.picking",
        string="Previous Pickings",
        compute="_compute_related_picking_ids",
        help="Previous pickings",
    )
    u_next_picking_ids = fields.One2many(
        "stock.picking",
        string="Next Pickings",
        compute="_compute_related_picking_ids",
        help="Next pickings",
    )
    u_created_backorder_ids = fields.One2many(
        "stock.picking",
        string="Created Backorders",
        compute="_compute_related_picking_ids",
        help="Backorders created from this picking",
    )

    # Picking quantity computed fields

    u_quantity_done = fields.Float(
        "Quantity Done",
        compute="_compute_picking_quantities",
        digits=(0, 0),
        help="Quantity done of the moves related to the picking in the UoM of the move(s)",
    )
    u_total_quantity = fields.Float(
        "Total Quantity",
        compute="_compute_picking_quantities",
        digits=(0, 0),
        help="Total quantity todo of the moves related to the picking in the UoM of the move(s)",
    )
    u_has_discrepancies = fields.Boolean(
        "Has Discrepancies",
        compute="_compute_picking_quantities",
        readonly=True,
        help="Flag to indicate if the picking has discrepancies.",
    )
    u_num_pallets = fields.Integer(
        "Total Pallets Count",
        compute="_compute_num_pallets",
        help="Total number of different pallets in the picking",
    )

    # search helpers for source and destination package
    u_package_id = fields.Many2one(
        "stock.quant.package",
        "Package",
        related="move_line_ids.package_id",
        help="Source package (used to search on pickings)",
    )
    u_result_package_id = fields.Many2one(
        "stock.quant.package",
        "Result Package",
        related="move_line_ids.result_package_id",
        help="Destination package (used to search on pickings)",
    )

    # Mark pickings as ready for deletion after refactoring
    u_is_empty = fields.Boolean(
        "Is Empty",
        default=False,
        index=True,
        help="Pickings that are unused after refactoring are empty and ready to be deleted",
    )

    # User responsible for Batch
    u_batch_user_id = fields.Many2one(
        string="Batch User",
        related="batch_id.user_id",
        store=False,
        help="User responsible for the batch",
    )

    def get_next_picking_name(self, vals, picking_type=None):
        """
        Override the method in core stock to customise the name generation.

        Backorders have a naming pattern of adding `-001` to it,
        so they are more visible to users.
        """
        if vals.get("backorder_id"):
            ir_sequence = picking_type.sequence_id
            # Specify sequence as it is picking type specific
            return get_next_name(self, "stock.picking", sequence=ir_sequence)
        return super().get_next_picking_name(vals, picking_type=picking_type)

    @api.depends("move_lines", "move_lines.move_orig_ids", "move_lines.move_orig_ids.picking_id")
    def _compute_first_picking_ids(self):
        """Compute first picking from moves that do not originate from other moves"""
        Move = self.env["stock.move"]

        for picking in self:
            first_moves = Move.browse()

            moves = picking.move_lines
            while moves:
                first_moves |= moves.filtered(lambda x: not x.move_orig_ids)
                moves = moves.move_orig_ids

            picking.u_first_picking_ids = first_moves.picking_id

    @api.depends(
        "move_lines",
        "move_lines.move_orig_ids",
        "move_lines.move_dest_ids",
        "move_lines.move_orig_ids.picking_id",
        "move_lines.move_dest_ids.picking_id",
    )
    def _compute_related_picking_ids(self):
        """Compute previous/next picking and created backorders"""
        for picking in self:
            picking.u_prev_picking_ids = picking.move_lines.move_orig_ids.picking_id
            picking.u_next_picking_ids = picking.move_lines.move_dest_ids.picking_id

            picking.u_created_backorder_ids = self.search([("backorder_id", "=", picking.id)])

    @api.depends("move_lines", "move_lines.quantity_done", "move_lines.product_uom_qty")
    def _compute_picking_quantities(self):
        """Compute the quantity done and to do of the picking from the moves"""
        for picking in self:
            total_qty_done = 0.0
            total_qty_todo = 0.0
            has_discrepancies = False

            for move in picking.move_lines.filtered(lambda ml: ml.state != "cancel"):
                # The move quantity done is in the unit of measure of the move not the product
                # So use the move UoM not the product for what is done and what is left to do.
                # This avoids the issue where it says left to do is different to the number of
                # boxes.
                # NOTE: Different UoMs across a picking could make these computed fields unreliable
                # in terms of how much work is done/left todo. Example 50% done - moved one crane
                # but 1000000 screws in one box.
                qty_done = move.quantity_done
                qty_todo = move.product_uom_qty

                if not has_discrepancies and qty_done != qty_todo:
                    has_discrepancies = True

                total_qty_done += qty_done
                total_qty_todo += qty_todo

            picking.u_quantity_done = total_qty_done
            picking.u_total_quantity = total_qty_todo
            picking.u_has_discrepancies = has_discrepancies

    @api.depends("move_line_ids", "move_line_ids.result_package_id")
    def _compute_num_pallets(self):
        """Compute the number of pallets from the operations"""
        for picking in self:
            picking.u_num_pallets = len(picking.move_line_ids.result_package_id)

    def get_empty_location_domain(self):
        """
        Return the domain for searching empty locations
        """
        return [("barcode", "!=", False), ("quant_ids", "=", False)]

    def get_empty_locations(self, limit=None, sort=True):
        """Returns the recordset of locations that are child of the
        instance dest location and are empty.
        Expects a singleton instance.

        :kwargs:
            - limit: Integer
                If set then the recordset returned will be less than or equal to the limit.
            - sort: Boolean
                If true the recordset will be returned by order of name.
                Note that the sort is carried out after the locations have been identified
                (and when the limit has been applied, if set)
        :returns: Move lines of picking
        """
        locations = self._get_child_dest_locations(self.get_empty_location_domain(), limit=limit)

        if sort:
            return locations.sorted(lambda l: l.name)
        else:
            return locations

    def do_unreserve(self):
        """Extend to delete moves if initial demand is 0"""
        res = super().do_unreserve()
        for move in self.move_lines.filtered(lambda m: not m.u_uom_initial_demand):
            # Set move back to draft so it can be deleted
            move.state = "draft"
            move.unlink()
        return res

    def _get_child_dest_locations(self, aux_domain=None, limit=None):
        """Return the child locations of the instance dest location.
        Extra domains are added to the child locations search query,
        when specified.
        Expects a singleton instance.

        :kwargs:
            - aux_domain: List of tuples
                Additional domain to use for filtering locations
            - limit: Integer
                If set then the recordset returned will be less than or equal to the limit.
        """
        Location = self.env["stock.location"]

        domain = [("id", "child_of", self.location_dest_id.ids)]
        if aux_domain is not None:
            domain.extend(aux_domain)
        return Location.search(domain, limit=limit)

    def get_move_lines(self, done=None):
        """Get move lines associated to picking, uses functions in stock_move_line
        :kwargs:
            - done: Boolean
                When not set means to return all move lines of the picking.
                Flag, if true returns all done move lines, else returns all incomplete
                move lines associated to picking
        :returns: Move lines of picking
        """
        mls = self.get_move_lines_ordered_by()
        if done:
            return mls.get_lines_done()
        elif done == False:
            return mls.get_lines_incomplete()
        return mls

    def get_move_lines_ordered_by(self, aux_domain=None, order="id"):
        """Get move lines with a search order by id instead of ordering by model _order attribute
        Args:
            aux_domain (list): Optional domain to extend the default domain
            order (char): Optional order
        """
        StockMoveLine = self.env["stock.move.line"]

        domain = [("picking_id", "in", self.ids)]
        if aux_domain is not None:
            domain += aux_domain
        return StockMoveLine.get_move_lines_ordered_by(domain=domain, order=order)

    def _backorder_move_lines(self, mls=None):
        """
        Create a backorder picking from self (expects a singleton)
        for all move lines not complete (and un-confirmed moves).
        All move lines must either have a qty_done == (0 or product_uom_qty),
        to enforce that splitting of mls is done prior to calling this method.
        The original picking (self) is not validated.

        The reason for this method is to maintain tracability of move lines,
        and not delete and re-create them inside _action_done().

        :returns: The created backorder
            If nothing to backorder (nothing done) returns an empty record set
        :raises:
            ValidationError: Nothing to backorder, quantity_done for all moves is zero
            ValidationError: Move line exists with qty_done < product_uom_qty

        NOTE: The current picking (self) is not yet complete until action_done
        is called. This is because the use case of this is not well defined,
        but instead think this of a helper method in drop off actions.
        One example may be because we want to call this on a sequence of move
        lines and propogate them through then call _action_done sequentially
        on the chain of pickings.
        NOTE: Previous iterations have allowed the passing of a subset of move lines.
        This is currently been removed because it creates an immediate backorder,
        future iterations may want to move a subset of incomplete lines into a backorder,
        when doing this the naming convention should be considered. The path becomes
        a tree!
        """
        Picking = self.env["stock.picking"]
        Move = self.env["stock.move"]

        # Based on backorder creation in stock_move._action_done
        self.ensure_one()

        if mls is None:
            moves = self.move_lines
            mls = self.move_line_ids
        else:
            moves = mls.move_id

        # Return if nothing has ben done yet
        if all(mv.quantity_done == 0 for mv in moves):
            _logger.info(
                "Nothing to backorder in picking %s, original picking retained!" % self.name
            )
            return Picking.browse()

        # Get the relevant moves, which are not fully fulfilled
        unfulfilled_moves = moves.filtered(
            lambda mv: sum(mv.move_line_ids.mapped("qty_done")) < mv.product_uom_qty
        )

        # Raise an error if:
        # * there are moves or move lines that are not fully fulfilled so we can backorder
        # something.
        # * if move lines need splitting
        if not unfulfilled_moves:
            raise ValidationError(
                _("There are no move lines within picking %s to backorder") % self.name
            )
        elif mls and any(ml.qty_done != 0 and ml.qty_done < ml.product_uom_qty for ml in mls):
            raise ValidationError(
                _("You cannot create a backorder for %s with a move line qty less than expected!")
                % self.name
            )

        # Iterate over the moves not fulfilled, and split out recording the newly created moves
        new_moves = Move.browse()
        for move in unfulfilled_moves:
            move_mls = mls.filtered(lambda ml: ml.move_id == move)
            new_moves |= move.split_out_incomplete_move(move_mls)

        # Create picking for completed move
        bk_picking = self._create_backorder_picking(new_moves)

        return bk_picking

    def _create_backorder_picking(self, moves):
        """Helper to create a backorder picking from the given moves"""
        bk_picking = self.copy(
            {
                "name": "/",
                "move_lines": [(6, 0, moves.ids)],
                "move_line_ids": [(6, 0, moves.move_line_ids.ids)],
                "backorder_id": self.id,
            }
        )
        return bk_picking

    def _requires_backorder(self, mls=None):
        """
        Checks if a backorder is required.
        If mls is None:
            checks if all move lines have the qty_done = total move qty  (excluding cancelled)
        If mls is not None:
            checks if all move lines within a picking are present in mls
        Cannot be consolidated with _check_backorder in Odoo core, because it
        does not take into account any move lines parameter.

        TODO: Review the case when mls is not None. It uses the move_orig_ids,
        but we no longer have update_orig_ids. The logic needs to be synchronised.
        See Issue 1797.

        :kwargs:
            - mls: A record set of move lines, default None.
        :returns: bool
        """
        # If the mls arg is not passed check the whole picking in self
        if mls is None:
            mls = self.move_line_ids
            moves = self.move_lines.filtered(lambda mv: mv.state != "cancel")
            return sum(moves.mapped("product_uom_qty")) != sum(mls.mapped("qty_done"))

        mls_moves = mls.move_id
        for move in self.move_lines:
            if (
                move not in mls_moves
                or not move.move_line_ids == mls.filtered(lambda x: x.move_id == move)
                or move.move_orig_ids.filtered(lambda x: x.state not in ("done", "cancel"))
            ):
                return True
        return False

    def create_picking(
        self,
        picking_type,
        products_info=None,
        confirm=False,
        assign=False,
        create_batch=False,
        **kwargs,
    ):
        """Create and return a picking for the given picking_type
        For multiple pickings a list of lists of dicts of product_info should be passed,
        and pickings with the same picking_type and other kwargs are the same.
        The kwargs are applied to pickings, not moves. If needed, the moves can be created outside of create_pickings with _create_moves


        :args:
            - picking_type: picking type of the picking
        :kwargs:
            - products_info: list of dicts (or list(list(dicts)) for multiple picks) with product information
            - confirm: boolean flag to trigger action_confirm
            - assign: boolean flag to trigger action_assign
            - create_batch: boolean flag if a batch should be created

        """
        Picking = self.env["stock.picking"]

        # Prepare stock.picking info
        picking_values, products_info = self._prepare_picking_info(
            picking_type, products_info=products_info, **kwargs
        )
        # Create pickings
        pickings = Picking.create(picking_values)
        # Prepare stock.moves
        if products_info:
            move_values = self._prepare_move(pickings, products_info)
            # Create stock.moves
            self._create_move(move_values)

        if confirm:
            pickings.action_confirm()

        if assign:
            pickings.action_assign()

        if create_batch:
            self._create_batch(pickings)
        return pickings

    def _prepare_picking_info(self, picking_type, products_info=None, **kwargs):
        """Prepare the picking_info and products_info
        :args:
            - picking_type: picking type of the picking

        :kwargs:
            - products_info: None or list of dicts with product information

        :returns:
            picking_values: list(dict) of picking values
            products_info: None if products_info is None, or list(list(dict)) of product, qty info
        """
        picking_values = {
            "picking_type_id": picking_type.id,
            "location_id": picking_type.default_location_src_id.id,
            "location_dest_id": picking_type.default_location_dest_id.id,
        }
        picking_values.update(kwargs)
        if not products_info:
            return [picking_values], products_info
        else:
            if any(isinstance(el, list) for el in products_info):
                num_pickings = len(products_info)
                picking_vals = [picking_values.copy() for i in range(num_pickings)]
            else:
                # Convert picking values to a list of picking values
                picking_vals = [picking_values]
                # Convert the products_info to a list of lists
                products_info = [products_info]
            return picking_vals, products_info

    def _create_batch(self, pickings):
        """Creates a batch for the supplied pickings"""
        PickingBatch = self.env["stock.picking.batch"]
        PickingBatch.create({"picking_ids": [(6, 0, pickings.ids)]})

    def _prepare_move(self, pickings, products_info, **kwargs):
        """Return a list of the move details to be used later in creation of the move(s).
        The purpose of this is to allow for multiple moves to be created at once.

        :args:
            - pickings: iterable of picking objects to be assigned to the moves
            - products_info: list(list(dict)) with dict of product, uom_qty and uom_id
            If uom_id is not specified, the product UoM is  used.

        :returns:
            Move_values: list(dict)
        """
        move_values = []
        for i, picking in enumerate(pickings):
            for product_info in products_info[i]:
                product = product_info.get("product")
                uom_qty = product_info.get("uom_qty") or product_info.get("qty")
                uom_id = product_info.get("uom_id") or product.uom_id.id
                vals = {
                    "product_id": product.id,
                    "name": product.name,
                    "product_uom": uom_id,
                    "product_uom_qty": uom_qty,
                    "location_id": picking.location_id.id,
                    "location_dest_id": picking.location_dest_id.id,
                    "picking_id": picking.id,
                    "priority": picking.priority,
                    "picking_type_id": picking.picking_type_id.id,
                    "description_picking": product._get_description(picking.picking_type_id),
                }
                vals.update(kwargs)
                move_values.append(vals)
        return move_values

    @api.model
    def _create_move(self, move_values):
        """Create and return move(s) for the given move_values.
        Should be used in conjunction with _prepare_move to obtain move_values

        :args:
            - move_values: list of dictionary values (or single dictionary) to create move

        :returns:
            - move
        """
        Move = self.env["stock.move"]
        return Move.create(move_values)

    def get_empty_pickings(self, limit=1000):
        """
        Find and yield marked (is_empty = True) pickings.
        Search in self when it is set, otherwise search all pickings.
        """
        PickingType = self.env["stock.picking.type"]

        domain = [("u_is_empty", "=", True)]

        if self:
            domain.append(("id", "in", self.ids))
        else:
            picking_types = PickingType.search([("u_auto_unlink_empty", "=", True)])
            if picking_types:
                domain.append(("picking_type_id", "in", picking_types.ids))

        while True:
            records = self.search(domain, limit=limit)
            if not records:
                break
            yield records

    def unlink_empty(self):
        """
        Delete pickings in self that are empty by checking the pickings with u_is_empty field
        set to True. If self is empty, find and delete any picking with the previous criterion.
        This is to prevent us leaving junk data behind when refactoring
        """
        StockPicking = self.env["stock.picking"]

        records = StockPicking.browse()
        for to_unlink in self.get_empty_pickings():
            records |= to_unlink
            _logger.info("Unlinking empty pickings %r", to_unlink)
            moves = to_unlink.move_lines
            move_lines = to_unlink.move_line_ids
            non_empty_pickings = moves.picking_id | move_lines.picking_id
            if non_empty_pickings:
                raise ValidationError(
                    _("Trying to unlink non empty pickings: %r") % non_empty_pickings.ids
                )
            to_unlink.unlink()

        return self - records
