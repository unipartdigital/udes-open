# -*- coding: utf-8 -*-
{
    "name": "UDES Stock",
    "summary": "udes stock",
    "description": "Core models and configuration for UDES Stock - Odoo 14",
    "author": "Unipart digital",
    "website": "http://github/unipartdigital/udes-open",
    "category": "UDES",
    "version": "0.1",
    "depends": ["base", "stock", "stock_picking_batch", "udes_common"],
    "data": [
        "data/stock_data.xml",
        "data/warehouse.xml",
        "data/stock_config.xml",
        "data/locations.xml",
        "data/picking_types.xml",
        "data/routes.xml",
        "data/company.xml",
        "views/stock_picking.xml",
        "views/stock_picking_type.xml",
        "views/stock_location_views.xml",
    ],
}
