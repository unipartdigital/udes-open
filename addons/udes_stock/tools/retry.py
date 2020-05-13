from functools import wraps
import logging
import time
from psycopg2 import OperationalError, errorcodes

_logger = logging.getLogger(__name__)

PG_CONCURRENCY_ERRORS_TO_RETRY = (
    errorcodes.LOCK_NOT_AVAILABLE,
    errorcodes.SERIALIZATION_FAILURE,
    errorcodes.DEADLOCK_DETECTED,
)


def retry_on_concurrency_error(max_retries=5, delay=1, delay_factor=2):
    """
    Decorator to auto-retry an operation when concurrency errors occur, up to
    max_retries extra times.
    """

    def inner_function(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            return _retry_on_concurrency_error(
                self,
                lambda: func(self, *args, **kwargs),
                max_retries,
                delay,
                delay_factor,
            )

        return wrapper

    return inner_function


def _retry_on_concurrency_error(
    self, f, max_retries=5, delay=1, delay_factor=2
):
    """
    Retries an operation when concurrency errors occur, up to max_retries
    extra times.
    """

    for tries in range(max_retries + 1):
        try:
            with self.env.cr.savepoint(), self.env.clear_upon_failure():
                return f()
        except OperationalError as e:
            if e.pgcode not in PG_CONCURRENCY_ERRORS_TO_RETRY:
                # don't do this
                raise
            if tries >= max_retries:
                _logger.info(
                    "%s, maximum number of tries reached"
                    % errorcodes.lookup(e.pgcode)
                )
                raise

            wait_time = delay * delay_factor ** tries
            _logger.info(
                "%s, retry %d/%d in %.04f sec..."
                % (
                    errorcodes.lookup(e.pgcode),
                    tries + 1,
                    max_retries,
                    wait_time,
                )
            )
            time.sleep(wait_time)
    # unreachable
