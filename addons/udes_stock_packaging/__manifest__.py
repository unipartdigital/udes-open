{
    "name": "UDES Stock Packaging",
    "summary": "udes stock",
    "description": "Stock packaging features for UDES - Odoo 14",
    "author": "Unipart Digital",
    "website": "http://github/unipartdigital/udes-open",
    "category": "UDES",
    "version": "0.1",
    "depends": ["uom", "stock", "package_hierarchy", "udes_stock", "udes_get_info"],
    "data": [
        "security/ir.model.access.csv",
        "data/package_types.xml",
        "views/container_type_views.xml",
        "views/package_type_views.xml",
        "views/stock_picking_type.xml",
        "views/stock_quant_package.xml",
    ],
}
