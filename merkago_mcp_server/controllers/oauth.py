# -*- coding: utf-8 -*-
import json
import logging
from html import escape
from urllib.parse import urlencode

from odoo import http, _
from odoo.http import request, Response

_logger = logging.getLogger(__name__)


def _json(payload, status=200, headers=None):
    hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)
    return Response(json.dumps(payload, default=str), status=status, headers=hdrs)


def _public_base():
    engine = request.env["merkago.mcp.engine"].sudo()
    return engine._public_url() or request.httprequest.host_url.rstrip("/")


def _auth_metadata():
    base = _public_base()
    return {
        "issuer": base,
        "authorization_endpoint": "%s/oauth/authorize" % base,
        "token_endpoint": "%s/oauth/token" % base,
        "registration_endpoint": "%s/oauth/register" % base,
        "revocation_endpoint": "%s/oauth/revoke" % base,
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["none", "client_secret_post", "client_secret_basic"],
        "scopes_supported": ["mcp", "claudeai", "openid"],
        "service_documentation": "%s/mcp/health" % base,
    }


def _resource_metadata():
    base = _public_base()
    return {
        "resource": "%s/mcp" % base,
        "authorization_servers": [base],
        "bearer_methods_supported": ["header"],
        "scopes_supported": ["mcp"],
        "resource_documentation": "%s/mcp/health" % base,
    }


AUTHORIZE_HTML = """<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Merkago MCP — Autoriser Claude</title>
  <style>
    :root {{ --bg:#0f172a; --card:#1e293b; --text:#f8fafc; --muted:#94a3b8; --accent:#38bdf8; --btn:#0ea5e9; }}
    body {{ margin:0; font-family: ui-sans-serif, system-ui, sans-serif; background:linear-gradient(160deg,#0f172a,#1e3a5f); color:var(--text); min-height:100vh; display:flex; align-items:center; justify-content:center; }}
    .card {{ background:var(--card); width:min(420px,92vw); padding:28px; border-radius:16px; box-shadow:0 20px 50px rgba(0,0,0,.35); }}
    h1 {{ font-size:1.25rem; margin:0 0 6px; }}
    p {{ color:var(--muted); font-size:.95rem; line-height:1.45; }}
    label {{ display:block; margin:14px 0 6px; font-size:.85rem; color:var(--muted); }}
    input {{ width:100%; box-sizing:border-box; padding:10px 12px; border-radius:8px; border:1px solid #334155; background:#0f172a; color:var(--text); }}
    button {{ margin-top:18px; width:100%; padding:12px; border:0; border-radius:8px; background:var(--btn); color:#fff; font-weight:600; cursor:pointer; }}
    .err {{ background:#7f1d1d; color:#fecaca; padding:10px 12px; border-radius:8px; margin-bottom:12px; font-size:.9rem; }}
    .brand {{ color:var(--accent); font-weight:700; letter-spacing:.02em; margin-bottom:8px; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="brand">Merkago MCP</div>
    <h1>Autoriser Claude Desktop</h1>
    <p>Connectez Claude a votre Odoo. Connexion avec un utilisateur interne Odoo.</p>
    {error}
    <form method="post" action="/oauth/authorize">
      <input type="hidden" name="client_id" value="{client_id}"/>
      <input type="hidden" name="redirect_uri" value="{redirect_uri}"/>
      <input type="hidden" name="response_type" value="{response_type}"/>
      <input type="hidden" name="state" value="{state}"/>
      <input type="hidden" name="scope" value="{scope}"/>
      <input type="hidden" name="code_challenge" value="{code_challenge}"/>
      <input type="hidden" name="code_challenge_method" value="{code_challenge_method}"/>
      <label>Login Odoo</label>
      <input name="login" type="text" autocomplete="username" required value="{login}"/>
      <label>Mot de passe</label>
      <input name="password" type="password" autocomplete="current-password" required/>
      <button type="submit">Autoriser Claude</button>
    </form>
  </div>
</body>
</html>
"""


