{
    'name': 'UDES Product Expiry Functionality',
    'version': '11.0',
    'summary': 'Inventory, Logistics, Warehousing',
    'description': "Holds specific functionality for product expiry for use with UDES",
    'depends': [
        'udes_stock',
        'product_expiry'
    ],
    'category': 'Warehouse',
    'sequence': 11,
    'demo': [
    ],
    'data': [
        'report/report_deliveryslip.xml',
        'views/stock_move_line_views.xml',
        'views/stock_picking_views.xml',
    ],
    'qweb': [
    ],
    'test': [
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
