"""R4.19 (owner, 14 Nov 2026: "In R4 create a story for laptop mode init to have OpenBao, we need the secrets working";
"Unseals by itself"; "Docker secrets"; "Server also keeps unseal keys like laptop non manually puts them"): the key
vault. OpenBao itself is faked by a small HTTP server that answers as its API does (sys/health, sys/init, sys/unseal,
sys/mounts, sys/audit and a KV version 2 engine)."""

from __future__ import annotations

import json
import re
import stat
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from eaxcli import vault  # noqa: E402

TEMPLATE = (REPO / "deploy/templates/eaexplorer.server.env").read_text(encoding="utf-8")
SECRET_KEYS = re.findall(r"^([A-Z0-9_]+)=change-me", TEMPLATE, re.MULTILINE)
COMPOSE = yaml.safe_load((REPO / "docker-compose.yml").read_text(encoding="utf-8"))


# ---------------------------------------------------------------- a stand-in OpenBao
class FakeBao:
    def __init__(self, audit_ok=True):
        self.initialized, self.sealed, self.key, self.token = False, True, "", ""
        self.mounts, self.kv, self.audit, self.audit_ok, self.calls = {"sys/": {}}, {}, {}, audit_ok, []
        bao = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, code, body=None):
                raw = json.dumps(body).encode() if body is not None else b""
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def _body(self):
                n = int(self.headers.get("Content-Length") or 0)
                return json.loads(self.rfile.read(n) or b"{}") if n else {}

            def _authed(self):
                return self.headers.get("X-Vault-Token") == bao.token and not bao.sealed

            def handle_any(self):
                path = self.path.split("?")[0].removeprefix("/v1/")
                bao.calls.append((self.command, path))
                if path == "sys/health":
                    return self._send(200, {"initialized": bao.initialized, "sealed": bao.sealed, "version": "2.7.2"})
                if path == "sys/init":
                    bao.initialized, bao.key, bao.token = True, "KEY1", "ROOT1"
                    return self._send(200, {"keys_base64": [bao.key], "root_token": bao.token})
                if path == "sys/unseal":
                    if self._body().get("key") == bao.key:
                        bao.sealed = False
                    return self._send(200, {"sealed": bao.sealed})
                if not self._authed():
                    return self._send(403, {"errors": ["permission denied"]})
                if path == "sys/mounts":
                    return self._send(200, {"data": bao.mounts})
                if path.startswith("sys/mounts/"):
                    bao.mounts[path.removeprefix("sys/mounts/") + "/"] = self._body()
                    return self._send(204)
                if path == "sys/audit":
                    return self._send(200, {"data": bao.audit})
                if path.startswith("sys/audit/"):
                    if not bao.audit_ok:
                        return self._send(400, {"errors": ["cannot enable audit device via API"]})
                    bao.audit[path.removeprefix("sys/audit/") + "/"] = self._body()
                    return self._send(204)
                m = re.match(r"^([a-z]+)/data/(.+)$", path)
                if m and f"{m.group(1)}/" in bao.mounts:
                    if self.command == "GET":
                        if path not in bao.kv:
                            return self._send(404, {"errors": []})
                        return self._send(200, {"data": {"data": bao.kv[path]}})
                    bao.kv[path] = self._body()["data"]
                    return self._send(200, {"data": {"version": 1}})
                return self._send(404, {"errors": ["no handler"]})

            do_GET = do_PUT = do_POST = handle_any

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def restart(self):                       # a container restart: sealed again
        self.sealed = True


@pytest.fixture
def bao():
    b = FakeBao()
    yield b
    b.server.shutdown()


def _env(**over) -> str:
    refs = "".join(f"{k}=openbao:{k}\n" for k in SECRET_KEYS)
    return "EAX_DEPLOYMENT=laptop\n" + refs + "EAX_SECRETS_FROM=openbao:eax/eaexplorer\n" + "".join(f"{k}={v}\n" for k, v in over.items())


# ---------------------------------------------------------------- the config file's side
def test_r4_19_references_and_where():
    text = _env()
    assert vault.where(text) == "eax/eaexplorer" and vault.where("EAX_SECRETS_FROM=aws:x\n") is None
    assert vault.where("EAX_SECRETS_FROM=openbao:\n") == vault.DEFAULT_WHERE
    refs = vault.references(text)
    assert set(refs) == set(SECRET_KEYS) and refs["EAX_DB_PASSWORD"] == "EAX_DB_PASSWORD"
    assert vault.is_reference("'openbao:X'") and not vault.is_reference("P^55w0rd1234&")
    turned = vault.with_references("A=1\nEAX_DB_PASSWORD=secret\nB=2\n", ["EAX_DB_PASSWORD"])
    assert turned == "A=1\nEAX_DB_PASSWORD=openbao:EAX_DB_PASSWORD\nB=2\n"


