{
    "name": "udes_permissions",
    "summary": """
        UDES Permissions
    """,
    "description": """
         UDES Permissions
    """,
    "author": "UDES",
    "website": "",
    "category": "Uncategorized",
    "version": "0.1",
    # any module necessary for this one to work correctly
    "depends": ["base"],
    # always loaded
    "data": [
        "data/res_groups.xml",
        "data/res_users.xml",
        "security/ir.model.access.csv",
        "views/user_template_view.xml",
    ],
    # only loaded in demonstration mode
    "demo": [],
}
