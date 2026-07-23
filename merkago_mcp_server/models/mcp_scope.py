# -*- coding: utf-8 -*-
from odoo import api, fields, models


class MerkagoMcpScope(models.Model):
    _name = "merkago.mcp.scope"
    _description = "MCP Model Scope"
    _order = "sequence, id"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    model_id = fields.Many2one("ir.model", required=True, ondelete="cascade")
    model_name = fields.Char(related="model_id.model", store=True, index=True, string="Model Name")
    perm_read = fields.Boolean(default=True)
    perm_write = fields.Boolean(default=False)
    perm_create = fields.Boolean(default=False)
    perm_unlink = fields.Boolean(default=False)
    pack = fields.Selection(
        selection=[
            ("contacts", "Contacts"),
            ("sales", "Sales"),
            ("accounting", "Accounting"),
            ("inventory", "Inventory"),
            ("custom", "Custom"),
        ],
        default="custom",
        required=True,
    )
    domain_force = fields.Char(
        string="Extra Domain",
        help="Optional domain as Python list, e.g. [('customer_rank','>',0)]",
    )
    note = fields.Text()

    @api.onchange("model_id")
    def _onchange_model_id(self):
        if self.model_id and not self.name:
            self.name = self.model_id.name