def test_r4_19_values_are_made_strong_and_the_broker_url_matches():
    got = vault.generate(SECRET_KEYS)
    assert set(got) == set(SECRET_KEYS)
    assert all(re.fullmatch(r"[0-9a-f]{40}", v) for k, v in got.items())               # no quoting anywhere
    assert got["EAX_DMS_BROKER_PASSWORD_URLENC"] == got["EAX_DMS_BROKER_PASSWORD"]
    assert len(set(got.values())) == len(SECRET_KEYS) - 1                              # each its own, but the derived one
    kept = vault.generate(["EAX_DB_PASSWORD", "EAX_OPS_TOKEN"], keep={"EAX_DB_PASSWORD": "old"})
    assert kept["EAX_DB_PASSWORD"] == "old" and kept["EAX_OPS_TOKEN"] != "old"
    assert vault.env_lines({"B": "2", "A": "x=y", "C": "bad\nline"}) == "A=x=y\nB=2\n"


# ---------------------------------------------------------------- set up, unsealed, values made once
def test_r4_19_first_start_sets_it_up_and_makes_every_value(bao, tmp_path):
    keys = vault.keys_path(tmp_path)
    assert keys == tmp_path / "persist" / "vault" / "keys.json"
    said = []
    c = vault.ready(keys, bao.url, "eax/eaexplorer", say=said.append)
    assert c.fresh and c.audited and "eax/" in bao.mounts and "eax/" in bao.audit
    saved = json.loads(keys.read_text())
    assert saved["unseal_key"] == "KEY1" and saved["root_token"] == "ROOT1"
    if sys.platform != "win32":
        assert stat.S_IMODE(keys.stat().st_mode) == 0o600                               # the owner only
    values = vault.resolve(_env(), c, "eax/eaexplorer")
    assert set(values) == set(SECRET_KEYS) and "eax/data/eaexplorer" in bao.kv
    assert any("first time" in s for s in said)
    # the next start: sealed again, unsealed with the kept key; the same values, nothing made again
    bao.restart()
    c2 = vault.ready(keys, bao.url, "eax/eaexplorer")
    assert not c2.fresh and not bao.sealed
    assert vault.resolve(_env(), c2, "eax/eaexplorer") == values


def test_r4_19_a_missing_value_is_refused_never_started_with_a_reference(bao, tmp_path):
    keys = tmp_path / "keys.json"
    c = vault.ready(keys, bao.url, "eax/eaexplorer")
    c.write("eax/eaexplorer", {"EAX_DB_PASSWORD": "x"})
    c.fresh = False
    with pytest.raises(vault.VaultError, match="no value for .*EAX_OPS_TOKEN"):
        vault.resolve(_env(), c, "eax/eaexplorer")


def test_r4_19_a_wrong_key_or_none_is_said(bao, tmp_path):
    keys = tmp_path / "keys.json"
    vault.ready(keys, bao.url, "eax/eaexplorer")
    bao.restart()
    vault.save_keys(keys, {"unseal_key": "WRONG", "root_token": "ROOT1"})
    with pytest.raises(vault.VaultError, match="still sealed"):
        vault.ready(keys, bao.url, "eax/eaexplorer")
    keys.unlink()
    with pytest.raises(vault.VaultError, match="no unseal key"):
        vault.ready(keys, bao.url, "eax/eaexplorer")


def test_r4_19_a_new_vault_volume_keeps_the_old_keys_aside(bao, tmp_path):
    keys = tmp_path / "keys.json"
    vault.save_keys(keys, {"unseal_key": "OLD", "root_token": "OLDROOT"})
    said = []
    c = vault.ready(keys, bao.url, "eax/eaexplorer", say=said.append)
    assert c.fresh and json.loads(keys.read_text())["root_token"] == "ROOT1"
    assert [p.name for p in tmp_path.glob("keys.*.old.json")] and any("moved aside" in s for s in said)


def test_r4_19_not_running_is_started_then_waited_for(tmp_path):
    started = []
    with pytest.raises(vault.VaultError, match="did not answer"):
        vault.ready(tmp_path / "k.json", "http://127.0.0.1:9", "eax/x", start=lambda: started.append(1), wait=1)
    assert started == [1]


