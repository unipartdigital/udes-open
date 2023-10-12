"""A model for the Add Product Classifications action."""

import base64
import string

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AddProductClassification(models.TransientModel):
    """Add product classification action wizard."""

    _name = "udes_warehouse_classification.add_product_classification"
    _description = "Warehouse Classification - Add product classification wizard"

    file_data = fields.Binary(
        string="Upload file", help="A file of product default codes, one code per line"
    )

    @api.model
    def upload_products(self):
        """
        Process uploaded product default codes.

        If all the provided default codes are valid this method will set the
        classifications selected in the UI on each corresponding product
        template.
        """
        ProductTemplate = self.env["product.template"]
        ProductWarehouseClassification = self.env["product.warehouse.classification"]

        self.ensure_one()
        classifications = ProductWarehouseClassification.browse(self.env.context["active_ids"])
        file_data = base64.b64decode(self.file_data).decode("utf-8")
        cleaned_data = set(clean_data(file_data))
        product_templates = ProductTemplate.search([("default_code", "in", list(cleaned_data))])

        if len(product_templates) < len(cleaned_data):
            unknown = cleaned_data - set(product_templates.mapped("default_code"))
            message = _("Unknown product code(s) {}").format(", ".join(repr(s) for s in unknown))
            raise ValidationError(message)

        product_templates.write(
            {"u_product_warehouse_classification_ids": [(4, c.id) for c in classifications]}
        )


def clean_data(data):
    """
    Prepare data for lookup

    Arguments:
        data: a string containing one or more lines
    Returns:
        Lines with leading and trailing whitespace removed
    """
    # ASCII whitespace + common unicode space-ish characters.
    whitespace = string.whitespace + "\u200b\u00a0\ufeff"
    for line in data.splitlines():
        cleaned = line.strip(whitespace)
        if cleaned:
            yield cleaned
