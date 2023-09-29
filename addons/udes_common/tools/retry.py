import time
import logging
from odoo.exceptions import UserError
from psycopg2 import OperationalError, errorcodes

_logger = logging.getLogger(__name__)

PG_CONCURRENCY_ERRORS_TO_RETRY = (
    errorcodes.LOCK_NOT_AVAILABLE,
    errorcodes.SERIALIZATION_FAILURE,
    errorcodes.DEADLOCK_DETECTED,
)


def odoo_retry(self, func, max_tries, raise_usererrors=True):
    """
    Wrapper function for mimicking Odoo's retry behaviour.

    If func has a return value, it must return a dict. This is due to needing to merge
    returns values both from func and from the try count of the wrapper.

    The caller will be responsible for unpacking the dict, and also for calling `self.env.cr.commit()`.
    The caller will also be responsible for handling -1 or > max_tries appropriately.

    Expects to be called like so:
    data = odoo_retry(self, function, max_tries)(function_param1, function_param2)
    If the function has a `self` param, you can pass the information through.

    i.e if the function `do_something(self, picking_type)` is on `stock.picking`, and you wish to call
    it on `pickings = stock.picking(1,2,3)` (so self inside the function resolves to `stock.picking(1,2,3)`)
    you can do:
    data = odoo_retry(self, pickings.do_something, 5)(picking_type)

    Note that `self` is also required to always be passed to `odoo_retry` to scope in the cursor.

    Param: func: function to wrap
    Param: max_tries: int: maximum number of times to retry

    Return: dict(): {"tries": int, ...extra} where extra is what func returns.

    """

    def wrapped_function(*args, **kwargs):
        all_data = {}
        tries = 0
        while True:
            try:
                with self.env.cr.savepoint():
                    func_data = func(*args, **kwargs)
                    all_data.update(func_data)
                    break
            except UserError as e:
                self.invalidate_cache()
                if raise_usererrors:
                    raise e
                tries = -1
                break
            except OperationalError as e:
                self.invalidate_cache()
                if e.pgcode not in PG_CONCURRENCY_ERRORS_TO_RETRY:
                    raise
                if tries >= max_tries:
                    _logger.info(
                        "%s, maximum number of tries reached" % errorcodes.lookup(e.pgcode)
                    )
                    break
                tries += 1
                wait_time = 1
                _logger.info(
                    "%s, retry %d/%d in %.04f sec..."
                    % (
                        errorcodes.lookup(e.pgcode),
                        tries,
                        max_tries,
                        wait_time,
                    )
                )
                time.sleep(wait_time)
        all_data.update({"tries": tries})
        return all_data

    return wrapped_function
