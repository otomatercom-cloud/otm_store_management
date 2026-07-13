# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError


class OtmStockAdjustment(models.Model):
    _name = 'otm.stock.adjustment'
    _description = 'Stock Adjustment'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'adjustment_date desc, id desc'

    name = fields.Char(string='Adjustment No.', required=True, copy=False, default='New', tracking=True)
    store_id = fields.Many2one('otm.store', string='Store', required=True, tracking=True)
    adjustment_date = fields.Date(string='Adjustment Date', default=fields.Date.context_today, required=True)
    reason = fields.Char(string='Reason')

    approved_by = fields.Many2one('res.users', string='Approved By', readonly=True)

    line_ids = fields.One2many('otm.stock.adjustment.line', 'adjustment_id', string='Adjustment Lines')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('otm.stock.adjustment') or 'New'
        return super().create(vals_list)

    def action_load_expected(self):
        """Populate expected_qty on each line from the current live-stock view."""
        Quant = self.env['otm.stock.quant']
        for adj in self:
            for line in adj.line_ids:
                domain = [
                    ('store_id', '=', adj.store_id.id),
                    ('product_tmpl_id', '=', line.product_tmpl_id.id),
                ]
                if line.batch_id:
                    domain.append(('batch_id', '=', line.batch_id.id))
                quants = Quant.search(domain)
                line.expected_qty = sum(quants.mapped('quantity'))

    def action_approve(self):
        Move = self.env['otm.stock.move']
        for adj in self:
            if not adj.line_ids:
                raise UserError('Add at least one line before approving.')
            for line in adj.line_ids:
                diff = line.actual_qty - line.expected_qty
                if not diff:
                    continue
                Move.create({
                    'reference': adj.name,
                    'move_type': 'adjustment_in' if diff > 0 else 'adjustment_out',
                    'product_tmpl_id': line.product_tmpl_id.id,
                    'batch_id': line.batch_id.id if line.batch_id else False,
                    'store_id': adj.store_id.id,
                    'quantity': diff,
                    'unit_cost': line.unit_cost,
                    'reason': adj.reason or line.reason or 'Physical Stock Adjustment',
                    'adjustment_id': adj.id,
                })
            adj.write({'state': 'approved', 'approved_by': self.env.user.id})

    def action_cancel(self):
        self.write({'state': 'cancelled'})


class OtmStockAdjustmentLine(models.Model):
    _name = 'otm.stock.adjustment.line'
    _description = 'Stock Adjustment Line'

    adjustment_id = fields.Many2one('otm.stock.adjustment', string='Adjustment', required=True, ondelete='cascade')
    product_tmpl_id = fields.Many2one('product.template', string='Product', required=True)
    batch_id = fields.Many2one('otm.product.batch', string='Batch')
    expected_qty = fields.Float(string='Expected Quantity')
    actual_qty = fields.Float(string='Actual Quantity')
    difference = fields.Float(compute='_compute_difference', string='Difference')
    unit_cost = fields.Float(string='Unit Cost')
    reason = fields.Char(string='Reason')

    @api.depends('expected_qty', 'actual_qty')
    def _compute_difference(self):
        for line in self:
            line.difference = line.actual_qty - line.expected_qty