def test_r4_19_audit_refused_through_the_api_is_said(tmp_path):
    b = FakeBao(audit_ok=False)
    try:
        assert vault.ready(tmp_path / "k.json", b.url, "eax/eaexplorer").audited is False
    finally:
        b.server.shutdown()


# ---------------------------------------------------------------- compose: the vault, and the values to every container
def test_r4_19_every_container_reading_the_config_file_takes_the_vaults_values():
    assert set(COMPOSE["x-secrets"]) == set(SECRET_KEYS)
    assert all(v == f"${{{k}:-}}" for k, v in COMPOSE["x-secrets"].items())
    for name, svc in COMPOSE["services"].items():
        if "env_file" in svc:
            env = svc.get("environment") or {}
            assert set(SECRET_KEYS) <= set(env), name                                    # environment wins over env_file


def test_r4_19_no_openbao_container_volume_or_setting_while_switched_off():
    """Owner, 14 Nov 2026, 20:36: "there should be no way or config for users to turn on openbao until I give details":
    no container, volume, network, backup set or setting for it; the code stays, switched off in the code itself."""
    assert "openbao" not in COMPOSE["services"] and "eax-vault" not in COMPOSE["volumes"]
    assert "vault" not in (COMPOSE.get("networks") or {})
    assert not any("vault" in str(m) for m in COMPOSE["services"]["backup"]["volumes"])
    for kind in ("laptop", "server"):
        env = (REPO / f"deploy/templates/eaexplorer.{kind}.env").read_text()
        assert "OPENBAO" not in env and "EAX_VAULT_PORT" not in env and "\nEAX_SECRETS_FROM=openbao" not in env
    assert '"vault": ("eax-vault",' not in (REPO / "services/ops/ops.py").read_text()
    assert "vault ${EAX_BACKUP_VAULT" not in (REPO / "services/backup/backup.sh").read_text()
    assert "_vault().ALLOWED and" in (REPO / "services/ops/console.py").read_text()
    assert (REPO / "deploy/openbao/openbao.hcl").exists()                               # kept for when he decides


# ---------------------------------------------------------------- eax: init, the three forms, the console
def test_r4_19_init_makes_references_and_names_the_vault(monkeypatch):
    from eaxcli import main
    text = main.with_vault((REPO / "deploy/templates/eaexplorer.laptop.env").read_text(encoding="utf-8"))
    refs = vault.references(text)
    assert set(refs) == set(SECRET_KEYS) and vault.where(text) == "eax/eaexplorer"
    assert "P^55w0rd1234&" not in "".join(ln for ln in text.splitlines() if ln.split("=")[0] in SECRET_KEYS)
    src = (REPO / "eaxcli/main.py").read_text()
    assert 'use_vault = vault_on() and "--no-vault" not in rest' in src
    # eax.ps1 and eax.sh make the same file (D331): each change-me key of the server template a reference
    ps = (REPO / "eax.ps1").read_text()
    assert '$useVault = $false' in ps and '"$k=openbao:$k"' in ps
    assert '"EAX_SECRETS_FROM=openbao:eax/eaexplorer"' in ps
    sh = (REPO / "eax.sh").read_text()
    assert "    NOVAULT=1   # R4.19" in sh and 'print p[1] "=openbao:" p[1]' in sh and 'print "EAX_SECRETS_FROM=openbao:eax/eaexplorer"' in sh


def test_r4_19_every_form_of_eax_reads_the_vault_before_making_containers():
    core = (REPO / "eaxcli/core.py").read_text()
    assert 'CREATING = ("up", "run", "create")' in core and "if args and args[0] in CREATING:\n        vault_env()" in core
    assert 'if v.startswith("openbao:"):\n                vault_env()' in core
    sh = (REPO / "eax.sh").read_text()
    assert 'case "${1:-}" in up|run|create) vault_env || return 1 ;; esac' in sh
    assert 'lines=$("$ROOT/eaxpy.sh" secrets env)' in sh and "openbao:*) vault_env" in sh
    ps = (REPO / "eax.ps1").read_text()
    assert '@("up", "run", "create") -contains $Arguments[0]) { Use-VaultEnv }' in ps
    assert '& (Join-Path $PSScriptRoot "eaxpy.ps1") secrets env' in ps and 'StartsWith("openbao:")' in ps
    secrets = (REPO / "eaxcli/secrets.py").read_text()
    assert 'contextlib.redirect_stdout(sys.stderr)' in secrets                          # only KEY=VALUE on the pipe
    help_ = (REPO / "eaxcli/help.txt").read_text()
    assert "OpenBao (R4.19) is switched off for now" in help_ and "### init [laptop|server]\n" in help_


