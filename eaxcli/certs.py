"""eax certs: certificate mode, EA Explorer's own certificates (R6-C1, R6-R1, R6-D1; D743 to D745).

  eax certs                      every certificate: who issued it, until when, renewed by itself or not
  eax certs renew [--force]      each one that is due (two-thirds of its life gone) made again, the database told
                                 (the schedule runs this every day); --force: every one now
  eax certs renew --authority    a new authority and every certificate with it (about every ten years; alerted months
                                 ahead): the database and the services are made again
  eax certs revoke <service>     a service's certificate refused at once and a new one issued (when a key may have
                                 been copied): api, library, views, keycloak, reports, dms
  eax certs switch certificate|password   change how the services sign in (EAX_AUTH_MODE); then eax restart

The certificates are made on this machine, by the setup service, in the Docker volume eax-certs: never in a backup or a
DR pack (a DR copy makes its own). The authority itself is changed only here, never from the screens (D743)."""

from __future__ import annotations

import json
import re
import subprocess

from .core import EAX, ENV_FILE, ENV_REL, ROOT, Failure, say, setting

SERVICES = ("api", "library", "views", "keycloak", "reports", "dms")


def _in_setup(args: list[str]) -> dict:
    """python -m eax.certs in a short-lived setup container, with eax-certs mounted (it holds the authority)."""
    from .core import compose_args
    p = subprocess.run(compose_args(["run", "--rm", "--no-deps", "-T", "setup", "python", "-m", "eax.certs", *args]),
                       cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    for line in reversed((p.stdout or "").splitlines()):
        if line.strip().startswith("{"):
            try:
                return json.loads(line)
            except ValueError:
                break
    return {"error": (p.stderr or p.stdout or f"exit {p.returncode}").strip()[-500:]}


def _reload_db() -> None:
    """The database reads its own certificate and the revocation list again (no restart, nobody signed out)."""
    from .core import compose_args
    subprocess.run(compose_args(["exec", "-T", "db", "psql", "-q", "-U", "postgres", "-d", "postgres", "-c",
                                 "SELECT pg_reload_conf()"]), cwd=ROOT, capture_output=True, text=True, check=False)


def listing_from(state: dict, values: dict) -> list[dict]:
    """For the operations helper (System Admin › Secrets): the certificates' summary the setup service writes
    (/eax-certs-summary/summary.json, names and dates only); none in password mode."""
    if values.get("EAX_AUTH_MODE", "password") != "certificate":
        return []
    try:
        with open("/eax-certs-summary/summary.json", encoding="utf-8") as f:
            return json.load(f).get("certificates") or []
    except (OSError, ValueError):
        return [{"name": "certificates", "what": "not made yet: they are made at the next eax up", "missing": True,
                 "auto": True, "days_left": None}]


def switch(mode: str) -> None:
    """EAX_AUTH_MODE set in the config file (a dated copy first)."""
    from .secrets import dated_copy
    if mode not in ("certificate", "password"):
        raise Failure(f"{EAX} certs switch certificate|password")
    text = ENV_FILE.read_text(encoding="utf-8")
    dated_copy(text)
    if re.search(r"^EAX_AUTH_MODE=", text, re.MULTILINE):
        text = re.sub(r"^EAX_AUTH_MODE=.*$", f"EAX_AUTH_MODE={mode}", text, flags=re.MULTILINE)
    else:
        text = text.rstrip("\n") + f"\nEAX_AUTH_MODE={mode}\n"
    ENV_FILE.write_text(text, encoding="utf-8", newline="\n")
    say(f"The services will sign in with {'certificates' if mode == 'certificate' else 'passwords'} ({ENV_REL}: "
        f"EAX_AUTH_MODE={mode}). Run {EAX} restart: the certificates are made as it starts; no data changes.")


def main(options: list[str]) -> int:
    """eax certs [list|renew [--force|--authority]|revoke <service>|switch certificate|password]."""
    if not ENV_FILE.exists():
        raise Failure(f"No {ENV_REL} yet: run {EAX} init first.")
    action = options[0] if options else "list"
    rest = options[1:]
    if action == "switch":
        switch(rest[0] if rest else "")
        return 0
    if setting("EAX_AUTH_MODE", "password") != "certificate":
        say(f"The services sign in with passwords: there are no certificates. {EAX} certs switch certificate, then "
            f"{EAX} restart, to use them (R6-C1).")
        return 0
    if action == "list":
        out = _in_setup(["list"])
        if out.get("error"):
            raise Failure(out["error"])
        for c in out.get("certificates", []):
            if c.get("missing"):
                say(f"  {c['name']:<10} not made yet ({EAX} up makes it)")
                continue
            say(f"  {c['name']:<10} until {c['not_after']} ({c['days_left']} days)  issued by {c['issuer']}  "
                f"{'renews by itself' if c['auto'] else 'renewed by a person: eax certs renew --authority'}")
        return 0
    if action == "renew":
        out = _in_setup(["renew-authority"] if "--authority" in rest else (["renew", "--force"] if "--force" in rest else ["renew"]))
        if out.get("error"):
            raise Failure(out["error"])
        if "--authority" in rest:
            from .secretsrot import recreate
            recreate(["db", "api", "library", "views", "keycloak", "reports", "dms", "backup"])
            say("A new authority and every certificate: the database and the services were made again.")
            return 0
        if out.get("renewed"):
            _reload_db()
        say(f"Renewed: {', '.join(out['renewed'])}." if out.get("renewed") else "Every certificate is current.")
        return 0
    if action == "revoke":
        svc = rest[0] if rest else ""
        if svc not in SERVICES:
            raise Failure(f"{EAX} certs revoke <service>: one of {', '.join(SERVICES)}")
        out = _in_setup(["revoke", svc])
        if out.get("error"):
            raise Failure(out["error"])
        _reload_db()
        say(f"{svc}'s certificate (serial {out['serial']}) is refused from now on; a new one was issued and {svc} uses it "
            "from its next connection.")
        return 0
    raise Failure(f"{EAX} certs [list|renew [--force|--authority]|revoke <service>|switch certificate|password]")
