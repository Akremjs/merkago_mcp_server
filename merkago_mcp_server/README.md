# Merkago MCP Server — Claude Connector (P2)

Native MCP server inside Odoo Community for **Claude Desktop**, with **OAuth 2.1 + PKCE**.

## Phase 2 features

- `/mcp/health`, `/mcp/sse`, `/mcp/messages`
- OAuth discovery: `/.well-known/oauth-authorization-server`, `/.well-known/oauth-protected-resource`
- `/oauth/register` (Dynamic Client Registration), `/oauth/authorize`, `/oauth/token`
- Legacy Bearer tokens still supported
- Tools: list/describe models, search_read, read, create, write, company_context
- Safe Mode, scopes, audit log

## Claude Desktop setup

1. Install / upgrade module
2. Set Public Base URL to `https://YOUR-DOMAIN` (Settings → Merkago MCP)
3. Ensure `dbfilter` selects one DB if multi-database
4. Claude → Connectors → Add custom connector
   - URL: `https://YOUR-DOMAIN/mcp/sse`
   - Leave OAuth Client ID / Secret **empty**
5. Sign in with your **Odoo internal user** on the Merkago authorize page

## Test

```bash
curl https://YOUR-DOMAIN/mcp/health
curl https://YOUR-DOMAIN/.well-known/oauth-authorization-server
curl -i https://YOUR-DOMAIN/mcp/sse   # expect 401 + WWW-Authenticate
```

## Next phases (CDC)

P3 Dashboards · P4 ACL UI · P5 CRM · P6 Documents/scrape · P7 Apps polish

## Author

AKREM.KHELIFI — https://merkago.net · OPL-1 · 143 USD
