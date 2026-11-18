"""The front door's certificate, uploaded on screen (Release 6.6, R6.6.3; owner, 16 Nov 2026, 06:40 to 06:50, and 17 Nov
2026, 19:47, D750: "Super or IT Admin, no restart").

A Super Admin or an IT Admin uploads the organisation's certificate, its chain and its key (System Admin › Security ›
Front door certificate). It is checked here before anything changes, and refused in words when wrong:
  * the certificate and the key are PEM, and the key is the certificate's;
  * it covers the names people open: EAX_HOSTNAME, reports.<it> and docs.<it> (a wildcard counts);
  * it is valid now and not ending within a week;
  * each certificate of the chain signed the one before it (the last may be the authority's own, or an intermediate the
    browsers already trust).
Then the operations helper puts it in place (tls.crt with its chain, tls.key), keeps the one in use to undo, checks the
web server takes it and reloads it in place: nobody's session is dropped, nothing restarts. The key is never shown
again, kept in the audit trail or written to a log. Backups carry it as they carry the certificate today.
"""

from __future__ import annotations

from datetime import UTC, datetime

from .metamodel_edit import EditError

MIN_DAYS = 7


def names_needed(hostname: str) -> list[str]:
    """The names the front door answers to (the screens, Reports, Documents)."""
    h = hostname.strip().lower()
    return [h, f"reports.{h}", f"docs.{h}"]


def _covers(pattern: str, name: str) -> bool:
    p = pattern.lower().rstrip(".")
    if p.startswith("*."):
        rest = name.split(".", 1)
        return len(rest) == 2 and rest[1] == p[2:]
    return p == name


def _load(pem: str, what: str):
    from cryptography import x509
    certs = []
    for block in pem.split("-----END CERTIFICATE-----"):
        if "-----BEGIN CERTIFICATE-----" in block:
            try:
                certs.append(x509.load_pem_x509_certificate((block.strip() + "\n-----END CERTIFICATE-----\n").encode()))
            except ValueError as exc:
                raise EditError(f"The {what} is not a readable PEM certificate: {exc}") from exc
    return certs


def check(cert_pem: str, chain_pem: str, key_pem: str, hostname: str, now: datetime | None = None) -> dict:
    """The certificate, its chain and its key checked (see the module's notes): what it is, or EditError saying why not."""
    from cryptography import x509
    from cryptography.hazmat.primitives import serialization
    now = now or datetime.now(UTC)
    certs = _load(cert_pem or "", "certificate")
    if not certs:
        raise EditError("Choose the certificate file (PEM: it starts with -----BEGIN CERTIFICATE-----).")
    leaf, chain = certs[0], certs[1:] + _load(chain_pem or "", "chain")
    try:
        key = serialization.load_pem_private_key((key_pem or "").encode(), password=None)
    except (ValueError, TypeError) as exc:
        raise EditError("The key is not a readable PEM private key without a password (it starts with -----BEGIN ... "
                        "PRIVATE KEY-----).") from exc
    pub = lambda k: k.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)  # noqa: E731
    if pub(key.public_key()) != pub(leaf.public_key()):
        raise EditError("The key is not this certificate's key: choose the key the certificate was made for.")
    try:
        san = leaf.extensions.get_extension_for_class(x509.SubjectAlternativeName).value.get_values_for_type(x509.DNSName)
    except x509.ExtensionNotFound:
        san = []
    missing = [n for n in names_needed(hostname) if not any(_covers(p, n) for p in san)]
    if missing:
        raise EditError(f"The certificate does not cover {', '.join(missing)} (it covers {', '.join(san) or 'no names'}): "
                        "people open EA Explorer, Reports and Documents at these names.")
    if leaf.not_valid_before_utc > now:
        raise EditError(f"The certificate is not valid yet (from {leaf.not_valid_before_utc:%Y-%m-%d}).")
    days = (leaf.not_valid_after_utc - now).days
    if leaf.not_valid_after_utc <= now:
        raise EditError(f"The certificate ended on {leaf.not_valid_after_utc:%Y-%m-%d}.")
    if days < MIN_DAYS:
        raise EditError(f"The certificate ends in {days} days ({leaf.not_valid_after_utc:%Y-%m-%d}): ask for a new one.")
    for child, parent in zip([leaf, *chain[:-1]], chain, strict=True):
        try:
            child.verify_directly_issued_by(parent)
        except Exception as exc:  # noqa: BLE001 - signature, name or kind: the chain is out of order or incomplete
            raise EditError(f"The chain is broken: {parent.subject.rfc4514_string()} did not issue "
                            f"{child.subject.rfc4514_string()} ({exc.__class__.__name__}). Put the certificates in order: "
                            "the site's, then each authority up to the root.") from exc
    last = (chain or [leaf])[-1]
    self_signed = last.issuer == last.subject
    return {"subject": leaf.subject.rfc4514_string(), "issuer": leaf.issuer.rfc4514_string(), "names": san,
            "not_before": leaf.not_valid_before_utc.isoformat(), "not_after": leaf.not_valid_after_utc.isoformat(),
            "days_left": days, "chain": len(chain), "ends_with_root": self_signed,
            "warning": "" if days > 30 else f"it ends in {days} days"}


def full_chain(cert_pem: str, chain_pem: str) -> str:
    """What the web server presents: the site's certificate, then the chain, each block once, in order."""
    out, seen = [], set()
    for pem in (cert_pem or "", chain_pem or ""):
        for block in pem.split("-----END CERTIFICATE-----"):
            if "-----BEGIN CERTIFICATE-----" in block:
                b = block[block.index("-----BEGIN CERTIFICATE-----"):].strip() + "\n-----END CERTIFICATE-----\n"
                if b not in seen:
                    seen.add(b)
                    out.append(b)
    return "".join(out)


def presented(host: str | None = None, port: int = 443) -> dict:
    """The certificate the front door presents now: who issued it, the names, when it ends."""
    import os
    import ssl

    from cryptography import x509
    host = host or os.environ.get("EAX_PROXY_HOST", "proxy")
    try:
        pem = ssl.get_server_certificate((host, port), timeout=10)
    except OSError as exc:
        return {"error": f"the front door did not answer: {exc}"}
    c = x509.load_pem_x509_certificate(pem.encode())
    try:
        san = c.extensions.get_extension_for_class(x509.SubjectAlternativeName).value.get_values_for_type(x509.DNSName)
    except x509.ExtensionNotFound:
        san = []
    end = c.not_valid_after_utc
    return {"subject": c.subject.rfc4514_string(), "issuer": c.issuer.rfc4514_string(), "names": san,
            "not_after": end.isoformat(), "days_left": (end - datetime.now(UTC)).days,
            "self_signed": c.issuer == c.subject}



def main() -> int:
    """`python -m eax.frontcert` (eax certs front install, from the machine): the certificate, chain and key as JSON on
    standard input, checked as the screen's upload is; one JSON line: what it is and the full chain, or the error. The
    key is read here only, never printed."""
    import json
    import sys
    body = json.loads(sys.stdin.read() or "{}")
    try:
        out = check(body.get("certificate", ""), body.get("chain", ""), body.get("key", ""), body.get("hostname", "localhost"))
        out["full_chain"] = full_chain(body.get("certificate", ""), body.get("chain", ""))
    except EditError as exc:
        out = {"error": str(exc)}
    print(json.dumps(out), flush=True)
    return 1 if out.get("error") else 0


if __name__ == "__main__":
    raise SystemExit(main())
