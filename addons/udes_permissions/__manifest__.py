{
    "name": "UDES Permissions",
    "description": """
        Allows users / system to configure a hierarchy of User Templates which have res.groups associated with them.
    """,
    "author": "Unipart Digital",
    "website": "",
    "category": "Specific Industry Applications",
    "version": "0.1",
    # any module necessary for this one to work correctly
    "depends": [
        "base",
        "udes_hierarchical_tree_view",
    ],
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
