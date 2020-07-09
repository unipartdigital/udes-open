"""EDI sale order request documents"""

import logging
from odoo import api, models

_logger = logging.getLogger(__name__)


class EdiSaleRequestDocument(models.AbstractModel):
    """Extend ``edi.sale.request.document`` to trigger pick factorisation"""

    _inherit = "edi.sale.request.document"

    @api.model
    def execute(self, doc):
        """Execute document"""
        SaleLineRequestRecord = self.sale_line_request_record_model(doc)

        # Execute document with pick factorisation disabled
        super(EdiSaleRequestDocument, self.with_context(disable_move_refactor=True)).execute(doc)

        # Perform pick factorisation
        reqs = SaleLineRequestRecord.search([("doc_id", "=", doc.id)])
        with self.statistics() as stats:
            moves = reqs.mapped("sale_line_id.move_ids")
            moves._action_refactor()
        _logger.info("%s refactored in %.2fs, %d queries", doc.name, stats.elapsed, stats.count)
