# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError


class OtmStockMove(models.Model):
    """Append-only ledger. Every purchase, receipt, transfer, issue, return
    and adjustment writes one or more rows here. Live stock (otm.stock.quant)
    is a read-only SQL view aggregated from this table, so the balance can
    never drift from the movement history.
    """
    _name = 'otm.stock.move'
    _description = 'Stock Movement Ledger'
    _order = 'date desc, id desc'
    _rec_name = 'reference'

    reference = fields.Char(string='Reference', required=True, index=True)
    date = fields.Datetime(string='Movement Date', required=True, default=fields.Datetime.now, index=True)

    move_type = fields.Selection([
        ('opening', 'Opening Stock'),
        ('donation', 'Donation Stock'),
        ('purchase', 'Purchase Receipt'),
        ('transfer_in', 'Transfer In'),
        ('transfer_out', 'Transfer Out'),
        ('issue', 'Issue'),
        ('return_in', 'Return'),
        ('adjustment_in', 'Adjustment (Increase)'),
        ('adjustment_out', 'Adjustment (Decrease)'),
    ], string='Movement Type', required=True, index=True)

    product_tmpl_id = fields.Many2one('product.template', string='Product', required=True, index=True)
    batch_id = fields.Many2one('otm.product.batch', string='Batch')

    store_id = fields.Many2one('otm.store', string='Store', required=True, index=True)
    location_id = fields.Many2one('otm.store.location', string='Location',
                                   domain="[('store_id', '=', store_id)]")

    from_store_id = fields.Many2one('otm.store', string='From Store')
    to_store_id = fields.Many2one('otm.store', string='To Store')

    quantity = fields.Float(string='Quantity', required=True,
                             help='Positive = stock in at store_id, Negative = stock out at store_id.')
    unit_cost = fields.Float(string='Unit Cost')
    total_cost = fields.Float(string='Total Cost', compute='_compute_total_cost', store=True)

    department = fields.Char(string='Department')
    reason = fields.Char(string='Reason')
    remarks = fields.Text(string='Remarks')

    user_id = fields.Many2one('res.users', string='Recorded By', default=lambda self: self.env.user, required=True)

    # generic polymorphic source-document link, one field per document type
    purchase_id = fields.Many2one('otm.purchase', string='Purchase Source', ondelete='set null')
    receipt_id = fields.Many2one('otm.stock.receipt', string='Receipt Source', ondelete='set null')
    transfer_id = fields.Many2one('otm.stock.transfer', string='Transfer Source', ondelete='set null')
    issue_id = fields.Many2one('otm.stock.issue', string='Issue Source', ondelete='set null')
    return_id = fields.Many2one('otm.stock.return', string='Return Source', ondelete='set null')
    adjustment_id = fields.Many2one('otm.stock.adjustment', string='Adjustment Source', ondelete='set null')

    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

    @api.depends('quantity', 'unit_cost')
    def _compute_total_cost(self):
        for move in self:
            move.total_cost = move.quantity * move.unit_cost

    def unlink(self):
        if not self.env.user.has_group('otm_store_management.group_otm_admin'):
            raise UserError('Ledger entries are permanent records and cannot be deleted. '
                             'Post a reversing adjustment instead.')
        return super().unlink()

    def write(self, vals):
        protected = {'quantity', 'unit_cost', 'move_type', 'product_tmpl_id', 'store_id'}
        if protected.intersection(vals) and not self.env.user.has_group('otm_store_management.group_otm_admin'):
            raise UserError('Ledger entries are permanent records; core fields cannot be edited '
                             'after posting. Post a reversing adjustment instead.')
        return super().write(vals)
