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

    def _extract_invalid_order_line(self, line):
        SaleRequestRecord = self.sale_request_record_model(line.doc_id)

        extracted = super()._extract_invalid_order_line(line)
        sale = SaleRequestRecord.search([('doc_id', '=', line.doc_id.id),
                                         ('name', '=', line.order_key)])
        extracted.insert(0, sale.client_order_ref)
        return extracted

    def _extract_invalid_order(self, order):
        extracted = super()._extract_invalid_order(order)
        extracted.insert(0, order.client_order_ref)
        return extracted
