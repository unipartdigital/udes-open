# -*- coding: utf-8 -*-

import logging

from collections import defaultdict

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    @api.depends(
        "move_lines",
        "move_lines.move_orig_ids",
        "move_lines.move_dest_ids",
        "move_lines.move_orig_ids.picking_id",
        "move_lines.move_dest_ids.picking_id",
    )
    def _compute_related_picking_ids(self):
        """Compute previous/next pickings"""
        Picking = self.env["stock.picking"]

        for picking in self:
            if picking.id:
                picking.u_created_back_orders = Picking.get_pickings(backorder_id=picking.id)

            picking.u_prev_picking_ids = picking.mapped("move_lines.move_orig_ids.picking_id")
            picking.u_next_picking_ids = picking.mapped("move_lines.move_dest_ids.picking_id")

    @api.depends("move_lines", "move_lines.move_orig_ids", "move_lines.move_orig_ids.picking_id")
    def _compute_first_picking_ids(self):
        """Compute first pickings"""
        Move = self.env["stock.move"]

        for picking in self:
            first_moves = Move.browse()
            moves = picking.move_lines
            while moves:
                first_moves |= moves.filtered(lambda x: not x.move_orig_ids)
                moves = moves.mapped("move_orig_ids")
            picking.u_first_picking_ids = first_moves.mapped("picking_id")

    u_mark = fields.Boolean(
        "Marked",
        default=True,
        index=True,
        help="Pickings that are unused after refactoring are unmarked " "and deleted",
    )

    # compute previous and next pickings
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
    u_first_picking_ids = fields.One2many(
        "stock.picking",
        string="First Pickings",
        compute="_compute_first_picking_ids",
        help="First pickings in the chain",
    )
    u_created_back_orders = fields.One2many(
        "stock.picking",
        string="Created Back Orders",
        compute="_compute_related_picking_ids",
        help="Created Back Orders",
    )

    def find_empty_pickings_to_unlink(self):
        """
        Finds empty pickings to unlink in self, when it is set, otherwise
        searches for any empty picking.

        Filter out of the generic search when the picking type does not
        have auto unlink empty enabled.
        """
        PickingType = self.env["stock.picking.type"]

        domain = [
            ("u_mark", "=", False),
            ("is_locked", "=", True),
        ]
        if self:
            domain.append(("id", "in", self.ids))
        else:
            pts = PickingType.search([("u_auto_unlink_empty", "=", False)])
            if pts:
                domain.append(("picking_type_id", "not in", pts.ids))
        while True:
            records = self.search(domain, limit=1000)
            if not records:
                break
            yield records

    def unlink_empty(self):
        """
        Delete pickings in self that are empty, locked and marked=False.
        If self is empty, find and delete any picking with the previous criterion.
        This is to prevent us leaving junk data behind when refactoring
        """
        records = self.browse()
        for to_unlink in self.find_empty_pickings_to_unlink():
            records |= to_unlink
            _logger.info("Unlinking empty pickings %s", to_unlink)
            moves = to_unlink.mapped("move_lines")
            move_lines = to_unlink.mapped("move_line_ids")
            non_empty_pickings = moves.mapped("picking_id") | move_lines.mapped("picking_id")
            if non_empty_pickings:
                raise ValidationError(
                    _("Trying to unlink non empty pickings: " "%s" % non_empty_pickings.ids)
                )
            to_unlink.unlink()

        return self - records

    @api.model
    def _new_picking_for_group(self, group_key, moves, **kwargs):
        """
        Find existing picking for the supplied group, if none found create a new one.
        Assign the moves to the picking and return it.
        """
        ProcurementGroup = self.env["procurement.group"]

        picking_type = moves.mapped("picking_type_id")
        picking_type.ensure_one()
        src_loc = moves.mapped("location_id")
        dest_loc = moves.mapped("location_dest_id")

        group = ProcurementGroup.get_group(group_identifier=group_key, create=True)

        # Look for an existing picking with the right group
        picking = self.search(
            [
                ("picking_type_id", "=", picking_type.id),
                ("location_id", "=", src_loc.id),
                ("location_dest_id", "=", dest_loc.id),
                ("group_id", "=", group.id),
                # NB: only workable pickings
                ("state", "in", ["assigned", "confirmed", "waiting"]),
            ]
        )

        if not picking:
            # Otherwise reuse the existing picking if all the moves
            # already belong to it and it contains no other moves
            # The picking_type_id, location_id and location_dest_id
            # will match already
            current_picking = moves.mapped("picking_id")
            if len(current_picking) == 1 and current_picking.mapped("move_lines") == moves:
                values = {"group_id": group.id}
                values.update(kwargs)

                current_picking.write(values)
                picking = current_picking

        if not picking or len(picking) > 1:
            # There was no suitable picking to reuse.
            # Create a new picking.
            values = {
                "picking_type_id": picking_type.id,
                "location_id": src_loc.id,
                "location_dest_id": dest_loc.id,
                "group_id": group.id,
            }
            values.update(kwargs)

            picking = self.create(values)

        else:
            # Avoid misleading values for extra fields.
            # If any of the fields in kwargs is set and its value is different
            # than the new one, set the field value to False to avoid misleading
            # values.
            # For instance, picking.origin is 'ASN001' and kwargs contains
            # origin with value 'ASN002', picking.origin is set to False.
            for field, value in kwargs.items():
                current_value = getattr(picking, field, None)
                if isinstance(current_value, models.BaseModel):
                    current_value = current_value.id
                if current_value and current_value != value:
                    setattr(picking, field, False)

        moves.write({"group_id": group.id, "picking_id": picking.id})

        move_lines = moves.mapped("move_line_ids")
        if move_lines:
            move_lines.write({"picking_id": picking.id})
            # After moving move lines check entire packages again just in case
            # some of the move lines are completing packages
            if picking.state != "done":
                picking._check_entire_pack()

        return picking

    def _get_package_search_domain(self, package):
        """Generate the domain for searching pickings of a package"""
        return [
            "|",
            ("move_line_ids.package_id", "child_of", package.id),
            ("move_line_ids.result_package_id", "child_of", package.id),
        ]

    def get_pickings(
        self,
        origin=None,
        package_name=None,
        states=None,
        picking_type_ids=None,
        allops=None,
        location_id=None,
        product_id=None,
        backorder_id=None,
        result_package_id=None,
        picking_priorities=None,
        picking_ids=None,
        batch_id=None,
        extra_domain=None,
    ):

        """ Search for pickings by various criteria

            @param (optional) origin
                Search for stock.picking records based on the origin
                field. Needs to be a complete match.

            @param (optional) package_name
                Search of stock.pickings associated with a specific
                package_name (exact match).

            @param (optional) product_id
                If it is set then location_id must also be set and stock.pickings
                are found using both of those values (states is optional).

            @param (optional) location_id
                If it is set then only internal transfers acting on that
                location are considered. In all cases, if states is set
                then only pickings in those states are considered.

            @param (optional) backorder_id
                Id of the backorder picking. If present, pickings are found
                by backorder_id and states.

            (IGNORE FOR NOW) @param (optional) allops: Boolean.
                If True, all pack operations are included. If False, only
                pack operations that are for the pallet identified by param
                pallet (and it's sub-packages) are included.
                Defaults to True.

            @param (optional) states
                A List of strings that are states for pickings. If present
                only pickings in the states present in the list are
                returned.
                Defaults to all, possible values:
                'draft', 'cancel', 'waiting', 'confirmed', 'assigned', 'done'

            @param (optional) result_package_id
                If an id is supplied all pickings that are registered to
                this package id will be returned. This can also be used
                in conjunction with the states parameter

            @param (optional) picking_priorities
                When supplied all pickings of set priorities and states
                will be searched and returned

            @param (optional) picking_ids
                When supplied pickings of the supplied picking ids will
                be searched and returned. If used in conjunction with
                priorities then only those pickings of those ids will be
                returned.

            @param (optional) picking_type_ids: Array (int)
                If it is set the pickings returned will be only from the picking types in the array.
        """
        Picking = self.env["stock.picking"]
        Package = self.env["stock.quant.package"]
        Users = self.env["res.users"]

        order = None

        if states is None:
            states = ["draft", "cancel", "waiting", "confirmed", "assigned", "done"]

        warehouse = Users.get_user_warehouse()
        if picking_type_ids is None:
            picking_type_ids = warehouse.get_picking_types().ids

        if self:
            domain = [("id", "in", self.mapped("id"))]
        elif origin:
            domain = [("origin", "=", origin)]
        elif backorder_id:
            domain = [("backorder_id", "=", backorder_id)]
        elif result_package_id:
            domain = [("move_line_ids.result_package_id", "=", result_package_id)]
        elif product_id:
            if not location_id:
                raise ValidationError(_("Please supply a location_id"))
            domain = [
                ("move_line_ids.product_id", "=", product_id),
                ("move_line_ids.location_id", "=", location_id),
            ]
        elif package_name:
            package = Package.get_package(package_name, no_results=True)
            if not package:
                return Picking.browse()
            domain = self._get_package_search_domain(package)
        elif picking_priorities:
            domain = [
                ("priority", "in", picking_priorities),
                ("picking_type_id", "=", warehouse.pick_type_id.id),
                ("batch_id", "=", False),
            ]
            if picking_ids is not None:
                domain.append(("id", "in", picking_ids))
            order = "priority desc, scheduled_date, id"
        elif picking_ids:
            domain = [("id", "in", picking_ids)]
        elif location_id:
            warehouse = Users.get_user_warehouse()
            domain = [
                ("location_id", "=", location_id),
                ("picking_type_id", "=", warehouse.int_type_id.id),
            ]
        elif batch_id is not None:
            domain = [("batch_id", "=", batch_id)]
        else:
            raise ValidationError(_("No valid options provided."))

        # add the states to the domain
        domain.append(("state", "in", states))
        # add the picking type ids to the domain
        domain.append(("picking_type_id", "in", picking_type_ids))

        # add extra domain if there is any
        if extra_domain:
            domain.extend(extra_domain)

        pickings = Picking.search(domain, order=order)

        return pickings

    def action_assign(self):
        """
        Unlink empty pickings after action_assign, as there may be junk data after a refactor
        """
        res = super(StockPicking, self).action_assign()
        if self:
            self.unlink_empty()
        return res

    def action_confirm(self):
        """Override action_confirm to unlink empty pickings if needed"""
        res = super(StockPicking, self).action_confirm()
        if self:
            self.unlink_empty()
        return res
