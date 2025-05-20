from odoo import fields, api, models, _
from odoo.exceptions import ValidationError


class StockWarehouse(models.Model):
    _name = "stock.warehouse"
    _inherit = ["stock.warehouse", "mail.thread"]

    def _domain_u_damaged_location_id(self):
        """
        Domain for locations outside Stock
        """
        return ["!", ("id", "child_of", self.env.ref("stock.stock_location_stock").id)]

    # Add tracking for archiving.
    active = fields.Boolean(tracking=True)
    u_damaged_location_id = fields.Many2one(
        comodel_name="stock.location",
        string="Default Damaged Location",
        domain=_domain_u_damaged_location_id,
        help="The damaged location is a location outside Stock (it cannot be a"
        " location under Stock/), because we do not want damaged stock to"
        " be picked",
    )
    u_good_location_id = fields.Many2one(
        comodel_name="stock.location",
        string="Default Goods Location",
        help="Goods receive location used by mobile client",
    )
    u_pi_count_move_picking_type = fields.Many2one(
        comodel_name="stock.picking.type",
        string="PI Count Picking Type",
        help="Picking type used to create PI Count move pickings.",
    )
    u_missing_stock_location_id = fields.Many2one(
        comodel_name="stock.location",
        string="Default Missing Stock Location",
        help="The location where missing stock is moved to",
    )
    u_stock_investigation_picking_type = fields.Many2one(
        comodel_name="stock.picking.type",
        string="Stock Investigation Picking Type",
        help="Picking type used to create stock investigation pickings.",
    )
    u_max_reservable_serials = fields.Integer(
        "Maximum Reservable Serial Products",
        default=1000,
        help=(
            "Maximum reservable serial products. I.e. value would limit to reserve serial products because "
            "if the number is very high is taking a lot time to create move lines."
        ),
    )
    u_allowed_tracking_types = fields.Char(
        string="Allowed Tracking Types",
        default="none,lot,serial",
        help="Allowed tracking types on product level, values are comma separated and can use any combination of 3 "
             "possible options none, lot,serial."
    )
    u_force_upper_case_config = fields.Text(
        string="Force Upper Case Configuration",
        default="{}",
        help=""" Values added should be like below example in a key-value dictionary manner. 
        Left part(valid UDES model) should contain model name and Right part should contain 
        (valid field of the UDES object) field name in a comma-separated manner. 
        Below example will force upper case on fields default_code and barcode of UDES models product.product and
        stock.location. At the moment this validation is available on UDES models product.product 
        and stock.location
        {
          "product.product":  "default_code,barcode",
          "stock.location": "barcode",
        }
        """
    )

    @api.constrains("u_allowed_tracking_types")
    def _constrain_allowed_tracking_types(self):
        Product = self.env["product.product"]
        for warehouse in self:
            allowed_tracking_types_list = warehouse.u_allowed_tracking_types.split(",")
            not_allowed_tracking_types = [
                tracking for tracking in ("none", "lot", "serial") if tracking not in allowed_tracking_types_list
            ]
            if not_allowed_tracking_types:
                # Find active products that have already the tracking not in allowed tracking types.
                products = Product.search([("tracking", "in", not_allowed_tracking_types)])
                # Raise validation error to archive or delete those products, in order to be able to change
                # the warehouse config.
                if products:
                    raise ValidationError(
                        _("In order to change allowed tracking types configuration, archive the following products:"
                          " \n %s") % ", ".join(products.mapped("display_name"))
                    )

    def get_picking_types(self):
        """Returns a recordset with the picking_types of the warehouse"""
        PickingType = self.env["stock.picking.type"]

        self.ensure_one()
        # get picking types of the warehouse
        picking_types = PickingType.search([("warehouse_id", "=", self.id)])
        if not picking_types:
            raise ValidationError(_("Cannot find picking types for warehouse %s.") % self.name)

        return picking_types

    def _get_sequence_values(self):
        """
        Purpose: Overwrite the hardcoded sequence values. This will mean that when the warehouse is created the sequences for each picking type
        will not be created with the old Odoo prefix (The sequences should not be created at all). When the warehouse name is updated the
        sequences for the picking types will not be updated with the old Odoo prefix.
        """
        return {
            "in_type_id": {},
            "out_type_id": {},
            "pack_type_id": {},
            "pick_type_id": {},
            "int_type_id": {},
        }

    def _get_picking_type_update_values(self):
        """
        Remove active and default locations keys from picking types which makes sure core
        functionalities are not changed for our custom picking types when relevant fields that
        trigger this method are modified on the warehouse record.
        """
        result = super(StockWarehouse, self)._get_picking_type_update_values()
        result.get("in_type_id", {}).pop("default_location_dest_id", None)
        result.get("out_type_id", {}).pop("default_location_src_id", None)
        result.get("pick_type_id", {}).pop("active", None)
        result.get("pick_type_id", {}).pop("default_location_dest_id", None)
        return result
