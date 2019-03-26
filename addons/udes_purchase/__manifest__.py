# -*- coding: utf-8 -*-
{
    'name': "UDES Purchase",
    'version': '11.0',
    'summary': 'UDES Purchase',
    'description': "UDES Purchase",
    'author': 'Unipart Digital',
    'category': 'Warehouse',
    'depends': [
        'purchase',
        'udes_security',
        'udes_stock'
    ],
    'data': [
        'reports/reorder_alert_template.xml',
        'data/reorder_alert_email.xml',
        'data/routes.xml',
        'data/scheduler.xml',
        'views/purchase_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
