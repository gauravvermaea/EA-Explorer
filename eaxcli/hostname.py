"""eax hostname: the name people open EA Explorer at, EAX_HOSTNAME in the config file (the owner, 18 Nov 2026, 10:32:
"Add the EAX_HOSTNAME in config"; 10:16: "Do we need to keep that this server is called by the name eaexplorer.com or
something? That can match the name in certificate").

People open https://<name>; Reports is at https://reports.<name> and Documents at https://docs.<name>. The organisation's
certificate must cover all three (System Admin > Secrets > Front door certificate checks it), the three need DNS records
pointing at this machine, and Keycloak signs people in at that name. On a laptop it is localhost. Switching to a DR site
is pointing the name at the other machine: people's bookmarks keep working.

  eax hostname                 the name and the three addresses
  eax hostname set <name>      the name changed (a dated copy of the config file first); then eax restart
"""

from __future__ import annotations

import re

from .core import EAX, ENV_FILE, Failure, say, setting

NAME = re.compile(r"^(?=.{1,253}$)(localhost|([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)+)$")


def valid(name: str) -> str:
    """The name, lower case, or Failure in words (pure)."""
    n = (name or "").strip().lower().rstrip(".")
    if n.startswith(("http://", "https://")) or "/" in n or ":" in n:
        raise Failure("Give the name only, e.g. ea.example.org (no https://, no port, no path).")
    if not NAME.match(n):
        raise Failure(f"{name} is not a host name: letters, digits and hyphens, in parts separated by dots, e.g. ea.example.org.")
    return n


def addresses(name: str) -> list[str]:
    """The three addresses people open (pure)."""
    return [f"https://{name}", f"https://reports.{name}", f"https://docs.{name}"]


def set_name(name: str) -> str:
    """EAX_HOSTNAME written to the config file, a dated copy first."""
    from .secrets import dated_copy, replace_values
    n = valid(name)
    text = ENV_FILE.read_text(encoding="utf-8")
    dated_copy(text)
    out, _ = replace_values(text, {"EAX_HOSTNAME": n})
    if not re.search(r"^EAX_HOSTNAME=", out, re.MULTILINE):
        out = out.rstrip("\n") + f"\n# The name people open EA Explorer at (eax hostname)\nEAX_HOSTNAME={n}\n"
    ENV_FILE.write_text(out, encoding="utf-8", newline="\n")
    return n


def main(argv: list[str]) -> int:
    """eax hostname [show] | set <name>."""
    action = argv[0] if argv else "show"
    if not ENV_FILE.exists():
        raise Failure(f"No config file yet: {EAX} init first.")
    if action == "show":
        n = setting("EAX_HOSTNAME", "localhost")
        say(f"EAX_HOSTNAME={n}: people open " + ", ".join(addresses(n)) + ".")
        if n == "ea.example.org":
            say(f"That is the template's example: {EAX} hostname set <your name>.", "yellow")
        return 0
    if action == "set" and len(argv) > 1:
        n = set_name(argv[1])
        say(f"EAX_HOSTNAME={n}. People will open " + ", ".join(addresses(n)) + ".")
        say(f"Next: DNS records for the three names pointing at this machine; a certificate covering all three (System Admin "
            f"> Secrets > Front door certificate, or {EAX} certs front install); then {EAX} restart.", "yellow")
        return 0
    raise Failure(f"{EAX} hostname [show] | set <name>")
