import logging
import os
from contextlib import contextmanager, nullcontext


logger = logging.getLogger(__name__)


class _NullObservation:
    def update(self, **kwargs):
        return None


def _langfuse_enabled():
    return all(
        [
            os.getenv("LANGFUSE_HOST"),
            os.getenv("LANGFUSE_PUBLIC_KEY"),
            os.getenv("LANGFUSE_SECRET_KEY"),
        ]
    )


def _build_langfuse_client():
    from langfuse import get_client

    return get_client()


@contextmanager
def trace_span(name, metadata=None, input_data=None, user_id=None, session_id=None):
    observation = _NullObservation()
    cm = nullcontext(observation)

    if _langfuse_enabled():
        try:
            client = _build_langfuse_client()
            cm = client.start_as_current_observation(name=name, as_type="span")
        except Exception:  # noqa: BLE001
            logger.exception("Failed to initialize Langfuse span", extra={"span_name": name})

    with cm as active_observation:
        observation = active_observation or _NullObservation()
        if not isinstance(observation, _NullObservation):
            try:
                update_payload = {}
                if metadata:
                    update_payload["metadata"] = metadata
                if input_data is not None:
                    update_payload["input"] = input_data
                if user_id is not None:
                    update_payload["user_id"] = user_id
                if session_id is not None:
                    update_payload["session_id"] = session_id
                if update_payload:
                    observation.update(**update_payload)
            except Exception:  # noqa: BLE001
                logger.exception("Failed to update Langfuse span", extra={"span_name": name})
                observation = _NullObservation()
        yield observation
