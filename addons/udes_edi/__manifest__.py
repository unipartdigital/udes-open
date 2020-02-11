# pylint: disable=missing-docstring,pointless-statement
{
    'name': "UDES-EDI",
    'summary': "Summary",
    'description': """
* Hides Raw Import from non-trusted users""",
    'version': '0.1',
    'author': "UDES",
    'category': "Extra Tools",
    "depends": ["base", "edi",  "udes_security"],
    'data': [
        'security/edi_security.xml',
    ],
}

