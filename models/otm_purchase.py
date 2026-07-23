# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError


class OtmPurchase(models.Model):
    _name = 'otm.purchase'
    _description = 'Purchase'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'purchase_date desc, id desc'

    name = fields.Char(string='Purchase No.', required=True, copy=False, default='New', tracking=True)
    vendor_id = fields.Many2one('res.partner', string='Vendor', tracking=True)
    store_id = fields.Many2one('otm.store', string='Default Store', required=True, tracking=True,
                                help='Used as the default store for new purchase lines. Each line can '
                                     'still be sent to a different store — useful when one vendor bill '
                                     'covers products for several stores.')

    purchase_type = fields.Selection([
        ('gst', 'GST Purchase'),
        ('non_gst', 'Non GST Purchase'),
        ('without_bill', 'Without Bill Purchase'),
        ('cash', 'Cash Purchase'),
        ('credit', 'Credit Purchase'),
        ('opening', 'Opening Stock'),
        ('donation', 'Donation Stock'),
        ('returned', 'Returned Stock'),
    ], string='Purchase Type', required=True, default='gst', tracking=True)

    invoice_number = fields.Char(string='Invoice Number')
    purchase_date = fields.Date(string='Purchase Date', default=fields.Date.context_today, required=True)
    bill_date = fields.Date(string='Bill Date')

    bill_attachment_ids = fields.Many2many(
        'ir.attachment', 'otm_purchase_bill_attachment_rel', 'purchase_id', 'attachment_id',
        string='Purchase Bill(s)',
        help='Photo or scan of the vendor invoice/bill for this purchase.')
    bill_attachment_count = fields.Integer(compute='_compute_bill_attachment_count')

    line_ids = fields.One2many('otm.purchase.line', 'purchase_id', string='Purchase Lines')

    bill_amount = fields.Float(string='Bill Amount (Taxable)', compute='_compute_amounts', store=True)
    cgst_amount = fields.Float(string='CGST', compute='_compute_amounts', store=True)
    sgst_amount = fields.Float(string='SGST', compute='_compute_amounts', store=True)
    igst_amount = fields.Float(string='IGST', compute='_compute_amounts', store=True)
    cess_amount = fields.Float(string='CESS')
    discount = fields.Float(string='Discount')
    freight = fields.Float(string='Freight')
    other_charges = fields.Float(string='Other Charges')
    grand_total = fields.Float(string='Grand Total', compute='_compute_amounts', store=True)
    is_interstate = fields.Boolean(string='Interstate (IGST applicable)')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('received', 'Received'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    receipt_ids = fields.One2many('otm.stock.receipt', 'purchase_id', string='Stock Receipts')
    receipt_count = fields.Integer(compute='_compute_receipt_count')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('otm.purchase') or 'New'
        return super().create(vals_list)

    @api.depends('line_ids.taxable_amount', 'line_ids.cgst_amount', 'line_ids.sgst_amount',
                 'line_ids.igst_amount', 'discount', 'freight', 'other_charges', 'cess_amount')
    def _compute_amounts(self):
        for purchase in self:
            purchase.bill_amount = sum(purchase.line_ids.mapped('taxable_amount'))
            purchase.cgst_amount = sum(purchase.line_ids.mapped('cgst_amount'))
            purchase.sgst_amount = sum(purchase.line_ids.mapped('sgst_amount'))
            purchase.igst_amount = sum(purchase.line_ids.mapped('igst_amount'))
            purchase.grand_total = (
                purchase.bill_amount + purchase.cgst_amount + purchase.sgst_amount
                + purchase.igst_amount + purchase.cess_amount + purchase.freight
                + purchase.other_charges - purchase.discount
            )

    def _compute_receipt_count(self):
        for purchase in self:
            purchase.receipt_count = len(purchase.receipt_ids)

    def _compute_bill_attachment_count(self):
        for purchase in self:
            purchase.bill_attachment_count = len(purchase.bill_attachment_ids)

    def action_confirm(self):
        for purchase in self:
            if not purchase.line_ids:
                raise UserError('Add at least one purchase line before confirming.')
            purchase.state = 'confirmed'
            for line in purchase.line_ids:
                if line.store_id and line.product_tmpl_id.otm_default_store_id != line.store_id:
                    line.product_tmpl_id.otm_default_store_id = line.store_id.id
            purchase._create_stock_receipt()

    def _create_stock_receipt(self):
        """One receipt per destination store — a single vendor bill can cover
        products headed to several different stores, but a GRN/receipt is
        always for one physical receiving location."""
        self.ensure_one()
        receipts = self.env['otm.stock.receipt']
        lines_by_store = {}
        for line in self.line_ids:
            lines_by_store[line.store_id] = lines_by_store.get(line.store_id, self.env['otm.purchase.line']) | line
        for store, lines in lines_by_store.items():
            receipt = self.env['otm.stock.receipt'].create({
                'purchase_id': self.id,
                'store_id': store.id,
                'vendor_id': self.vendor_id.id,
                'invoice_number': self.invoice_number,
                'received_date': fields.Date.context_today(self),
                'line_ids': [(0, 0, {
                    'product_tmpl_id': line.product_tmpl_id.id,
                    'quantity': line.quantity,
                    'purchase_price': line.unit_price,
                    'selling_price': line.selling_price,
                }) for line in lines],
            })
            receipts |= receipt
        return receipts

    def action_view_receipts(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'otm_store_management.action_otm_stock_receipt')
        action['domain'] = [('purchase_id', '=', self.id)]
        return action

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})


