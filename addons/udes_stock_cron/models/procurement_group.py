from odoo import api, models, _
from odoo.exceptions import UserError
from odoo.addons.stock.models.stock_rule import ProcurementException
from odoo.osv import expression


class ProcurementGroup(models.Model):
    _inherit = "procurement.group"

    @api.model
    def run(self, procurements, raise_user_error=True):
        # raise ProcurementException in case we find a faulty procurement
        # we want to skip the procurement instead of raising an UserError if dealing with cron
        # so capture exception as ProcurementException and later raise a single UserError
        # with method _procure_orderpoint_confirm()
        def raise_exception(procurement_errors):
            if raise_user_error:
                _procurements, errors = zip(*procurement_errors)
                raise UserError("\n".join(errors))
            else:
                raise ProcurementException(procurement_errors)

        procurement_errors = []
        for procurement in procurements:
            # check procurement is of orderpoint and u_one_product_per_location warehouse
            # configuration is enabled
            if (
                procurement.values.get("orderpoint_id")
                and procurement.values.get("warehouse_id").u_one_product_per_location
            ):
                # check one product per location if location already has product(s)
                # create an error message
                if other_products_in_location := procurement.location_id.quant_ids.filtered(
                    lambda x: x.product_id != procurement.product_id
                ):
                    error = _(
                        'Error with operation "%s". Location "%s" already contains other products.'
                    ) % (
                        procurement.name,
                        procurement.location_id.display_name,
                    )
                    procurement_errors.append((procurement, error))
        if procurement_errors:
            raise_exception(procurement_errors)
        return super(ProcurementGroup, self).run(
            procurements, raise_user_error=raise_user_error
        )
