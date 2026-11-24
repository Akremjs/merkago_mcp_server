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
    mcp_tool_list = fields.Boolean(string="Lister les modèles")
    mcp_tool_describe = fields.Boolean(string="Décrire un modèle")
    mcp_tool_search = fields.Boolean(string="Rechercher")
    mcp_tool_read = fields.Boolean(string="Lire")
    mcp_tool_create = fields.Boolean(string="Créer")
    mcp_tool_write = fields.Boolean(string="Modifier")
    mcp_tool_company = fields.Boolean(string="Contexte société")

    _MCP_TOOL_FIELDS = {
        "mcp_tool_list": "odoo_list_models",
        "mcp_tool_describe": "odoo_describe_model",
        "mcp_tool_search": "odoo_search_read",
        "mcp_tool_read": "odoo_read",
        "mcp_tool_create": "odoo_create",
        "mcp_tool_write": "odoo_write",
        "mcp_tool_company": "odoo_company_context",
    }

    @api.model
    def get_values(self):
        res = super().get_values()
        engine = self.env["merkago.mcp.engine"]
        disabled = engine._disabled_tools()
        res.update(
            {
                field: tool not in disabled
                for field, tool in self._MCP_TOOL_FIELDS.items()
            }
        )
        return res

    def set_values(self):
        super().set_values()
        disabled = [
            tool
            for field, tool in self._MCP_TOOL_FIELDS.items()
            if not self[field]
        ]
        self.env["merkago.mcp.engine"].set_disabled_tools(disabled)

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