class OtmPurchaseLine(models.Model):
    _name = 'otm.purchase.line'
    _description = 'Purchase Line'

    purchase_id = fields.Many2one('otm.purchase', string='Purchase', required=True, ondelete='cascade')
    product_tmpl_id = fields.Many2one('product.template', string='Product', required=True)
    store_id = fields.Many2one('otm.store', string='Store', required=True,
                                help='Destination store for this line. Pre-filled from the product\'s '
                                     'usual store if it has one, otherwise from the purchase\'s default '
                                     'store — change it per line to split one bill across stores.')
    quantity = fields.Float(string='Quantity', required=True, default=1.0)
    uom_id = fields.Many2one('uom.uom', string='UoM')
    unit_price = fields.Float(string='Purchase Rate', required=True,
                               help='The rate you pay the vendor per unit — this is what gets posted '
                                    'as the stock cost, not the selling rate.')
    selling_price = fields.Float(string='Selling Rate',
                                  help='Optional — the rate this batch will be sold/issued at. '
                                       'Has no effect on stock cost or the purchase ledger.')
    gst_percent = fields.Float(string='GST %')
    taxable_amount = fields.Float(compute='_compute_tax', store=True)
    cgst_amount = fields.Float(compute='_compute_tax', store=True)
    sgst_amount = fields.Float(compute='_compute_tax', store=True)
    igst_amount = fields.Float(compute='_compute_tax', store=True)

    @api.onchange('product_tmpl_id')
    def _onchange_product(self):
        if self.product_tmpl_id:
            self.gst_percent = self.product_tmpl_id.otm_gst_percent
            self.uom_id = self.product_tmpl_id.otm_purchase_uom_id or self.product_tmpl_id.uom_id
            if self.product_tmpl_id.otm_default_store_id:
                self.store_id = self.product_tmpl_id.otm_default_store_id

    @api.depends('quantity', 'unit_price', 'gst_percent', 'purchase_id.is_interstate')
    def _compute_tax(self):
        for line in self:
            line.taxable_amount = line.quantity * line.unit_price
            tax = line.taxable_amount * (line.gst_percent or 0.0) / 100.0
            if line.purchase_id.is_interstate:
                line.igst_amount = tax
                line.cgst_amount = 0.0
                line.sgst_amount = 0.0
            else:
                line.igst_amount = 0.0
                line.cgst_amount = tax / 2.0
                line.sgst_amount = tax / 2.0
