# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class MerkagoMcpConnectWizard(models.TransientModel):
    _name = "merkago.mcp.connect.wizard"
    _description = "Connecter Claude à Odoo"

    status = fields.Selection(
        [
            ("ok", "Prêt"),
            ("warning", "Attention"),
            ("error", "À corriger"),
        ],
        string="Statut",
        compute="_compute_status",
    )
    status_message = fields.Char(string="Message", compute="_compute_status")
    mcp_enabled = fields.Boolean(
        string="Serveur MCP activé",
        default=True,
    )
    mcp_safe_mode = fields.Boolean(
        string="Mode lecture seule (Safe Mode)",
        default=False,
        help="Recommandé : Claude peut lire Odoo mais pas créer ni modifier.",
    )
    public_base_url = fields.Char(
        string="URL publique de votre Odoo",
        help="Ex. https://erp.votre-domaine.com — utilisée par Claude pour se connecter.",
    )
    sse_url = fields.Char(string="URL à coller dans Claude", compute="_compute_urls")
    health_url = fields.Char(string="URL de test", compute="_compute_urls")
    instructions = fields.Text(string="Étapes", compute="_compute_urls")
    test_result = fields.Text(string="Résultat du test", readonly=True)
    checklist = fields.Text(string="Checklist", compute="_compute_status")
    oauth_sessions = fields.Integer(
        string="Connexions OAuth actives",
        compute="_compute_status",
    )
    tool_list = fields.Boolean(string="Lister les modèles", default=True)
    tool_describe = fields.Boolean(string="Décrire un modèle", default=True)
    tool_search = fields.Boolean(string="Rechercher", default=True)
    tool_read = fields.Boolean(string="Lire", default=True)
    tool_create = fields.Boolean(string="Créer", default=True)
    tool_write = fields.Boolean(string="Modifier", default=True)
    tool_company = fields.Boolean(string="Contexte société", default=True)

    _TOOL_FIELDS = {
        "tool_list": "odoo_list_models",
        "tool_describe": "odoo_describe_model",
        "tool_search": "odoo_search_read",
        "tool_read": "odoo_read",
        "tool_create": "odoo_create",
        "tool_write": "odoo_write",
        "tool_company": "odoo_company_context",
    }

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        engine = self.env["merkago.mcp.engine"]
        icp = self.env["ir.config_parameter"].sudo()
        public = (icp.get_param("merkago_mcp.public_base_url") or "").rstrip("/")
        web_base = (icp.get_param("web.base.url") or "").rstrip("/")
        if not public and web_base:
            public = web_base
            icp.set_param("merkago_mcp.public_base_url", public)
        if icp.get_param("merkago_mcp.enabled", "True") != "True":
            # keep user choice if explicitly disabled; otherwise engine defaults to on
            pass
        disabled = engine._disabled_tools()
        res.update(
            {
                "public_base_url": public or web_base,
                "mcp_enabled": engine._is_enabled(),
                "mcp_safe_mode": engine._safe_mode(),
            }
        )
        res.update(
            {
                field: tool not in disabled
                for field, tool in self._TOOL_FIELDS.items()
            }
        )
        return res

    @api.depends("public_base_url")
    def _compute_urls(self):
        for wiz in self:
            base = (wiz.public_base_url or "").rstrip("/")
            wiz.sse_url = "%s/mcp/sse" % base if base else ""
            wiz.health_url = "%s/mcp/health" % base if base else ""
            wiz.instructions = _(
                "1) Copiez l'URL ci-dessus.\n"
                "2) Ouvrez Claude Desktop → Paramètres → Connecteurs → Ajouter un connecteur.\n"
                "3) Collez l'URL. Laissez Client ID et Secret vides.\n"
                "4) Connectez-vous avec votre compte Odoo, puis cliquez sur Autoriser.\n"
                "5) Revenez ici et cliquez sur « Tester la connexion ».\n\n"
                "Méthode recommandée : OAuth (sans token). "
                "Le token Bearer reste disponible en mode avancé (menu Générer un token)."
            )

    @api.depends("public_base_url", "mcp_enabled", "mcp_safe_mode")
    def _compute_status(self):
        OAuth = self.env["merkago.mcp.oauth.access"].sudo()
        for wiz in self:
            base = (wiz.public_base_url or "").rstrip("/")
            sessions = OAuth.search_count([("active", "=", True)])
            wiz.oauth_sessions = sessions
            if not wiz.mcp_enabled:
                wiz.status = "error"
                wiz.status_message = _("Le serveur MCP est désactivé.")
            elif not base:
                wiz.status = "error"
                wiz.status_message = _("Indiquez l'URL publique HTTPS de votre Odoo.")
            elif base.startswith("http://") and "localhost" not in base and "127.0.0.1" not in base:
                wiz.status = "warning"
                wiz.status_message = _(
                    "URL en HTTP : Claude exige souvent HTTPS. Configurez un certificat SSL."
                )
            elif sessions:
                wiz.status = "ok"
                wiz.status_message = _(
                    "Prêt — %(n)s connexion(s) Claude active(s). Safe Mode : %(safe)s."
                ) % {
                    "n": sessions,
                    "safe": _("ON (lecture seule)") if wiz.mcp_safe_mode else _("OFF"),
                }
            else:
                wiz.status = "ok"
                wiz.status_message = _(
                    "Prêt à connecter Claude. Safe Mode : %(safe)s."
                ) % {
                    "safe": _("ON (lecture seule)") if wiz.mcp_safe_mode else _("OFF"),
                }
            scopes = self.env["merkago.mcp.scope"].sudo().search_count([("active", "=", True)])
            https = base.startswith("https://") or "localhost" in base or "127.0.0.1" in base
            lines = [
                _("URL publique : %s") % ("OK" if base else _("manquante")),
                _("HTTPS : %s") % ("OK" if https and base else _("à corriger")),
                _("Serveur MCP : %s") % ("OK" if wiz.mcp_enabled else _("désactivé")),
                _("Scopes actifs : %s") % scopes,
                _("OAuth : OK (Client ID et Secret vides dans Claude)"),
                _("Safe Mode : %s") % (_("ON") if wiz.mcp_safe_mode else _("OFF")),
            ]
            if scopes < 1:
                lines.append(_("→ Activez un pack de droits (Contacts, Ventes, Stock)."))
            wiz.checklist = "\n".join(lines)

    def _save_settings(self):
        self.ensure_one()
        icp = self.env["ir.config_parameter"].sudo()
        base = (self.public_base_url or "").rstrip("/")
        icp.set_param("merkago_mcp.public_base_url", base)
        icp.set_param("merkago_mcp.enabled", "True" if self.mcp_enabled else "False")
        icp.set_param("merkago_mcp.safe_mode", "True" if self.mcp_safe_mode else "False")
        disabled = [
            tool
            for field, tool in self._TOOL_FIELDS.items()
            if not self[field]
        ]
        self.env["merkago.mcp.engine"].set_disabled_tools(disabled)
        return base

    def _apply_pack(self, pack, label):
        self.ensure_one()
        self._save_settings()
        result = self.env["merkago.mcp.scope"].apply_pack(pack)
        skipped = ", ".join(result["skipped"]) if result["skipped"] else _("aucun")
        return self._notify(
            _("%(label)s : %(n)s modèle(s) activé(s). Ignorés (app absente) : %(skip)s")
            % {"label": label, "n": result["activated"], "skip": skipped},
            "success" if result["activated"] else "warning",
            sticky=True,
        )

    def action_pack_contacts(self):
        return self._apply_pack("contacts", _("Contacts"))

    def action_pack_sales(self):
        return self._apply_pack("sales", _("Ventes / CRM"))

    def action_pack_inventory(self):
        return self._apply_pack("inventory", _("Stock / Produits"))

    def action_pack_accounting(self):
        return self._apply_pack("accounting", _("Comptabilité"))

    def action_open_demo_video(self):
        return {
            "type": "ir.actions.act_url",
            "url": "https://www.youtube.com/watch?v=1nYfrDcir1c",
            "target": "new",
        }

    def action_save(self):
        self.ensure_one()
        self._save_settings()
        return self._notify(_("Paramètres enregistrés."), "success")

    def action_show_sse_url(self):
        self.ensure_one()
        self._save_settings()
        if not self.sse_url:
            return self._notify(_("Renseignez d'abord l'URL publique."), "warning")
        return self._notify(
            _("URL à coller dans Claude :\n%s") % self.sse_url,
            "success",
            sticky=True,
            title=_("URL Claude"),
        )

    def action_show_instructions(self):
        self.ensure_one()
        self._save_settings()
        return self._notify(self.instructions or "", "info", sticky=True, title=_("Étapes Claude"))

    def action_test_connection(self):
        self.ensure_one()
        self._save_settings()
        engine = self.env["merkago.mcp.engine"]
        enabled = engine._is_enabled()
        base = engine._public_url()
        module = self.env["ir.module.module"].sudo().search(
            [("name", "=", "merkago_mcp_server")], limit=1
        )
        version = module.latest_version or module.installed_version or ""
        lines = [
            _("Serveur MCP : %s") % (_("activé") if enabled else _("désactivé")),
            _("URL publique : %s") % (base or _("manquante")),
            _("Health : %s/mcp/health") % (base or "—"),
            _("SSE : %s/mcp/sse") % (base or "—"),
            _("Version module : %s") % version,
            _("Safe Mode : %s") % (_("ON") if engine._safe_mode() else _("OFF")),
            _("Connexions OAuth actives : %s") % self.oauth_sessions,
        ]
        if not enabled:
            lines.append(_("→ Activez le serveur MCP puis réessayez."))
        elif not base:
            lines.append(_("→ Indiquez l'URL publique HTTPS."))
        elif base.startswith("http://") and "localhost" not in base:
            lines.append(_("→ Passez en HTTPS pour Claude Desktop / Claude.ai."))
        else:
            lines.append(_("→ Collez l'URL SSE dans Claude (Client ID / Secret vides)."))
        self.test_result = "\n".join(lines)
        return {
            "type": "ir.actions.act_window",
            "name": _("Connecter Claude"),
            "res_model": "merkago.mcp.connect.wizard",
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_open_settings(self):
        self._save_settings()
        return {
            "type": "ir.actions.act_window",
            "name": _("Paramètres Merkago MCP"),
            "res_model": "res.config.settings",
            "view_mode": "form",
            "target": "current",
            "context": {"module": "merkago_mcp_server"},
        }

    def action_open_token_wizard(self):
        self._save_settings()
        return {
            "type": "ir.actions.act_window",
            "name": _("Générer un token (avancé)"),
            "res_model": "merkago.mcp.token.wizard",
            "view_mode": "form",
            "target": "new",
        }

    def _notify(self, message, ntype="success", sticky=False, title=None):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": title or _("Connecter Claude"),
                "message": message,
                "sticky": sticky,
                "type": ntype,
            },
        }
