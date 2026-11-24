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

    @api.model
    def apply_pack(self, pack):
        """Activate a ready-made scope pack. Skips models that are not installed."""
        specs = SCOPE_PACKS.get(pack) or []
        IrModel = self.env["ir.model"].sudo()
        activated = 0
        skipped = []
        for model_name, label, sequence in specs:
            model = IrModel.search([("model", "=", model_name)], limit=1)
            if not model:
                skipped.append(model_name)
                continue
            existing = self.sudo().search([("model_name", "=", model_name)], limit=1)
            vals = {
                "name": label,
                "model_id": model.id,
                "pack": pack,
                "sequence": sequence,
                "active": True,
                "perm_read": True,
                "perm_write": False,
                "perm_create": False,
                "perm_unlink": False,
            }
            if existing:
                existing.write({"active": True, "pack": pack, "perm_read": True})
            else:
                self.sudo().create(vals)
            activated += 1
        return {"activated": activated, "skipped": skipped}


SCOPE_PACKS = {
    "contacts": [
        ("res.partner", "Contacts / Partners", 10),
        ("res.users", "Users (read)", 90),
    ],
    "sales": [
        ("sale.order", "Sales Orders", 30),
        ("sale.order.line", "Sales Order Lines", 31),
        ("crm.lead", "CRM Opportunities", 32),
    ],
    "inventory": [
        ("product.template", "Products / Templates", 20),
        ("product.product", "Products / Variants", 21),
        ("product.category", "Product Categories", 22),
        ("stock.quant", "Stock On Hand", 23),
    ],
    "accounting": [
        ("account.move", "Invoices / Entries", 40),
        ("account.move.line", "Journal Items", 41),
        ("account.payment", "Payments", 42),
    ],
}
