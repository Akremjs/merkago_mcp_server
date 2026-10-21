# Merkago MCP Server — Claude Connector (`merkago_mcp_server`)

Serveur MCP natif dans **Odoo Community** pour **Claude Desktop** (OAuth 2.1 + PKCE).

## Branches (Apps Odoo)

| Branche | Odoo | URL d’enregistrement Apps |
|---------|------|---------------------------|
| `17.0` | Odoo 17 | `ssh://git@github.com/Akremjs/merkago_mcp_server.git#17.0` |
| `18.0` | Odoo 18 | `ssh://git@github.com/Akremjs/merkago_mcp_server.git#18.0` |
| `19.0` | Odoo 19 | `ssh://git@github.com/Akremjs/merkago_mcp_server.git#19.0` |
| `20.0` | Odoo 20 | `ssh://git@github.com/Akremjs/merkago_mcp_server.git#20.0` |

## Phase 2

- MCP `/mcp/health`, `/mcp/sse`, `/mcp/messages`
- OAuth 2.1 + PKCE + Dynamic Client Registration
- Safe Mode, scopes, audit

## Prix / licence

- **88.42 USD** · **OPL-1** (part Odoo Apps incluse)
- Auteur : **AKREM.KHELIFI** — [merkago.net](https://merkago.net)

## Notes Odoo 20

- Vues `list` (ex-`tree`)
- Groupes via `res.groups.privilege`
- Contraintes SQL via `models.Constraint`
