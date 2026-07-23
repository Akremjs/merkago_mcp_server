# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    mcp_enabled = fields.Boolean(
        string="Enable MCP Server",
        config_parameter="merkago_mcp.enabled",
        default=True,
    )
    mcp_safe_mode = fields.Boolean(
        string="Safe Mode (read-only)",
        config_parameter="merkago_mcp.safe_mode",
        default=True,
    )
    mcp_allow_write = fields.Boolean(
        string="Allow Writes",
        config_parameter="merkago_mcp.allow_write",
        default=False,
    )
    mcp_allow_unlink = fields.Boolean(
        string="Allow Unlink",
        config_parameter="merkago_mcp.allow_unlink",
        default=False,
    )
    mcp_public_base_url = fields.Char(
        string="Public Base URL",
        config_parameter="merkago_mcp.public_base_url",
        help="e.g. https://erp.example.com — used for Claude connector link",
    )
    mcp_default_limit = fields.Integer(
        string="Default Limit",
        config_parameter="merkago_mcp.default_limit",
        default=80,
    )
    mcp_max_limit = fields.Integer(
        string="Max Limit",
        config_parameter="merkago_mcp.max_limit",
        default=200,
    )
    mcp_daily_quota = fields.Integer(
        string="Daily Quota / Token",
        config_parameter="merkago_mcp.daily_quota",
        default=2000,
    )
    mcp_audit_enabled = fields.Boolean(
        string="Audit Log",
        config_parameter="merkago_mcp.audit_enabled",
        default=True,
    )
    mcp_claude_instructions = fields.Text(
        string="Claude Connector Help",
        compute="_compute_mcp_claude_instructions",
    )

    @api.depends("mcp_public_base_url")
    def _compute_mcp_claude_instructions(self):
        engine = self.env["merkago.mcp.engine"]
        info = engine.get_claude_connector_info()
        for rec in self:
            rec.mcp_claude_instructions = info["instructions"]

    def action_mcp_copy_claude_help(self):
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Claude Connector",
                "message": self.mcp_claude_instructions,
                "sticky": True,
                "type": "success",
            },
        }
