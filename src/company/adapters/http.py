"""One opener for every outbound call the company makes.

Adapters read their base URL from the environment, which makes the *scheme* a
runtime value rather than a constant: ``MODEL_API_BASE=file:///etc/passwd``
would otherwise turn a completions call into a local file read, and the result
would land in a checkpoint that gets published to a static site. So every
request goes through :func:`open_https`, which refuses anything but ``https``
before the opener sees the URL.

This is a boundary control, not a lint fix. The company treats everything
outside its own process as untrusted, and the environment it is handed at
start-up is outside its own process.

:class:`SchemeRefused` subclasses ``ValueError`` on purpose: every adapter
already catches ``ValueError`` and degrades, so a misconfigured base URL makes
the company *more cautious* rather than crashing it, and the tier that answered
still says so in the checkpoint.
"""

from __future__ import annotations

import urllib.request
from typing import Any

# https only. Not http (credentials travel in these headers), not file, not
# ftp, not a custom scheme a handler somewhere might claim.
ALLOWED_SCHEMES = frozenset({"https"})


class SchemeRefused(ValueError):
    """The request URL used a scheme this company will not open."""


def open_https(req: urllib.request.Request, timeout: float) -> Any:
    """Open ``req`` if and only if its scheme is allowed.

    ``Request.type`` is the parsed scheme; a URL with no scheme at all raises
    ``ValueError`` from urllib before we get here, which is the same outcome.
    """
    if req.type not in ALLOWED_SCHEMES:
        raise SchemeRefused(f"refusing to open a {req.type!r} URL; allowed: https")
    # Audited: the scheme is checked on the line above, which is the whole
    # point of this function.
    return urllib.request.urlopen(req, timeout=timeout)  # noqa: S310
