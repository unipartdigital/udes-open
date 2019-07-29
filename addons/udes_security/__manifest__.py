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
        'data/auth_brute_force.xml',
        'data/res_groups.xml',
    ]
}
