from odoo.tests.common import HttpCase
from contextlib import contextmanager


class UDESHttpCase(HttpCase):
    """
    Use test cursor for environment
    Include release contextmanager, if opening a URL, use:
    ```
    with self.release():
        return self.url_open(...)
    ```

    Helps when doing authenticate() calls and url_open() as different users.
    """

    def setUp(self):
        super().setUp()

        def restore(cr=self.cr, env=self.env):
            """
            Restore original cursor and environment once changes made with test cursor
            """
            self.env = env
            self.cr = cr

        self.cr = self.registry.cursor()
        self.env = self.env(self.cr)
        self.addCleanup(restore)

    @contextmanager
    def release(self):
        """
        Workaround from print module to temporarily release test cursor
        """
        # Commit so that any changes are visible to external threads
        self.cr.commit()
        # Release thread's cursor lock
        self.cr.release()
        try:
            # Allow external threads to use the cursor
            yield
        finally:
            # Reacquire thread's cursor lock
            self.cr.acquire()
            # Flush cache so that external changes are picked up
            self.env.clear()
