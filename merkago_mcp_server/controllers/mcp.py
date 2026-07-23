# -*- coding: utf-8 -*-
import json
import logging

from odoo import http, _
from odoo.http import request, Response

_logger = logging.getLogger(__name__)


def _json_response(payload, status=200):
    return Response(
        json.dumps(payload, default=str),
        status=status,
        mimetype="application/json",
    )


def _get_bearer_token():
    auth = request.httprequest.headers.get("Authorization") or ""
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    # Also accept ?token= or X-MCP-Token
    return (
        request.httprequest.headers.get("X-MCP-Token")
        or request.params.get("token")
        or ""
    )


def _authenticate():
    raw = _get_bearer_token()
    token = request.env["merkago.mcp.token"].sudo().authenticate(raw)
    return token


class MerkagoMcpController(http.Controller):

    @http.route("/mcp/health", type="http", auth="public", methods=["GET"], csrf=False)
    def mcp_health(self, **kwargs):
        engine = request.env["merkago.mcp.engine"].sudo()
        enabled = engine._is_enabled()
        return _json_response(
            {
                "status": "ok" if enabled else "disabled",
                "service": "merkago_mcp_server",
                "version": "17.0.1.0.0",
                "phase": "P1",
                "enabled": enabled,
            }
        )

    @http.route(
        "/mcp/sse",
        type="http",
        auth="public",
        methods=["GET", "POST"],
        csrf=False,
    )
    def mcp_sse(self, **kwargs):
        """SSE endpoint for Claude connectors (P1 simplified handshake)."""
        token = _authenticate()
        if not token:
            return _json_response({"error": "Unauthorized"}, status=401)
        engine = request.env["merkago.mcp.engine"].sudo()
        if not engine._is_enabled():
            return _json_response({"error": "MCP disabled"}, status=503)

        base = engine._public_url() or request.httprequest.host_url.rstrip("/")
        messages_url = "%s/mcp/messages" % base

        def generate():
            # MCP SSE: announce message endpoint then keep-alive
            yield "event: endpoint\ndata: %s\n\n" % messages_url
            yield "event: message\ndata: %s\n\n" % json.dumps(
                {
                    "jsonrpc": "2.0",
                    "method": "notifications/message",
                    "params": {"level": "info", "data": "Merkago MCP P1 ready"},
                }
            )
            yield ": keepalive\n\n"

        headers = {
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
        return Response(generate(), headers=headers)

    @http.route(
        "/mcp/messages",
        type="http",
        auth="public",
        methods=["POST", "GET"],
        csrf=False,
    )
    def mcp_messages(self, **kwargs):
        token = _authenticate()
        if not token:
            return _json_response({"error": "Unauthorized"}, status=401)
        engine = request.env["merkago.mcp.engine"].sudo()
        if not engine._is_enabled():
            return _json_response({"error": "MCP disabled"}, status=503)

        try:
            raw = request.httprequest.get_data(as_text=True) or "{}"
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            return _json_response({"error": "Invalid JSON"}, status=400)

        # Batch support
        if isinstance(payload, list):
            results = [self._handle_rpc(token, engine, item) for item in payload]
            return _json_response(results)

        return _json_response(self._handle_rpc(token, engine, payload))

    def _handle_rpc(self, token, engine, payload):
        req_id = payload.get("id")
        method = payload.get("method")
        params = payload.get("params") or {}
        ip = request.httprequest.remote_addr

        try:
            if method in ("initialize", "notifications/initialized"):
                result = {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {
                        "name": "merkago_mcp_server",
                        "version": "17.0.1.0.0",
                    },
                }
                if method.startswith("notifications/"):
                    return {"jsonrpc": "2.0", "result": None}
                return {"jsonrpc": "2.0", "id": req_id, "result": result}

            if method == "ping":
                return {"jsonrpc": "2.0", "id": req_id, "result": {}}

            if method == "tools/list":
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"tools": engine.list_tools()},
                }

            if method == "tools/call":
                name = params.get("name")
                arguments = params.get("arguments") or {}
                data = engine.call_tool(token, name, arguments, ip=ip)
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(data, default=str, ensure_ascii=False),
                            }
                        ]
                    },
                }

            if method == "resources/list":
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "resources": [
                            {
                                "uri": "odoo://guide/odoo_conventions",
                                "name": "Odoo conventions for Claude",
                                "mimeType": "text/plain",
                            }
                        ]
                    },
                }

            if method == "resources/read":
                uri = (params.get("uri") or "")
                if uri == "odoo://guide/odoo_conventions":
                    text = (
                        "Odoo MCP guide:\n"
                        "- Domains are lists of tuples, e.g. [['is_company','=',True]]\n"
                        "- Always set a reasonable limit\n"
                        "- Respect multi-company\n"
                        "- Safe Mode blocks create/write\n"
                        "- Prefer odoo_list_models then odoo_describe_model before writing\n"
                    )
                    return {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "contents": [
                                {
                                    "uri": uri,
                                    "mimeType": "text/plain",
                                    "text": text,
                                }
                            ]
                        },
                    }

            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": "Method not found: %s" % method},
            }
        except Exception as exc:
            _logger.exception("MCP RPC error")
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32000, "message": str(exc)},
            }
