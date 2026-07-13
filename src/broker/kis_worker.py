"""Compatibility module forwarding to the KIS worker infrastructure adapter."""

import sys

from infrastructure.kis import worker as _worker

sys.modules[__name__] = _worker
