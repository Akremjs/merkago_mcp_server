# Merkago MCP Server — Claude Connector (`merkago_mcp_server`)

Serveur MCP natif dans **Odoo Community** pour **Claude Desktop** uniquement.

## Branches (Apps Odoo)

| Branche | Odoo | URL d’enregistrement Apps |
|---------|------|---------------------------|
| `17.0` | Odoo 17 | `ssh://git@github.com/Akremjs/merkago_mcp_server.git#17.0` |
| `18.0` | Odoo 18 | `ssh://git@github.com/Akremjs/merkago_mcp_server.git#18.0` |
| `19.0` | Odoo 19 | `ssh://git@github.com/Akremjs/merkago_mcp_server.git#19.0` |

Un seul dossier module à la racine du dépôt : `merkago_mcp_server/`

## Phase 1 (socle)

- Endpoints `/mcp/health`, `/mcp/sse`, `/mcp/messages`
- Auth Bearer, Safe Mode, scopes, audit CSV
- Tools : list/describe models, search_read, read, create, write, company_context

## Prix / licence

- **143.00 USD** · **OPL-1**
- Auteur : **AKREM.KHELIFI** — [merkago.net](https://merkago.net)

## Installation (dev)

1. Cloner la branche voulue (`17.0` / `18.0` / `19.0`)
2. Ajouter le parent du dossier `merkago_mcp_server` dans `addons_path`
3. Installer **Merkago MCP Server — Claude Connector**
4. Configurer `dbfilter` si plusieurs bases, générer un token, brancher Claude Desktop sur `/mcp/sse`
