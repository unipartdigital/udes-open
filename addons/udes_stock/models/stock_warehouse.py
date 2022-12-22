# -*- coding: utf-8 -*-

from odoo import fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools.func import lazy_property


class StockWarehouse(models.Model):
    _inherit = "stock.warehouse"

    def _domain_u_damaged_location_id(self):
        """
        Domain for locations outside Stock
        """
        Location = self.env["stock.location"]
        stock_children_locations = Location.search(
            [("id", "child_of", self.env.ref("stock.stock_location_stock").id)]
        ).mapped("id")

        return [("id", "not in", stock_children_locations)]

    def _domain_warehouse_picking_types(self):
        """
        Domain for getting picking types in the current warehouse
        """
        User = self.env["res.users"]

        warehouse = User.get_user_warehouse()
        return [("warehouse_id", "=", warehouse.id)]

    u_handle_damages_picking_type_ids = fields.Many2many(
        comodel_name="stock.picking.type",
        relation="stock_warehouse_damages_picking_types_rel",
        string="Which Picking Types Handle Damages",
    )
    u_missing_stock_location_id = fields.Many2one(
        comodel_name="stock.location", string="The Location Where Missing Stock Is Moved To"
    )
    u_print_labels_picking_type_ids = fields.Many2many(
        comodel_name="stock.picking.type",
        relation="stock_warehouse_print_label_picking_types_rel",
        string="Picking types which automatically print labels",
    )
    u_damaged_location_id = fields.Many2one(
        comodel_name="stock.location",
        string="The Location Where Damaged Stock Is Moved To",
        domain=_domain_u_damaged_location_id,
        help="The damaged location is a location outside Stock (it cannot be a"
        " location under Stock/), because we do not want damaged stock to"
        " be picked",
    )
    u_temp_dangerous_location_id = fields.Many2one(
        comodel_name="stock.location",
        string="Dangerous Goods Location (staging location outside Stock)",
        help="Location that temporary stores the dangerous" " products waiting to be putaway.",
    )
    u_probres_location_id = fields.Many2one(
        comodel_name="stock.location",
        string="PROBRES Location",
        help="Location that temporary stores the products cannot be putaway,"
        " and require special attention",
    )
    u_incomplete_location_id = fields.Many2one(
        comodel_name="stock.location",
        string="Incomplete Location",
        help="Location that temporary stores the products" " partially dropped from a picking",
    )
    u_dangerous_location_id = fields.Many2one(
        comodel_name="stock.location",
        string="Dangerous Location (inside Stock)",
        help="The dangerous location is the location inside Stock where"
        " the dangerous products are stored. It might have sublocations.",
    )
    u_pallet_barcode_regex = fields.Char("Pallet Barcode Format", default="^PAL(\\d)+$")
    u_package_barcode_regex = fields.Char("Package Barcode Format", default="^PACK(\\d)+$")
    u_product_barcode_regex = fields.Char("Product Barcode Replacement Regex", default="")
    u_pi_count_move_picking_type = fields.Many2one(
        comodel_name="stock.picking.type",
        string="PI Count Picking Type",
        help="Picking type used to create PI Count move pickings.",
    )
    u_stock_investigation_picking_type = fields.Many2one(
        comodel_name="stock.picking.type",
        string="Stock Investigation Picking Type",
        help="Picking type used to create stock investigation pickings.",
    )
    u_show_rpc_timing = fields.Boolean(
        string="Show RPC timing", default=False, help="Show RPC call times on mobile UI"
    )

    u_reserved_package_name = fields.Char(
        "Reserved package name(s)",
        default="UDES00000",
        help="A comma seperated list of values which can't be used for package "
        "names and are reserved for PI purposes.",
    )

    u_max_package_depth = fields.Integer(
        "Maximum Package Recursion",
        default=2,
        help="Maximum depth for package hierarchy. I.e. a value of 2 would limit the number of levels in hierarchy to 2, one level of packages(with no subpackages) inside an outer package.",
    )

    u_inventory_adjust_reserved = fields.Boolean(
        string="Inventory Adjust Reserved Stock",
        default=False,
        help="Allow users to inventory adjust reserved stock.",
    )

    u_disable_no_backorder_button_picking_type_ids = fields.Many2many(
        comodel_name="stock.picking.type",
        relation="stock_warehouse_disable_no_backorder_button_rel",
        string="Which Picking Types to hide the `No Backorder`",
        help="Which Picking Types have to always create backorders on validate when the pickings "
        "are not fully available, so hide the `No backorder` button.",
        domain=_domain_warehouse_picking_types,
    )

    u_allow_create_picking_reserved_package = fields.Boolean(
        string="Allow Pickings for Packages/Pallets with Reserved Quants",
        default=False,
        help="Allow on the fly pickings to be created for packages with reserved quants "
        "from the package view. "
        "Users must also be a member of the group_manage_reserved_packages group.",
    )

    u_log_batch_picking = fields.Boolean(
        string="Log batch picking",
        default=False,
        help="Logs details when picking is added to batch picking",
    )
    u_show_current_quantity = fields.Boolean(
        string="Show Current Quantity",
        default=False,
        help="Show current quantity on old mobile look up. "
             "If this is set True the field to compute current quantity on stock should be added",
    )

    @lazy_property
    def reserved_package_name(self):
        return (
            list(map(lambda s: s.strip(), self.u_reserved_package_name.split(",")))
            if self.u_reserved_package_name
            else []
        )

    def _prepare_info(self):
        """
            Prepares the following info of the warehouse in self:
            - in_type_id: int
            - out_type_id: int
            - pack_type_id: int
            - pick_type_id: int
            - int_type_id: int
            - put_type_id: int
            - u_missing_stock_location_id: int
            - u_damaged_location_id: int
            - u_temp_dangerous_location_id: int
            - u_probres_location_id: int
            - u_incomplete_location_id: int
            - u_dangerous_location_id: int
            - u_handle_damages_picking_type_ids: list(int)
            - u_print_labels_picking_type_ids: list(int)
            - u_disable_no_backorder_button_picking_type_ids: list(int)
            - u_pallet_barcode_regex: string
            - u_package_barcode_regex: string
            - u_product_barcode_regex: string
            - u_show_rpc_timing: boolean
            - u_allow_create_picking_reserved_package: boolean
        """
        self.ensure_one()

        put_away_type = self._get_a_type("Putaway")
        replen_type = self._get_a_type("Replen")

        return {
            "in_type_id": self.in_type_id.id,
            "out_type_id": self.out_type_id.id,
            "pack_type_id": self.pack_type_id.id,
            "pick_type_id": self.pick_type_id.id,
            "int_type_id": self.int_type_id.id,
            "put_type_id": put_away_type.id if put_away_type else None,
            "replen_type_id": replen_type.id if replen_type else None,
            "u_missing_stock_location_id": self.u_missing_stock_location_id.id,
            "u_damaged_location_id": self.u_damaged_location_id.id,
            "u_temp_dangerous_location_id": self.u_temp_dangerous_location_id.id,
            "u_probres_location_id": self.u_probres_location_id.id,
            "u_incomplete_location_id": self.u_incomplete_location_id.id,
            "u_dangerous_location_id": self.u_dangerous_location_id.id,
            "u_handle_damages_picking_type_ids": self.u_handle_damages_picking_type_ids.ids,
            "u_print_labels_picking_type_ids": self.u_print_labels_picking_type_ids.ids,
            "u_disable_no_backorder_button_picking_type_ids": self.u_disable_no_backorder_button_picking_type_ids.ids,
            "u_pallet_barcode_regex": self.u_pallet_barcode_regex,
            "u_package_barcode_regex": self.u_package_barcode_regex,
            "u_product_barcode_regex": self.u_product_barcode_regex,
            "u_pi_count_move_picking_type": self.u_pi_count_move_picking_type.id,
            "u_stock_investigation_picking_type": self.u_stock_investigation_picking_type.id,
            "u_show_rpc_timing": self.u_show_rpc_timing,
            "u_allow_create_picking_reserved_package": self.u_allow_create_picking_reserved_package,
            "u_show_current_quantity": self.u_show_current_quantity,
        }

    def get_info(self):
        """ Return a list with the information of each warhouse in self.
        """
        res = []
        for warehouse in self:
            res.append(warehouse._prepare_info())

        return res

    def get_picking_types(self):
        """ Returns a recordset with the picking_types of the warehouse
        """
        PickingType = self.env["stock.picking.type"]

        self.ensure_one()
        # get picking types of the warehouse
        picking_types = PickingType.search([("warehouse_id", "=", self.id)])
        if not picking_types:
            raise ValidationError(_("Cannot find picking types for warehouse %s.") % self.name)

        return picking_types

    def _get_a_type(self, picking_type_name):
        # Short term fix
        put = self.get_picking_types().filtered(lambda pt: pt.name == picking_type_name)

        # Restored to a non null default as some customer functionality may
        # rely on defaulting to internal transfer instead of None
        if not put:
            put = self.int_type_id

        return put
