{
    "name": "UDES LDAP",
    "summary": """
        Lightweight Directory Access Protocol integration for UDES""",
    "description": """UDES-specific LDAP configuration and functionality""",
    "author": "Unipart Digital Team",
    "website": "http://www.unipart.io",
    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/openerp/addons/base/module/module_data.xml
    # for the full list
    "category": "tools",
    "version": "11.0.3.0.0",
    # any module necessary for this one to work correctly
    "depends": [
        "auth_ldaps",
        "udes_security",
    ],
    # always loaded
    "data": [
        "security/ir.model.access.csv",
        "views/res_company_ldap_views.xml",
    ],
}
