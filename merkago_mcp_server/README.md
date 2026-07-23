# Merkago MCP Server — Claude Connector (P1)

Native MCP server inside Odoo Community for **Claude Desktop**.

CDC: `/home/almalinux/CDC_merkago_mcp_server.md` (v2.0 parity — this release is **Phase 1**).

## Phase 1 features

- `/mcp/health`, `/mcp/sse`, `/mcp/messages`
- Bearer token auth
- Tools: `odoo_list_models`, `odoo_describe_model`, `odoo_search_read`, `odoo_read`, `odoo_create`, `odoo_write`, `odoo_company_context`
- Safe Mode, scopes, audit log (+ CSV export)
- Settings instructions for Claude Desktop

## Install

1. Add `merkago_mcp_server` to addons path
2. Update Apps list → install **Merkago MCP Server — Claude Connector**
3. Settings → Merkago MCP → set Public Base URL, keep Safe Mode ON
4. Merkago MCP → Generate Token (copy secret once)
5. Claude Desktop → Connectors → custom connector:
   - URL: `https://YOUR-DOMAIN/mcp/sse`
   - Auth header: `Bearer <token>`

## Multi-database (important for Claude)

Claude Desktop has no Odoo session cookie. If several databases exist on the same instance, `/mcp/*` returns **404** until a DB is selected.

Fix: set `dbfilter` in `odoo.conf` so the public Host resolves to one DB, e.g. `dbfilter = ^merkago$`, then restart Odoo. After that, bare `GET /mcp/health` works without a browser session.

## Test (curl)

```bash
# With dbfilter (or after visiting /web?db=YOUR_DB once in the same cookie jar):
curl https://YOUR-DOMAIN/mcp/health
curl -X POST -H "Authorization: Bearer mcp_xxx" -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' \
  https://YOUR-DOMAIN/mcp/messages
```

## Next phases (CDC)

P2 OAuth · P3 Dashboards · P4 ACL UI · P5 CRM · P6 Documents/scrape · P7 Apps polish

## Author

AKREM.KHELIFI — https://merkago.net · OPL-1 · 143 USD
