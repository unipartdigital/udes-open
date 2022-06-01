from odoo import models

class ResUsers(models.Model):
    _inherit = "res.users"

    def _is_superuser_or_admin(self):
        """
        Return True if user is active user superuser or admin, otherwise False.

        Note: Admin here means the admin user that Odoo creates by default,
              not just any user with permission to edit settings.
        """
        if not self and self.env.su:
            return True
        
        if self._is_superuser():
            return True

        try:
            if self.env.uid == self.env.ref("base.user_admin").id:
                return True
        except ValueError:
            # Admin user has been deleted
            pass

        return False
