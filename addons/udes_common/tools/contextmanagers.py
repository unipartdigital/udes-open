"""Context managers for UDES."""

import contextlib


@contextlib.contextmanager
def temp_env(env, cursor_factory):
    """
    Preserve pending ORM writes and restore afterwards.

    This is a helper for an Odoo bug where it commits all pending writes even
    when the cursor is not the original env cursor.

    Example usage:

    ```
    from odoo import http
    with temp_env(
        http.request.env, http.request.registry
    ) as tmp_env, tmp_env.cr as temp_cr:
        ...
    ```

    Params:
        env: Environment - the original env that we are "forking"
        cursor_factory - an object with a `cursor()` method that returns a new
                         cursor such as record.pool or http.registry
    """
    # cf https://github.com/unipartdigital/odoo-edi/commit/7bb82cce86a3855bddebb7f3f6d840d1f089b90b
    towrite = env.all.towrite.copy()
    tocompute = env.all.tocompute.copy()
    new_env = env(cr=cursor_factory.cursor())
    new_env.all.towrite.clear()
    new_env.all.tocompute.clear()
    try:
        yield new_env
    finally:
        # Restore the original records to write in the main transcation
        env.all.towrite = towrite
        env.all.tocompute = tocompute
