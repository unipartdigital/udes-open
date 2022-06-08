"""UDES core picking functionality."""
import logging

from odoo import api, models, fields, _
from odoo.exceptions import ValidationError, UserError
from .common import get_next_name
from odoo.addons.udes_common.models.fields import PreciseDatetime
from odoo.exceptions import ValidationError
from lxml import etree

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    # Adding fields to be hidden by default from form view.
    DetailedFormViewFields = [
        "u_first_picking_ids",
        "u_prev_picking_ids",
        "u_next_picking_ids",
        "u_created_backorder_ids",
        "u_first_pickings_qty",
        "u_prev_pickings_qty",
        "u_next_pickings_qty",
        "u_back_orders_qty",
    ]

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
    u_first_pickings_qty = fields.Integer(
        "First Pickings Qty",
        compute="_compute_first_picking_ids",
        help="First pickings quantity",
    )
    u_prev_picking_ids = fields.One2many(
        "stock.picking",
        string="Previous Pickings",
        compute="_compute_related_picking_ids",
        help="Previous pickings",
    )
    u_prev_pickings_qty = fields.Integer(
        "Previous Pickings Qty",
        compute="_compute_related_picking_ids",
        help="Previous pickings quantity",
    )
    u_next_picking_ids = fields.One2many(
        "stock.picking",
        string="Next Pickings",
        compute="_compute_related_picking_ids",
        help="Next pickings",
    )
    u_next_pickings_qty = fields.Integer(
        "Next Pickings Qty",
        compute="_compute_related_picking_ids",
        help="Next pickings quantity",
    )
    u_created_backorder_ids = fields.One2many(
        "stock.picking",
        string="Created Backorders",
        compute="_compute_related_picking_ids",
        help="Backorders created from this picking",
    )
    u_back_orders_qty = fields.Integer(
        "Created Back Orders Qty",
        compute="_compute_related_picking_ids",
        help="Created back orders quantity",
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
    # Date started for the picking, the done date time can be date_done
    # although the precision is less.
    u_date_started = PreciseDatetime(
        string="Date Started",
        help="Last date when the picking has been assigned.",
        readonly=True,
        copy=False,
    )
    u_assigned_user_ids = fields.One2many(
        comodel_name="res.users",
        inverse_name="u_picking_id",
        string="Assigned Users",
        copy=False,
        readonly=True,
        help="The assigned users to the picking",
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

            first_pickings = first_moves.picking_id
            picking.u_first_picking_ids = first_pickings
            picking.u_first_pickings_qty = len(first_pickings)

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
            back_orders = self.search([("backorder_id", "=", picking.id)])
            prev_pickings = picking.move_lines.move_orig_ids.picking_id
            next_pickings = picking.move_lines.move_dest_ids.picking_id

            picking.u_prev_picking_ids = prev_pickings
            picking.u_prev_pickings_qty = len(prev_pickings)
            picking.u_next_picking_ids = next_pickings
            picking.u_next_pickings_qty = len(next_pickings)
            picking.u_created_backorder_ids = back_orders
            picking.u_back_orders_qty = len(back_orders)

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
        # TODO: review if this is the best filter
        if self.location_dest_id.usage != "internal":
            domain.append(("usage", "=", "internal"))
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

    def _check_backorder_allowed(self, mls_to_keep, moves_to_move):
        """
        Assert that a backorder is allowed to be generated from self
        provided the subset of mls to move.
        Asserts that:
            * All moves being moved cannot be cancelled or done
            * All mls to retain must either be done or cancelled if any mls are being moved
            that have qty_done > 0.
        
        The latter condition is to ensure we do not place work done into
        a backorder and validate it whilst leaving the remaining work incomplete in the
        original picking. It does not restrict a user from essentially splitting a picking up,
        provided either:
            * The mls (and corresponding moves) being moved do not have the qty_done set
            * All the mls being retained have qty_done == product_uom_qty if any mls being
            moved have qty_done > 0.
        """
        self.ensure_one()

        # Only look at moving out incomplete moves from the picking
        incomplete_moves = self.move_lines.get_incomplete_moves()

        if moves_to_move - incomplete_moves:
            raise ValidationError(_("You cannot move completed or cancelled moves to a backorder!"))

        # Ensure that if we are moving done mls, all the mls_to_keep are also done
        if (
            mls_to_keep.get_lines_incomplete()
            and (incomplete_moves.move_line_ids - mls_to_keep).get_lines_done()
        ):
            raise ValidationError(
                _(
                    "You cannot create a backorder for done move lines whilst retaining incomplete ones"
                )
            )

    def _backorder_move_lines(self, mls_to_keep=None):
        """
        Create a backorder picking from self (expects a singleton)
        for all move lines not complete (and un-confirmed moves).
        All move lines must either have a qty_done == (0 or product_uom_qty),
        to enforce that splitting of mls is done prior to calling this method.
        The original picking (self) is not validated.

        The reason for this method is to maintain traceability of move lines,
        and not delete and re-create them inside _action_done().

        :returns: The created backorder
            If nothing to backorder (nothing done) returns an empty record set
        :raises:
            ValidationError: Move line exists with qty_done < product_uom_qty
            ValidationError: Backorder not allowed, retaining incomplete work
                whilst moving done work.

        NOTE: The current picking (self) is not yet complete until action_done
        is called. This is because the use case of this is not well defined,
        but instead think this of a helper method in drop off actions.
        One example may be because we want to call this on a sequence of move
        lines and propagate them through then call _action_done sequentially
        on the chain of pickings.
        """
        Picking = self.env["stock.picking"]
        Move = self.env["stock.move"]

        # Based on backorder creation in stock_move._action_done
        self.ensure_one()

        # Only look at moving out incomplete moves from the picking
        incomplete_moves = self.move_lines.get_incomplete_moves()

        # Check the state of self is allowed
        incomplete_moves.check_move_lines_not_partially_fulfilled()

        # Create a record for the moves to be moved into the backorder
        new_moves = Move.browse()

        # Determine the mls to keep if not provided
        if not mls_to_keep:
            mls_to_keep = incomplete_moves.move_line_ids.get_lines_done()

        # If any moves are untouched by mls_to_keep add them directly to new_moves
        touched_moves = mls_to_keep.mapped("move_id")
        untouched_moves = incomplete_moves - touched_moves
        new_moves |= untouched_moves

        # Check a backorder is allowed, we don't want to move work completed out, if
        # the original picking is not done.
        self._check_backorder_allowed(mls_to_keep, untouched_moves)

        for move in touched_moves.get_uncovered_moves(mls_to_keep):
            rel_mls = mls_to_keep & move.move_line_ids
            new_moves |= move.split_out_move(mls_to_keep=rel_mls)

        # Create backorder picking for remaining moves and return
        if new_moves:
            return self._create_backorder_picking(new_moves)

        # If no backorder return an empty record set
        return Picking.browse()

    def backorder_move_lines(self, mls_to_keep=None):
        """
        Create a backorder from self (singleton).

        Check first a backorder is required via `_requires_backorder`.

        If a backorder is required then:
            * mls_to_keep is None: Retain all move lines that
            have product_uom_qty == qty_done. All remaining work is
            placed into a backorder.
            * mls_to_keep is not None: Retain mls_to_keep in the original
            picking and backorder all remaining work.

        :returns:
            * The newly created backorder, or an empty record set.
        :raises:
            ValidationError: Move line exists with qty_done < product_uom_qty
            ValidationError: Backorder not allowed, retaining incomplete work
                whilst moving done work.

        NOTE: Neither pickings have `_action_done` called on them, this is strictly to
        create a backorder.
        NOTE: An appropriate use case of this method would be when trying to drop off
        working, or move work out of a picking so the original can be processed. The choice
        of empty record set is such that you can iteratively keep adding the returned result
        to another record set with no change if a backorder is not required.

        ```
        backorders = Picking.browse()
        for picking in original_pickings:
            # Determine mls to keep in the original picking and backorder the rest
            mls_to_keep = ...
            backorders |= picking.backorder_move_lines(mls_to_keep)
            
        original_pickings._action_done()
        ```
        """
        Picking = self.env["stock.picking"]
        if self._requires_backorder(mls=mls_to_keep):
            return self._backorder_move_lines(mls_to_keep=mls_to_keep)
        return Picking.browse()

    def _create_backorder_picking(self, moves):
        """
        Helper to create a backorder picking from the given moves
        NOTE: function uses sudo to override permissions. This is because creating
        a backorder requires having the picking create permission and we treat backorders
        creation differently from generic picking creation. E.g. the system needs to be able
        to create barckorders when pickings are validated regardless of the user's generic
        permissions.
        """
        bk_picking = self.sudo().copy(
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
        * If mls is None:
            - Checks if all move lines have the qty_done = total move qty (excluding cancelled)
        * If mls is not None:
            - Checks the move lines cover all moves within a picking. All moves are covered
            by the mls iff: The total of the move lines == total of the move 
            (minus any cancelled or done).
        
        Cannot be consolidated with _check_backorder in Odoo core, because it
        does not take into account any move lines parameter.

        :kwargs:
            - mls: A record set of move lines, default None.
        :returns: bool
        """
        # If the mls arg is not passed check the whole picking in self
        if mls is None:
            mls = self.move_line_ids
            moves = self.move_lines.filtered(lambda mv: mv.state != "cancel")
            return sum(moves.mapped("product_uom_qty")) != sum(mls.mapped("qty_done"))

        # Look through all incomplete moves to check if the mls passed cover the
        # remaining moves.
        mls_moves = mls.move_id
        incomplete_moves = self.move_lines.get_incomplete_moves()
        for move in incomplete_moves:
            rel_mls = mls.filtered(lambda x: x.move_id == move)
            if (
                # Move not in the specified mls
                move not in mls_moves
                # All mls cover the move
                or move.product_uom_qty != sum(rel_mls.mapped("product_uom_qty"))
                # Any of the oriignal moves remain incomplete
                or move.move_orig_ids.get_incomplete_moves()
            ):
                return True
        return False

    def create_picking(
        self,
        picking_type,
        products_info=None,
        group_id=None,
        confirm=False,
        assign=False,
        create_batch=False,
        **kwargs,
    ):
        """Create and return a picking for the given picking_type
        For multiple pickings a list of lists of dicts of product_info should be passed,
        and pickings with the same picking_type and other kwargs are the same.
        The kwargs are applied to pickings, not moves. If needed, the moves can be created outside
        of create_pickings with _create_moves


        :args:
            - picking_type: picking type of the picking
        :kwargs:
            - products_info: list of dicts (or list(list(dicts)) for multiple picks)
            with product information
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
            move_values = self._prepare_move(pickings, products_info, group_id=group_id)
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

    def unassign_users(self, skip_users=None):
        """
        Unassign the user(s) from the pickings in self.
        """
        for picking in self:
            picking._unassign_users(skip_users=skip_users)

    def _unassign_users(self, skip_users=None):
        """
        Unassign the user(s) from the picking in self if multiple users cannot
        exist on that picking type.
        If skip_users is specified, kick out all users in the picking except
        those in the skip_users recordset.
        """
        User = self.env["res.users"]
        self.ensure_one()

        picking = self
        users_to_unassign = User.browse()

        picking_type = picking.picking_type_id
        if not picking_type.can_handle_multiple_users():
            users_to_unassign = picking.u_assigned_user_ids
            if skip_users:
                users_to_unassign -= skip_users
            # TODO create_switch_user_event is a method that is not ported and doesn't seem
            # that should be ported as part of this module
            # if users_to_unassign:
            #     picking.create_switch_user_event(user_ids=users_to_unassign)
        users_to_unassign.sudo().write({"u_picking_id": False, "u_picking_assigned_time": False})

    @staticmethod
    def get_stock_investigation_message(quants):
        """
        Dummy method to be overridden on a per-customer basis.

        :args:
            - reason: stock.quant
                The quants for which to create the investigation message
        :returns: str
        """
        return ""

    def raise_stock_investigation(self, reason, quants, location):
        """
        Raises a stock investigation picking with the provided reason, quants and location.
        Un-reserves stock from affected pickings, creates stock investigation and reserves the stock,
        finally tries to reserve stock for the original pickings.

        :args:
            - reason: str
                The reason for which the stock is being investigated
            - quants: stock.quant
                The stock quants to reserve and investigate in the new picking
            - location:
                The location where the quants need to be investigated
        """
        Group = self.env["procurement.group"]

        wh = self.env.user.get_user_warehouse()
        stock_inv_pick_type = wh.u_stock_investigation_picking_type or wh.int_type_id
        group = Group.get_or_create(reason, create=True)

        # Post message and un-reserve stock
        for pick in self:
            pick.message_post(body=reason)
            pick.do_unreserve()

        # create a stock investigation pick
        investigation_picking = quants.create_picking(
            stock_inv_pick_type,
            only_available=True,
            location_id=location.id,
            group_id=group.id,
            confirm=True,
            assign=True,
        )

        picking_details = self.get_stock_investigation_message(quants.exists())

        if picking_details:
            picking_header = _("Stock Investigation created with: <br>")
            investigation_picking.message_post(body=picking_header + picking_details)

        # Try to re-assign the picking after creating the stock investigation
        # picking as we have reserved the problematic stock
        self.action_assign()

    def _check_entire_pack(self):
        """
        Override to avoid values at result_package_id when
        user scans products/avoid _check_entire_pack of products
        """
        pickings = self.filtered(
            lambda p: p.picking_type_id.u_user_scans != "product"
            and p.picking_type_id.u_target_storage_format != "product"
        )
        super(StockPicking, pickings)._check_entire_pack()

    def log_name(self):
        """This can probably go to models later"""
        return f"Picking{self.id, self.name}"

    def assert_valid_state(self):
        """Checks if the transfer is in a valid state, i.e., not done or cancel
        otherwise it raises and error
        """
        self.ensure_one()
        if self.state in ("done", "cancel"):
            raise ValidationError(_("Wrong state %s for %s") % (self.state, self.log_name()))

    def add_unexpected_parts(self, product_quantities):
        """ TODO not needed for now, add to readme when implemented
            return new mls?
        """
        raise ValidationError(_("Cannot handle over receiving!"))

    def validate_picking(self, create_backorder=False, force_validate=False):
        """ Validates a picking and returns its backorder if any has been created.
            Will raise an error if create_backorder is False and there are incomplete lines.
            Optionally will mark as done all lines of the picking if force_validate is set to True.
        """
        Picking = self.env["stock.picking"]

        new_picking = Picking.browse()
        requires_backorder = False
        mls_to_keep = None
        with self.statistics() as stats:
            self.assert_valid_state()
            # Mark all move lines as done if force validate
            if force_validate:
                self.move_line_ids.mark_as_done()
            # Check if a backorder is required and can be created:
            # a) Multi users is enabled
            # b) There are incomplete move lines and create backorder is allowed
            multi_users_enabled = self.picking_type_id.u_multi_users_enabled
            if self.move_line_ids.get_lines_incomplete():
                if multi_users_enabled:
                    user = self.env.user
                    mls_to_keep = self.move_line_ids.filtered(
                        lambda ml: ml.qty_done > 0 and ml.u_done_by_id == user
                    )
                    requires_backorder = True
                elif not create_backorder:
                    raise ValidationError(
                        _(
                            "Cannot validate %s because there are move lines todo and "
                            "backorder not allowed"
                        )
                        % self.log_name()
                    )
                else:
                    requires_backorder = True
            if requires_backorder:
                # NOTE: Added sudo() - Uses sudo() here as a user might not have the full access rights to stock.picking
                # but still needs more access rights for the flow
                new_picking = self.sudo().backorder_move_lines(mls_to_keep=mls_to_keep)

            # NOTE: Added sudo() - Uses sudo() here as a user might not have the full access rights to stock.picking
            # but still needs more access rights for the flow
            self.sudo()._action_done()
        _logger.info(
            "%s udes_stock::validate_picking in %.2fs, %d queries",
            self.log_name(),
            stats.elapsed,
            stats.count,
        )

        return new_picking

    @api.model
    def _fields_view_get(self, view_id=None, view_type="form", toolbar=False, submenu=False):
        result = super(StockPicking, self)._fields_view_get(
            view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu
        )
        # Set Autofocus on Additional Info
        if self._context.get("view_all_fields"):
            doc = etree.XML(result["arch"])
            for node in doc.xpath("//page[@name='extra']"):
                node.set("autofocus", "autofocus")
            result["arch"] = etree.tostring(doc)
        return result

    def action_detailed_view(self):
        """Function will call the picking form with a context view_all_fields set to True
        which will un hide the fields that were hidden"""
        form_view = self.env.ref("stock.view_picking_form")
        return self.base_model_detailed_view(self._name, form_view)

    def open_related_pickings(self, picking_ids, related_pickings_description):
        """Main method which is called from all models to redirect to a form view with context
        view_all_fields True in order to remove the fields that are configured in helpers"""
        self.ensure_one()
        if len(picking_ids) == 1:
            form_view = self.env.ref("stock.view_picking_form")
            action = {
                "type": "ir.actions.act_window",
                "view_type": "form",
                "view_model": "form",
                "views": [(form_view.id, "form")],
                "res_model": "stock.picking",
                "view_id": form_view.id,
                "res_id": picking_ids[0],
                "context": {"view_all_fields": False},
            }
        else:
            action = {
                "type": "ir.actions.act_window",
                "name": _("%s") % related_pickings_description,
                "res_model": "stock.picking",
                "view_type": "form",
                "view_mode": "tree,form",
                "domain": [("id", "in", picking_ids)],
                "context": {"view_all_fields": False},
            }
        return action

    def open_first_pickings(self):
        """Open first pickings button will redirect to first pickings"""
        return self.open_related_pickings(
            self.u_first_picking_ids.ids, "First Pickings"
        )

    def open_prev_pickings(self):
        """Open prev pickings button will redirect to previous pickings"""
        return self.open_related_pickings(
            self.u_prev_picking_ids.ids, "Previous Pickings"
        )

    def open_next_pickings(self):
        """Open next pickings button will redirect to next pickings"""
        return self.open_related_pickings(
            self.u_next_picking_ids.ids, "Next Pickings"
        )

    def open_back_orders(self):
        """Open back orders button will redirect to created back orders"""
        return self.open_related_pickings(
            self.u_created_backorder_ids.ids, "Created Back Orders"
        )

    @staticmethod
    def _get_package_search_domain(package):
        """
        Generate the domain for searching pickings that use a package.
        Useful as this can be overridden in other modules if functionality is expanded.

        :args:
            - package: a stock.quant.package object
        """
        return [
            "|",
            ("move_line_ids.package_id", "=", package.id),
            ("move_line_ids.result_package_id", "=", package.id),
        ]
