"""Certificate mode: EA Explorer's own certificate authority and each service's certificate (R6-C1, R6-R1, R6-T1, R6-D1;
D743 to D745).

With EAX_AUTH_MODE=certificate the services sign in to PostgreSQL with certificates instead of passwords. The setup
service makes them at each start (and `eax certs renew` on a schedule), on this machine, in the Docker volume eax-certs,
which is never in a backup or a DR pack: a DR copy makes its own authority and certificates (R6-D1).

  eax-certs/ca/ca.key, ca.crt          the authority (10 years); its key never leaves this folder
  eax-certs/ca/crl.pem                 the certificates revoked (eax certs revoke)
  eax-certs/<service>/ca.crt           the authority's certificate, to check the database's
  eax-certs/<service>/client.crt, client.key (client.key.pk8 for Keycloak's Java)   a client's certificate, its name the
                                       service's (CN api, keycloak, ...); PostgreSQL maps it to the logins that service
                                       uses (deploy/postgres/certificate/pg_ident.conf), never to postgres
  eax-certs/db/server.crt, server.key  the database server's certificate (names: db, localhost)

Each service sees only its own folder (docker-compose's volume subpath). A key is owned by root and readable by the
service's group only (0640): libpq and PostgreSQL accept that, and a process running as root reads it too.
Certificates last EAX_CERT_DAYS (30) and are renewed when two-thirds of that has passed (R6-T1); the authority is
renewed by `eax certs renew --authority` only (every certificate changes at once), alerted months ahead (R6-R1)."""

from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path

ROOT = Path(os.environ.get("EAX_CERTS_DIR", "/eax-certs"))
CA_DAYS = 3650
DEFAULT_DAYS = 30
# the services that sign in with a certificate: the logins PostgreSQL lets each use (pg_ident.conf), and the group that
# may read its key (root owns it, 0640)
CLIENTS: dict[str, dict] = {
    "api": {"logins": ["eax_app", "eax_migrator", "eax_report"], "gid": 10001,
            "what": "the API, the job runner and the self-test"},
    "library": {"logins": ["eax_library"], "gid": 10002, "what": "the library service"},
    "views": {"logins": ["eax_views"], "gid": 10003, "what": "the drawn views service"},
    "keycloak": {"logins": ["keycloak"], "gid": 0, "what": "Keycloak (sign-in)"},
    "reports": {"logins": ["superset", "eax_report"], "gid": 1000, "what": "Reports (Superset)"},
    "dms": {"logins": ["mayan"], "gid": 1000, "what": "Documents (Mayan EDMS)"},
}
SERVER = {"db": {"gid": 70, "names": ["db", "localhost"], "what": "the database server (PostgreSQL)"}}
# the SQL window's own logins (D742): their certificates beside the API's (it opens the window's connections), as
# api/<name>.crt and .key; IT Admins read, Super Admins read and write; never postgres
CONSOLE = {"console-it": "eax_console_it", "console-super": "eax_console_super"}
# with only the authority's certificate: they reach the database as postgres with its password, over TLS
CA_ONLY = ["backup"]


def _gid(name: str, default: int) -> int:
    v = os.environ.get(f"EAX_CERT_GID_{name.upper()}", "")
    return int(v) if v.isdigit() else default


def _x509():
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
    return x509, hashes, serialization, ec, ExtendedKeyUsageOID, NameOID


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _write(path: Path, data: bytes, mode: int, gid: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".new")
    tmp.write_bytes(data)
    os.chmod(tmp, mode)
    if gid is not None:
        try:
            os.chown(tmp, 0, gid)
        except (PermissionError, OSError):     # tests, not root: the mode still holds
            pass
    os.replace(tmp, path)


def _key():
    _, _, _, ec, _, _ = _x509()
    return ec.generate_private_key(ec.SECP256R1())


def _pem_key(key) -> bytes:
    _, _, serialization, _, _, _ = _x509()
    return key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL,
                             serialization.NoEncryption())


def _der_pk8(key) -> bytes:
    """The key as PKCS#8 DER, which PostgreSQL's Java driver (Keycloak) reads."""
    _, _, serialization, _, _, _ = _x509()
    return key.private_bytes(serialization.Encoding.DER, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())


def load_cert(path: Path):
    """A certificate read from its PEM file."""
    x509 = _x509()[0]
    return x509.load_pem_x509_certificate(path.read_bytes())


