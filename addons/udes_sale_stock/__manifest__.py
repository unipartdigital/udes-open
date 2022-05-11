# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    "name": "UDES Sale Stock Functionality",
    "version": "14.0",
    "summary": "Inventory, Logistics, Warehousing",
    "description": "Extension of sale_stock model for UDES",
    "depends": ["edi_sale", "sale_management", "sale_stock", "udes_stock", "l10n_uk",],
    "category": "Warehouse",
    "sequence": 12,
    "demo": [],
    "data": [
        "views/edi_sale_request_views.xml",
        "views/sale_order_views.xml",
        "views/stock_warehouse.xml",
        "views/branding_res_config_settings.xml",
        "data/branding_digest_tip_data.xml",
    ],
    "qweb": [],
    "test": [],
    "installable": True,
    "application": False,
    "auto_install": False,
}
