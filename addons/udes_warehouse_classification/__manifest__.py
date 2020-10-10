# -*- coding: utf-8 -*-
{
    "name": "UDES Warehouse Classification",
    "summary": """Custom messaging for products in warehousing""",
    "description": """
        Model intended to allow for messaging (both for alerting and attaching to reports) based
        on product and picking type. 
    """,
    "version": "11.0",
    "category": "Warehouse",
    "depends": ["udes_stock"],
    "data": [
        "security/ir.model.access.csv",
        "views/warehouse_product_classification.xml",
        "views/product_template.xml",
    ],
    "demo": [],
    "test": [],
    "installable": True,
    "application": False,
    "auto_install": False,
}
