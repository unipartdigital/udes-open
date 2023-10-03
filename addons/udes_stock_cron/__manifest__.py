{
    "name": "UDES Stock Cron",
    "summary": "Udes stock cron",
    "description": "Core models and configuration for UDES Stock cron - Odoo 14",
    "author": "Unipart Digital",
    "website": "http://github/unipartdigital/udes-open",
    "category": "UDES",
    "version": "0.1",
    "depends": [
        "stock",
        "stock_picking_batch",
        "udes_cron",
        "udes_stock",
        "udes_security",
    ],
    "data": [
        "data/ir_cron.xml",
        "views/stock_picking_type.xml",
        "security/ir.model.access.csv",
        "wizard/reservation_views.xml",
    ],
}
