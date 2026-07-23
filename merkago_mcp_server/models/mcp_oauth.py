# -*- coding: utf-8 -*-
import base64
import hashlib
import secrets
import time
from datetime import timedelta
from urllib.parse import urlparse

from odoo import api, fields, models, _
from odoo.exceptions import UserError


CLAUDE_REDIRECT_ALLOWLIST = (
    "https://claude.ai/api/mcp/auth_callback",
    "https://claude.com/api/mcp/auth_callback",
)


class MerkagoMcpOauthClient(models.Model):
    _name = "merkago.mcp.oauth.client"
    _description = "MCP OAuth Client"
    _order = "id desc"

    name = fields.Char(required=True)
    client_id = fields.Char(required=True, index=True, copy=False)
    client_secret_hash = fields.Char(copy=False)
    client_secret_prefix = fields.Char(readonly=True, copy=False)
    redirect_uris = fields.Text(
        required=True,
        default="\n".join(CLAUDE_REDIRECT_ALLOWLIST),
        help="One redirect URI per line.",
    )
    grant_types = fields.Char(default="authorization_code,refresh_token")
    token_endpoint_auth_method = fields.Char(default="none")
    active = fields.Boolean(default=True)
    dynamic = fields.Boolean(
        string="Dynamically Registered",
        default=False,
        help="Created via RFC 7591 Dynamic Client Registration.",
    )

    _sql_constraints = [
        ("client_id_uniq", "unique(client_id)", "Client ID must be unique."),
    ]

    @api.model
    def _hash_secret(self, secret):
        return hashlib.sha256(secret.encode("utf-8")).hexdigest()

    @api.model
    def _generate_client_id(self):
        return "mcp_cli_%s" % secrets.token_urlsafe(16)

    @api.model
    def _generate_client_secret(self):
        return "mcp_sec_%s" % secrets.token_urlsafe(24)

    def _redirect_uri_list(self):
        self.ensure_one()
        return [u.strip() for u in (self.redirect_uris or "").splitlines() if u.strip()]

    def _redirect_allowed(self, redirect_uri):
        self.ensure_one()
        if not redirect_uri:
            return False
        if redirect_uri in self._redirect_uri_list():
            return True
        if redirect_uri in CLAUDE_REDIRECT_ALLOWLIST:
            return True
        parsed = urlparse(redirect_uri)
        if parsed.scheme == "http" and parsed.hostname in ("127.0.0.1", "localhost"):
            if parsed.path in ("/callback", "/oauth/callback", ""):
                return True
        return False

    def check_secret(self, secret):
        self.ensure_one()
        if not self.client_secret_hash:
            return True  # public client (PKCE)
        if not secret:
            return False
        return self.client_secret_hash == self._hash_secret(secret)

    @api.model
    def register_dynamic(self, payload):
        """RFC 7591 Dynamic Client Registration."""
        redirect_uris = payload.get("redirect_uris") or list(CLAUDE_REDIRECT_ALLOWLIST)
        if isinstance(redirect_uris, str):
            redirect_uris = [redirect_uris]
        name = payload.get("client_name") or "Claude Desktop"
        auth_method = payload.get("token_endpoint_auth_method") or "none"
        client_id = self._generate_client_id()
        vals = {
            "name": name,
            "client_id": client_id,
            "redirect_uris": "\n".join(redirect_uris),
            "grant_types": ",".join(payload.get("grant_types") or ["authorization_code", "refresh_token"]),
            "token_endpoint_auth_method": auth_method,
            "dynamic": True,
        }
        raw_secret = None
        if auth_method not in ("none",):
            raw_secret = self._generate_client_secret()
            vals["client_secret_hash"] = self._hash_secret(raw_secret)
            vals["client_secret_prefix"] = raw_secret[:12]
        client = self.sudo().create(vals)
        result = {
            "client_id": client.client_id,
            "client_name": client.name,
            "redirect_uris": redirect_uris,
            "grant_types": [g.strip() for g in client.grant_types.split(",") if g.strip()],
            "response_types": ["code"],
            "token_endpoint_auth_method": auth_method,
            "client_id_issued_at": int(time.time()),
        }
        if raw_secret:
            result["client_secret"] = raw_secret
        return result


