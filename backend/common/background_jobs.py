import logging
import threading

from django.db import close_old_connections

logger = logging.getLogger(__name__)


def run_background_job(*, name, target, args=(), kwargs=None):
    resolved_kwargs = kwargs or {}

    def _runner():
        close_old_connections()
        try:
            target(*args, **resolved_kwargs)
        except Exception:
            logger.exception("Background job %s failed", name)
        finally:
            close_old_connections()

    thread = threading.Thread(
        target=_runner,
        name=f"finmodpro-{name}",
        daemon=True,
    )
    thread.start()
    return thread
