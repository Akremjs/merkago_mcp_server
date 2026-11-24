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
        default=True,
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
    oauth_sessions = fields.Integer(
        string="Connexions OAuth actives",
        compute="_compute_status",
    )

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
        res.update(
            {
                "public_base_url": public or web_base,
                "mcp_enabled": engine._is_enabled(),
                "mcp_safe_mode": engine._safe_mode(),
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

    def _save_settings(self):
        self.ensure_one()
        icp = self.env["ir.config_parameter"].sudo()
        base = (self.public_base_url or "").rstrip("/")
        icp.set_param("merkago_mcp.public_base_url", base)
        icp.set_param("merkago_mcp.enabled", "True" if self.mcp_enabled else "False")
        # Boolean ICP: store True explicitly; delete/False for off so engine default works
        if self.mcp_safe_mode:
            icp.set_param("merkago_mcp.safe_mode", "True")
        else:
            param = icp.search([("key", "=", "merkago_mcp.safe_mode")], limit=1)
            if param:
                param.unlink()
            else:
                icp.set_param("merkago_mcp.safe_mode", "False")
        return base

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
