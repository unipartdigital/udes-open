# -*- coding: utf-8 -*-
{
    'name': "Warehouse Config",

    'summary': """
        UDES Warehouse Config""",

    'description': """
        Add warehouse and picking types configuration fields
    """,

    'author': "Unipart Digital Team",
    'website': "http://www.unipart.io",

    'category': 'API',
    'version': '11',

    # any module necessary for this one to work correctly
    'depends': [
        'stock',
    ],

    # always loaded
    'data': [
        'views/stock_picking_type.xml',
        'views/stock_warehouse.xml',
    ],
    'demo': [
    ],
}
