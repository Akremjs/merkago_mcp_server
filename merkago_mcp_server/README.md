# Claude Connector Odoo (20.0)

Native MCP server for Claude Desktop / Claude.ai with OAuth 2.1 + PKCE.

* Endpoints `/mcp/health`, `/mcp/sse`, `/mcp/messages`
* OAuth 2.1 + PKCE + Dynamic Client Registration
* Tools: list/describe models, search_read, read, create, write
* Safe Mode, scopes, audit log

## Installation (important)

**Do not** use Apps → *Import Module* (zip). That path only loads XML/CSV data —
it never registers Python models, which causes `model_merkago_mcp_*` / `model_id` errors.

Correct install:

1. Unzip and copy `merkago_mcp_server/` into the Odoo addons path (or Odoo.sh git repo)
2. Restart Odoo → Update Apps List → Install **Claude Connector Odoo**
3. Depends: `mail`, `contacts`, `product`

See `INSTALL.txt` at the archive root (French).

Module Odoo **20.0** — adaptations : vues `list`, `res.groups.privilege`, `models.Constraint`.

AKREM.KHELIFI — https://merkago.net · OPL-1 · 88.42 USD
