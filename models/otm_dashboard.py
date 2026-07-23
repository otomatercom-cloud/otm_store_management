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
            is_out = qty <= 0
            is_below_reorder = bool(product.otm_reorder_qty) and qty <= product.otm_reorder_qty
            if is_out or is_below_reorder:
                if is_out:
                    status = 'out'
                elif product.otm_critical_qty and qty <= product.otm_critical_qty:
                    status = 'critical'
                else:
                    status = 'low'
                avg_daily = product.otm_avg_daily_consumption
                days_cover = round(qty / avg_daily, 1) if avg_daily > 0 else None
                low_stock_rows.append({
                    'product': product.name,
                    'store': store.name,
                    'status': status,
                    'current_qty': round(qty, 2),
                    'reorder_qty': product.otm_reorder_qty,
                    'critical_qty': product.otm_critical_qty,
                    'max_qty': product.otm_max_qty,
                    'uom': product.uom_id.name,
                    'last_month_consumption': round(product.otm_last_month_consumption, 2),
                    'avg_daily_consumption': round(avg_daily, 2),
                    'days_of_cover': days_cover,
                })
        # most urgent first: stock-out, then critical, then low; within a
        # tier, fewest days of cover first (unknown rate goes last)
        _severity_rank = {'out': 0, 'critical': 1, 'low': 2}
        low_stock_rows.sort(key=lambda r: (
            _severity_rank[r['status']],
            r['days_of_cover'] is None,
            r['days_of_cover'] or 0,
        ))

        # full per-store breakdown (every product, not just the low ones) —
        # used for the store card grid: total listed / out / critical /
        # low / ok, per store.
        store_status_counts = {}
        store_value = {}
        for (store, product), qty in store_product_qty.items():
            counts = store_status_counts.setdefault(
                store, {'total': 0, 'out': 0, 'critical': 0, 'low': 0, 'ok': 0})
            counts['total'] += 1
            if qty <= 0:
                counts['out'] += 1
            elif product.otm_critical_qty and qty <= product.otm_critical_qty:
                counts['critical'] += 1
            elif product.otm_reorder_qty and qty <= product.otm_reorder_qty:
                counts['low'] += 1
            else:
                counts['ok'] += 1
        for q in quants:
            store_value[q.store_id] = store_value.get(q.store_id, 0.0) + q.value

        stores_summary = []
        for store in Store.search([], order='name'):
            counts = store_status_counts.get(
                store, {'total': 0, 'out': 0, 'critical': 0, 'low': 0, 'ok': 0})
            healthy_pct = round((counts['ok'] / counts['total']) * 100) if counts['total'] else 100
            stores_summary.append({
                'id': store.id,
                'name': store.name,
                'code': store.code,
                'manager': store.manager_id.name or None,
                'total_products': counts['total'],
                'out_count': counts['out'],
                'critical_count': counts['critical'],
                'low_count': counts['low'],
                'ok_count': counts['ok'],
                'at_risk_count': counts['out'] + counts['critical'] + counts['low'],
                'healthy_pct': healthy_pct,
                'value': round(store_value.get(store, 0.0), 2),
            })

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
                'stock_out': len([r for r in low_stock_rows if r['status'] == 'out']),
                'expired': len(expired),
                'near_expiry': len(near_expiry),
                'pending_approvals': pending_approvals,
            },
            'low_stock_items': low_stock_rows,
            'stores': stores_summary,
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
