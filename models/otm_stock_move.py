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

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if (vals.get('quantity') or 0.0) < 0:
                self._check_sufficient_stock(vals)
        return super().create(vals_list)

    def _check_sufficient_stock(self, vals):
        """Raise if posting this outgoing quantity would take the balance
        below zero — checked at store level (and batch, if given), and
        additionally at the specific location if one is set on this move.
        Location-level fungibility is assumed only when no location is
        specified; once a move names a location, it must not drain that
        location past what it actually holds, even if other locations in
        the same store have surplus."""
        base_domain = [
            ('product_tmpl_id', '=', vals.get('product_tmpl_id')),
            ('store_id', '=', vals.get('store_id')),
        ]
        if vals.get('batch_id'):
            base_domain.append(('batch_id', '=', vals['batch_id']))

        product = self.env['product.template'].browse(vals.get('product_tmpl_id'))
        store = self.env['otm.store'].browse(vals.get('store_id'))
        uom_name = product.uom_id.name or 'unit(s)'

        store_balance = sum(self.search(base_domain).mapped('quantity'))
        if store_balance + vals.get('quantity', 0.0) < -0.0001:
            raise UserError(
                f'Not enough stock: {product.name} at {store.name} has {store_balance:g} '
                f'{uom_name} on hand, which is not enough to cover this movement of '
                f'{abs(vals.get("quantity", 0.0)):g} {uom_name}. Reduce the quantity, choose a '
                f'different store or batch, or post a stock adjustment first if the recorded '
                f'balance is wrong.'
            )

        if vals.get('location_id'):
            location_domain = base_domain + [('location_id', '=', vals['location_id'])]
            location_balance = sum(self.search(location_domain).mapped('quantity'))
            if location_balance + vals.get('quantity', 0.0) < -0.0001:
                location = self.env['otm.store.location'].browse(vals['location_id'])
                raise UserError(
                    f'Not enough stock at that location: {product.name} at {store.name} / '
                    f'{location.name} has only {location_balance:g} {uom_name} on hand, even '
                    f'though the store overall has more. Pick the location that actually holds '
                    f'this stock, or leave location blank to draw from the store as a whole.'
                )

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
