from odoo import models, fields, api
from .common import PRIORITY_GROUPS
from odoo.exceptions import ValidationError


class StockPicking(models.Model):
    _inherit = "stock.picking"

    u_location_category_id = fields.Many2one(
        comodel_name="stock.location.category",
        compute="_compute_location_category",
        string="Location Category",
        help="Used to know which pickers have the right equipment to pick it. "
             "In case multiple location categories are found in the picking it "
             "will be empty.",
        readonly=True,
        store=True,
    )

    @api.depends("move_line_ids", "move_line_ids.location_id")
    def _compute_location_category(self):
        """ Compute location category from move lines"""
        for picking in self:
            if picking.move_line_ids:
                categories = picking.move_line_ids.mapped("location_id.u_location_category_id")
                picking.u_location_category_id = categories if len(categories) == 1 else False

    def get_move_lines_done(self):
        """ Return the recordset of move lines done. """
        return self.move_line_ids.filtered(lambda o: o.qty_done > 0)

    def is_valid_location_dest_id(self, location=None, location_ref=None):
        """Whether the specified location or location reference is a valid
        putaway location for the picking. Expects a singleton instance.

        Parameters
        ----------
        location : Location obj
            Location record
        location_ref: char
            Location identifier can be the ID, name or the barcode

        Returns a boolean indicating the validity check outcome.
        """
        Location = self.env["stock.location"]
        self.ensure_one()

        if not location and not location_ref:
            raise ValidationError("Must specify a location or ref")

        dest_location = location or Location.get_location(location_ref)
        if not dest_location:
            raise ValidationError(_("The specified location is unknown."))

        valid_locations = self._get_child_dest_locations([("id", "=", dest_location.id)])

        return valid_locations.exists()

    def search_for_pickings(self, picking_type_id, picking_priorities, limit=1, domain=None):
        """Search for next available pickings based on picking type and priorities
        Parameters
        ----------
        picking_type_id : integer
            Id of picking type
        picking_priorities: List of integers
            List of priority ids
        limit: integer
            Location identifier can be the ID, name or the barcode.
            If limit = -1 means unbounded
        domain: Optional domain used when searching the pickings
        """
        Users = self.env["res.users"]
        PickingType = self.env["stock.picking.type"]

        search_domain = [] if domain is None else domain
        # Extra search parameters
        search_domain.extend(
            [
                ("picking_type_id", "=", picking_type_id),
                ("state", "=", "assigned"),
                ("batch_id", "=", False),
            ]
        )

        if limit == -1:
            limit = None
        if picking_priorities:
            search_domain.append(("priority", "in", picking_priorities))
        # Filter pickings by location categories if they are enabled for the given picking type
        picking_type = PickingType.browse(picking_type_id)
        if picking_type.u_use_location_categories:
            categories = Users.get_user_location_categories()
            if categories:
                search_domain.append(("u_location_category_id", "child_of", categories.ids))
        if picking_type.u_batch_dest_loc_not_allowed:
            search_domain.extend([("location_dest_id.u_blocked", "!=", True)])
        # Note: order should be determined by stock.picking._order
        pickings = self.search(search_domain, limit=limit)
        if not pickings:
            return None
        return pickings

    @api.model
    def _get_priority_groups(self):
        return list(PRIORITY_GROUPS.values())

    @api.model
    def get_priorities(self, picking_type_id=None):
        """Return a list of dicts containing the priorities of the
        all defined priority groups, in the following format:
            [
                {
                    'name': 'Picking',
                    'priorities': [
                        OrderedDict([('id', '2'), ('name', 'Urgent')]),
                        OrderedDict([('id', '1'), ('name', 'Normal')])
                    ]
                },
                {
                    ...
                },
                ...
            ]
        """

        if picking_type_id is None:
            return self._get_priority_groups()

        groups_with_pickings = []
        for group in self._get_priority_groups():
            priorities = [p["id"] for p in group["priorities"]]
            if self._priorities_has_ready_pickings(priorities, picking_type_id):
                groups_with_pickings.append(group)
        return groups_with_pickings

    def _priorities_has_ready_pickings(self, priorities, picking_type_id):
        domain = [
            ("picking_type_id", "=", picking_type_id),
            ("priority", "in", priorities),
            ("state", "=", "assigned"),
        ]
        return self.search_count(domain) >= 1
