from odoo import models, fields, api
from odoo.exceptions import UserError
from odoo.tools.translate import _
import base64, io, csv


class UploadCsvImageWizard(models.TransientModel):
    _name = "upload.csv.image.wizard"
    _description = "Upload Product Images in Bulk with .csv"

    csv_file = fields.Binary(string="CSV File", required=True)
    csv_filename = fields.Char(string="CSV Filename")
    image_1920 = fields.Binary(String="Image", required=True)

    def action_upload_image(self):
        "Read each line from a CSV and apply the uploaded images to matching products"
        ProductTemplate = self.env["product.template"]
        CsvCheck = self.env["ir.attachment"]

        if not self.csv_file or not self.image_1920:
            return

        try:
            CsvCheck._check_valid_csv(self.csv_file)
        except Exception:
            raise UserError(
                _("The uploaded file is not a valid base64-encoded file: %s") % self.csv_filename
            )

        try:
            decoded = base64.b64decode(self.csv_file)
            data = io.StringIO(decoded.decode("utf-8"))
        except Exception:
            raise UserError(_("The uploaded file could not be dedcoded: %s") % self.csv_filename)

        reader = csv.DictReader(data)
        required_fields = {"internal_reference", "name"}
        missing_fields = required_fields - set(reader.fieldnames or [])
        if missing_fields:
            raise UserError(_("Missing required CSV columns: %s") % "".join(missing_fields))

        updated = 0
        line_no = 1
        errors = []

        for row in reader:
            line_no += 1
            barcode = (row.get("internal_reference") or "").strip()
            name = (row.get("name") or "").strip()

            if not barcode or not name:
                errors.append(_("Line %d: Missing barcode or name") % line_no)
                continue

            product = ProductTemplate.search([("default_code", "=", barcode)], limit=1)

            if not product:
                errors.append(_("Line %d: No product found for barcode '%s'") % (line_no, barcode))
                continue

            product.write({"image_1920": self.image_1920})
            updated += 1

        if updated == 0:
            raise UserError(_("No products were updated, please verify your CSV contents"))

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Upload Complete",
                "message": f"{updated} products updated",
                "sticky": False,
            },
        }
