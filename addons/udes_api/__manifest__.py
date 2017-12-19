# -*- coding: utf-8 -*-
{
    'name': "UDES API",

    'summary': """
        UDES API""",

    'description': """
        A set of API end points for getting data in and out of Odoo 
    """,

    'author': "Unipart Digital Team",
    'website': "http://www.unipart.io",

    'category': 'API',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': [
        'stock',
        'warehouse_config',
    ],

    # always loaded
    'data': [
    ],
    'demo': [
    ],
}
