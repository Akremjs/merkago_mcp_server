# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class MerkagoMcpTokenWizard(models.TransientModel):
    _name = "merkago.mcp.token.wizard"
    _description = "Generate MCP Token"

    name = fields.Char(required=True, default="Claude Desktop")
    user_id = fields.Many2one(
        "res.users",
        required=True,
        default=lambda self: self.env.user,
        domain="[('share', '=', False)]",
    )
    scope_ids = fields.Many2many("merkago.mcp.scope", string="Scopes")
    company_ids = fields.Many2many("res.company", string="Sandbox Companies")
    safe_mode = fields.Boolean(default=True)
    raw_token = fields.Char(readonly=True)
    token_id = fields.Many2one("merkago.mcp.token", readonly=True)

    def action_generate(self):
        self.ensure_one()
        Token = self.env["merkago.mcp.token"]
        raw = Token._generate_raw_token()
        token = Token.create(
            {
                "name": self.name,
                "user_id": self.user_id.id,
                "scope_ids": [(6, 0, self.scope_ids.ids)],
                "company_ids": [(6, 0, self.company_ids.ids)],
                "safe_mode": self.safe_mode,
                "token_prefix": raw[:12],
                "token_hash": Token._hash_token(raw),
            }
        )
        self.write({"raw_token": raw, "token_id": token.id})
        return {
            "type": "ir.actions.act_window",
            "res_model": "merkago.mcp.token.wizard",
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
            "name": _("Copy your token now"),
        }
