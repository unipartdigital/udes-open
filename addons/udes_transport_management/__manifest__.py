{
    'name': 'UDES Transport Management',
    'summary': 'UDES Transport Management',
    'description': """
        Transport management module:
        - Trailer Information for transfers
    """,
    'author': 'Unipart Digital Team',
    'website': 'https://unipart.io',
    'category': 'Security',
    'application': True,
    'version': '0.1',
    'depends': [
        'stock',
        'udes_stock',
    ],
    'data': [
        'data/picking_types.xml',
        'security/ir.model.access.csv',
        'views/stock_picking_views.xml',
        'views/stock_picking_type.xml',
    ],
}
