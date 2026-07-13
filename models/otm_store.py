# -*- coding: utf-8 -*-
from odoo import api, fields, models


class OtmStore(models.Model):
    _name = 'otm.store'
    _description = 'Store'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(string='Store Name', required=True, tracking=True)
    code = fields.Char(string='Store Code', required=True, tracking=True, copy=False)
    manager_id = fields.Many2one('res.users', string='Store Manager', tracking=True)
    department = fields.Char(string='Department')
    location = fields.Char(string='Physical Location')
    description = fields.Text(string='Description')
    active = fields.Boolean(default=True)
    status = fields.Selection([
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('closed', 'Closed'),
    ], string='Status', default='active', tracking=True)

    location_ids = fields.One2many('otm.store.location', 'store_id', string='Storage Locations')
    location_count = fields.Integer(compute='_compute_location_count', string='Locations')

    move_ids = fields.One2many('otm.stock.move', 'store_id', string='Stock Movements')
    quant_ids = fields.One2many('otm.stock.quant', 'store_id', string='Live Stock')
    product_count = fields.Integer(compute='_compute_stock_stats', string='Products in Stock')
    inventory_value = fields.Float(compute='_compute_stock_stats', string='Inventory Value')
    low_stock_count = fields.Integer(compute='_compute_stock_stats', string='Low Stock Products')
    stock_out_count = fields.Integer(compute='_compute_stock_stats', string='Stock Out Products')

    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

    _sql_constraints = [
        ('code_uniq', 'unique(code, company_id)', 'Store code must be unique per company.'),
    ]

    @api.depends('location_ids')
    def _compute_location_count(self):
        for store in self:
            store.location_count = len(store.location_ids)

    def _compute_stock_stats(self):
        Quant = self.env['otm.stock.quant']
        for store in self:
            quants = Quant.search([('store_id', '=', store.id)])
            store.product_count = len(quants.mapped('product_tmpl_id'))
            store.inventory_value = sum(q.quantity * q.average_cost for q in quants)

            # aggregate per product — a product can have several quant rows
            # in this store (different locations/batches), and reorder /
            # stock-out thresholds are evaluated against the store total,
            # not any single row.
            product_qty = {}
            for q in quants:
                product_qty[q.product_tmpl_id] = product_qty.get(q.product_tmpl_id, 0.0) + q.quantity

            low = 0
            out = 0
            for product, qty in product_qty.items():
                if qty <= 0:
                    out += 1
                elif product.otm_reorder_qty and qty <= product.otm_reorder_qty:
                    low += 1
            store.low_stock_count = low
            store.stock_out_count = out

    def action_view_locations(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'otm_store_management.action_otm_store_location')
        action['domain'] = [('store_id', '=', self.id)]
        action['context'] = {'default_store_id': self.id}
        return action

    def action_view_live_stock(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'otm_store_management.action_otm_stock_quant')
        action['domain'] = [('store_id', '=', self.id)]
        return action

    def action_view_ledger(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'otm_store_management.action_otm_stock_move')
        action['domain'] = [('store_id', '=', self.id)]
        return action

    def _compute_display_name(self):
        for store in self:
            store.display_name = f'[{store.code}] {store.name}' if store.code else store.name

    @api.model
    def _cron_check_stock_alerts(self):
        """Scheduled action: raises a chatter activity on the store manager
        for every store that currently has stock-out, low-stock, near-expiry
        or expired items."""
        Quant = self.env['otm.stock.quant']
        Batch = self.env['otm.product.batch']
        activity_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        for store in self.search([('status', '=', 'active')]):
            if not store.manager_id:
                continue

            # aggregate per product first — a product can have several
            # quant rows in the same store (different locations/batches)
            product_qty = {}
            for q in Quant.search([('store_id', '=', store.id)]):
                product_qty[q.product_tmpl_id] = product_qty.get(q.product_tmpl_id, 0.0) + q.quantity

            out_count = 0
            low_count = 0
            for product, qty in product_qty.items():
                if qty <= 0:
                    out_count += 1
                elif product.otm_reorder_qty and qty <= product.otm_reorder_qty:
                    low_count += 1

            batches = Batch.search([('quant_ids.store_id', '=', store.id)])
            expiring = batches.filtered(lambda b: b.expiry_state in ('near_expiry', 'expired'))

            if not out_count and not low_count and not expiring:
                continue

            note = []
            if out_count:
                note.append(f'{out_count} product(s) completely OUT OF STOCK.')
            if low_count:
                note.append(f'{low_count} product(s) at or below reorder level.')
            if expiring:
                note.append(f'{len(expiring)} batch(es) expired or nearing expiry.')
            store.activity_schedule(
                activity_type_id=activity_type.id if activity_type else False,
                user_id=store.manager_id.id,
                summary='Store stock alert',
                note=' '.join(note),
            )
