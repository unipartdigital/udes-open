from odoo import models


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    def _prepare_task_info(self):
        """ Prepares info of a task
        """
        task = super(StockMoveLine, self)._prepare_task_info()
        picking = self.mapped('picking_id')
        picking.ensure_one()

        if picking.picking_type_id.u_user_scans == 'product':
            task.update(
                {'product_packaging':
                    self.mapped('move_id.sale_line_id.product_packaging.name')})

        return task
