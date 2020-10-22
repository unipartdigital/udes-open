{
    "name": "UDES Delivery Control",
    "summary": """
        UDES Delivery Control
    """,
    "author": "UDES",
    "website": "https://www.unipart.io",
    "category": "Inventory",
    "license": "LGPL-3",
    "version": "11.0.1.0.0",
    "depends": ["udes_stock"],
    "data": [
        "data/picking_types.xml",
        "security/ir.model.access.csv",
        "security/udes_stock_security.xml",
        "views/stock_picking.xml",
        "views/stock_picking_vehicle_type.xml",
    ],
    "demo": [],
}
