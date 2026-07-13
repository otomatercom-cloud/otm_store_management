# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError


class OtmStockIssue(models.Model):
    _name = 'otm.stock.issue'
    _description = 'Stock Issue'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'issue_date desc, id desc'

    name = fields.Char(string='Issue No.', required=True, copy=False, default='New', tracking=True)
    store_id = fields.Many2one('otm.store', string='Issuing Store', required=True, tracking=True)
    department = fields.Selection([
        ('kitchen', 'Kitchen'),
        ('accounts', 'Accounts'),
        ('marketing', 'Marketing'),
        ('maintenance', 'Maintenance'),
        ('it', 'IT'),
        ('hostel', 'Hostel'),
        ('admin', 'Admin'),
        ('housekeeping', 'Housekeeping'),
        ('other', 'Other'),
    ], string='Department', required=True, tracking=True)
    employee_id = fields.Many2one('res.users', string='Issued To')
    issue_date = fields.Date(string='Issue Date', default=fields.Date.context_today, required=True)
    reason = fields.Char(string='Reason')

    approved_by = fields.Many2one('res.users', string='Approved By', readonly=True)
    issued_by = fields.Many2one('res.users', string='Issued By', readonly=True)

    line_ids = fields.One2many('otm.stock.issue.line', 'issue_id', string='Issue Lines')
    total_cost = fields.Float(compute='_compute_total_cost')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('issued', 'Issued'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    @api.depends('line_ids.quantity', 'line_ids.unit_cost')
    def _compute_total_cost(self):
        for issue in self:
            issue.total_cost = sum(line.quantity * line.unit_cost for line in issue.line_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('otm.stock.issue') or 'New'
        return super().create(vals_list)

    def action_approve(self):
        for rec in self:
            if not rec.line_ids:
                raise UserError('Add at least one line before approving.')
        self.write({'state': 'approved', 'approved_by': self.env.user.id})

    def action_issue(self):
        Move = self.env['otm.stock.move']
        for issue in self:
            for line in issue.line_ids:
                Move.create({
                    'reference': issue.name,
                    'move_type': 'issue',
                    'product_tmpl_id': line.product_tmpl_id.id,
                    'batch_id': line.batch_id.id if line.batch_id else False,
                    'store_id': issue.store_id.id,
                    'quantity': -abs(line.quantity),
                    'unit_cost': line.unit_cost,
                    'department': dict(issue._fields['department'].selection).get(issue.department),
                    'reason': issue.reason or 'Department Issue',
                    'issue_id': issue.id,
                })
            issue.write({'state': 'issued', 'issued_by': self.env.user.id})

    def action_cancel(self):
        for issue in self:
            if issue.state == 'issued':
                raise UserError('Cannot cancel an issue that already posted stock movements. '
                                 'Use Stock Return instead.')
            issue.state = 'cancelled'


class OtmStockIssueLine(models.Model):
    _name = 'otm.stock.issue.line'
    _description = 'Stock Issue Line'

    issue_id = fields.Many2one('otm.stock.issue', string='Issue', required=True, ondelete='cascade')
    product_tmpl_id = fields.Many2one('product.template', string='Product', required=True)
    batch_id = fields.Many2one('otm.product.batch', string='Batch')
    quantity = fields.Float(string='Quantity', required=True, default=1.0)
    uom_id = fields.Many2one('uom.uom', string='UoM')
    unit_cost = fields.Float(string='Unit Cost')
