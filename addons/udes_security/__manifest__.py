# pylint: disable=missing-docstring,pointless-statement
{
    'name': "UDES Security",
    'summary': "UDES security enhancements",
    'description': """
Security enhancements used by UDES
==================================
""",
    'version': '0.1',
    'depends': [
        'web',
        'password_security',
        'auth_brute_force',
        'auth_session_timeout',
    ],
    'category': "Authentication",
    'data': [
        'views/res_users_views.xml',
        'data/auth_brute_force.xml',
        'data/ir_config_parameter_data.xml',
        'data/res_groups.xml',
        'data/res_users.xml',
    ]
}
