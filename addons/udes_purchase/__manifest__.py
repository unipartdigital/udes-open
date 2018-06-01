# -*- coding: utf-8 -*-
{
    'name': "UDES Purchase",
    'version': '11.0',
    'summary': 'UDES Purchase',
    'description': "UDES Purchase",
    'author': 'Unipart Digital',
    'category': 'Warehouse',
    'depends': ['purchase'],
    'data': [
        'data/routes.xml',
        'data/scheduler.xml',
        'views/purchase_views.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
