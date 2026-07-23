# -*- coding: utf-8 -*-
import hashlib
import secrets

from odoo import api, fields, models, _


class MerkagoMcpToken(models.Model):
    _name = "merkago.mcp.token"
    _description = "MCP Bearer Token"
    _order = "id desc"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    user_id = fields.Many2one(
        "res.users",
        required=True,
        default=lambda self: self.env.user,
        domain="[('share', '=', False)]",
    )
    token_prefix = fields.Char(readonly=True, copy=False)
    token_hash = fields.Char(readonly=True, copy=False)
    scope_ids = fields.Many2many("merkago.mcp.scope", string="Scopes")
    company_ids = fields.Many2many(
        "res.company",
        string="Sandbox Companies",
        help="Leave empty to use the user's allowed companies.",
    )
    safe_mode = fields.Boolean(
        string="Force Safe Mode",
        help="If enabled, this token is read-only even when global write is allowed.",
    )
    daily_quota = fields.Integer(
        string="Daily Quota",
        default=0,
        help="0 = use global settings quota.",
    )
    calls_today = fields.Integer(readonly=True, default=0)
    calls_day = fields.Date(readonly=True)
    last_used = fields.Datetime(readonly=True)
    expires_at = fields.Datetime()
    call_count = fields.Integer(readonly=True, default=0)

    def _hash_token(self, raw_token):
        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    @api.model
    def _generate_raw_token(self):
        return "mcp_%s" % secrets.token_urlsafe(32)

    def action_open_generate_wizard(self):
        return {
            "type": "ir.actions.act_window",
            "name": _("Generate Token"),
            "res_model": "merkago.mcp.token.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_name": self.name or _("Claude Desktop"),
                "default_user_id": self.user_id.id or self.env.user.id,
            },
        }

    @api.model
    def authenticate(self, raw_token):
        if not raw_token:
            return self.browse()
        raw_token = raw_token.strip()
        if raw_token.lower().startswith("bearer "):
            raw_token = raw_token[7:].strip()
        token_hash = self._hash_token(raw_token)
        token = self.sudo().search(
            [("token_hash", "=", token_hash), ("active", "=", True)],
            limit=1,
        )
        if not token:
            return self.browse()
        if token.expires_at and token.expires_at < fields.Datetime.now():
            return self.browse()
        return token

    def _check_quota(self, global_quota):
        self.ensure_one()
        today = fields.Date.context_today(self)
        quota = self.daily_quota or global_quota or 0
        if not quota:
            return True
        if self.calls_day != today:
            self.sudo().write({"calls_day": today, "calls_today": 0})
        return self.calls_today < quota

    def _bump_usage(self):
        self.ensure_one()
        today = fields.Date.context_today(self)
        vals = {
            "last_used": fields.Datetime.now(),
            "call_count": self.call_count + 1,
        }
        if self.calls_day != today:
            vals.update({"calls_day": today, "calls_today": 1})
        else:
            vals["calls_today"] = self.calls_today + 1
        self.sudo().write(vals)
