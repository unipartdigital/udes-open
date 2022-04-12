{
    "name": "UDES Stock Picking Batch",
    "summary": "UDES Stock Picking Batch",
    "author": "Unipart Digital Team",
    "website": "https://unipart.io",
    "category": "Specific Industry Applications",
    "license": "LGPL-3",
    "application": True,
    "version": "14.0.0.0.1",
    "depends": [
        "base",
        "stock",
        "udes_security",
        "stock_picking_batch",
        "udes_simple_location_blocking",
    ],
    "external_dependencies": {},
    "data": [
        "views/stock_picking_batch.xml",
        "views/stock_warehouse.xml",
        "views/stock_picking_type.xml",
        "views/res_users.xml",
        "views/stock_picking.xml"
    ],
    "demo": [],
}
