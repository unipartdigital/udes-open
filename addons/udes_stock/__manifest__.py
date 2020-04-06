# -*- coding: utf-8 -*-
{
    "name": "udes_stock",
    "summary": "udes stock",
    "description": "Core models and configuration for udes stock - odoo 13",
    "author": "Unipart digital",
    "website": "http://github/unipartdigital/udes-open",
    "category": "UDES",
    "version": "0.1",
    "depends": [
        'base',
        'stock',
        'stock_picking_batch',
    ],
    'data': [
        'data/stock_data.xml',
        'data/warehouse.xml',
        'data/stock_config.xml',
        'data/locations.xml',
        'data/picking_types.xml',
        'data/routes.xml',
        'data/company.xml',
    ],
}
