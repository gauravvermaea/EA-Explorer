"""R6-F1 (owner, 17 Nov 2026, 18:52: "Yes, both modes"; D745): every password and key reaches the containers as a file
of its own under /run/secrets (Docker secrets), never as an environment variable, so docker inspect shows none; the
containers read work/config.env, the config file without them."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

API = Path(__file__).resolve().parents[1]
REPO = API.parents[1]
sys.path.insert(0, str(REPO))

from eaxcli import core  # noqa: E402

COMPOSE = (REPO / "docker-compose.yml").read_text(encoding="utf-8")
KEYS = core.secret_keys()


def test_no_secret_is_put_into_a_containers_environment():
    """No ${EAX_<secret>} anywhere in the compose files: a value interpolated there is in docker inspect."""
    for f in [REPO / "docker-compose.yml", *(REPO / "deploy" / "compose").rglob("*.yml")]:
        text = f.read_text(encoding="utf-8")
        for k in KEYS:
            assert not re.search(r"\$\{" + k + r"[:}]", text), (f.name, k)
    assert "env_file: work/eaexplorer.env" not in COMPOSE and "env_file: work/config.env" in COMPOSE


def test_every_secret_is_declared_and_every_service_names_only_declared_ones():
    data = yaml.safe_load(COMPOSE)
    declared = set(data["secrets"])
    assert set(KEYS) - {"EAX_REPLICATION_PASSWORD"} <= declared            # the standby's own file declares that one
    assert all(v == {"environment": k} for k, v in data["secrets"].items())
    for name, svc in data["services"].items():
        for s in svc.get("secrets", []):
            assert s in declared, (name, s)
    assert data["services"]["dms-broker"]["secrets"] == ["EAX_DMS_BROKER_PASSWORD"]          # each only its own
    assert "EAX_DB_SUPERUSER_PASSWORD" not in data["services"]["keycloak"]["secrets"]
    assert data["services"]["db"]["environment"]["POSTGRES_PASSWORD_FILE"] == "/run/secrets/EAX_DB_SUPERUSER_PASSWORD"


def test_the_three_forms_strip_the_same_keys():
    """eaxcli, eax.ps1 and eax.sh write work/config.env without the same keys (D331)."""
    ps = (REPO / "eax.ps1").read_text(encoding="utf-8")
    sh = (REPO / "eax.sh").read_text(encoding="utf-8")
    for k in core.EXTRA_SECRET_KEYS:
        assert f'"{k}"' in ps.split("function Write-ServiceEnv")[1].split("\n}\n")[0], k
        assert k in sh.split("service_env() {")[1].split("\n}\n")[0], k
    text = "A=1\nEAX_DB_PASSWORD=x\n# EAX_DB_PASSWORD=comment kept\nEAX_SMTP_PASSWORD=y\nEAX_HOSTNAME=h\n"
    out = core.config_without_secrets(text, KEYS)
    assert "EAX_DB_PASSWORD=x" not in out and "EAX_SMTP_PASSWORD" not in out and "EAX_HOSTNAME=h" in out and "A=1" in out


def test_the_python_services_read_the_files_into_their_own_process(tmp_path):
    from eax import secretfiles
    (tmp_path / "EAX_DB_PASSWORD").write_text("from-file\n")
    (tmp_path / "EAX_OPS_TOKEN").write_text("")
    (tmp_path / "not-ours").write_text("x")
    env = {"EAX_LIBRARY_KEY": "given"}
    (tmp_path / "EAX_LIBRARY_KEY").write_text("file")
    assert secretfiles.load(tmp_path, env) == ["EAX_DB_PASSWORD"]
    assert env == {"EAX_LIBRARY_KEY": "given", "EAX_DB_PASSWORD": "from-file"}       # a value given stays; empty skipped
    assert "_secretfiles.load()" in (API / "eax" / "__init__.py").read_text()


def test_every_entrypoint_reads_them():
    for f in ("services/api/entrypoint.sh", "services/backup/entrypoint.sh", "services/library/entrypoint.sh",
              "services/views/entrypoint.sh", "deploy/superset/superset-init.sh", "deploy/superset/reports-start.sh",
              "deploy/postgres/initdb/01-databases.sh"):
        assert "for _f in /run/secrets/EAX_*; do" in (REPO / f).read_text(encoding="utf-8"), f


@pytest.mark.skipif(not shutil.which("bash"), reason="no bash")
def test_documents_fills_its_placeholders_from_the_files(tmp_path):
    secrets = tmp_path / "s"
    secrets.mkdir()
    (secrets / "EAX_MAYAN_DB_PASSWORD").write_text("p&ss/w0rd")
    script = (REPO / "deploy/secrets/mayan-start.sh").read_text().replace("/run/secrets", str(secrets))
    script = re.sub(r'^ENTRY=.*$', "ENTRY=env", script, flags=re.M)
    (tmp_path / "m.sh").write_text(script)
    env = {**os.environ, "MAYAN_DATABASES": '{"PASSWORD":"{{EAX_MAYAN_DB_PASSWORD}}"}'}
    out = subprocess.run(["bash", str(tmp_path / "m.sh")], env=env, capture_output=True, text=True, check=True).stdout
    assert 'MAYAN_DATABASES={"PASSWORD":"p&ss/w0rd"}' in out
    assert "{{EAX_MAYAN_DB_PASSWORD}}" in COMPOSE and "${EAX_MAYAN_DB_PASSWORD}" not in COMPOSE


@pytest.mark.skipif(not shutil.which("docker"), reason="no docker compose here")
def test_the_resolved_configuration_holds_no_password(tmp_path):
    """docker compose config, as eax runs it, with the laptop template: no password in it anywhere."""
    for f in ("docker-compose.yml",):
        shutil.copy(REPO / f, tmp_path / f)
    shutil.copytree(REPO / "deploy", tmp_path / "deploy")
    (tmp_path / "work").mkdir()
    (tmp_path / "services" / "api").mkdir(parents=True)
    shutil.copy(API / "version.toml", tmp_path / "services" / "api" / "version.toml")
    env_text = (REPO / "deploy/templates/eaexplorer.laptop.env").read_text()
    (tmp_path / "work" / "eaexplorer.env").write_text(env_text)
    (tmp_path / "work" / "config.env").write_text(core.config_without_secrets(env_text, KEYS))
    for extra in ([], ["-f", "deploy/compose/auth/docker-compose.certificate.yml"]):
        r = subprocess.run(["docker", "compose", "--env-file", "work/eaexplorer.env", "-f", "docker-compose.yml", "-f",
                            "deploy/compose/docker-compose.laptop.yml", *extra, "config"], cwd=tmp_path,
                           capture_output=True, text=True)
        if r.returncode != 0 and "Cannot connect" in r.stderr:
            pytest.skip("docker compose needs a daemon here")
        assert r.returncode == 0, r.stderr
        assert "55w0rd" not in r.stdout and "P%5E55" not in r.stdout
