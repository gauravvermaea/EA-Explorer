"""The self-test's checks of how the services sign in to the database (Release 6, R6-C1; owner, 17 Nov 2026, 21:07: "add
UT's for certificate mode and those can only be tested if we are using certificates and skipped otherwise, same for
password mode and can be skipped otherwise").

Run in the security suite, from the test runner, which signs in as the API does (in certificate mode it has the API's
certificate folder, read only, and PGSSL* pointing at it). Each check is about one mode: in the other mode it is
recorded as skipped, saying why, so a run always shows every check.

Certificate mode (EAX_AUTH_MODE=certificate):
  the certificates are there, issued by EA Explorer's own authority and not near their end
  the API's login signs in with its certificate and no password
  a connection without TLS is refused
  the API's login with its password but no certificate is refused
  the API's certificate is refused for another service's login, and for the superuser
  the SQL window's two logins sign in with their own certificates

Password mode (EAX_AUTH_MODE=password, every laptop and every installation from before Release 6):
  the API's login signs in with its password
  a wrong password is refused
  no certificate is in use (none mounted, the client library not asked for one)
  the SQL window asks for a database user and password (D752)
  on a server, the passwords are not the laptop's default
"""

from __future__ import annotations

import os
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

Record = Callable[..., None]
CERTS = Path(os.environ.get("EAX_TEST_CERTS_DIR", "/eax-certs"))
LAPTOP_DEFAULT = "P^55w0rd1234&"
OTHER_LOGIN = "eax_library"        # another service's login: the API's certificate must not open it
WARN_DAYS = 7


def mode() -> str:
    """The installation's mode, as the runner was started with it (the config file's EAX_AUTH_MODE)."""
    v = (os.environ.get("EAX_AUTH_MODE") or "password").strip().lower()
    return "certificate" if v == "certificate" else "password"


def _conninfo(**over) -> dict:
    from ..config import get_settings
    s = get_settings()
    out = {"host": s.db_host, "port": s.db_port, "dbname": s.db_name, "user": s.db_user, "connect_timeout": 10}
    out.update({k: v for k, v in over.items() if v is not None})
    return out


def _tls(cert: str | None = None) -> dict:
    """TLS checked against EA Explorer's authority, with a client certificate from the folder (or none)."""
    out = {"sslmode": "verify-full", "sslrootcert": str(CERTS / "ca.crt")}
    if cert:
        out.update(sslcert=str(CERTS / f"{cert}.crt"), sslkey=str(CERTS / f"{cert}.key"))
    else:
        out.update(sslcert="", sslkey="")
    return out


def _try(connect, **kw) -> tuple[bool, str]:
    """Signs in and runs SELECT 1: (worked, why not)."""
    try:
        with connect(**kw) as conn:
            conn.execute("SELECT 1")
        return True, ""
    except Exception as exc:  # noqa: BLE001 - every refusal is an answer here
        return False, str(exc).strip().splitlines()[0][:200] if str(exc).strip() else exc.__class__.__name__


def _connect():
    import psycopg
    return psycopg.connect


def run(record: Record, connect=None, now: datetime | None = None) -> None:
    """Every check of both modes: those of the other mode recorded as skipped."""
    connect = connect or _connect()
    m = mode()
    certificate_checks(record, connect, now) if m == "certificate" else _skip(record, CERTIFICATE_CHECKS, "password")
    password_checks(record, connect) if m == "password" else _skip(record, PASSWORD_CHECKS, "certificate")


CERTIFICATE_CHECKS = (
    "certificate mode: the certificates are there and current",
    "certificate mode: the API signs in with its certificate, no password",
    "certificate mode: a connection without TLS is refused",
    "certificate mode: the API's password without its certificate is refused",
    "certificate mode: the API's certificate is refused for another service's login",
    "certificate mode: the API's certificate is refused for the superuser",
    "certificate mode: the SQL window's logins sign in with their own certificates",
)
PASSWORD_CHECKS = (
    "password mode: the API signs in with its password",
    "password mode: a wrong password is refused",
    "password mode: no certificate is in use",
    "password mode: the SQL window asks for a database user and password",
    "password mode: a server's passwords are not the laptop default",
)


def _skip(record: Record, names: tuple[str, ...], actual: str) -> None:
    why = (f"the installation uses {'certificates' if actual == 'certificate' else 'passwords'} "
           f"(EAX_AUTH_MODE={actual}): checked only in {'password' if actual == 'certificate' else 'certificate'} mode")
    for name in names:
        record(name, "skipped", why, 0)


def _cert_days(path: Path, now: datetime) -> tuple[int, str]:
    from cryptography import x509
    c = x509.load_pem_x509_certificate(path.read_bytes())
    return (c.not_valid_after_utc - now).days, c.issuer.rfc4514_string()