def authority(root: Path = ROOT, name: str = "EA Explorer", renew: bool = False) -> tuple:
    """The authority's key and certificate: made once, kept; made again only when asked (every certificate changes)."""
    x509, hashes, serialization, _, _, NameOID = _x509()
    key_p, crt_p = root / "ca" / "ca.key", root / "ca" / "ca.crt"
    if key_p.exists() and crt_p.exists() and not renew:
        key = serialization.load_pem_private_key(key_p.read_bytes(), None)
        return key, load_cert(crt_p)
    key = _key()
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, f"{name} internal authority"),
                         x509.NameAttribute(NameOID.ORGANIZATION_NAME, "EA Explorer")])
    now = _now()
    cert = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - dt.timedelta(minutes=5))
            .not_valid_after(now + dt.timedelta(days=CA_DAYS))
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
            .add_extension(x509.KeyUsage(digital_signature=False, content_commitment=False, key_encipherment=False,
                                         data_encipherment=False, key_agreement=False, key_cert_sign=True, crl_sign=True,
                                         encipher_only=False, decipher_only=False), critical=True)
            .sign(key, hashes.SHA256()))
    _write(key_p, _pem_key(key), 0o600, 0)
    _write(crt_p, cert.public_bytes(serialization.Encoding.PEM), 0o644)
    write_crl(root, key, cert, [])
    return key, cert


def issue(ca_key, ca_cert, cn: str, days: int, server_names: list[str] | None = None) -> tuple:
    """A certificate for a client (its CN the service's name) or the server (its names)."""
    x509, hashes, _, _, EKU, NameOID = _x509()
    key = _key()
    now = _now()
    b = (x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)]))
         .issuer_name(ca_cert.subject).public_key(key.public_key()).serial_number(x509.random_serial_number())
         .not_valid_before(now - dt.timedelta(minutes=5)).not_valid_after(now + dt.timedelta(days=days))
         .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True))
    if server_names:
        b = b.add_extension(x509.SubjectAlternativeName([x509.DNSName(n) for n in server_names]), critical=False)
        b = b.add_extension(x509.ExtendedKeyUsage([EKU.SERVER_AUTH]), critical=False)
    else:
        b = b.add_extension(x509.ExtendedKeyUsage([EKU.CLIENT_AUTH]), critical=False)
    return key, b.sign(ca_key, hashes.SHA256())


def due(path: Path, days: int, now: dt.datetime | None = None) -> bool:
    """A certificate is renewed when two-thirds of its life has passed, or it is missing or unreadable (R6-T1)."""
    try:
        c = load_cert(path)
    except (OSError, ValueError):
        return True
    now = now or _now()
    life = (c.not_valid_after_utc - c.not_valid_before_utc).total_seconds()
    return (now - c.not_valid_before_utc).total_seconds() >= life * 2 / 3 or c.not_valid_after_utc <= now


