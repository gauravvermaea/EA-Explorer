"""Opening a web address (Bandit B310, the full test of 24 Nov 2026, D912): urllib's urlopen also opens file:// and other
schemes, so an address read from a setting or a form could read a file of the container. Every address EA Explorer
opens goes through here: http and https only, anything else refused as urllib refuses an unknown one."""

import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urlsplit

SCHEMES = ("http", "https")


def urlopen(req: Any, *args: Any, **kwargs: Any) -> Any:
    """urllib.request.urlopen for an http or https address (a text or a Request); urllib.error.URLError for any other."""
    url = req.full_url if isinstance(req, urllib.request.Request) else str(req)
    scheme = urlsplit(url).scheme.lower()
    if scheme not in SCHEMES:
        raise urllib.error.URLError(f"only http and https addresses are opened, not {scheme or 'one with no scheme'}")
    return urllib.request.urlopen(req, *args, **kwargs)  # nosec B310 - the scheme is checked above
