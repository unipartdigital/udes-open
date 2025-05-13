from odoo import models, fields, api, _


class PackageType(models.Model):
    _name = "package.type"
    _description = "Package Type"
    _order = "sequence"
    _inherit = ["mail.thread", "mixin.stock.model"]

    _get_info_field_names = {
        "package_type_regex",
    }

    active = fields.Boolean(default=True, string="Active", tracking=True)
    name = fields.Char(
        string="Name",
        required=True,
        tracking=True,
        help="The name of the package type, e.g Pallet, Package, Trolley etc.",
    )
    package_type_regex = fields.Char(
        "Package Type Format",
        help="If is not set, it will allow all names to be entered when creating a package linked with this type."
    )
    sequence = fields.Integer(
        "Sequence", default=100, help="Used to order package types"
    )
    sequence_id = fields.Many2one(
        "ir.sequence", string="Package Sequence",
    )
