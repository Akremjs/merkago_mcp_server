# Claude Connector Odoo (20.0)

Serveur MCP natif dans Odoo pour **Claude Desktop** et **Claude.ai** : OAuth 2.1 + PKCE, Safe Mode, droits par application, outils activables.

Module Odoo **20.0** — adaptations : vues `list`, `res.groups.privilege`, `models.Constraint`.

## Installation

Copiez le dossier `merkago_mcp_server/` dans le chemin **addons** Odoo (serveur, Docker ou dépôt Git Odoo.sh).

1. Redémarrez Odoo
2. Mode développeur → Applications → Mettre à jour la liste des applications
3. Installez **Claude Connector Odoo**

Dépendances installées avec le module : `mail`, `contacts`, `product`.

Le bouton Applications → Importer un module ne charge pas le Python de ce connecteur (`model_merkago_mcp_*`). Voir `INSTALL.txt`.

## Après l'installation

1. **Claude Connector → Connecter Claude**
2. Renseignez l'URL publique HTTPS. La checklist indique ce qui manque.
3. **Droits en un clic** : Contacts, Ventes/CRM, Stock, Comptabilité (lecture seule).
4. Autre application : **Droits (scopes) → Nouveau**, choisissez le modèle Odoo.
5. Décochez les outils que Claude ne doit pas voir. Safe Mode masque Créer et Modifier.
6. Copiez l'URL `https://VOTRE-DOMAINE/mcp/sse` dans Claude → Connecteurs. Client ID et Secret vides. Autorisez avec un utilisateur interne.

## Vérification

```bash
curl https://VOTRE-DOMAINE/mcp/health
```

La réponse indique `safe_mode`, la liste `tools` et le nombre de `scopes`.

## Author

AKREM.KHELIFI — https://merkago.net · OPL-1 · 88.42 USD
