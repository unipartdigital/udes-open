from odoo import fields, models


class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

    u_reserve_as_packages = fields.Boolean(
        string="Reserve Entire Packages",
        default=False,
        help="Flag to indicate reservations should be rounded up to entire packages.",
    )

    def get_pallet_barcode_format(self):
        """Override the method to get the pallet barcode regex from pallet type if not set on the picking type."""
        pallet_type = self.env.ref("udes_stock_packaging.pallet_package_type")
        self.ensure_one()
        return self.u_pallet_barcode_regex or pallet_type.package_type_regex

    def get_package_barcode_format(self):
        """Override the method to get the pallet barcode regex from package type if not set on the picking type."""
        package_type = self.env.ref("udes_stock_packaging.package_package_type")
        self.ensure_one()
        return self.u_package_barcode_regex or package_type.package_type_regex
