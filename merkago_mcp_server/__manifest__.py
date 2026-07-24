# -*- coding: utf-8 -*-
{
    "name": "Merkago MCP Server — Claude Connector",
    "version": "17.0.2.0.0",
    "category": "Productivity",
    "summary": "Connect Claude Desktop to Odoo via native MCP + OAuth",
    "description": """
Merkago MCP Server (Claude Connector)
=====================================

Phase 2 (CDC 2.0): native MCP + OAuth 2.1 / PKCE for Claude Desktop.

* Endpoints /mcp/health, /mcp/sse, /mcp/messages
* OAuth 2.1 + PKCE + Dynamic Client Registration
* Bearer token authentication (legacy)
* Tools: list/describe models, search_read, read, create, write
* Safe Mode, scopes, audit log

Author: AKREM.KHELIFI — merkago.net
""",
    "author": "AKREM.KHELIFI",
    "website": "https://merkago.net",
    "license": "OPL-1",
    "price": 90.00,
    "currency": "USD",
    "images": [
        "static/description/main_screenshot.png",
        "static/description/banner.png",
        "static/description/icon.png",
        "static/description/cl1.png",
        "static/description/cl2.png",
        "static/description/cl3.png",
        "static/description/cl4.png",
        "static/description/cl5.png",
        "static/description/cl6.png",
    ],
    "depends": ["mail", "contacts"],
    "data": [
        "security/mcp_security.xml",
        "security/ir.model.access.csv",
        "data/mcp_scope_data.xml",
        "wizard/mcp_token_wizard_views.xml",
        "views/mcp_scope_views.xml",
        "views/mcp_token_views.xml",
        "views/mcp_audit_views.xml",
        "views/mcp_oauth_views.xml",
        "views/res_config_settings_views.xml",
        "views/menu_views.xml",
    ],
    "installable": True,
    "application": True,
}
