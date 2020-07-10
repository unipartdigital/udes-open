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

    def get_unmarked_pickings(self):
        """
        Find and yield unmarked (u_mark = False) pickings.
        Search in self when it is set, otherwise search all pickings.
        """
        PickingType = self.env["stock.picking.type"]

        domain = [
            ("u_mark", "=", False),
            ("is_locked", "=", True),
        ]

        if self:
            domain.append(("id", "in", self.ids))
        else:
            picking_types = PickingType.search([("u_auto_unlink_empty", "=", True)])
            if picking_types:
                domain.append(("picking_type_id", "in", picking_types.ids))

        while True:
            records = self.search(domain, limit=1000)
            if not records:
                break
            yield records

    def _get_default_new_picking_for_group_values(
        self, group, picking_type, location, dest_location
    ):
        """
        Return a dict of values for a new picking based on the supplied 
        Procurement Group Picking Type, Location and Destination Location.
        """
        values = {
            "group_id": group.id,
            "picking_type_id": picking_type.id,
            "location_id": location.id,
            "location_dest_id": dest_location.id,
        }

        return values

    def _remove_misleading_values(self, **kwargs):
        """
        If any of the fields in kwargs is set and its value is different
        than the new one, set the field value to False to avoid misleading values.
        E.g. if picking.origin is 'ASN001' and kwargs contains origin with value 
        'ASN002', picking.origin is set to False.
        """
        self.ensure_one()

        for field, value in kwargs.items():
            if field in self:
                current_value = self[field]

                if isinstance(current_value, models.BaseModel):
                    current_value = current_value.id
                if current_value and current_value != value:
                    self[field] = False

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
            picking_values = self._get_default_new_picking_for_group_values(
                group, picking_type, src_loc, dest_loc
            )
            picking_values.update(kwargs)

            picking = self.create_picking(picking_type, **picking_values)

        else:
            picking._remove_misleading_values(**kwargs)

        moves.write({"group_id": group.id, "picking_id": picking.id})

        move_lines = moves.mapped("move_line_ids")
        if move_lines:
            move_lines.write({"picking_id": picking.id})
            # After moving move lines check entire packages again just in case
            # some of the move lines are completing packages
            if picking.state != "done":
                picking._check_entire_pack()

        return picking

    def _prepare_extra_info_for_new_picking_for_group(self, moves):
        """
        Given the group of moves to refactor and its related pickings,
        prepare the extra info for the new pickings that might be created
        for the group of moves.
        Fields with more than one value are going to be ignored.
        """
        values = {}

        origins = list(set(self.mapped("origin")))
        if len(origins) == 1:
            values["origin"] = origins[0]

        partners = self.partner_id
        if len(partners) == 1:
            values["partner_id"] = partners.id

        dates_done = list(set(moves.mapped("date")))
        if len(dates_done) == 1:
            values["date_done"] = dates_done[0]

        return values

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
        for to_unlink in self.get_unmarked_pickings():
            records |= to_unlink
            _logger.info("Unlinking empty pickings %s", to_unlink)
            moves = to_unlink.move_lines
            move_lines = to_unlink.move_line_ids
            non_empty_pickings = moves.picking_id | move_lines.picking_id
            if non_empty_pickings:
                raise ValidationError(
                    _("Trying to unlink non empty pickings: " "%s" % non_empty_pickings.ids)
                )
            to_unlink.unlink()

        return self - records
