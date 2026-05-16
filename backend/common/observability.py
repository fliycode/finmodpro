import logging
from contextlib import contextmanager, nullcontext


logger = logging.getLogger(__name__)


class _NullObservation:
    def update(self, **kwargs):
        return None


@contextmanager
def trace_span(name, metadata=None, input_data=None, user_id=None, session_id=None):
    observation = _NullObservation()
    with nullcontext(observation):
        yield observation
