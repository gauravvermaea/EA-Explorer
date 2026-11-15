"""eax ticket (R5.11, D692): the service desk's requests from the command line, for admins. It runs
eax/servicedesk.py in the api container:

  eax ticket [list [open|all|<status>]]     the requests (every team's), overdue said
  eax ticket show REQ-12                    one request, its details and its history
  eax ticket comment REQ-12 <text>          a comment (as "eax")
  eax ticket status REQ-12 <status> [note]  in-progress, waiting-requester, done or declined
"""

from __future__ import annotations

from .core import Failure, attached, compose_args


def main(rest: list[str]) -> int:
    """eax ticket: the service desk's requests in the api container."""
    args = rest or ["list"]
    if args[0] not in ("list", "show", "comment", "status"):
        raise Failure("eax ticket list | show REQ-n | comment REQ-n <text> | status REQ-n <status> [note]")
    return attached(compose_args(["exec", "-T", "api", "python", "-m", "eax.servicedesk", *args]))
