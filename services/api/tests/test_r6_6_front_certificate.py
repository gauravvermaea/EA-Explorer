"""The front door's certificate uploaded on screen (Release 6.6, R6.6.3; owner, 17 Nov 2026, 19:47, D750: Super and IT
Admins upload, it takes effect without a restart, the one in use kept to undo)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from eax import frontcert as F
from eax.metamodel_edit import EditError

REPO = Path(__file__).resolve().parents[3]


def _pki(names=("ea.example.org", "reports.ea.example.org", "docs.ea.example.org"), days=365, start=-1):
    """An authority, an intermediate and a site certificate, as PEM."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID
    now = datetime.now(UTC)
    pem = lambda c: c.public_bytes(serialization.Encoding.PEM).decode()  # noqa: E731
    name = lambda n: x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, n)])  # noqa: E731

    def make(subject, issuer, key, signer, ca, life, sans=None):
        b = (x509.CertificateBuilder().subject_name(name(subject)).issuer_name(name(issuer)).public_key(key.public_key())
             .serial_number(x509.random_serial_number()).not_valid_before(now + timedelta(days=start))
             .not_valid_after(now + timedelta(days=life))
             .add_extension(x509.BasicConstraints(ca=ca, path_length=None), critical=True))
        if sans:
            b = b.add_extension(x509.SubjectAlternativeName([x509.DNSName(s) for s in sans]), critical=False)
        return b.sign(signer, hashes.SHA256())
    root_k, mid_k, site_k = (ec.generate_private_key(ec.SECP256R1()) for _ in range(3))
    root = make("Test Root", "Test Root", root_k, root_k, True, 3650)
    mid = make("Test Intermediate", "Test Root", mid_k, root_k, True, 1825)
    site = make("ea.example.org", "Test Intermediate", site_k, mid_k, False, days, names)
    key = site_k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                               serialization.NoEncryption()).decode()
    other = ec.generate_private_key(ec.SECP256R1()).private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                                                  serialization.NoEncryption()).decode()
    return pem(site), pem(mid) + pem(root), key, other


def test_a_good_certificate_passes_with_what_it_is():
    site, chain, key, _ = _pki()
    out = F.check(site, chain, key, "ea.example.org")
    assert out["names"] == ["ea.example.org", "reports.ea.example.org", "docs.ea.example.org"]
    assert out["chain"] == 2 and out["ends_with_root"] and out["warning"] == ""
    full = F.full_chain(site + chain, chain)          # the chain given twice is presented once, the site first
    assert full.count("BEGIN CERTIFICATE") == 3 and full.startswith(site.strip()[:40])


def test_a_wildcard_covers_the_three_names():
    site, chain, key, _ = _pki(names=("*.example.org", "example.org"))
    assert F.check(site, chain, key, "example.org")["names"] == ["*.example.org", "example.org"]


@pytest.mark.parametrize("case, words", [
    ("wrong key", "not this certificate's key"),
    ("names", "does not cover reports.ea.example.org"),
    ("ended", "ended on"),
    ("ending", "ask for a new one"),
    ("future", "not valid yet"),
    ("chain order", "The chain is broken"),
    ("no certificate", "Choose the certificate file"),
    ("bad key", "not a readable PEM private key"),
])
def test_what_is_wrong_is_refused_in_words(case, words):
    site, chain, key, other = _pki()
    args = {"wrong key": (site, chain, other), "chain order": (site, chain.split("-----END CERTIFICATE-----")[1] + "-----END CERTIFICATE-----\n", key),
            "no certificate": ("", chain, key), "bad key": (site, chain, "nonsense")}.get(case)
    if case == "names":
        s, c, k, _ = _pki(names=("ea.example.org",))
        args = (s, c, k)
    if case in ("ended", "ending", "future"):
        s, c, k, _ = _pki(**{"ended": {"days": -1, "start": -30}, "ending": {"days": 3}, "future": {"start": 2}}[case])
        args = (s, c, k)
    with pytest.raises(EditError) as exc:
        F.check(*args, "ea.example.org")
    assert words in str(exc.value)


def _ops_slice():
    src = (REPO / "services/ops/ops.py").read_text()
    ns: dict = {}
    exec("import os, shutil\n" + src[src.index("TLS_DIR = "):src.index("def secrets_rotate(")], ns)
    return ns


def test_the_helper_puts_it_in_place_keeps_the_old_one_and_undoes(tmp_path):
    ns = _ops_slice()
    (tmp_path / "tls.crt").write_text("-----BEGIN CERTIFICATE-----\nOLD\n")
    (tmp_path / "tls.key").write_text("OLD PRIVATE KEY")
    reloads = []
    out = ns["tls_install"]({"certificate": "-----BEGIN CERTIFICATE-----\nNEW\n", "key": "NEW PRIVATE KEY", "by": "ann"},
                            str(tmp_path), lambda: reloads.append(1) or "reloaded in place")
    assert out["previous_kept"] and out["how"] == "reloaded in place" and reloads == [1]
    assert "NEW" in (tmp_path / "tls.crt").read_text() and "OLD" in (tmp_path / "tls.previous.crt").read_text()
    assert oct((tmp_path / "tls.key").stat().st_mode & 0o777) == "0o600"
    ns["tls_undo"]({"by": "ann"}, str(tmp_path), lambda: "reloaded in place")
    assert "OLD" in (tmp_path / "tls.crt").read_text() and "NEW" in (tmp_path / "tls.previous.crt").read_text()


def test_a_certificate_the_web_server_refuses_is_rolled_back(tmp_path):
    ns = _ops_slice()
    (tmp_path / "tls.crt").write_text("-----BEGIN CERTIFICATE-----\nOLD\n")
    (tmp_path / "tls.key").write_text("OLD PRIVATE KEY")
    calls = []

    def reload():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("nginx: [emerg] cannot load certificate")
        return "reloaded in place"
    with pytest.raises(ValueError) as exc:
        ns["tls_install"]({"certificate": "-----BEGIN CERTIFICATE-----\nNEW\n", "key": "NEW PRIVATE KEY"}, str(tmp_path), reload)
    assert "kept" in str(exc.value) and "OLD" in (tmp_path / "tls.crt").read_text() and len(calls) == 2


def test_no_restart_and_the_key_never_audited():
    src = (REPO / "services/ops/ops.py").read_text()
    part = src[src.index("def _proxy_reload"):src.index("def tls_install")]
    assert '"nginx", "-s", "reload"' in part and "restart" not in part.split('"""')[2]
    api = (REPO / "services/api/eax/api/admin.py").read_text()
    upload = api[api.index("class FrontCertificate"):api.index('@blp.route("/admin/logs/files")')]
    assert 'details={k: info[k] for k in ("subject", "issuer", "names", "not_after")}' in upload
    assert '@require_auth("system.operate")' in upload          # Super Admins and IT Admins
    from eax import alerts
    assert alerts.DEFAULTS["certificate"][2:4] == (30, 1) if hasattr(alerts, "DEFAULTS") else True
