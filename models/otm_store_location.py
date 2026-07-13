# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class OtmStoreLocation(models.Model):
    _name = 'otm.store.location'
    _description = 'Storage Location'
    _order = 'complete_name'
    _parent_store = True
    _parent_name = 'parent_id'

    name = fields.Char(string='Location Name', required=True)
    store_id = fields.Many2one('otm.store', string='Store', required=True, ondelete='cascade', index=True)
    parent_id = fields.Many2one('otm.store.location', string='Parent Location',
                                 domain="[('store_id', '=', store_id)]", ondelete='cascade')
    parent_path = fields.Char(index=True, unaccent=False)
    child_ids = fields.One2many('otm.store.location', 'parent_id', string='Sub Locations')
    complete_name = fields.Char(compute='_compute_complete_name', store=True, recursive=True)
    location_type = fields.Selection([
        ('rack', 'Rack'),
        ('shelf', 'Shelf'),
        ('bin', 'Bin'),
        ('container', 'Container'),
        ('cold_storage', 'Cold Storage / Freezer'),
        ('other', 'Other'),
    ], string='Location Type', default='other')
    barcode = fields.Char(string='Barcode')
    active = fields.Boolean(default=True)

    @api.depends('name', 'parent_id.complete_name')
    def _compute_complete_name(self):
        for loc in self:
            if loc.parent_id:
                loc.complete_name = f'{loc.parent_id.complete_name} / {loc.name}'
            else:
                loc.complete_name = loc.name

    @api.constrains('parent_id')
    def _check_parent_recursion(self):
        if not self._check_recursion():
            raise ValidationError('A location cannot be its own parent / create a cycle.')
