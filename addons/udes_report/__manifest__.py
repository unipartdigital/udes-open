# -*- coding: utf-8 -*-
{
    'name': "UDES Report",

    'summary': """
        Creates and exports stock reports
        """,

    'author': "Unipart Digital",
    'website': "http://unipart.io",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/odoo/addons/base/module/module_data.xml
    # for the full list
    'category': 'Specific Industry Applications',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base',
                'stock',
                'udes_api'],

    # always loaded
    # NB(ale): order is important for deps
    'data': [
        'views/menu.xml',
        'views/export.xml',
        'data/stock_email.xml',
    ],

    # only loaded in demonstration mode
    'demo': [],
}
