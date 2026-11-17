"""R6-C1 (owner, 17 Nov 2026, 18:39 to 18:47; D743): certificate mode with EA Explorer's own certificate authority. Each
service signs in to PostgreSQL with its own certificate, only for its own logins, never as postgres; a revoked one is
refused at once; certificates renew at two-thirds of their life; the authority stays on the machine (never in a backup)."""
from __future__ import annotations

import datetime as dt
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

import pytest

from eax import certs as C

REPO = Path(__file__).resolve().parents[3]
PG = Path("/usr/lib/postgresql/16/bin")


def test_every_certificate_is_made_once_and_renewed_only_when_due(tmp_path):
    made = C.ensure(tmp_path, 30)
    assert set(made) == {"db", *C.CLIENTS, *C.CONSOLE}
    assert (tmp_path / "api" / "console-it.key").exists() and (tmp_path / "api" / "console-super.crt").exists()
    assert C.ensure(tmp_path, 30) == []                                   # current: nothing again
    for f in C.CLIENTS:
        assert (tmp_path / f / "client.key").stat().st_mode & 0o777 == 0o640
        assert not (tmp_path / f / "ca.key").exists()                      # the authority's key only in ca/
    assert (tmp_path / "keycloak" / "client.key.pk8").exists() and not (tmp_path / "api" / "client.key.pk8").exists()
    assert (tmp_path / "backup" / "ca.crt").exists() and not (tmp_path / "backup" / "client.key").exists()
    later = dt.datetime.now(dt.UTC) + dt.timedelta(days=21)
    assert C.due(tmp_path / "api" / "client.crt", 30, later) and not C.due(tmp_path / "api" / "client.crt", 30)
    rows = {r["name"]: r for r in C.listing(tmp_path)}
    assert rows["authority"]["auto"] is False and rows["api"]["auto"] and 28 <= rows["api"]["days_left"] <= 30
    assert (tmp_path / "summary" / "summary.json").exists()


def test_the_database_maps_each_certificate_to_its_own_logins_and_never_postgres():
    ident = (REPO / "deploy/postgres/certificate/pg_ident.conf").read_text()
    pairs = {(m.group(1), m.group(2)) for m in re.finditer(r"^eax\s+(\S+)\s+(\S+)", ident, re.M)}
    assert pairs == {(svc, login) for svc, s in C.CLIENTS.items() for login in s["logins"]} | set(C.CONSOLE.items())
    assert not any(login == "postgres" for _, login in pairs)
    hba = [ln.split() for ln in (REPO / "deploy/postgres/certificate/pg_hba.conf").read_text().splitlines()
           if ln.strip() and not ln.startswith("#")]
    assert all(r[0] in ("local", "hostssl") for r in hba)                  # no plain connection over the network
    assert ["hostssl", "all", "all", "samenet", "cert", "map=eax"] in hba
    assert all(r[-1] != "trust" for r in hba if r[0] != "local")


def test_eax_adds_the_certificate_file_in_every_form():
    assert "deploy/compose/auth/docker-compose.certificate.yml" in (REPO / "eaxcli/core.py").read_text()
    assert "deploy/compose/auth/docker-compose.certificate.yml" in (REPO / "eax.ps1").read_text()
    assert "deploy/compose/auth/docker-compose.certificate.yml" in (REPO / "eax.sh").read_text()
    over = (REPO / "deploy/compose/auth/docker-compose.certificate.yml").read_text()
    for svc in ("api", "library", "views", "keycloak", "reports", "dms", "db", "backup"):
        assert f"subpath: {svc}" in over, svc                              # each sees only its own folder


def test_the_authority_is_never_backed_up():
    ops = (REPO / "services/ops/ops.py").read_text()
    assert '"eax-certs":' in ops.split("NOT_NEEDED = {")[1].split("}")[0]


@pytest.mark.skipif(not (PG / "initdb").exists() or os.geteuid() != 0 or not shutil.which("psql"),
                    reason="needs PostgreSQL 16's binaries and root (to run them as postgres)")
def test_a_real_database_accepts_and_refuses_as_designed():
    """The owner, 17 Nov 2026, 18:34: "what happens if someone steals certificate ...": its own logins only, never
    postgres; no plain connection; a revoked certificate refused at once."""
    import tempfile
    tmp_path = Path(tempfile.mkdtemp(prefix="eax-r6-", dir="/tmp"))      # reachable by the postgres user
    os.chmod(tmp_path, 0o755)
    root = tmp_path / "certs"
    C.ensure(root, 30)
    base = tmp_path / "pg"
    base.mkdir()
    shutil.copy(REPO / "deploy/postgres/certificate/pg_hba.conf", base)
    shutil.copy(REPO / "deploy/postgres/certificate/pg_ident.conf", base)
    subprocess.run(["chown", "-R", "postgres", str(tmp_path)], check=True)
    os.chmod(root / "db" / "server.key", 0o600)
    port = "55466"
    su = lambda cmd: subprocess.run(["su", "postgres", "-c", cmd], capture_output=True, text=True)  # noqa: E731
    su(f"{PG}/initdb -D {base}/data -U postgres")
    opts = (f"-p {port} -k {base} -c listen_addresses=127.0.0.1 -c ssl=on -c ssl_cert_file={root}/db/server.crt "
            f"-c ssl_key_file={root}/db/server.key -c ssl_ca_file={root}/db/ca.crt -c ssl_crl_file={root}/db/crl.pem "
            f"-c hba_file={base}/pg_hba.conf -c ident_file={base}/pg_ident.conf")
    su(f'{PG}/pg_ctl -D {base}/data -l {base}/log -o "{opts}" -w start')
    try:
        su(f"psql -h {base} -p {port} -U postgres -c \"CREATE ROLE eax_app LOGIN; CREATE ROLE mayan LOGIN; "
           f"ALTER ROLE postgres PASSWORD 'pw-of-postgres'\"")
        mine = tmp_path / "mine"
        shutil.copytree(root / "api", mine)
        os.chmod(mine / "client.key", 0o600)

        def who(user, cert=True, mode="verify-full", password=""):
            env = {**os.environ, "PGUSER": user, "PGSSLMODE": mode, "PGSSLROOTCERT": str(root / "api" / "ca.crt"),
                   "PGSSLCERT": str(mine / "client.crt") if cert else "/none", "PGSSLKEY": str(mine / "client.key") if cert else "/none",
                   "PGPASSWORD": password}
            r = subprocess.run(["psql", f"host=localhost port={port} dbname=postgres", "-tAc", "select current_user"],
                               env=env, capture_output=True, text=True)
            return r.stdout.strip() if r.returncode == 0 else "refused"
        assert who("eax_app") == "eax_app"
        assert who("mayan") == "refused"                                # not its login
        assert who("postgres", password="wrong") == "refused"           # never the superuser by certificate
        assert who("eax_app", cert=False) == "refused"
        assert who("postgres", cert=False, password="pw-of-postgres") == "postgres"   # the superuser: password, over TLS
        assert who("postgres", cert=False, mode="disable", password="pw-of-postgres") == "refused"   # no plain
        C.revoke("api", root)
        subprocess.run(["chown", "-R", "postgres", str(root)], check=True)
        su(f"psql -h {base} -p {port} -U postgres -c 'select pg_reload_conf()'")
        time.sleep(1)
        assert who("eax_app") == "refused"                              # the copied, revoked one
    finally:
        su(f"{PG}/pg_ctl -D {base}/data -m immediate stop")
        shutil.rmtree(tmp_path, ignore_errors=True)