class MerkagoMcpOauthCode(models.Model):
    _name = "merkago.mcp.oauth.code"
    _description = "MCP OAuth Authorization Code"
    _order = "id desc"

    code = fields.Char(required=True, index=True)
    client_id = fields.Many2one("merkago.mcp.oauth.client", required=True, ondelete="cascade")
    user_id = fields.Many2one("res.users", required=True, ondelete="cascade")
    redirect_uri = fields.Char(required=True)
    code_challenge = fields.Char(required=True)
    code_challenge_method = fields.Char(default="S256")
    scope = fields.Char(default="mcp")
    expires_at = fields.Datetime(required=True)
    used = fields.Boolean(default=False)

    @api.model
    def create_code(self, client, user, redirect_uri, code_challenge, method="S256", scope="mcp"):
        raw = secrets.token_urlsafe(32)
        rec = self.sudo().create(
            {
                "code": raw,
                "client_id": client.id,
                "user_id": user.id,
                "redirect_uri": redirect_uri,
                "code_challenge": code_challenge,
                "code_challenge_method": method or "S256",
                "scope": scope or "mcp",
                "expires_at": fields.Datetime.now() + timedelta(minutes=10),
            }
        )
        return raw, rec

    def consume(self, code_verifier, redirect_uri):
        self.ensure_one()
        if self.used:
            raise UserError(_("Authorization code already used."))
        if self.expires_at < fields.Datetime.now():
            raise UserError(_("Authorization code expired."))
        if redirect_uri and redirect_uri != self.redirect_uri:
            raise UserError(_("redirect_uri mismatch."))
        if self.code_challenge_method == "S256":
            digest = hashlib.sha256((code_verifier or "").encode("ascii")).digest()
            computed = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
            if computed != self.code_challenge:
                raise UserError(_("PKCE verification failed."))
        elif self.code_challenge_method == "plain":
            if (code_verifier or "") != self.code_challenge:
                raise UserError(_("PKCE verification failed."))
        else:
            raise UserError(_("Unsupported code_challenge_method."))
        self.sudo().write({"used": True})
        return True


class MerkagoMcpOauthAccess(models.Model):
    _name = "merkago.mcp.oauth.access"
    _description = "MCP OAuth Access Token"
    _order = "id desc"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    client_id = fields.Many2one("merkago.mcp.oauth.client", required=True, ondelete="cascade")
    user_id = fields.Many2one("res.users", required=True, ondelete="cascade")
    token_prefix = fields.Char(readonly=True)
    token_hash = fields.Char(required=True, index=True)
    refresh_hash = fields.Char(index=True)
    scope = fields.Char(default="mcp")
    expires_at = fields.Datetime(required=True)
    mcp_token_id = fields.Many2one("merkago.mcp.token", ondelete="set null")

    @api.model
    def _hash(self, raw):
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @api.model
    def issue(self, client, user, scope="mcp", hours=24):
        access_raw = "mcp_at_%s" % secrets.token_urlsafe(32)
        refresh_raw = "mcp_rt_%s" % secrets.token_urlsafe(32)
        Token = self.env["merkago.mcp.token"].sudo()
        mcp_token = Token.create(
            {
                "name": _("OAuth — %s") % (client.name or "Claude"),
                "user_id": user.id,
                "token_prefix": access_raw[:12],
                "token_hash": Token._hash_token(access_raw),
                "safe_mode": self.env["ir.config_parameter"]
                .sudo()
                .get_param("merkago_mcp.safe_mode", "True")
                == "True",
            }
        )
        # attach all active scopes by default
        scopes = self.env["merkago.mcp.scope"].sudo().search([("active", "=", True)])
        if scopes:
            mcp_token.scope_ids = [(6, 0, scopes.ids)]
        rec = self.sudo().create(
            {
                "name": mcp_token.name,
                "client_id": client.id,
                "user_id": user.id,
                "token_prefix": access_raw[:12],
                "token_hash": self._hash(access_raw),
                "refresh_hash": self._hash(refresh_raw),
                "scope": scope or "mcp",
                "expires_at": fields.Datetime.now() + timedelta(hours=hours),
                "mcp_token_id": mcp_token.id,
            }
        )
        return {
            "access_token": access_raw,
            "refresh_token": refresh_raw,
            "token_type": "Bearer",
            "expires_in": hours * 3600,
            "scope": scope or "mcp",
            "record": rec,
        }

    @api.model
    def authenticate(self, raw_token):
        if not raw_token:
            return self.browse()
        raw_token = raw_token.strip()
        if raw_token.lower().startswith("bearer "):
            raw_token = raw_token[7:].strip()
        rec = self.sudo().search(
            [("token_hash", "=", self._hash(raw_token)), ("active", "=", True)],
            limit=1,
        )
        if not rec:
            return self.browse()
        if rec.expires_at and rec.expires_at < fields.Datetime.now():
            return self.browse()
        return rec

    def refresh(self, refresh_raw):
        self.ensure_one()
        if self.refresh_hash != self._hash(refresh_raw):
            raise UserError(_("Invalid refresh token."))
        # rotate
        return self.issue(self.client_id, self.user_id, scope=self.scope)
