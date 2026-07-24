# -*- coding: utf-8 -*-
import json
import logging

from odoo import http
from odoo.http import request, Response

_logger = logging.getLogger(__name__)


def _json_response(payload, status=200, headers=None):
    hdrs = {}
    if headers:
        hdrs.update(headers)
    return Response(
        json.dumps(payload, default=str),
        status=status,
        mimetype="application/json",
        headers=hdrs,
    )


def _www_authenticate():
    engine = request.env["merkago.mcp.engine"].sudo()
    base = engine._public_url() or request.httprequest.host_url.rstrip("/")
    meta = "%s/.well-known/oauth-protected-resource" % base
    return 'Bearer realm="mcp", resource_metadata="%s"' % meta


def _get_bearer_token():
    auth = request.httprequest.headers.get("Authorization") or ""
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return (
        request.httprequest.headers.get("X-MCP-Token")
        or request.params.get("token")
        or ""
    )


def _authenticate():
    raw = _get_bearer_token()
    if not raw:
        return request.env["merkago.mcp.token"].browse()
    token = request.env["merkago.mcp.token"].sudo().authenticate(raw)
    if token:
        return token
    oauth = request.env["merkago.mcp.oauth.access"].sudo().authenticate(raw)
    if oauth and oauth.mcp_token_id and oauth.mcp_token_id.active:
        return oauth.mcp_token_id
    return request.env["merkago.mcp.token"].browse()


def _unauthorized():
    return _json_response(
        {"error": "Unauthorized"},
        status=401,
        headers={"WWW-Authenticate": _www_authenticate()},
    )


class MerkagoMcpController(http.Controller):

    @http.route("/mcp/health", type="http", auth="public", methods=["GET"], csrf=False)
    def mcp_health(self, **kwargs):
        engine = request.env["merkago.mcp.engine"].sudo()
        enabled = engine._is_enabled()
        return _json_response(
            {
                "status": "ok" if enabled else "disabled",
                "service": "merkago_mcp_server",
                "version": "17.0.2.0.0",
                "phase": "P2",
                "enabled": enabled,
                "oauth": True,
            }
        )

    @http.route(
        ["/mcp", "/mcp/sse"],
        type="http",
        auth="public",
        methods=["GET", "POST"],
        csrf=False,
    )
    def mcp_sse(self, **kwargs):
        """GET = classic SSE; POST with JSON = Streamable HTTP (Claude Desktop)."""
        token = _authenticate()
        if not token:
            return _unauthorized()
        engine = request.env["merkago.mcp.engine"].sudo()
        if not engine._is_enabled():
            return _json_response({"error": "MCP disabled"}, status=503)

        # Claude / Streamable HTTP posts JSON-RPC directly to the connector URL.
        if request.httprequest.method == "POST":
            raw = (request.httprequest.get_data(as_text=True) or "").strip()
            ctype = (request.httprequest.mimetype or "").lower()
            accept = (request.httprequest.headers.get("Accept") or "").lower()
            looks_json = (
                raw.startswith("{")
                or raw.startswith("[")
                or "application/json" in ctype
                or "application/json" in accept
            )
            if looks_json:
                return self._rpc_http(token, engine, raw)

        base = engine._public_url() or request.httprequest.host_url.rstrip("/")
        messages_url = "%s/mcp/messages" % base

        def generate():
            yield "event: endpoint\ndata: %s\n\n" % messages_url
            yield "event: message\ndata: %s\n\n" % json.dumps(
                {
                    "jsonrpc": "2.0",
                    "method": "notifications/message",
                    "params": {"level": "info", "data": "Merkago MCP P2 ready"},
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
            return _unauthorized()
        engine = request.env["merkago.mcp.engine"].sudo()
        if not engine._is_enabled():
            return _json_response({"error": "MCP disabled"}, status=503)

        raw = request.httprequest.get_data(as_text=True) or "{}"
        return self._rpc_http(token, engine, raw)

    def _rpc_http(self, token, engine, raw):
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            return _json_response({"error": "Invalid JSON"}, status=400)

        if isinstance(payload, list):
            results = [self._handle_rpc(token, engine, item) for item in payload]
            return _json_response(results)

        # JSON-RPC notification (no id): Streamable HTTP expects 202 + empty body
        if isinstance(payload, dict) and "id" not in payload:
            self._handle_rpc(token, engine, payload)
            return Response("", status=202)

        return _json_response(self._handle_rpc(token, engine, payload))

    def _handle_rpc(self, token, engine, payload):
        req_id = payload.get("id")
        method = payload.get("method")
        params = payload.get("params") or {}
        ip = request.httprequest.remote_addr

        try:
            if method in ("initialize", "notifications/initialized"):
                client_version = (params or {}).get("protocolVersion") or "2024-11-05"
                supported = {"2024-11-05", "2025-03-26", "2025-06-18"}
                protocol_version = client_version if client_version in supported else "2024-11-05"
                result = {
                    "protocolVersion": protocol_version,
                    "capabilities": {"tools": {}},
                    "serverInfo": {
                        "name": "merkago_mcp_server",
                        "version": "17.0.2.0.0",
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
                uri = params.get("uri") or ""
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
