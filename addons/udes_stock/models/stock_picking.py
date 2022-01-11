# -*- coding: utf-8 -*-
from odoo import api, models, fields, _
from odoo.exceptions import ValidationError


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
        locations = self._get_child_dest_locations(
            aux_domain=[("barcode", "!=", False), ("quant_ids", "=", False)], limit=limit
        )

        if sort:
            return locations.sorted(lambda l: l.name)
        else:
            return locations

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
        mls = self.move_line_ids
        if done:
            return self.move_line_ids.get_lines_done()
        elif done == False:
            return self.move_line_ids.get_lines_incomplete()
        return mls

    def _backorder_move_lines(self, mls=None):
        """Creates a backorder pick from self (expects a singleton)
        and a subset of stock.move.lines are then moved into it.

        Ensure this function is only called if _requires_back_order is True
        if everything is done - then a new pick is created and the old one is empty
        """
        Move = self.env["stock.move"]
        # Based on backorder creation in stock_move._action_done
        self.ensure_one()

        if mls is None:
            mls = self.move_line_ids.filtered(lambda x: x.qty_done > 0)

        # Test that the intersection of mls and move lines in picking is empty,
        # therefore we have some relevant move lines
        if not (mls & self.move_line_ids):
            raise ValidationError(
                _("There are no move lines within picking %s to backorder") % self.name
            )

        new_moves = Move.browse()
        for move, move_mls in mls.groupby("move_id"):
            new_moves |= move.split_out_move_lines(move_mls)

        # Create picking for completed move
        bk_picking = self.copy(
            {
                "name": "/",
                "move_lines": [(6, 0, new_moves.ids)],
                "move_line_ids": [(6, 0, new_moves.move_line_ids.ids)],
                "backorder_id": self.id,
            }
        )

        return bk_picking

    def _requires_backorder(self, mls):
        """Checks if a backorder is required by checking if all move lines
        within a picking are present in mls
        Cannot be consolidated with _check_backorder in Odoo core, because it
        does not take into account any move lines parameter.
        """
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
                uom_qty = product_info.get("uom_qty")
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
