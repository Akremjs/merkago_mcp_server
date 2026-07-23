# -*- coding: utf-8 -*-
import base64
import csv
import io

from odoo import fields, models, _
from odoo.exceptions import UserError


class MerkagoMcpAudit(models.Model):
    _name = "merkago.mcp.audit.log"
    _description = "MCP Audit Log"
    _order = "id desc"

    token_id = fields.Many2one("merkago.mcp.token", ondelete="set null", index=True)
    user_id = fields.Many2one("res.users", index=True)
    tool_name = fields.Char(required=True, index=True)
    model_name = fields.Char(index=True)
    summary = fields.Text()
    result_count = fields.Integer()
    ok = fields.Boolean(default=True)
    error = fields.Text()
    duration_ms = fields.Integer()
    ip = fields.Char()

    def action_export_csv(self):
        logs = self.search([], limit=5000, order="id desc")
        if not logs:
            raise UserError(_("No audit lines to export."))
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(
            [
                "id",
                "create_date",
                "user",
                "token",
                "tool",
                "model",
                "ok",
                "result_count",
                "duration_ms",
                "summary",
                "error",
                "ip",
            ]
        )
        for line in logs:
            writer.writerow(
                [
                    line.id,
                    line.create_date,
                    line.user_id.login if line.user_id else "",
                    line.token_id.name if line.token_id else "",
                    line.tool_name,
                    line.model_name or "",
                    line.ok,
                    line.result_count,
                    line.duration_ms,
                    (line.summary or "")[:500],
                    (line.error or "")[:500],
                    line.ip or "",
                ]
            )
        data = buf.getvalue().encode("utf-8")
        attachment = self.env["ir.attachment"].create(
            {
                "name": "mcp_audit_export.csv",
                "type": "binary",
                "datas": base64.b64encode(data),
                "mimetype": "text/csv",
            }
        )
        return {
            "type": "ir.actions.act_url",
            "url": "/web/content/%s?download=true" % attachment.id,
            "target": "self",
        }
