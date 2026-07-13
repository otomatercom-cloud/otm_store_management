{
    'name': 'Otomater Store Management',
    'version': '19.0.1.0.0',
    'category': 'Inventory/Inventory',
    'summary': 'Multi-store inventory, purchase, transfer, issue, return and '
                'stock ledger management for schools, colleges, restaurants, '
                'hospitals, hotels and factories.',
    'description': """
Otomater Store Management
==========================
A complete multi-store inventory management product built by Otomater on
Odoo 19. Provides full traceability of every stock movement (who, when,
quantity, from, to, reason, cost, batch, purchase source) across unlimited
stores and departments.

Key capabilities:
- Store & storage location management
- Extended product master (GST, HSN, reorder levels, batch/expiry tracking)
- Purchase management (GST / Non-GST / Cash / Credit / Opening / Donation)
- Stock receipt (GRN) with batch, manufacturing & expiry capture
- Internal transfer with a full approval workflow
- Department-wise stock issue and return
- Physical stock adjustment with variance approval
- Live stock, low-stock alerts, expiry tracking and a full stock ledger
- Manager dashboard (OWL) with KPIs and charts
- Role-based security (Store Manager, Purchase Manager, Inventory Manager,
  Department Manager, Auditor, Admin)
""",
    'author': 'Otomater',
    'company': 'Otomater',
    'website': 'https://otomater.com',
    'license': 'OPL-1',
    'depends': ['base', 'mail', 'product', 'uom'],
    'data': [
        'security/otm_store_security.xml',
        'security/ir.model.access.csv',
        'security/otm_store_record_rules.xml',
        'data/otm_sequence_data.xml',
        'data/otm_cron_data.xml',
        'views/otm_store_views.xml',
        'views/otm_store_location_views.xml',
        'views/product_template_views.xml',
        'views/otm_product_batch_views.xml',
        'views/otm_purchase_views.xml',
        'views/otm_stock_receipt_views.xml',
        'views/otm_stock_transfer_views.xml',
        'views/otm_stock_issue_views.xml',
        'views/otm_stock_return_views.xml',
        'views/otm_stock_adjustment_views.xml',
        'views/otm_stock_move_views.xml',
        'views/otm_stock_quant_views.xml',
        'views/otm_dashboard_views.xml',
        'views/otm_menus.xml',
        'report/otm_report_actions.xml',
        'report/otm_receipt_report_templates.xml',
        'report/otm_transfer_report_templates.xml',
    ],
    'demo': [
        'demo/otm_demo_data.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'otm_store_management/static/src/js/otm_dashboard.js',
            'otm_store_management/static/src/xml/otm_dashboard_templates.xml',
            'otm_store_management/static/src/css/otm_dashboard.css',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
