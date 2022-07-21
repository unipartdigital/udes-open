"""EDI sale order request documents"""

from odoo import models


class EdiSaleRequestDocument(models.AbstractModel):
    """Extend ``edi.sale.request.document`` to generate a notifier suffix"""

    _inherit = "edi.sale.request.document"

    def report_invalid_records(self, doc):
        """Generate a suffix for the notifier to use if it is a partial success

        This function is only called if fail_fast is disabled.
        """
        res = super().report_invalid_records(doc)
        if res:
            doc.notifier_subject_suffix = " - with issues"
        else:
            doc.notifier_subject_suffix = False
        return res
