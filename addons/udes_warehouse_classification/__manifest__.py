# -*- coding: utf-8 -*-
{
    "name": "UDES Warehouse Classification",
    "summary": """Custom messaging for products in warehousing""",
    "description": """
        Model intended to allow for messaging (both for alerting and attaching to reports) based
        on product and picking type.
    """,
    "version": "14.0.0.0",
    "category": "Warehouse",
    "depends": ["udes_stock","udes_stock_permissions"],
    "data": [
        "data/ir_module_category_data.xml",
        "security/res_groups.xml",
        "data/res_users_data.xml",
        "data/user_template.xml", 
        "security/ir.model.access.csv",
        "views/warehouse_product_classification.xml",
        "views/product_template.xml",
        "wizard/add_product_classification_view.xml",
    ],
    "demo": [],
    "test": [],
    "installable": True,
    "application": False,
    "auto_install": False,
}
