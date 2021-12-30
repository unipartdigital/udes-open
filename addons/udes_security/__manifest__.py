{
    "name": "UDES Security",
    "summary": """UDES Security""",
    "author": "Unipart Digital Team",
    "website": "https://unipart.io",
    "category": "Specific Industry Applications",
    "license": "LGPL-3",
    "application": True,
    "version": "14.0.0.0.0",
    "depends": ["base",],
    "external_dependencies": {"python": ["xlrd", "xlwt"]},
    "data": [
        "data/res_groups.xml",
        "data/res_users.xml",
        "views/res_groups_views.xml",
    ],
    "demo": [],
}
