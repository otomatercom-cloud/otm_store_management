# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError


class OtmStockReturn(models.Model):
    _name = 'otm.stock.return'
    _description = 'Stock Return'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'return_date desc, id desc'

    name = fields.Char(string='Return No.', required=True, copy=False, default='New', tracking=True)
    store_id = fields.Many2one('otm.store', string='Returning To Store', required=True, tracking=True)
    source_issue_id = fields.Many2one('otm.stock.issue', string='Source Issue')
    department = fields.Char(string='Department')
    return_date = fields.Date(string='Return Date', default=fields.Date.context_today, required=True)
    reason = fields.Char(string='Reason')

    approved_by = fields.Many2one('res.users', string='Approved By', readonly=True)
    received_by = fields.Many2one('res.users', string='Received By', readonly=True)

    line_ids = fields.One2many('otm.stock.return.line', 'return_id', string='Return Lines')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('received', 'Received'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('otm.stock.return') or 'New'
        return super().create(vals_list)

    def action_approve(self):
        for rec in self:
            if not rec.line_ids:
                raise UserError('Add at least one line before approving.')
        self.write({'state': 'approved', 'approved_by': self.env.user.id})

    def action_receive(self):
        Move = self.env['otm.stock.move']
        for ret in self:
            for line in ret.line_ids:
                if line.condition == 'good':
                    Move.create({
                        'reference': ret.name,
                        'move_type': 'return_in',
                        'product_tmpl_id': line.product_tmpl_id.id,
                        'batch_id': line.batch_id.id if line.batch_id else False,
                        'store_id': ret.store_id.id,
                        'quantity': abs(line.quantity),
                        'unit_cost': line.unit_cost,
                        'department': ret.department,
                        'reason': f'Return: {line.condition}',
                        'return_id': ret.id,
                    })
                # damaged / expired / rejected quantities are recorded on the
                # line for reporting but are intentionally not put back into
                # sellable/usable live stock.
            ret.write({'state': 'received', 'received_by': self.env.user.id})

    def action_cancel(self):
        self.write({'state': 'cancelled'})


class OtmStockReturnLine(models.Model):
    _name = 'otm.stock.return.line'
    _description = 'Stock Return Line'

    return_id = fields.Many2one('otm.stock.return', string='Return', required=True, ondelete='cascade')
    product_tmpl_id = fields.Many2one('product.template', string='Product', required=True)
    batch_id = fields.Many2one('otm.product.batch', string='Batch')
    quantity = fields.Float(string='Quantity', required=True, default=1.0)
    uom_id = fields.Many2one('uom.uom', string='UoM')
    unit_cost = fields.Float(string='Unit Cost')
    condition = fields.Selection([
        ('good', 'Good'),
        ('damaged', 'Damaged'),
        ('expired', 'Expired'),
        ('rejected', 'Rejected'),
    ], string='Condition', required=True, default='good')
