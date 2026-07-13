# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    otm_gst_percent = fields.Float(string='GST %')
    otm_hsn_code = fields.Char(string='HSN Code')
    otm_purchase_uom_id = fields.Many2one('uom.uom', string='Purchase Unit')
    otm_issue_uom_id = fields.Many2one('uom.uom', string='Issue Unit')
    otm_min_qty = fields.Float(string='Minimum Quantity')
    otm_max_qty = fields.Float(string='Maximum Quantity')
    otm_reorder_qty = fields.Float(string='Reorder Quantity')
    otm_critical_qty = fields.Float(string='Critical Quantity')
    otm_preferred_vendor_id = fields.Many2one('res.partner', string='Preferred Vendor')
    otm_shelf_life_days = fields.Integer(string='Shelf Life (Days)')
    otm_expiry_alert_days = fields.Integer(string='Expiry Alert (Days Before)', default=30)
    otm_is_perishable = fields.Boolean(string='Perishable')
    otm_is_batch_tracked = fields.Boolean(string='Batch Tracked')
    otm_storage_type = fields.Selection([
        ('normal', 'Normal'),
        ('cold', 'Cold Storage'),
        ('freezer', 'Freezer'),
        ('hazardous', 'Hazardous'),
        ('secure', 'Secure / Controlled'),
    ], string='Storage Type', default='normal')

    otm_quant_ids = fields.One2many('otm.stock.quant', 'product_id', string='Live Stock')
    otm_current_qty = fields.Float(compute='_compute_otm_stock', string='Current Stock')
    otm_is_low_stock = fields.Boolean(compute='_compute_otm_stock', string='Low Stock', search='_search_low_stock')

    def _compute_otm_stock(self):
        Quant = self.env['otm.stock.quant']
        for product in self:
            quants = Quant.search([('product_tmpl_id', '=', product.id)])
            qty = sum(quants.mapped('quantity'))
            product.otm_current_qty = qty
            product.otm_is_low_stock = bool(product.otm_reorder_qty) and qty <= product.otm_reorder_qty

    def _search_low_stock(self, operator, value):
        # Evaluated in Python since the low-stock flag depends on a
        # per-product reorder threshold, not a single stored aggregate.
        low_ids = []
        for product in self.search([]):
            if product.otm_is_low_stock:
                low_ids.append(product.id)
        if (operator == '=' and value) or (operator == '!=' and not value):
            return [('id', 'in', low_ids)]
        return [('id', 'not in', low_ids)]
