{
    "name": "UDES Stock Refactoring",
    "summary": """UDES Stock Refactoring""",
    "author": "Unipart Digital Team",
    "website": "https://unipart.io",
    "category": "Specific Industry Applications",
    "license": "LGPL-3",
    "application": True,
    "version": "14.0.2.1.0",
    "depends": [
        "base",
        "stock",
        "udes_common",
        "stock_picking_batch",
        "udes_stock",
    ],
    "external_dependencies": {},
    "data": [
        "security/ir.model.access.csv",
        "data/picking_types.xml",
        "views/stock_picking_type_views.xml",
        "wizard/refactor_action_views.xml",
    ],
    "demo": [],
}
