from odoo import models


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    def _prepare_task_info(self):
        """ Prepares info of a task
        """
        task = super(StockMoveLine, self)._prepare_task_info()
        picking = self.mapped('picking_id')
        picking.ensure_one()
        user_scans = picking.picking_type_id.u_user_scans
        use_packaging = picking.picking_type_id.u_use_product_packaging
        if user_scans == 'product' and use_packaging:
            product_packaging = None
            privacy = self.env.ref('udes_stock.privacy_wrapping')
            if privacy in self.mapped('move_id.sale_line_id.product_packaging'):
                product_packaging = privacy.name

            task.update({
                'product_packaging': product_packaging
            })

        return task
