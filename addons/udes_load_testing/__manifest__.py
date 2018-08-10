# -*- coding: utf-8 -*-
{
    'name': 'udes_load_testing',
    'summary': """Load testing for the udes_stock""",
    'description': """Load testing for udes_stock""",
    'author': 'Unipart Digital',
    'category': 'Extra Tools',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': [
        'base',
        'udes_stock',
    ],

    'external_dependencies': {
        'python': [
            'ascii_graph',
            'parameterized',
            ]
    },

    'sequence': 50,
    'installable': True,
    'application': False,
    'auto_install': False,
}
