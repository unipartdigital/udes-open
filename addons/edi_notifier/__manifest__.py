# -*- coding: utf-8 -*-
{
    "name": "edi_notifier",
    "summary": """
        Send email notifications when EDI documents fail/pass
    """,
    "description": """
        Send email notifications when EDI documents fail/pass
    """,
    "author": "Unipart Digital",
    "website": "",
    "category": "Uncategorized",
    "version": "0.1",
    # any module necessary for this one to work correctly
    "depends": ["base", "edi", "mail", "udes_security"],
    # always loaded
    "data": [
        "data/mail_templates.xml",
        "security/ir.model.access.csv",
        "views/notifiers.xml",
        "views/edi_document_type.xml",
        "views/mail_template.xml",
        "views/ir_cron_view.xml",
        "views/ir_actions_view.xml",
    ],
    # only loaded in demonstration mode
    "demo": [],
}
