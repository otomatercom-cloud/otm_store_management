# -*- coding: utf-8 -*-
from odoo import fields, models, tools


class OtmStockQuant(models.Model):
    """Live stock balance. This is a plain PostgreSQL VIEW aggregated from
    otm.stock.move (never written to directly), so on-hand quantity can
    never drift from the ledger.
    """
    _name = 'otm.stock.quant'
    _description = 'Live Stock Balance'
    _auto = False
    _order = 'product_tmpl_id'
    _rec_name = 'product_tmpl_id'

    product_tmpl_id = fields.Many2one('product.template', string='Product', readonly=True)
    batch_id = fields.Many2one('otm.product.batch', string='Batch', readonly=True)
    store_id = fields.Many2one('otm.store', string='Store', readonly=True)
    location_id = fields.Many2one('otm.store.location', string='Location', readonly=True)
    quantity = fields.Float(string='Current Quantity', readonly=True)
    average_cost = fields.Float(string='Average Cost', readonly=True)
    value = fields.Float(string='Stock Value', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                SELECT
                    row_number() OVER () AS id,
                    m.product_tmpl_id AS product_tmpl_id,
                    m.batch_id AS batch_id,
                    m.store_id AS store_id,
                    m.location_id AS location_id,
                    SUM(m.quantity) AS quantity,
                    CASE WHEN SUM(m.quantity) > 0
                         THEN SUM(CASE WHEN m.quantity > 0 THEN m.quantity * m.unit_cost ELSE 0 END)
                              / NULLIF(SUM(CASE WHEN m.quantity > 0 THEN m.quantity ELSE 0 END), 0)
                         ELSE 0
                    END AS average_cost,
                    SUM(m.total_cost) AS value
                FROM otm_stock_move m
                GROUP BY m.product_tmpl_id, m.batch_id, m.store_id, m.location_id
            )
        """)
