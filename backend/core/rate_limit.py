from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

# Single shared limiter instance — imported by api/index.py (to attach to app)
# and by any router that needs @limiter.limit() decorators.
limiter = Limiter(key_func=get_remote_address)
