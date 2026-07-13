# -*- coding: utf-8 -*-
from odoo import fields, models


class OtmDashboard(models.AbstractModel):
    _name = 'otm.dashboard'
    _description = 'Store Management Dashboard Data Provider'

    def get_dashboard_data(self):
        Store = self.env['otm.store']
        Move = self.env['otm.stock.move']
        Quant = self.env['otm.stock.quant']
        Batch = self.env['otm.product.batch']
        Transfer = self.env['otm.stock.transfer']
        Issue = self.env['otm.stock.issue']
        Adjustment = self.env['otm.stock.adjustment']

        today = fields.Date.context_today(self)
        month_start = today.replace(day=1)

        quants = Quant.search([])

        # Aggregate to (store, product) first — a product can have several
        # quant rows in the same store (different locations/batches), and
        # the reorder threshold is a store-level total, not a per-row one.
        store_product_qty = {}
        for q in quants:
            key = (q.store_id, q.product_tmpl_id)
            store_product_qty[key] = store_product_qty.get(key, 0.0) + q.quantity

        low_stock_rows = []
        for (store, product), qty in store_product_qty.items():
            if product.otm_reorder_qty and qty <= product.otm_reorder_qty:
                avg_daily = product.otm_avg_daily_consumption
                days_cover = round(qty / avg_daily, 1) if avg_daily > 0 else None
                low_stock_rows.append({
                    'product': product.name,
                    'store': store.name,
                    'current_qty': round(qty, 2),
                    'reorder_qty': product.otm_reorder_qty,
                    'max_qty': product.otm_max_qty,
                    'uom': product.uom_id.name,
                    'last_month_consumption': round(product.otm_last_month_consumption, 2),
                    'avg_daily_consumption': round(avg_daily, 2),
                    'days_of_cover': days_cover,
                })
        # most urgent (fewest days of cover) first; unknown rate goes last
        low_stock_rows.sort(key=lambda r: (r['days_of_cover'] is None, r['days_of_cover'] or 0))

        batches = Batch.search([])
        expired = batches.filtered(lambda b: b.expiry_state == 'expired')
        near_expiry = batches.filtered(lambda b: b.expiry_state == 'near_expiry')

        purchase_moves_month = Move.search([
            ('move_type', '=', 'purchase'), ('date', '>=', month_start)])
        issue_moves_month = Move.search([
            ('move_type', '=', 'issue'), ('date', '>=', month_start)])

        purchase_today = Move.search_count([
            ('move_type', '=', 'purchase'), ('date', '>=', today)])
        transfer_today = Transfer.search_count([('transfer_date', '=', today)])
        issue_today = Issue.search_count([('issue_date', '=', today)])

        pending_approvals = (
            Transfer.search_count([('state', 'in', ('requested',))])
            + Issue.search_count([('state', '=', 'draft')])
            + Adjustment.search_count([('state', '=', 'draft')])
        )

        # department wise consumption (current month, from issue moves)
        dept_consumption = {}
        for m in issue_moves_month:
            key = m.department or 'Other'
            dept_consumption[key] = dept_consumption.get(key, 0) + abs(m.total_cost)

        # store wise stock value
        store_stock = {}
        for q in quants:
            key = q.store_id.name
            store_stock[key] = store_stock.get(key, 0) + q.value

        return {
            'cards': {
                'total_stores': Store.search_count([]),
                'total_products': len(quants.mapped('product_tmpl_id')),
                'inventory_value': sum(quants.mapped('value')),
                'today_purchase': purchase_today,
                'today_transfer': transfer_today,
                'today_issue': issue_today,
                'low_stock': len(low_stock_rows),
                'expired': len(expired),
                'near_expiry': len(near_expiry),
                'pending_approvals': pending_approvals,
            },
            'low_stock_items': low_stock_rows,
            'department_consumption': [
                {'label': k, 'value': round(v, 2)} for k, v in
                sorted(dept_consumption.items(), key=lambda x: -x[1])
            ],
            'store_wise_stock': [
                {'label': k, 'value': round(v, 2)} for k, v in
                sorted(store_stock.items(), key=lambda x: -x[1])
            ],
            'monthly_purchase_value': round(sum(purchase_moves_month.mapped('total_cost')), 2),
            'monthly_consumption_value': round(abs(sum(issue_moves_month.mapped('total_cost'))), 2),
        }
