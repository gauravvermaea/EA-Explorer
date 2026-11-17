"""The self-test's checks of certificate mode and password mode (R6-C1; owner, 17 Nov 2026, 21:07: "add UT's for
certificate mode and those can only be tested if we are using certificates and skipped otherwise, same for password
mode and can be skipped otherwise").

Two kinds here:
  * the checks' own logic, with a stand-in database, in both modes (always run);
  * the checks against the real database of the installation these tests run in, marked certificate_mode or
    password_mode: each runs only in its mode (tests/conftest.py) and only when that database answers.
"""

from datetime import UTC, datetime, timedelta

import pytest

from eax.testing import auth_mode as am


class FakeDb:
    """Lets in what a correctly set up database lets in, for the mode given; or everything (broken=True)."""
    def __init__(self, mode: str, broken: bool = False):
        self.mode, self.broken, self.calls = mode, broken, []

    def __call__(self, **kw):
        self.calls.append(kw)
        if self.broken or self._allowed(kw):
            return self
        raise RuntimeError(f'FATAL: no pg_hba.conf entry for user "{kw.get("user")}"')

    def _allowed(self, kw) -> bool:
        if self.mode == "password":
            return kw.get("password") == "right" and not kw.get("sslcert")
        if kw.get("sslmode") == "disable" or not kw.get("sslcert"):
            return False
        cert = kw["sslcert"].rsplit("/", 1)[-1][:-4]
        return {"client": {"eax_app", "eax_migrator", "eax_report"}, "console-it": {"eax_console_it"},
                "console-super": {"eax_console_super"}}.get(cert, set()) >= {kw.get("user")}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql):
        return None


