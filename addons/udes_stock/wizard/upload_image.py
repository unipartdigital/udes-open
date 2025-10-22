from odoo import models, fields, api

class StockUploadProductImageWizard(models.TransientModel):
    _name = "stock.upload.product.image.wizard"
    _description = "UDES Stock Product Image Uploader"

    image_1920 = fields.Binary(string="Image", attatchment=True, required=True)
    product_ids = fields.Many2many("product.template", string="Products")

    def action_upload_image(self):
        for product in self.product_ids:
            product.image_1920 = self.image_1920
        return {"type":"ir.actions.act_window_close"}
