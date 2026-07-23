# -*- coding: utf-8 -*-
import ast
import json
import logging
import time

from odoo import models, _
from odoo.exceptions import AccessError, UserError
from odoo.osv import expression

_logger = logging.getLogger(__name__)

SENSITIVE_FIELDS = {
    "password",
    "new_password",
    "totp_secret",
    "totp_counter",
    "api_key",
    "private_key",
    "oauth_uid",
    "signup_token",
    "password_crypt",
}


class MerkagoMcpEngine(models.AbstractModel):
    _name = "merkago.mcp.engine"
    _description = "MCP Tool Engine"

    def _icp(self, key, default=None):
        return self.env["ir.config_parameter"].sudo().get_param(key, default)

    def _is_enabled(self):
        return self._icp("merkago_mcp.enabled", "True") == "True"

    def _safe_mode(self, token=None):
        if token and token.safe_mode:
            return True
        return self._icp("merkago_mcp.safe_mode", "True") == "True"

    def _allow_write(self):
        return self._icp("merkago_mcp.allow_write", "False") == "True"

    def _allow_unlink(self):
        return self._icp("merkago_mcp.allow_unlink", "False") == "True"

    def _max_limit(self):
        try:
            return int(self._icp("merkago_mcp.max_limit", "200"))
        except ValueError:
            return 200

    def _default_limit(self):
        try:
            return int(self._icp("merkago_mcp.default_limit", "80"))
        except ValueError:
            return 80

    def _global_quota(self):
        try:
            return int(self._icp("merkago_mcp.daily_quota", "2000"))
        except ValueError:
            return 2000

    def _public_url(self):
        return (self._icp("merkago_mcp.public_base_url") or self._icp("web.base.url") or "").rstrip("/")

    def get_claude_connector_info(self):
        base = self._public_url()
        return {
            "sse_url": "%s/mcp/sse" % base if base else "/mcp/sse",
            "messages_url": "%s/mcp/messages" % base if base else "/mcp/messages",
            "health_url": "%s/mcp/health" % base if base else "/mcp/health",
            "instructions": _(
                "Claude Desktop → Settings → Connectors → Add custom connector.\n"
                "URL: %(sse)s\n"
                "Auth: Bearer <your MCP token>\n"
                "Generate a token in Merkago MCP → Tokens."
            )
            % {"sse": "%s/mcp/sse" % base if base else "/mcp/sse"},
        }

    def _user_env(self, token):
        return self.env(user=token.user_id.id)

    def _allowed_scopes(self, token):
        scopes = token.scope_ids.filtered("active")
        if not scopes:
            scopes = self.env["merkago.mcp.scope"].sudo().search([("active", "=", True)])
        return scopes

    def _get_scope(self, token, model_name):
        return self._allowed_scopes(token).filtered(lambda s: s.model_name == model_name)[:1]

    def _filter_fields(self, Model, fields_list):
        valid = []
        for fname in fields_list or []:
            if fname in SENSITIVE_FIELDS:
                continue
            if fname not in Model._fields:
                continue
            field = Model._fields[fname]
            if getattr(field, "groups", None) and "base.group_system" in (field.groups or ""):
                continue
            valid.append(fname)
        if not valid:
            # default public-ish fields
            for fname in ("id", "display_name", "name"):
                if fname in Model._fields:
                    valid.append(fname)
        return valid

    def _company_domain(self, token):
        companies = token.company_ids or token.user_id.company_ids
        if not companies:
            return []
        return ["|", ("company_id", "=", False), ("company_id", "in", companies.ids)]

    def _merge_domain(self, token, scope, domain):
        domain = list(domain or [])
        extras = []
        if scope and scope.domain_force:
            try:
                extras.append(ast.literal_eval(scope.domain_force))
            except Exception as exc:
                raise UserError(_("Invalid scope domain: %s") % exc)
        company_dom = self._company_domain(token)
        parts = [domain] if domain else []
        parts.extend(extras)
        if company_dom:
            parts.append(company_dom)
        if not parts:
            return []
        return expression.AND(parts) if len(parts) > 1 else parts[0]

    def _audit(self, token, tool_name, model_name, summary, ok=True, error=None, count=0, duration_ms=0, ip=None):
        if self._icp("merkago_mcp.audit_enabled", "True") != "True":
            return
        self.env["merkago.mcp.audit.log"].sudo().create(
            {
                "token_id": token.id,
                "user_id": token.user_id.id,
                "tool_name": tool_name,
                "model_name": model_name,
                "summary": summary,
                "ok": ok,
                "error": error,
                "result_count": count,
                "duration_ms": duration_ms,
                "ip": ip,
            }
        )

    def list_tools(self):
        return [
            {
                "name": "odoo_list_models",
                "description": "List Odoo models exposed to this MCP token (whitelist scopes).",
                "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
            },
            {
                "name": "odoo_describe_model",
                "description": "Describe fields of an Odoo model available to this token.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"model": {"type": "string"}},
                    "required": ["model"],
                },
            },
            {
                "name": "odoo_search_read",
                "description": "Search and read Odoo records. Domain is an Odoo domain list.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "model": {"type": "string"},
                        "domain": {"type": "array"},
                        "fields": {"type": "array", "items": {"type": "string"}},
                        "limit": {"type": "integer"},
                        "offset": {"type": "integer"},
                        "order": {"type": "string"},
                    },
                    "required": ["model"],
                },
            },
            {
                "name": "odoo_read",
                "description": "Read Odoo records by ids.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "model": {"type": "string"},
                        "ids": {"type": "array", "items": {"type": "integer"}},
                        "fields": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["model", "ids"],
                },
            },
            {
                "name": "odoo_create",
                "description": "Create an Odoo record (blocked in Safe Mode).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "model": {"type": "string"},
                        "values": {"type": "object"},
                    },
                    "required": ["model", "values"],
                },
            },
            {
                "name": "odoo_write",
                "description": "Write Odoo records (blocked in Safe Mode).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "model": {"type": "string"},
                        "ids": {"type": "array", "items": {"type": "integer"}},
                        "values": {"type": "object"},
                    },
                    "required": ["model", "ids", "values"],
                },
            },
            {
                "name": "odoo_company_context",
                "description": "Show current user and allowed companies for this token.",
                "inputSchema": {"type": "object", "properties": {}},
            },
        ]

    def call_tool(self, token, name, arguments=None, ip=None):
        arguments = arguments or {}
        if not self._is_enabled():
            raise UserError(_("MCP server is disabled."))
        if not token._check_quota(self._global_quota()):
            raise UserError(_("Daily MCP quota exceeded for this token."))
        start = time.time()
        try:
            result = self._dispatch(token, name, arguments)
            duration = int((time.time() - start) * 1000)
            token._bump_usage()
            count = 0
            if isinstance(result, list):
                count = len(result)
            elif isinstance(result, dict) and "records" in result:
                count = len(result.get("records") or [])
            self._audit(
                token,
                name,
                arguments.get("model"),
                json.dumps(arguments, default=str)[:1000],
                ok=True,
                count=count,
                duration_ms=duration,
                ip=ip,
            )
            return result
        except Exception as exc:
            duration = int((time.time() - start) * 1000)
            self._audit(
                token,
                name,
                arguments.get("model"),
                json.dumps(arguments, default=str)[:1000],
                ok=False,
                error=str(exc),
                duration_ms=duration,
                ip=ip,
            )
            raise

    def _dispatch(self, token, name, arguments):
        env = self._user_env(token)
        if name == "odoo_list_models":
            scopes = self._allowed_scopes(token)
            return [
                {
                    "model": s.model_name,
                    "name": s.name,
                    "perm_read": s.perm_read,
                    "perm_write": s.perm_write,
                    "perm_create": s.perm_create,
                    "perm_unlink": s.perm_unlink,
                    "pack": s.pack,
                }
                for s in scopes
            ]
        if name == "odoo_company_context":
            return {
                "user": token.user_id.login,
                "companies": token.company_ids.mapped("name")
                or token.user_id.company_ids.mapped("name"),
                "safe_mode": self._safe_mode(token),
                "allow_write": self._allow_write() and not self._safe_mode(token),
            }
        if name == "odoo_describe_model":
            model_name = arguments.get("model")
            scope = self._get_scope(token, model_name)
            if not scope or not scope.perm_read:
                raise AccessError(_("Model not allowed: %s") % model_name)
            Model = env[model_name]
            fields_info = []
            for fname, field in Model._fields.items():
                if fname in SENSITIVE_FIELDS:
                    continue
                fields_info.append(
                    {
                        "name": fname,
                        "type": field.type,
                        "string": field.string,
                        "required": bool(field.required),
                    }
                )
            return {"model": model_name, "fields": fields_info[:200]}
        if name == "odoo_search_read":
            return self._tool_search_read(env, token, arguments)
        if name == "odoo_read":
            return self._tool_read(env, token, arguments)
        if name == "odoo_create":
            return self._tool_create(env, token, arguments)
        if name == "odoo_write":
            return self._tool_write(env, token, arguments)
        raise UserError(_("Unknown tool: %s") % name)

    def _tool_search_read(self, env, token, arguments):
        model_name = arguments.get("model")
        scope = self._get_scope(token, model_name)
        if not scope or not scope.perm_read:
            raise AccessError(_("Read not allowed on %s") % model_name)
        Model = env[model_name]
        domain = self._merge_domain(token, scope, arguments.get("domain") or [])
        limit = min(int(arguments.get("limit") or self._default_limit()), self._max_limit())
        offset = int(arguments.get("offset") or 0)
        order = arguments.get("order") or "id desc"
        fields_list = self._filter_fields(Model, arguments.get("fields"))
        records = Model.search_read(domain, fields_list, offset=offset, limit=limit, order=order)
        return {"records": records, "limit": limit, "offset": offset}

    def _tool_read(self, env, token, arguments):
        model_name = arguments.get("model")
        scope = self._get_scope(token, model_name)
        if not scope or not scope.perm_read:
            raise AccessError(_("Read not allowed on %s") % model_name)
        Model = env[model_name]
        ids = arguments.get("ids") or []
        fields_list = self._filter_fields(Model, arguments.get("fields"))
        return {"records": Model.browse(ids).read(fields_list)}

    def _ensure_write_allowed(self, token, scope, need_create=False):
        if self._safe_mode(token):
            raise UserError(_("Safe Mode is enabled — writes are blocked."))
        if not self._allow_write():
            raise UserError(_("Writes are disabled in MCP settings."))
        if need_create and (not scope or not scope.perm_create):
            raise AccessError(_("Create not allowed on this model."))
        if not need_create and (not scope or not scope.perm_write):
            raise AccessError(_("Write not allowed on this model."))

    def _sanitize_values(self, values):
        values = dict(values or {})
        for key in list(values):
            if key in SENSITIVE_FIELDS:
                values.pop(key, None)
        return values

    def _tool_create(self, env, token, arguments):
        model_name = arguments.get("model")
        scope = self._get_scope(token, model_name)
        self._ensure_write_allowed(token, scope, need_create=True)
        values = self._sanitize_values(arguments.get("values"))
        rec = env[model_name].create(values)
        return {"id": rec.id, "display_name": rec.display_name}

    def _tool_write(self, env, token, arguments):
        model_name = arguments.get("model")
        scope = self._get_scope(token, model_name)
        self._ensure_write_allowed(token, scope, need_create=False)
        values = self._sanitize_values(arguments.get("values"))
        ids = arguments.get("ids") or []
        recs = env[model_name].browse(ids)
        recs.write(values)
        return {"updated": len(recs)}
