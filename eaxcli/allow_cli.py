"""eax allow (R5.2, D686): the IP allow lists from the machine itself, for when no screen can be reached (a list that
shut someone out). It runs services/ops/allowlist.py in the operations helper's container, which writes nginx's files,
tests them and reloads the proxy:

  eax allow                       the lists (show)
  eax allow clear                 every list emptied: every address may come in again
  eax allow add <place> <address> [name]       places: site, signin, admin, mcp, machine
  eax allow remove <place> <address>
"""

from __future__ import annotations

from .core import Failure, attached, compose_args


def main(rest: list[str]) -> int:
    """eax allow: the IP allow lists from the machine (show, clear, add, remove), through the operations helper."""
    args = rest or ["show"]
    if args[0] not in ("show", "clear", "add", "remove"):
        raise Failure("eax allow [show|clear|add <place> <address> [name]|remove <place> <address>]")
    return attached(compose_args(["exec", "-T", "ops", "python3", "/app/allowlist.py", *args]))
