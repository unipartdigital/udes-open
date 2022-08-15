{
    "name": "UDES Stock",
    "summary": "udes stock",
    "description": "Core models and configuration for UDES Stock - Odoo 14",
    "author": "Unipart Digital",
    "website": "http://github/unipartdigital/udes-open",
    "category": "UDES",
    "version": "0.1",
    "depends": [
        "base",
        "stock",
        "stock_sms",
        "stock_picking_batch",
        "udes_common",
        "package_hierarchy",
        "udes_security",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/stock_data.xml",
        "data/stock_config.xml",
        "data/locations.xml",
        "data/picking_types.xml",
        "data/company.xml",
        "data/product_categories.xml",
        "data/warehouse.xml",
        "data/routes.xml",
        "data/scheduler.xml",
        "report/deliveryslip_reports.xml",
        "report/deliveryslip_templates.xml",
        "report/external_layout.xml",
        "report/external_layout_standard.xml",
        "wizard/stock_backorder_confirmation_views.xml",
        "wizard/stock_immediate_transfer_views.xml",
        "views/assets.xml",
        "views/product_views.xml",
        "views/stock_picking.xml",
        "views/stock_picking_type.xml",
        "views/stock_move_views.xml",
        "views/stock_op_analysis.xml",
        "views/stock_orderpoint_views.xml",
        "views/stock_location_views.xml",
        "views/stock_template.xml",
        "views/stock_scrap_views.xml",
        "views/stock_warehouse.xml",
        "views/product_template.xml",
        "views/stock_warehouse.xml",
        "views/stock_location_category_views.xml",
        "views/stock_scheduler_compute_views.xml",
        "views/res_users_view.xml",
        "wizard/reservation_views.xml",
    ],
}
