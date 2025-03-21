from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ContainerType(models.Model):
    _name = "container.type"
    _description = "Container Type"
    _inherit = ["mail.thread", "mixin.stock.model"]

    _get_info_field_names = {
        "length",
        "width",
        "height",
        "weight",
    }

    active = fields.Boolean(default=True, string="Active", tracking=True)
    name = fields.Char(
        string="Name",
        required=True,
        tracking=True,
        help="The name of the container type, e.g Medium Box 1.",
    )
    length = fields.Float(
        string="Length (mm)",
        required=True,
        tracking=True,
        help="The length of the container type in mm.",
    )
    width = fields.Float(
        string="Width (mm)",
        required=True,
        tracking=True,
        help="The width of the container type in mm.",
    )
    height = fields.Float(
        string="Height (mm)",
        required=True,
        tracking=True,
        help="The height of the container type in mm.",
    )
    weight = fields.Float(
        string="Weight (kg)",
        required=True,
        tracking=True,
        help="The weight of the container type in kg.",
    )
    use_product_dims = fields.Boolean(
        string="Use Product Dimensions",
        default=False,
        help="If checked, the package will use product dimensions instead of box dimensions."
    )

    _sql_constraints = [
        (
            "name_uniq",
            "unique (name)",
            "A container type with that name already exists.",
        ),
    ]

    @api.constrains("length", "width", "height", "weight")
    def _check_dimensions_and_weight(self):
        """
        Ensure these fields do not contain negative quantities else
        it could impact calculations when the container types are used.
        """
        non_negative_fields = ["length", "width", "height", "weight"]
        violating_records = self.filtered(lambda ct: any([getattr(ct, f) <= 0 for f in non_negative_fields]))
        if violating_records:
            raise ValidationError(
                _(
                    "Dimensions and weight must be positive values. "
                    "%s have physical attributes which are less than 0."
                    % ", ".join(violating_records.mapped("name"))
                )
            )
