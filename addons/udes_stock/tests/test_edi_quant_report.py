"""Stock level report tests"""

import base64
from itertools import islice
import xlrd
from odoo.addons.edi_stock.tests.common import EdiQuantCase


class TestQuantReport(EdiQuantCase):
    """Stock level report tests"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.doc_type_quant_report = cls.env.ref(
            'udes_stock.edi_quant_report_document_type'
        )

    @classmethod
    def create_quant_report(cls):
        """Create stock level report document"""
        return cls.create_document(cls.doc_type_quant_report)

    def output_worksheets(self, doc):
        """Get output worksheet contents"""
        self.assertEqual(len(doc.output_ids), 1)
        attachment = doc.output_ids
        self.assertRegex(attachment.datas_fname, r'STK\d+\.xls')
        wb = xlrd.open_workbook(
            file_contents=base64.b64decode(attachment.datas)
        )
        return [
            [
                [x.value for x in row]
                for row in islice(sheet.get_rows(), 1, None)
            ] for sheet in wb.sheets()
        ]

    def test01_empty(self):
        """Empty stock"""
        doc = self.create_quant_report()
        self.assertTrue(doc.action_execute())
        detail, summary = self.output_worksheets(doc)
        self.assertEqual(detail, [])
        self.assertEqual(summary, [])

    def test02_basic(self):
        """Basic operation"""
        Package = self.env['stock.quant.package']
        pal01 = Package.create({'name': "PAL01"})
        pal02 = Package.create({'name': "PAL02"})
        pal03 = Package.create({'name': "PAL03"})
        self.create_quant(self.fridge, self.apple, 3)
        self.create_quant(self.fridge, self.apple, 1, package_id=pal01.id)
        self.create_quant(self.fridge, self.banana, 2, package_id=pal01.id)
        self.create_quant(self.fridge, self.cherry, 100, package_id=pal02.id)
        self.create_quant(self.cupboard, self.apple, 10, package_id=pal03.id)
        self.create_quant(self.cupboard, self.banana, 1)
        self.create_quant(self.cupboard, self.cherry, 20, package_id=pal03.id)
        doc = self.create_quant_report()
        self.assertTrue(doc.action_execute())
        detail, summary = self.output_worksheets(doc)
        self.assertEqual(detail, [
            ['APPLE', 'CUPBOARD', 'PAL03', 10],
            ['APPLE', 'FRIDGE', '', 3],
            ['APPLE', 'FRIDGE', 'PAL01', 1],
            ['BANANA', 'CUPBOARD', '', 1],
            ['BANANA', 'FRIDGE', 'PAL01', 2],
            ['CHERRY', 'CUPBOARD', 'PAL03', 20],
            ['CHERRY', 'FRIDGE', 'PAL02', 100],
        ])
        self.assertEqual(summary, [
            ['APPLE', 3, 14],
            ['BANANA', 2, 3],
            ['CHERRY', 2, 120],
        ])
