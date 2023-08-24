{
    "name": "UDES Security",
    "summary": """UDES Security""",
    "author": "Unipart Digital",
    "website": "https://unipart.io",
    "category": "Specific Industry Applications",
    "license": "LGPL-3",
    "application": True,
    "version": "14.0.0.0.0",
    "depends": ["base", "base_setup", "web", "portal", "udes_common"],
    "data": [
        "data/ir_module_category_data.xml",
        "data/res_groups.xml",
        "data/res_users.xml",
        "security/ir.model.access.csv",
        "security/ir_model_access.xml",
        "views/res_company_view.xml",
        "views/res_groups_views.xml",
        "views/allowed_file_type_views.xml",
        "views/ir_attachment_views.xml",
        "views/webclient_templates.xml",
        "views/no_desktop_access_template_views.xml",
        "data/allowed_file_type_data.xml",
        "views/res_config_settings_view.xml",
        "data/setup_default_domains.xml",
        "views/domain_allowlist_view.xml",
    ],
    "qweb": [
        "static/src/xml/custom_chatter_topbar.xml"
    ],
    "demo": [],
}
