import logging
from odoo import api, models, fields

_logger = logging.getLogger(__name__)


class EdiSaleRequestRecord(models.AbstractModel):
    """
    Extend ``edi.sale.request.record`` to add 
    Requested Date and Customer Reference fields
    """

    _inherit = "edi.sale.request.record"

    requested_date = fields.Datetime("Requested Date")
    client_order_ref = fields.Char(string="Customer Reference", readonly=True)

    @api.model
    def target_values(self, record_vals):
        """
        Override to add Requested Date and Customer Reference fields 
        to ``sale.order`` value dictionary
        """
        so_vals = super().target_values(record_vals)
        so_vals.update(
            {
                "requested_date": record_vals["requested_date"],
                "client_order_ref": record_vals["client_order_ref"],
            }
        )
        return so_vals
