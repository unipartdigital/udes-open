# -*- coding: utf-8 -*-

from odoo import api, models, _


class StockPickingBatch(models.Model):
    _inherit = 'stock.picking.batch'

    def get_next_task(self, skipped_product_ids=None):
        """ Gets the next not completed task of the batch to be done
        """
        self.ensure_one()

        mls = self.get_available_move_lines(state='not_done', skipped_product_ids=skipped_product_ids, sorted=True)
        tasks_picked = len(self.get_available_move_lines().filtered(lambda ml: ml.qty_done == ml.product_qty)) > 0

        task = {'tasks_picked': tasks_picked,
                'num_tasks_to_pick': 0,
                }
        if mls:
            task.update(mls[0]._prepare_task_info())
            user_scans = mls[0].picking_id.picking_type_id.u_user_scans
            if user_scans == 'product':
                num_tasks_to_pick = len(mls)
            else:
                # TODO: check pallets
                num_tasks_to_pick = len(mls.mapped('package_id'))
            task['num_tasks_to_pick'] = num_tasks_to_pick

        return task
