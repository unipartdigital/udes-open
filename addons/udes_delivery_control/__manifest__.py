# -*- coding: utf-8 -*-
{
    "name": "udes_delivery_control",
    "summary": """
        UDES Delivery Control
    """,
    "description": """
        UDES Delivery Control
    """,
    "author": "UDES",
    "website": "",
    "category": "Uncategorized",
    "version": "0.1",
    # any module necessary for this one to work correctly
    "depends": ["udes_stock"],
    # always loaded
    "data": [
        "data/picking_types.xml",
    ],
    # only loaded in demonstration mode
    "demo": [],
}
