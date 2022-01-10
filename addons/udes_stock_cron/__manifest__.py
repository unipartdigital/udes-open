# -*- coding: utf-8 -*-
{
    "name": "UDES Stock Cron",
    "summary": "Udes stock cron",
    "description": "Core models and configuration for UDES Stock cron - Odoo 14",
    "author": "Unipart Digital",
    "website": "http://github/unipartdigital/udes-open",
    "category": "UDES",
    "version": "0.1",
    "depends": ["stock", "stock_picking_batch", "udes_cron", "udes_stock"],
    "data": [
        "data/ir_cron.xml",
        "views/stock_picking_type.xml",
    ],
}
