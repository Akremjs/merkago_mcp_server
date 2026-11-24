# -*- coding: utf-8 -*-
{
    "name": "Claude Connector Odoo",
    "version": "17.0.2.0.10",
    "category": "Productivity",
    "summary": "Connectez Claude à Odoo : MCP natif, OAuth et droits par application",
    "description": """
Claude Connector Odoo (Merkago)
================================

Serveur MCP natif dans Odoo pour Claude Desktop et Claude.ai.
OAuth 2.1 + PKCE, Safe Mode, droits par modèle, journal d'audit.

Installation
------------
Copiez le dossier merkago_mcp_server/ dans le chemin addons Odoo
(serveur, Docker ou dépôt Git Odoo.sh). Redémarrez Odoo, mettez à jour
la liste des applications, puis installez « Claude Connector Odoo ».
Le bouton Applications → Importer un module ne charge pas le code Python
de ce connecteur.

Dépendances : mail, contacts, product.

Connexion Claude
----------------
Menu Claude Connector → Connecter Claude.
La checklist vérifie l'URL HTTPS, le serveur MCP, les droits et l'OAuth.
Collez l'URL /mcp/sse dans Claude. Laissez Client ID et Secret vides,
puis autorisez avec un utilisateur interne Odoo.

Droits
------
Quatre boutons en un clic : Contacts, Ventes/CRM, Stock, Comptabilité
(lecture seule ; l'application Odoo doit être installée).
Pour une autre application : Droits (scopes) → Nouveau → choisir le modèle.

Outils
------
Lister, décrire, rechercher, lire, créer, modifier, contexte société.
Chaque outil peut être masqué. Créer et Modifier restent masqués en Safe Mode.

Author: AKREM.KHELIFI — merkago.net
""",
    "author": "AKREM.KHELIFI",
    "website": "https://merkago.net",
    "license": "OPL-1",
    "price": 88.42,
    "currency": "USD",
    # Cover / thumbnail for Odoo Apps (official path)
    "images": [
        "images/main_screenshot.jpg",
        "static/description/cl1.png",
        "static/description/cl2.png",
        "static/description/cl3.png",
        "static/description/cl4.png",
        "static/description/cl5.png",
        "static/description/cl6.png",
    ],
    "depends": ["mail", "contacts", "product"],
    "data": [
        "security/mcp_security.xml",
        "security/ir.model.access.csv",
        "data/mcp_scope_data.xml",
        "wizard/mcp_token_wizard_views.xml",
        "wizard/mcp_connect_wizard_views.xml",
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
