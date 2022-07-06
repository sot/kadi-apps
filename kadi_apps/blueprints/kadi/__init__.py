from .kadi import blueprint  # noqa

from .kadi import EVENT_MODELS


def _init_():
    from kadi_apps.rendering import CONTEXT
    CONTEXT['event_models'] = EVENT_MODELS


_init_()
