"""Stock level report"""

import io
import xlwt
from odoo import api, fields, models
from odoo.tools.translate import _


class EdiDocument(models.Model):
    """Extend ``edi.document`` to include stock level report records"""

    _inherit = 'edi.document'

    u_quant_report_ids = fields.One2many(
        'udes_stock.edi.quant.report.record', 'doc_id',
        string="Stock Level Reports",
    )


class EdiQuantReportRecord(models.Model):
    """Stock level report record"""

    _name = 'udes_stock.edi.quant.report.record'
    _inherit = 'edi.quant.report.record'
    _description = "Stock Level Report"

    location_id = fields.Many2one('stock.location', string="Location",
                                  required=True, readonly=True, index=True)
    package_id = fields.Many2one('stock.quant.package', string="Package",
                                 required=False, readonly=True, index=True)

    @api.model
    def record_values(self, quants):
        """Construct EDI record value dictionary"""
        vals = super().record_values(quants)
        vals.update({
            'location_id': quants.mapped('location_id').id,
            'package_id': quants.mapped('package_id').id,
        })
        return vals


class EdiQuantReportDocument(models.AbstractModel):
    """Stock level report document"""

    _name = 'udes_stock.edi.quant.report.document'
    _inherit = 'edi.quant.report.document'
    _description = "Stock Level Report"

    @api.model
    def quant_report_list(self, _doc, quants):
        """Get quants for which reports should be generated

        Quants are grouped by product, location, and package, and
        assigned a reporting name based on the order within the
        report.
        """

        # Precache associated records
        quants.mapped('product_id.default_code')
        quants.mapped('location_id.name')
        quants.mapped('package_id.name')

        # Sort, group, and index by grouping key
        key = lambda x: (x.product_id.default_code, x.location_id.name,
                         x.package_id.name or '')
        return (v.with_context(default_name='%05d' % i) for i, (k, v) in
                enumerate(quants.groupby(key=key)))

    @api.model
    def execute(self, doc):
        """Execute document"""
        super().execute(doc)

        # Precache associated records
        recs = doc.u_quant_report_ids
        recs.mapped('product_id.default_code')
        recs.mapped('location_id.name')
        recs.mapped('package_id.name')

        # Construct workbook
        wb = xlwt.Workbook()

        # Construct stock detail worksheet
        detail = wb.add_sheet(_("Stock File"))
        for col, label in enumerate((_("Part Number"), _("Location"),
                                     _("Pallet"), _("Quantity"))):
            detail.write(0, col, label)
        for row, rec in enumerate(recs, start=1):
            detail.write(row, 0, rec.product_id.default_code)
            detail.write(row, 1, rec.location_id.name)
            if rec.package_id:
                detail.write(row, 2, rec.package_id.name)
            detail.write(row, 3, rec.qty)

        # Construct stock summary worksheet
        summary = wb.add_sheet(_("Stock Summary"))
        for col, label in enumerate((_("Part Number"), _("Pallet Count"),
                                     _("Quantity"))):
            summary.write(0, col, label)
        for row, (product, product_recs) in enumerate(
                recs.groupby(key=lambda x: x.product_id, sort=False), start=1
        ):
            summary.write(row, 0, product.default_code)
            summary.write(row, 1, len(product_recs))
            summary.write(row, 2, sum(x.qty for x in product_recs))

        # Construct spreadsheet file
        with io.BytesIO() as output:
            wb.save(output)
            data = output.getvalue()

        # Construct output attachment
        prepare_date = fields.Datetime.from_string(doc.prepare_date)
        filename = '%s%s.xls' % (doc.doc_type_id.sequence_id.prefix,
                                 prepare_date.strftime('%Y%m%d%H%M%S'))
        doc.output(filename, data)
