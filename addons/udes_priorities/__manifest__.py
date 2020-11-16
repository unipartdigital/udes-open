# -*- coding: utf-8 -*-
{
    "name": "UDES Priorities",
    "summary": """Dynamic priorities for UDES Stock""",
    "description": """Dynamic priorities for UDES Stock""",
    "author": "Unipart Digital",
    "website": "http://unipart.io",
    "category": "Warehouse",
    "version": "0.1",
    "depends": ["udes_stock"],
    "data": [
        "data/default_priority_groups.xml",
        "data/default_priorities.xml",
        "security/ir.model.access.csv",
        "views/priorities.xml",
        "views/priority_groups.xml",
    ],
}