def certificate_checks(record: Record, connect, now: datetime | None = None) -> None:
    """The checks that need certificate mode (see the module's notes)."""
    now = now or datetime.now(UTC)
    n = CERTIFICATE_CHECKS
    missing = [f for f in ("ca.crt", "client.crt", "client.key") if not (CERTS / f).is_file()]
    if missing:
        record(n[0], "failed", f"not in {CERTS}: {', '.join(missing)} (the setup service makes them at eax up)", 0)
    else:
        try:
            days, issuer = _cert_days(CERTS / "client.crt", now)
            ca_days, _ = _cert_days(CERTS / "ca.crt", now)
        except Exception as exc:  # noqa: BLE001 - unreadable: a failure with why
            record(n[0], "failed", f"the certificates could not be read: {exc}", 0)
        else:
            bad = days < WARN_DAYS or ca_days < 60
            record(n[0], "failed" if bad else "passed",
                   f"the API's certificate ends in {days} days, the authority's in {ca_days}; issued by {issuer}"
                   + (" (eax certs renew)" if bad else ""), 0)
    ok, why = _try(connect, **_conninfo(), **_tls("client"))
    record(n[1], "passed" if ok else "failed", "signed in as the API's login with its certificate" if ok else why, 0)
    ok, why = _try(connect, **_conninfo(password=os.environ.get("EAX_DB_PASSWORD") or None), sslmode="disable")
    record(n[2], "failed" if ok else "passed", "a plain connection was let in" if ok else f"refused: {why}", 0)
    ok, why = _try(connect, **_conninfo(password=os.environ.get("EAX_DB_PASSWORD") or "not-the-password"), **_tls(None))
    record(n[3], "failed" if ok else "passed", "a password alone was let in over TLS" if ok else f"refused: {why}", 0)
    ok, why = _try(connect, **_conninfo(user=OTHER_LOGIN), **_tls("client"))
    record(n[4], "failed" if ok else "passed",
           f"the API's certificate opened {OTHER_LOGIN}" if ok else f"refused for {OTHER_LOGIN}: {why}", 0)
    ok, why = _try(connect, **_conninfo(user="postgres"), **_tls("client"))
    record(n[5], "failed" if ok else "passed", "the API's certificate opened the superuser" if ok else f"refused: {why}", 0)
    from .. import sqlconsole
    said, failed = [], False
    for user, _key, cert in sqlconsole.CONSOLE_LOGINS.values():
        if not (CERTS / f"{cert}.crt").is_file():
            said.append(f"{user}: no certificate {cert}.crt")
            failed = True
            continue
        ok, why = _try(connect, **_conninfo(user=user), **_tls(cert))
        said.append(f"{user}: {'signed in' if ok else why}")
        failed = failed or not ok
    record(n[6], "failed" if failed else "passed", "; ".join(said), 0)


def password_checks(record: Record, connect) -> None:
    """The checks that need password mode (see the module's notes)."""
    n = PASSWORD_CHECKS
    pw = os.environ.get("EAX_DB_PASSWORD") or ""
    ok, why = _try(connect, **_conninfo(password=pw or None))
    record(n[0], "passed" if ok else "failed", "signed in as the API's login with its password" if ok else why, 0)
    ok, why = _try(connect, **_conninfo(password=(pw or "x") + "-wrong"))
    record(n[1], "failed" if ok else "passed", "a wrong password was let in" if ok else f"refused: {why}", 0)
    in_use = [x for x in ("PGSSLCERT", "PGSSLKEY") if os.environ.get(x)] + (["/eax-certs"] if CERTS.is_dir() and
                                                                           any(CERTS.glob("*.key")) else [])
    record(n[2], "failed" if in_use else "passed",
           f"certificate settings found in password mode: {', '.join(in_use)}" if in_use else "none mounted, none asked for", 0)
    from .. import sqlconsole
    record(n[3], "passed" if sqlconsole.typed_login() else "failed",
           f"the window starts with {sqlconsole.DEFAULT_USER} and a password to type" if sqlconsole.typed_login()
           else "the window would not ask for a login", 0)
    if (os.environ.get("EAX_DEPLOYMENT") or "laptop").strip().lower() == "laptop":
        record(n[4], "skipped", "a laptop keeps the laptop default on purpose (EAX_DEPLOYMENT=laptop)", 0)
    else:
        same = [k for k in ("EAX_DB_PASSWORD", "EAX_DB_SUPERUSER_PASSWORD", "EAX_DB_MIGRATOR_PASSWORD")
                if os.environ.get(k) == LAPTOP_DEFAULT]
        record(n[4], "failed" if same else "passed",
               f"still the laptop default: {', '.join(same)} (eax secrets rotate)" if same else "none is the laptop default", 0)