def _revoked(root: Path) -> list[dict]:
    try:
        return json.loads((root / "ca" / "revoked.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def write_crl(root: Path, ca_key, ca_cert, revoked: list[dict]) -> None:
    """The revocation list PostgreSQL checks (ssl_crl_file), next updated within a day."""
    x509, hashes, serialization, _, _, _ = _x509()
    now = _now()
    b = x509.CertificateRevocationListBuilder().issuer_name(ca_cert.subject).last_update(now).next_update(now + dt.timedelta(days=2))
    for r in revoked:
        b = b.add_revoked_certificate(x509.RevokedCertificateBuilder().serial_number(int(r["serial"]))
                                      .revocation_date(dt.datetime.fromisoformat(r["at"])).build())
    crl = b.sign(ca_key, hashes.SHA256())
    _write(root / "ca" / "crl.pem", crl.public_bytes(serialization.Encoding.PEM), 0o644)
    _write(root / "db" / "crl.pem", crl.public_bytes(serialization.Encoding.PEM), 0o644)


def _place(root: Path, folder: str, ca_cert, key, cert, gid: int, server: bool = False, pk8: bool = False) -> None:
    _, _, serialization, _, _, _ = _x509()
    d = root / folder
    _write(d / "ca.crt", ca_cert.public_bytes(serialization.Encoding.PEM), 0o644)
    stem = "server" if server else "client"
    _write(d / f"{stem}.key", _pem_key(key), 0o640, gid)
    if pk8:
        _write(d / f"{stem}.key.pk8", _der_pk8(key), 0o640, gid)
    _write(d / f"{stem}.crt", cert.public_bytes(serialization.Encoding.PEM), 0o644)


def ensure(root: Path = ROOT, days: int | None = None, force: bool = False, name: str = "EA Explorer") -> list[str]:
    """Every certificate made, or renewed when due (or when forced): the names renewed. The authority is made once."""
    _, _, serialization, _, _, _ = _x509()
    days = days or int(os.environ.get("EAX_CERT_DAYS") or DEFAULT_DAYS)
    ca_key, ca_cert = authority(root, name)
    made = []
    for folder, s in SERVER.items():
        if force or due(root / folder / "server.crt", days):
            k, c = issue(ca_key, ca_cert, folder, days, s["names"])
            _place(root, folder, ca_cert, k, c, _gid(folder, s["gid"]), server=True)
            made.append(folder)
    for folder, s in CLIENTS.items():
        if force or due(root / folder / "client.crt", days):
            k, c = issue(ca_key, ca_cert, folder, days)
            _place(root, folder, ca_cert, k, c, _gid(folder, s["gid"]), pk8=folder == "keycloak")
            made.append(folder)
    for name in CONSOLE:
        if force or due(root / "api" / f"{name}.crt", days):
            k, c = issue(ca_key, ca_cert, name, days)
            _write(root / "api" / f"{name}.key", _pem_key(k), 0o640, _gid("api", CLIENTS["api"]["gid"]))
            _write(root / "api" / f"{name}.crt", c.public_bytes(serialization.Encoding.PEM), 0o644)
            made.append(name)
    for folder in CA_ONLY:
        _write(root / folder / "ca.crt", ca_cert.public_bytes(serialization.Encoding.PEM), 0o644)
    write_crl(root, ca_key, ca_cert, _revoked(root))
    write_summary(root, made)
    return made


def write_summary(root: Path = ROOT, renewed: list[str] | None = None) -> None:
    """summary/summary.json: the certificates' names and dates (never a key), which the operations helper reads for
    System Admin › Secrets and the alerts (it has no cryptography library of its own)."""
    _write(root / "summary" / "summary.json",
           json.dumps({"at": _now().isoformat(), "renewed": renewed or [], "certificates": listing(root)}, indent=1).encode(),
           0o644)


def revoke(service: str, root: Path = ROOT, days: int | None = None) -> dict:
    """A service's certificate revoked at once (PostgreSQL refuses it from its next connection) and a new one issued."""
    if service not in CLIENTS:
        raise ValueError(f"No such service: one of {', '.join(CLIENTS)}")
    cert = load_cert(root / service / "client.crt")
    revoked = _revoked(root) + [{"service": service, "serial": str(cert.serial_number), "at": _now().isoformat()}]
    _write(root / "ca" / "revoked.json", json.dumps(revoked, indent=1).encode(), 0o600, 0)
    ca_key, ca_cert = authority(root)
    days = days or int(os.environ.get("EAX_CERT_DAYS") or DEFAULT_DAYS)
    k, c = issue(ca_key, ca_cert, service, days)
    _place(root, service, ca_cert, k, c, _gid(service, CLIENTS[service]["gid"]), pk8=service == "keycloak")
    write_crl(root, ca_key, ca_cert, revoked)
    return {"revoked": service, "serial": str(cert.serial_number)}


def listing(root: Path = ROOT, now: dt.datetime | None = None) -> list[dict]:
    """Every certificate (never a key): who issued it, until when, days left, renewed by itself or not."""
    now = now or _now()
    out = []
    entries = [("authority", root / "ca" / "ca.crt", "the internal certificate authority (renewed by a person: eax certs "
                                                       "renew --authority)", False)]
    entries += [(f, root / f / "server.crt", s["what"], True) for f, s in SERVER.items()]
    entries += [(f, root / f / "client.crt", s["what"], True) for f, s in CLIENTS.items()]
    for name, path, what, auto in entries:
        try:
            c = load_cert(path)
        except (OSError, ValueError):
            out.append({"name": name, "what": what, "missing": True, "auto": auto, "days_left": None})
            continue
        left = (c.not_valid_after_utc - now).days
        cn = c.issuer.rfc4514_string()
        out.append({"name": name, "what": what, "issuer": cn.replace("CN=", "").split(",")[0],
                    "not_after": c.not_valid_after_utc.strftime("%Y-%m-%d"), "days_left": left, "auto": auto,
                    "due": left <= 0, "warn": next((w for w in (90, 30, 14, 7) if not auto and 0 < left <= w), None),
                    "due_at": c.not_valid_after_utc.strftime("%Y-%m-%d"), "serial": str(c.serial_number)})
    return out


def main(argv: list[str]) -> int:
    """python -m eax.certs ensure|renew [--force]|renew-authority|revoke <service>|list (in the setup image, eax-certs
    mounted at /eax-certs): one JSON line."""
    cmd = argv[0] if argv else "list"
    try:
        if cmd in ("ensure", "renew"):
            out = {"renewed": ensure(force="--force" in argv)}
        elif cmd == "renew-authority":
            authority(ROOT, renew=True)
            out = {"renewed": ensure(force=True), "authority": "renewed: every certificate changed"}
        elif cmd == "revoke" and len(argv) > 1:
            out = revoke(argv[1])
            write_summary(ROOT, [argv[1]])
        elif cmd == "list":
            out = {"certificates": listing()}
        else:
            out = {"error": "python -m eax.certs ensure|renew [--force]|renew-authority|revoke <service>|list"}
    except (OSError, ValueError) as exc:
        out = {"error": str(exc)[:500]}
    print(json.dumps(out, default=str), flush=True)
    return 1 if out.get("error") else 0


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv[1:]))
