# pylint: disable=missing-docstring,pointless-statement
{
    "name": "UDES Security",
    "summary": "UDES security enhancements",
    "description": """
Security enhancements used by UDES
==================================
""",
    "version": "0.1",
    "depends": ["web", "password_security", "auth_brute_force", "auth_session_timeout"],
    "category": "Authentication",
    "data": [
        "security/res_groups.xml",
        "security/ir.model.access.csv",
        "security/ir_rule.xml",
        "views/base_language_install_view.xml",
        "views/base_menu.xml",
        "views/allowed_file_type_views.xml",
        "views/readonly_desktop_user_exception_views.xml",
        "views/res_users_views.xml",
        "views/webclient_templates.xml",
        "data/auth_brute_force.xml",
        "data/allowed_file_type_data.xml",
        "data/ir_config_parameter_data.xml",
        "data/res_users.xml",
    ],
}