class MerkagoMcpOauthController(http.Controller):

    # ---- Discovery ----
    @http.route(
        [
            "/.well-known/oauth-authorization-server",
            "/.well-known/oauth-authorization-server/mcp",
            "/.well-known/oauth-authorization-server/mcp/sse",
            "/mcp/.well-known/oauth-authorization-server",
        ],
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def oauth_as_metadata(self, **kwargs):
        return _json(_auth_metadata())

    @http.route(
        [
            "/.well-known/oauth-protected-resource",
            "/.well-known/oauth-protected-resource/mcp",
            "/.well-known/oauth-protected-resource/mcp/sse",
            "/mcp/.well-known/oauth-protected-resource",
        ],
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def oauth_rs_metadata(self, **kwargs):
        return _json(_resource_metadata())

    # ---- Dynamic Client Registration ----
    @http.route("/oauth/register", type="http", auth="public", methods=["POST"], csrf=False)
    def oauth_register(self, **kwargs):
        try:
            raw = request.httprequest.get_data(as_text=True) or "{}"
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            return _json({"error": "invalid_client_metadata"}, status=400)
        Client = request.env["merkago.mcp.oauth.client"].sudo()
        result = Client.register_dynamic(payload)
        return _json(result, status=201)

    # ---- Authorize ----
    @http.route("/oauth/authorize", type="http", auth="public", methods=["GET", "POST"], csrf=False)
    def oauth_authorize(self, **kwargs):
        params = {**kwargs}
        if request.httprequest.method == "POST":
            # also merge form
            params.update({k: v for k, v in request.params.items()})

        client_id = params.get("client_id") or ""
        redirect_uri = params.get("redirect_uri") or ""
        response_type = params.get("response_type") or "code"
        state = params.get("state") or ""
        scope = params.get("scope") or "mcp"
        code_challenge = params.get("code_challenge") or ""
        code_challenge_method = params.get("code_challenge_method") or "S256"
        login = params.get("login") or ""
        password = params.get("password") or ""
        error_html = ""

        Client = request.env["merkago.mcp.oauth.client"].sudo()
        client = Client.search([("client_id", "=", client_id), ("active", "=", True)], limit=1)

        def render(err=None):
            err_block = ('<div class="err">%s</div>' % escape(str(err))) if err else ""
            html = AUTHORIZE_HTML.format(
                error=err_block,
                client_id=escape(client_id),
                redirect_uri=escape(redirect_uri),
                response_type=escape(response_type),
                state=escape(state),
                scope=escape(scope),
                code_challenge=escape(code_challenge),
                code_challenge_method=escape(code_challenge_method),
                login=escape(login),
            )
            return Response(html, status=200, mimetype="text/html")

        if not client_id or not redirect_uri or not code_challenge:
            return render(_("Missing OAuth parameters (client_id, redirect_uri, code_challenge)."))
        if response_type != "code":
            return render(_("Only response_type=code is supported."))
        if not client:
            # Auto-provision unknown Claude client (helps when DCR skipped)
            client = Client.create(
                {
                    "name": "Claude (auto)",
                    "client_id": client_id,
                    "redirect_uris": redirect_uri,
                    "dynamic": True,
                    "token_endpoint_auth_method": "none",
                }
            )
        if not client._redirect_allowed(redirect_uri):
            return render(_("redirect_uri not allowed for this client."))

        if request.httprequest.method == "GET":
            # If already logged into Odoo backend session, skip password form
            if request.session.uid:
                user = request.env["res.users"].sudo().browse(request.session.uid)
                if user and user.active and not user.share:
                    return self._finish_authorize(
                        client, user, redirect_uri, code_challenge, code_challenge_method, scope, state
                    )
            return render()

        # POST: authenticate
        db = request.db
        try:
            uid = request.session.authenticate(db, login, password)
        except Exception:
            uid = False
        if not uid:
            return render(_("Login ou mot de passe incorrect."))
        user = request.env["res.users"].sudo().browse(uid)
        if user.share:
            return render(_("Portal users cannot authorize MCP. Use an internal user."))
        return self._finish_authorize(
            client, user, redirect_uri, code_challenge, code_challenge_method, scope, state
        )

    def _finish_authorize(self, client, user, redirect_uri, code_challenge, method, scope, state):
        Code = request.env["merkago.mcp.oauth.code"].sudo()
        raw_code, _rec = Code.create_code(
            client, user, redirect_uri, code_challenge, method=method, scope=scope
        )
        q = {"code": raw_code}
        if state:
            q["state"] = state
        target = "%s?%s" % (redirect_uri, urlencode(q))
        return request.redirect(target, local=False)

    # ---- Token ----
    @http.route("/oauth/token", type="http", auth="public", methods=["POST"], csrf=False)
    def oauth_token(self, **kwargs):
        # support form and JSON
        params = dict(request.params)
        try:
            raw = request.httprequest.get_data(as_text=True) or ""
            if raw and request.httprequest.mimetype == "application/json":
                params.update(json.loads(raw))
        except Exception:
            pass

        grant_type = params.get("grant_type")
        client_id = params.get("client_id") or ""
        client_secret = params.get("client_secret") or ""

        # Basic auth
        auth = request.httprequest.authorization
        if auth and not client_id:
            client_id = auth.username or ""
            client_secret = auth.password or ""

        Client = request.env["merkago.mcp.oauth.client"].sudo()
        client = Client.search([("client_id", "=", client_id), ("active", "=", True)], limit=1)
        if not client or not client.check_secret(client_secret):
            return _json({"error": "invalid_client"}, status=401)

        Access = request.env["merkago.mcp.oauth.access"].sudo()
        try:
            if grant_type == "authorization_code":
                code = params.get("code")
                redirect_uri = params.get("redirect_uri")
                code_verifier = params.get("code_verifier")
                Code = request.env["merkago.mcp.oauth.code"].sudo()
                rec = Code.search([("code", "=", code), ("used", "=", False)], limit=1)
                if not rec or rec.client_id.id != client.id:
                    return _json({"error": "invalid_grant"}, status=400)
                rec.consume(code_verifier, redirect_uri)
                issued = Access.issue(client, rec.user_id, scope=rec.scope or "mcp")
            elif grant_type == "refresh_token":
                refresh = params.get("refresh_token")
                rec = Access.search([("refresh_hash", "=", Access._hash(refresh)), ("active", "=", True)], limit=1)
                if not rec or rec.client_id.id != client.id:
                    return _json({"error": "invalid_grant"}, status=400)
                issued = rec.refresh(refresh)
            else:
                return _json({"error": "unsupported_grant_type"}, status=400)
        except Exception as exc:
            _logger.exception("oauth token error")
            return _json({"error": "invalid_grant", "error_description": str(exc)}, status=400)

        return _json(
            {
                "access_token": issued["access_token"],
                "refresh_token": issued["refresh_token"],
                "token_type": "Bearer",
                "expires_in": issued["expires_in"],
                "scope": issued["scope"],
            }
        )

    @http.route("/oauth/revoke", type="http", auth="public", methods=["POST"], csrf=False)
    def oauth_revoke(self, **kwargs):
        token = request.params.get("token") or ""
        Access = request.env["merkago.mcp.oauth.access"].sudo()
        rec = Access.authenticate(token)
        if rec:
            rec.write({"active": False})
            if rec.mcp_token_id:
                rec.mcp_token_id.write({"active": False})
        return _json({"revoked": True})