def test_r4_19_rotating_a_database_login_changes_it_in_the_database_without_a_command_line():
    from eaxcli import secrets as s
    assert set(s.DB_LOGINS) | s.JUST_HERE | set(s.ELSEWHERE) == set(SECRET_KEYS)          # each key: how it changes
    src = (REPO / "eaxcli/secrets.py").read_text()
    assert 'input=f"ALTER ROLE' in src                                                  # the value on psql's input


def test_r4_19_persist_never_deletes_the_vaults_keys(tmp_path):
    from eaxcli import persist
    (tmp_path / "persist" / "vault").mkdir(parents=True)
    (tmp_path / "persist" / "vault" / "keys.json").write_text("{}")
    (tmp_path / "persist" / "banner.json").write_text("{}")
    with pytest.raises(ValueError, match="never deleted"):
        persist.delete("vault", tmp_path)
    assert persist.delete_all(tmp_path) == ["banner.json"]
    assert (tmp_path / "persist" / "vault" / "keys.json").exists()


def test_r4_19_the_console_writes_a_password_into_the_vault():
    src = (REPO / "services/ops/console.py").read_text()
    assert src.count("set_secret(") >= 4 and 'set_config("EAX_KC_ADMIN_PASSWORD"' not in src
    assert 'vault.url_for(inside=True)' in src


# ---------------------------------------------------------------- the containers, the health page and the self-test
def test_r4_19_a_reference_reaching_a_container_stops_the_setup(monkeypatch):
    from eax.setup.__main__ import check_config
    monkeypatch.setenv("EAX_DB_PASSWORD", "openbao:EAX_DB_PASSWORD")
    assert any("key vault's values were not read (EAX_DB_PASSWORD)" in p for p in check_config())


def test_r4_19_health_says_off_without_the_vault(monkeypatch):
    from eax import health
    monkeypatch.delenv("EAX_SECRETS_FROM", raising=False)
    assert health.check_vault()["status"] == "off"
    monkeypatch.setenv("EAX_SECRETS_FROM", "openbao:eax/eaexplorer")
    assert health.check_vault()["status"] == "down"                                      # no openbao here
    assert health.check_vault in health.CHECKS


def test_r4_19_the_self_test_checks_the_vault():
    from eax.testing import security
    seen = []

    def rec(name, outcome, detail, ms):
        seen.append((name, outcome))
    security.key_vault(rec, lambda: {"used": True, "unsealed": True, "where": "eax/eaexplorer", "references": 23,
                                     "missing": [], "clear": ["EAX_OPS_TOKEN"], "audit": True, "in_environment": ["api"]})
    got = dict(seen)
    assert got["key vault unsealed"] == "passed" and got["key vault: every reference has a value"] == "passed"
    assert got["key vault: no password in the config file in clear"] == "failed"
    assert got["key vault: no password in a container's environment"] == "warning"
    seen.clear()
    security.key_vault(rec, lambda: {"used": False})
    assert seen == [("key vault", "skipped")]
    run = (REPO / "services/api/eax/testing/run.py").read_text()
    assert run.count("security.key_vault(rec)") == 2


# ---------------------------------------------------------------- switched off for now (owner, 14 Nov 2026, 20:34)
def test_r4_19_openbao_is_switched_off_for_every_installation(tmp_path, monkeypatch):
    """"For now disable openbao by default. No installation can use it. All passwords go back in env file." """
    from eaxcli import core, main
    from eaxcli import secrets as s
    assert vault.ALLOWED is False and not main.vault_on()
    env = tmp_path / "eaexplorer.env"
    env.write_text(_env(), encoding="utf-8")
    monkeypatch.setattr(core, "ENV_FILE", env)
    monkeypatch.setitem(core._vault, "done", False)
    with pytest.raises(core.Failure, match="switched off"):
        core.vault_env()                                       # a config file still pointing there: said, nothing started
    for action in ("migrate", "rotate", "set", "new", "push"):
        with pytest.raises(core.Failure, match="switched off"):
            s.openbao("push" if action == "migrate" else action, ["EAX_DB_PASSWORD"], _env(), "eax/eaexplorer", {})
