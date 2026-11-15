"""IP allow-listing, the API's side (R5.2, D686): checks a change before the operations helper writes it for nginx.

The lists themselves, nginx's files and the reload are the operations helper's (services/ops/allowlist.py); here:
  * every entry is an address or a range (IPv4 or IPv6, CIDR), each place one of PLACES;
  * **never a lock-out**: a change that would refuse the address of the person making it, on the site, the sign-in
    pages or System Admin, is refused (they would lose the screen they are on); 127.0.0.0/8, ::1 and the
    installation's own Docker networks are always allowed (the operations helper adds them to every list);
  * a machine credential may be limited to its own addresses (allowed_addresses, checked at every call).
"""

from __future__ import annotations

import ipaddress

PLACES = ("site", "signin", "admin", "mcp", "machine")
ALWAYS = ("127.0.0.0/8", "::1/128")
# the places a person signed in to the screens needs, to stay on the screen they are changing this from
SCREEN_PLACES = ("site", "signin", "admin")


class Refused(Exception):
    """An allow-list change refused (a bad address, or one that would lock out its maker)."""
    pass


def network(raw: str) -> ipaddress.IPv4Network | ipaddress.IPv6Network:
    """An address or range as a network, refused when it is not one."""
    try:
        return ipaddress.ip_network(str(raw).strip(), strict=False)
    except ValueError as exc:
        raise Refused(f"{raw or '(empty)'} is not an address or a range (for example 10.1.2.3 or 10.1.0.0/16).") from exc


def clean(body: dict) -> dict:
    """The allow lists checked: known places only, every address a valid one, ranges written in their plain form."""
    lists = {}
    for place, entries in (body.get("lists") or {}).items():
        if place not in PLACES:
            raise Refused(f"No place called {place}: {', '.join(PLACES)}.")
        out = []
        for e in entries or []:
            e = e if isinstance(e, dict) else {"address": e}
            out.append({"address": str(network(e.get("address"))), "name": str(e.get("name") or "")[:80],
                        "why": str(e.get("why") or "")[:200]})
        lists[place] = out
    trusted = []
    for e in body.get("trusted") or []:
        e = e if isinstance(e, dict) else {"address": e}
        trusted.append({"address": str(network(e.get("address"))), "name": str(e.get("name") or "")[:80], "why": ""})
    return {"lists": {p: lists.get(p, []) for p in PLACES}, "trusted": trusted}


def _in(ip, nets) -> bool:
    return any(ip.version == n.version and ip in n for n in nets)


def allowed(lists: dict, place: str, address: str, internal=()) -> bool:
    """Whether an address may reach a place: the site's list (not for the client-certificate port, which has its own)
    and the place's own; an empty list lets everyone in."""
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return True                      # an address we cannot read is not ours to judge (nginx decides)
    if _in(ip, [ipaddress.ip_network(n) for n in (*ALWAYS, *internal)]):
        return True
    for p in ({place} if place == "machine" else {"site", place}):
        entries = lists.get(p) or []
        if entries and not _in(ip, [network(e["address"]) for e in entries]):
            return False
    return True


def guard(lists: dict, address: str, internal=()) -> None:
    """Refuse a change that would lock out the person making it."""
    for place in SCREEN_PLACES:
        if not allowed(lists, place, address, internal):
            raise Refused(f"This would refuse your own address ({address}) on {place}: add it (or its range) first. "
                          "Nothing was changed.")


def credential_allows(addresses, address: str) -> bool:
    """A machine credential limited to its own addresses (empty: any)."""
    if not addresses:
        return True
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return False
    return _in(ip, [network(a) for a in addresses])
