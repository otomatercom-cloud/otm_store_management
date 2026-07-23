# -*- coding: utf-8 -*-
from odoo import api, fields, models


class OtmProductBatch(models.Model):
    _name = 'otm.product.batch'
    _description = 'Product Batch / Lot'
    _order = 'expiry_date, name'

    name = fields.Char(string='Batch Number', required=True, copy=False)
    product_tmpl_id = fields.Many2one('product.template', string='Product', required=True, index=True)
    manufacturing_date = fields.Date(string='Manufacturing Date')
    expiry_date = fields.Date(string='Expiry Date', index=True)
    purchase_price = fields.Float(string='Purchase Rate')
    selling_price = fields.Float(string='Selling Rate')
    vendor_id = fields.Many2one('res.partner', string='Vendor')
    receipt_id = fields.Many2one('otm.stock.receipt', string='Source Receipt', ondelete='set null')
    active = fields.Boolean(default=True)

    expiry_state = fields.Selection([
        ('ok', 'Good'),
        ('near_expiry', 'Near Expiry'),
        ('expired', 'Expired'),
    ], compute='_compute_expiry_state', string='Expiry Status', store=True)
    days_to_expiry = fields.Integer(compute='_compute_expiry_state', string='Days to Expiry')

    quant_ids = fields.One2many('otm.stock.quant', 'batch_id', string='Live Stock')
    current_qty = fields.Float(compute='_compute_current_qty', string='Current Quantity')

    _sql_constraints = [
        ('batch_product_uniq', 'unique(name, product_tmpl_id)',
         'A batch number must be unique per product.'),
    ]

    @api.depends('expiry_date')
    def _compute_expiry_state(self):
        today = fields.Date.context_today(self)
        for batch in self:
            if not batch.expiry_date:
                batch.expiry_state = 'ok'
                batch.days_to_expiry = 0
                continue
            delta = (batch.expiry_date - today).days
            batch.days_to_expiry = delta
            alert_days = batch.product_tmpl_id.otm_expiry_alert_days or 30
            if delta < 0:
                batch.expiry_state = 'expired'
            elif delta <= alert_days:
                batch.expiry_state = 'near_expiry'
            else:
                batch.expiry_state = 'ok'

    def _compute_current_qty(self):
        for batch in self:
            batch.current_qty = sum(batch.quant_ids.mapped('quantity'))
