{
    'name': 'UDES Delivery Slot',
    'summary': 'Delivery Slots for sale orders',
    'description': """Record different delivery slots""",
    'author': 'Unipart Digital Team',
    'website': 'https://unipart.io',
    'category': 'Warehouse',
    'application': True,
    'version': '0.1',
    'depends': [
        'sale_stock'
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/delivery_slot_views.xml',
        'views/sale_order_views.xml',
        'data/delivery_slot_data.xml',
    ],
}
