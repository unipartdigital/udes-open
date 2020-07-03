# -*- coding: utf-8 -*-

import logging

from collections import defaultdict

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    u_mark = fields.Boolean(
        "Marked",
        default=True,
        index=True,
        help="Pickings that are unused after refactoring are unmarked and deleted",
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

        group = ProcurementGroup.get_or_create(group_key, create=True)

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

    def action_assign(self):
        """Override action_assign to unlink empty pickings if needed"""
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

    def action_done(self):
        """Override action_done to unlink empty pickings if needed"""
        res = super(StockPicking, self).action_done()
        if self:
            self.unlink_empty()
        return res

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
