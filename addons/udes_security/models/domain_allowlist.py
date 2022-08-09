from odoo import models, fields, api, service, _
import re
import ast
from werkzeug import urls

WILDCARD_PART_CHECK = re.compile("[\*|\?|\]](?!\.)")
WILDCARD_ENDING_CHECK = re.compile("\*$")


class DomainAllowlist(models.Model):
    _name = "udes_security.domain.allowlist"
    _description = "List of allowed domains"

    name = fields.Char(required=True)
    domain = fields.Char(required=True)
    active = fields.Boolean(default=True)

    def _get_host(self):
        return urls.url_parse(self.env["ir.config_parameter"].sudo().get_param("web.base.url")).host

    @api.model
    def _setup_default_domains(self):
        allowlist = list(
            ast.literal_eval(service.server.config.get_misc("udes", "domain_allowlist", "[]"))
        )
        # Get host url
        allowlist.append(self._get_host())

        already_in_list = self.search([]).mapped("domain")
        for allowed_domain in allowlist:
            if allowed_domain not in already_in_list:
                self.create(
                    {
                        "name": _("Default: %s") % allowed_domain,
                        "domain": allowed_domain,
                        "active": True,
                    }
                )

    @api.model_create_multi
    def create(self, vals_list):
        """Extend create to massage domain if someone gives a url"""
        for values in vals_list:
            domain = values.get("domain")
            if domain:
                parsed_domain = urls.url_parse(domain)
                # Note: if domain is just the domain then it will appear in path not netloc
                values["domain"] = parsed_domain.netloc or parsed_domain.path
        return super().create(vals_list)

    def write(self, values):
        """Extend write to massage domain if someone gives a url"""
        domain = values.get("domain")
        if domain:
            parsed_domain = urls.url_parse(domain)
            # Note: if domain is just the domain then it will appear in path not netloc
            values["domain"] = parsed_domain.netloc or parsed_domain.path
        super().write(values)

    @api.onchange("domain")
    def warning_for_risky_wildcards(self):
        """Warn about risky wildcards
        Examples:
         *wholesome.domain would match with "notwholesome.domain"
         wholesome.* would match with "wholesome.notreally"

        Note: this is only `onchange` so doesn't contrain the value
        """
        if self.domain and (WILDCARD_PART_CHECK.search(self.domain) or WILDCARD_ENDING_CHECK.search(self.domain)):
            msg = "\n".join(
                [
                    "%s contains a potentially risky wildcard",
                    "Examples of risky wildcards:",
                    "     *wholesome.com would match with notwholesome.com",
                    "     wholesome.* would match with wholesome.notreally.com",
                ]
            )
            return {
                "warning": {
                    "title": _("Potentially risky wildcard"),
                    "message": _(msg) % self.domain,
                }
            }
