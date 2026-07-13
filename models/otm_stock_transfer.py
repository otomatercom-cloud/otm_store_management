# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError


class OtmStockTransfer(models.Model):
    _name = 'otm.stock.transfer'
    _description = 'Internal Stock Transfer'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'transfer_date desc, id desc'

    name = fields.Char(string='Transfer No.', required=True, copy=False, default='New', tracking=True)
    from_store_id = fields.Many2one('otm.store', string='From Store', required=True, tracking=True)
    to_store_id = fields.Many2one('otm.store', string='To Store', required=True, tracking=True)
    from_location_id = fields.Many2one('otm.store.location', string='From Location',
                                        domain="[('store_id', '=', from_store_id)]")
    to_location_id = fields.Many2one('otm.store.location', string='To Location',
                                      domain="[('store_id', '=', to_store_id)]")

    requested_by = fields.Many2one('res.users', string='Requested By', default=lambda self: self.env.user)
    approved_by = fields.Many2one('res.users', string='Approved By', readonly=True)
    issued_by = fields.Many2one('res.users', string='Issued By', readonly=True)
    received_by = fields.Many2one('res.users', string='Received By', readonly=True)

    transfer_date = fields.Date(string='Transfer Date', default=fields.Date.context_today, required=True)
    expected_date = fields.Date(string='Expected Date')
    completed_date = fields.Date(string='Completed Date', readonly=True)

    reason = fields.Char(string='Reason')
    remarks = fields.Text(string='Remarks')

    line_ids = fields.One2many('otm.stock.transfer.line', 'transfer_id', string='Transfer Lines')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('requested', 'Requested'),
        ('approved', 'Approved'),
        ('issued', 'Issued'),
        ('received', 'Received'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    @api.constrains('from_store_id', 'to_store_id')
    def _check_stores_differ(self):
        for transfer in self:
            if transfer.from_store_id and transfer.from_store_id == transfer.to_store_id:
                raise UserError('From Store and To Store must be different.')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('otm.stock.transfer') or 'New'
        return super().create(vals_list)

    def action_request(self):
        for rec in self:
            if not rec.line_ids:
                raise UserError('Add at least one transfer line before requesting.')
            rec.state = 'requested'

    def action_approve(self):
        self.write({'state': 'approved', 'approved_by': self.env.user.id})

    def action_issue(self):
        """Move stock out of the source store immediately on issue."""
        Move = self.env['otm.stock.move']
        for transfer in self:
            for line in transfer.line_ids:
                Move.create({
                    'reference': transfer.name,
                    'move_type': 'transfer_out',
                    'product_tmpl_id': line.product_tmpl_id.id,
                    'batch_id': line.batch_id.id if line.batch_id else False,
                    'store_id': transfer.from_store_id.id,
                    'location_id': transfer.from_location_id.id,
                    'from_store_id': transfer.from_store_id.id,
                    'to_store_id': transfer.to_store_id.id,
                    'quantity': -abs(line.quantity),
                    'unit_cost': line.unit_cost,
                    'reason': transfer.reason or 'Internal Transfer',
                    'transfer_id': transfer.id,
                })
            transfer.write({'state': 'issued', 'issued_by': self.env.user.id})

    def action_receive(self):
        """Move stock into the destination store on confirmed receipt."""
        Move = self.env['otm.stock.move']
        for transfer in self:
            for line in transfer.line_ids:
                Move.create({
                    'reference': transfer.name,
                    'move_type': 'transfer_in',
                    'product_tmpl_id': line.product_tmpl_id.id,
                    'batch_id': line.batch_id.id if line.batch_id else False,
                    'store_id': transfer.to_store_id.id,
                    'location_id': transfer.to_location_id.id,
                    'from_store_id': transfer.from_store_id.id,
                    'to_store_id': transfer.to_store_id.id,
                    'quantity': abs(line.quantity),
                    'unit_cost': line.unit_cost,
                    'reason': transfer.reason or 'Internal Transfer',
                    'transfer_id': transfer.id,
                })
            transfer.write({
                'state': 'received',
                'received_by': self.env.user.id,
                'completed_date': fields.Date.context_today(self),
            })

    def action_cancel(self):
        for transfer in self:
            if transfer.state in ('issued', 'received'):
                raise UserError('Cannot cancel a transfer that has already posted stock movements. '
                                 'Post a reversing transfer instead.')
            transfer.state = 'cancelled'


class OtmStockTransferLine(models.Model):
    _name = 'otm.stock.transfer.line'
    _description = 'Stock Transfer Line'

    transfer_id = fields.Many2one('otm.stock.transfer', string='Transfer', required=True, ondelete='cascade')
    product_tmpl_id = fields.Many2one('product.template', string='Product', required=True)
    batch_id = fields.Many2one('otm.product.batch', string='Batch')
    quantity = fields.Float(string='Quantity', required=True, default=1.0)
    uom_id = fields.Many2one('uom.uom', string='UoM')
    unit_cost = fields.Float(string='Unit Cost')