def _make_certs(folder, days=30, ca_days=3650):
    """A small authority and the API's and the SQL window's certificates, as the setup service makes them."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID
    now = datetime.now(UTC)
    ca_key = ec.generate_private_key(ec.SECP256R1())
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "EA Explorer test authority")])
    ca = (x509.CertificateBuilder().subject_name(ca_name).issuer_name(ca_name).public_key(ca_key.public_key())
          .serial_number(1).not_valid_before(now - timedelta(days=1)).not_valid_after(now + timedelta(days=ca_days))
          .sign(ca_key, hashes.SHA256()))
    (folder / "ca.crt").write_bytes(ca.public_bytes(serialization.Encoding.PEM))
    for stem in ("client", "console-it", "console-super"):
        key = ec.generate_private_key(ec.SECP256R1())
        c = (x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, stem)]))
             .issuer_name(ca_name).public_key(key.public_key()).serial_number(x509.random_serial_number())
             .not_valid_before(now - timedelta(days=1)).not_valid_after(now + timedelta(days=days)).sign(ca_key, hashes.SHA256()))
        (folder / f"{stem}.crt").write_bytes(c.public_bytes(serialization.Encoding.PEM))
        (folder / f"{stem}.key").write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                                               serialization.NoEncryption()))


def _results(monkeypatch, tmp_path, mode, db, deployment="laptop", certs=True, days=30, extra_env=None):
    monkeypatch.setenv("EAX_AUTH_MODE", mode)
    monkeypatch.setenv("EAX_DB_PASSWORD", "right")
    monkeypatch.setenv("EAX_DEPLOYMENT", deployment)
    for k, v in (extra_env or {}).items():
        monkeypatch.setenv(k, v)
    if mode == "password":
        monkeypatch.delenv("PGSSLCERT", raising=False)
        monkeypatch.delenv("PGSSLKEY", raising=False)
    folder = tmp_path / "eax-certs"
    folder.mkdir()
    if certs:
        _make_certs(folder, days=days)
    monkeypatch.setattr(am, "CERTS", folder)
    out = {}
    am.run(lambda name, outcome, detail="", ms=0: out.__setitem__(name, (outcome, detail)), connect=db)
    return out


def test_certificate_mode_passes_on_a_correct_database_and_skips_the_password_checks(monkeypatch, tmp_path):
    out = _results(monkeypatch, tmp_path, "certificate", FakeDb("certificate"))
    for name in am.CERTIFICATE_CHECKS:
        assert out[name][0] == "passed", (name, out[name])
    for name in am.PASSWORD_CHECKS:
        assert out[name][0] == "skipped" and "uses certificates" in out[name][1]


def test_certificate_mode_fails_when_the_database_lets_anything_in(monkeypatch, tmp_path):
    out = _results(monkeypatch, tmp_path, "certificate", FakeDb("certificate", broken=True))
    for name in am.CERTIFICATE_CHECKS[2:6]:     # no TLS, a password alone, another login, the superuser
        assert out[name][0] == "failed", name


def test_certificate_mode_fails_without_certificates_or_near_their_end(monkeypatch, tmp_path):
    out = _results(monkeypatch, tmp_path, "certificate", FakeDb("certificate"), certs=False)
    assert out[am.CERTIFICATE_CHECKS[0]][0] == "failed" and "eax up" in out[am.CERTIFICATE_CHECKS[0]][1]
    assert out[am.CERTIFICATE_CHECKS[6]][0] == "failed"
    (tmp_path / "b").mkdir()
    out = _results(monkeypatch, tmp_path / "b", "certificate", FakeDb("certificate"), days=3)
    assert out[am.CERTIFICATE_CHECKS[0]][0] == "failed" and "eax certs renew" in out[am.CERTIFICATE_CHECKS[0]][1]


def test_password_mode_passes_and_skips_the_certificate_checks(monkeypatch, tmp_path):
    out = _results(monkeypatch, tmp_path, "password", FakeDb("password"), certs=False)
    for name in am.PASSWORD_CHECKS[:4]:
        assert out[name][0] == "passed", (name, out[name])
    assert out[am.PASSWORD_CHECKS[4]][0] == "skipped"          # a laptop keeps the default on purpose
    for name in am.CERTIFICATE_CHECKS:
        assert out[name][0] == "skipped" and "uses passwords" in out[name][1]


def test_password_mode_fails_on_a_wrong_password_let_in_certificates_left_or_a_server_on_the_default(monkeypatch, tmp_path):
    out = _results(monkeypatch, tmp_path, "password", FakeDb("password", broken=True), deployment="server", certs=True,
                   extra_env={"EAX_DB_SUPERUSER_PASSWORD": am.LAPTOP_DEFAULT})
    assert out[am.PASSWORD_CHECKS[1]][0] == "failed"           # a wrong password let in
    assert out[am.PASSWORD_CHECKS[2]][0] == "failed"           # certificates still mounted
    assert out[am.PASSWORD_CHECKS[4]] == ("failed", "still the laptop default: EAX_DB_SUPERUSER_PASSWORD (eax secrets rotate)")


def test_the_security_suite_runs_them():
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / "eax" / "testing" / "run.py").read_text()
    assert "auth_mode.run(rec)" in src


# ---------------------------------------------------------------- against the installation's own database, per mode
def _live(mode: str) -> dict:
    out: dict = {}
    am.run(lambda name, outcome, detail="", ms=0: out.__setitem__(name, (outcome, detail)))
    first = am.CERTIFICATE_CHECKS[1] if mode == "certificate" else am.PASSWORD_CHECKS[0]
    if out[first][0] == "failed" and ("connect" in out[first][1].lower() or "timeout" in out[first][1].lower()):
        pytest.skip(f"the installation's database does not answer here: {out[first][1]}")
    return out


@pytest.mark.certificate_mode
def test_live_certificate_mode():
    out = _live("certificate")
    bad = {n: v for n, v in out.items() if n in am.CERTIFICATE_CHECKS and v[0] == "failed"}
    assert not bad, bad


@pytest.mark.password_mode
def test_live_password_mode():
    out = _live("password")
    bad = {n: v for n, v in out.items() if n in am.PASSWORD_CHECKS and v[0] == "failed"}
    assert not bad, bad


# ---------------------------------------------------------------- the certificate checks against a real PostgreSQL
_PG = __import__("pathlib").Path("/usr/lib/postgresql/16/bin")


@pytest.mark.skipif(not (_PG / "initdb").exists() or __import__("os").geteuid() != 0
                    or not __import__("shutil").which("psql"), reason="needs PostgreSQL 16's binaries and root")
def test_the_certificate_checks_pass_on_a_real_database_set_up_as_eax_up_does(monkeypatch):
    """The checks themselves against PostgreSQL 16 started with EA Explorer's own certificate settings
    (deploy/postgres/certificate), so a check that would pass a wrongly set up database is caught here."""
    import os
    import shutil
    import subprocess
    import tempfile
    from pathlib import Path

    from eax import certs as C
    repo = Path(__file__).resolve().parents[3]
    tmp = Path(tempfile.mkdtemp(prefix="eax-r6m-", dir="/tmp"))
    os.chmod(tmp, 0o755)
    root = tmp / "certs"
    C.ensure(root, 30)
    base = tmp / "pg"
    base.mkdir()
    shutil.copy(repo / "deploy/postgres/certificate/pg_hba.conf", base)
    shutil.copy(repo / "deploy/postgres/certificate/pg_ident.conf", base)
    subprocess.run(["chown", "-R", "postgres", str(tmp)], check=True)
    os.chmod(root / "db" / "server.key", 0o600)
    port = "55468"
    su = lambda cmd: subprocess.run(["su", "postgres", "-c", cmd], capture_output=True, text=True)  # noqa: E731
    su(f"{_PG}/initdb -D {base}/data -U postgres")
    opts = (f"-p {port} -k {base} -c listen_addresses=127.0.0.1 -c ssl=on -c ssl_cert_file={root}/db/server.crt "
            f"-c ssl_key_file={root}/db/server.key -c ssl_ca_file={root}/db/ca.crt -c ssl_crl_file={root}/db/crl.pem "
            f"-c hba_file={base}/pg_hba.conf -c ident_file={base}/pg_ident.conf")
    su(f'{_PG}/pg_ctl -D {base}/data -l {base}/log -o "{opts}" -w start')
    try:
        su(f"psql -h {base} -p {port} -U postgres -c \"CREATE ROLE eax_app LOGIN PASSWORD 'app-pw'; CREATE ROLE eax_library LOGIN; "
           f"CREATE ROLE eax_console_it LOGIN; CREATE ROLE eax_console_super LOGIN; ALTER ROLE postgres PASSWORD 'pg-pw'\"")
        mine = tmp / "mine"
        shutil.copytree(root / "api", mine)
        for k in mine.glob("*.key"):
            os.chmod(k, 0o600)
        monkeypatch.setattr(am, "CERTS", mine)
        for k, v in {"EAX_AUTH_MODE": "certificate", "EAX_DB_HOST": "localhost", "EAX_DB_PORT": port, "EAX_DB_NAME": "postgres",
                     "EAX_DB_USER": "eax_app", "EAX_DB_PASSWORD": "app-pw"}.items():
            monkeypatch.setenv(k, v)
        for k in ("PGSSLCERT", "PGSSLKEY", "PGSSLMODE", "PGSSLROOTCERT", "PGPASSWORD", "PGUSER"):
            monkeypatch.delenv(k, raising=False)
        out = {}
        am.run(lambda name, outcome, detail="", ms=0: out.__setitem__(name, (outcome, detail)))
        bad = {n: v for n, v in out.items() if n in am.CERTIFICATE_CHECKS and v[0] != "passed"}
        assert not bad, bad
        assert all(out[n][0] == "skipped" for n in am.PASSWORD_CHECKS)
    finally:
        su(f"{_PG}/pg_ctl -D {base}/data -m immediate stop")
        shutil.rmtree(tmp, ignore_errors=True)
