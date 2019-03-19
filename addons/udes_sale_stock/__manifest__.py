# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'UDES Sale Stock Functionality',
    'version': '11.0',
    'summary': 'Inventory, Logistics, Warehousing',
    'description': "Extension of sale_stock model for UDES",
    'depends': [
        'edi_sale',
        'sale_order_dates',
        'sale_stock',
        'udes_stock',
    ],
    'category': 'Warehouse',
    'sequence': 12,
    'demo': [
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/udes_sale_stock_security.xml',
        'data/stock_config.xml',
        'views/sale_order_views.xml',
        'views/res_users_views.xml',
        'views/res_groups_views.xml',
    ],
    'qweb': [
    ],
    'test': [
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
