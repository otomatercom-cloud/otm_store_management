# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError


class OtmStockReceipt(models.Model):
    _name = 'otm.stock.receipt'
    _description = 'Stock Receipt (GRN)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'received_date desc, id desc'

    name = fields.Char(string='GRN No.', required=True, copy=False, default='New', tracking=True)
    purchase_id = fields.Many2one('otm.purchase', string='Purchase', ondelete='set null')
    vendor_id = fields.Many2one('res.partner', string='Vendor')
    store_id = fields.Many2one('otm.store', string='Store', required=True, tracking=True)
    location_id = fields.Many2one('otm.store.location', string='Location',
                                   domain="[('store_id', '=', store_id)]")
    invoice_number = fields.Char(string='Invoice Number')
    received_date = fields.Date(string='Received Date', default=fields.Date.context_today, required=True)
    received_by = fields.Many2one('res.users', string='Received By', default=lambda self: self.env.user)

    line_ids = fields.One2many('otm.stock.receipt.line', 'receipt_id', string='Receipt Lines')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
    ], string='Status', default='draft', tracking=True)

    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('otm.stock.receipt') or 'New'
        return super().create(vals_list)

    def action_confirm(self):
        Move = self.env['otm.stock.move']
        Batch = self.env['otm.product.batch']
        for receipt in self:
            if receipt.state == 'confirmed':
                continue
            if not receipt.line_ids:
                raise UserError('Add at least one line before confirming the receipt.')
            for line in receipt.line_ids:
                batch = line.batch_id
                if not batch and line.batch_number:
                    batch = Batch.create({
                        'name': line.batch_number,
                        'product_tmpl_id': line.product_tmpl_id.id,
                        'manufacturing_date': line.manufacturing_date,
                        'expiry_date': line.expiry_date,
                        'purchase_price': line.purchase_price,
                        'selling_price': line.selling_price,
                        'vendor_id': receipt.vendor_id.id,
                        'receipt_id': receipt.id,
                    })
                    line.batch_id = batch.id
                Move.create({
                    'reference': receipt.name,
                    'date': fields.Datetime.now(),
                    'move_type': receipt.purchase_id.purchase_type if receipt.purchase_id and
                                 receipt.purchase_id.purchase_type in ('opening', 'donation') else 'purchase',
                    'product_tmpl_id': line.product_tmpl_id.id,
                    'batch_id': batch.id if batch else False,
                    'store_id': receipt.store_id.id,
                    'location_id': receipt.location_id.id,
                    'quantity': line.quantity,
                    'unit_cost': line.purchase_price,
                    'reason': 'Stock Receipt',
                    'user_id': self.env.user.id,
                    'purchase_id': receipt.purchase_id.id if receipt.purchase_id else False,
                    'receipt_id': receipt.id,
                })
            receipt.state = 'confirmed'

    def action_reset_draft(self):
        for receipt in self:
            if receipt.env['otm.stock.move'].search([('receipt_id', '=', receipt.id)]):
                raise UserError('Cannot reset to draft: ledger entries already posted for this receipt. '
                                 'Post a stock adjustment to correct quantities instead.')
        self.write({'state': 'draft'})


class OtmStockReceiptLine(models.Model):
    _name = 'otm.stock.receipt.line'
    _description = 'Stock Receipt Line'

    receipt_id = fields.Many2one('otm.stock.receipt', string='Receipt', required=True, ondelete='cascade')
    product_tmpl_id = fields.Many2one('product.template', string='Product', required=True)
    quantity = fields.Float(string='Quantity', required=True, default=1.0)
    uom_id = fields.Many2one('uom.uom', string='UoM')
    batch_id = fields.Many2one('otm.product.batch', string='Existing Batch')
    batch_number = fields.Char(string='New Batch Number')
    manufacturing_date = fields.Date(string='Manufacturing Date')
    expiry_date = fields.Date(string='Expiry Date')
    purchase_price = fields.Float(string='Purchase Price')
    selling_price = fields.Float(string='Selling Price')
    gst_percent = fields.Float(string='GST %')

    @api.onchange('product_tmpl_id')
    def _onchange_product(self):
        if self.product_tmpl_id:
            self.gst_percent = self.product_tmpl_id.otm_gst_percent
            self.uom_id = self.product_tmpl_id.otm_issue_uom_id or self.product_tmpl_id.uom_id
