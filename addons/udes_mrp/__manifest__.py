# -*- coding: utf-8 -*-
{
    'name': "UDES MRP",

    'summary': """
        UDES extension for MRP module
        """,

    'author': "Unipart Digital",
    'website': "http://unipart.io",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/odoo/addons/base/module/module_data.xml
    # for the full list
    'category': 'Specific Industry Applications',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': [
        'base',
        'mrp',
        'udes_security',
    ],

    # always loaded
    'data': [
        'report/mrp_production_templates.xml',
        'views/mrp_production_views.xml'
    ],

    # only loaded in demonstration mode
    'demo': [],
}
