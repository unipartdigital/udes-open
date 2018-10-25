# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'UDES Sale Stock Functionality',
    'version': '11.0',
    'summary': 'Inventory, Logistics, Warehousing',
    'description': "Extension of sale_stock model for UDES",
    'depends': [
        'sale_stock',
    ],
    'category': 'Warehouse',
    'sequence': 12,
    'demo': [
    ],
    'data': [
        'data/product_packaging.xml',
    ],
    'qweb': [
    ],
    'test': [
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
