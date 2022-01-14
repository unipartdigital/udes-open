{
    "name": "UDES Security",
    "summary": """UDES Security""",
    "author": "Unipart Digital Team",
    "website": "https://unipart.io",
    "category": "Specific Industry Applications",
    "license": "LGPL-3",
    "application": True,
    "version": "14.0.0.0.0",
    "depends": ["base", "web", "udes_common"],
    "data": [
        "data/res_groups.xml",
        "data/res_users.xml",
        "security/ir.model.access.csv",
        "views/res_groups_views.xml",
        "views/allowed_file_type_views.xml",
        "views/ir_attachment_views.xml",
        "views/webclient_templates.xml",
        "data/allowed_file_type_data.xml",
    ],
    "demo": [],
}
