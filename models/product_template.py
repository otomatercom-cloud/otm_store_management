# -*- coding: utf-8 -*-
import calendar
from datetime import timedelta
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
    otm_default_store_id = fields.Many2one(
        'otm.store', string='Default Store',
        help='The store this product is usually purchased into. Updated automatically whenever '
             'a purchase line for this product is confirmed with a store — used to pre-fill the '
             'store on future purchase lines for this product. You can also set it manually.')
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

    otm_quant_ids = fields.One2many('otm.stock.quant', 'product_tmpl_id', string='Live Stock')
    otm_current_qty = fields.Float(compute='_compute_otm_stock', string='Current Stock')
    otm_is_low_stock = fields.Boolean(compute='_compute_otm_stock', string='Low Stock', search='_search_low_stock')
    otm_is_stock_out = fields.Boolean(compute='_compute_otm_stock', string='Stock Out', search='_search_stock_out')
    otm_stock_status = fields.Selection([
        ('ok', 'OK'),
        ('low', 'Low Stock'),
        ('critical', 'Critical'),
        ('out', 'Stock Out'),
    ], compute='_compute_otm_stock', string='Stock Status')

    otm_last_month_consumption = fields.Float(
        compute='_compute_otm_consumption', string='Last Month Consumption',
        help='Total quantity issued last calendar month, across all stores.')
    otm_avg_daily_consumption = fields.Float(
        compute='_compute_otm_consumption', string='Avg Daily Consumption',
        help='Last month\'s consumption divided by the number of days in that month.')
    otm_projected_month_consumption = fields.Float(
        compute='_compute_otm_consumption', string='Projected This Month',
        help='Last month\'s average daily consumption rate projected across the days in '
             'the current month — i.e. "if this month consumes at the same rate as last '
             'month, this is the expected quantity."')
    otm_days_of_cover = fields.Float(
        compute='_compute_otm_consumption', string='Days of Cover',
        help='Current stock divided by last month\'s average daily consumption rate.')

    def _compute_otm_stock(self):
        Quant = self.env['otm.stock.quant']
        for product in self:
            quants = Quant.search([('product_tmpl_id', '=', product.id)])
            qty = sum(quants.mapped('quantity'))
            product.otm_current_qty = qty
            product.otm_is_low_stock = bool(product.otm_reorder_qty) and qty <= product.otm_reorder_qty
            product.otm_is_stock_out = qty <= 0
            if qty <= 0:
                product.otm_stock_status = 'out'
            elif product.otm_critical_qty and qty <= product.otm_critical_qty:
                product.otm_stock_status = 'critical'
            elif product.otm_reorder_qty and qty <= product.otm_reorder_qty:
                product.otm_stock_status = 'low'
            else:
                product.otm_stock_status = 'ok'

    def _compute_otm_consumption(self):
        Move = self.env['otm.stock.move']
        today = fields.Date.context_today(self)
        first_of_this_month = today.replace(day=1)
        last_month_end = first_of_this_month - timedelta(days=1)
        first_of_last_month = last_month_end.replace(day=1)
        days_in_last_month = (last_month_end - first_of_last_month).days + 1
        days_in_this_month = calendar.monthrange(today.year, today.month)[1]

        for product in self:
            moves = Move.search([
                ('product_tmpl_id', '=', product.id),
                ('move_type', '=', 'issue'),
                ('date', '>=', first_of_last_month),
                ('date', '<', first_of_this_month),
            ])
            # issue moves are stored as negative quantities on the ledger
            consumed = abs(sum(moves.mapped('quantity')))
            avg_daily = consumed / days_in_last_month if days_in_last_month else 0.0

            product.otm_last_month_consumption = consumed
            product.otm_avg_daily_consumption = avg_daily
            product.otm_projected_month_consumption = avg_daily * days_in_this_month
            product.otm_days_of_cover = (product.otm_current_qty / avg_daily) if avg_daily > 0 else 0.0

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

    def _search_stock_out(self, operator, value):
        out_ids = []
        for product in self.search([]):
            if product.otm_is_stock_out:
                out_ids.append(product.id)
        if (operator == '=' and value) or (operator == '!=' and not value):
            return [('id', 'in', out_ids)]
        return [('id', 'not in', out_ids)]
