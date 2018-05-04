# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'UDES Core Functionality',
    'version': '11.0',
    'summary': 'Inventory, Logistics, Warehousing',
    'description': "Holds core functionality for UDES Modules",
    'depends': [
        'stock',
        'stock_picking_batch'
    ],
    'category': 'Warehouse',
    'sequence': 11,
    'demo': [
    ],
    'data': [
        'data/stock_config.xml',
        'views/product_template.xml',
        'views/res_users.xml',
        'views/stock_inventory.xml',
        'views/stock_location.xml',
        'views/stock_picking.xml',
        'wizard/change_quant_location_view.xml',
        'views/stock_quant_views.xml',
        'views/create_planned_transfer_asset.xml',
    ],
    'qweb': [
        'static/src/xml/create_planned_transfer_button.xml'
    ],
    'test': [
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
