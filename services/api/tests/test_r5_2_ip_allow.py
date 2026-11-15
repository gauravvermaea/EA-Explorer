"""R5.2 (owner, 14 Nov 2026: "IP white listing"; 15 Nov 2026, D686: "I assume 5.2 ip white listing will be managed on
nginx"): allow lists per place at the front door, never a lock-out, a credential limited to its own addresses."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from eax import ip_allow  # noqa: E402
from eax import machine_access as ma  # noqa: E402
from eax.setup import __main__ as setup  # noqa: E402

spec = importlib.util.spec_from_file_location("allowlist", REPO / "services/ops/allowlist.py")
AL = importlib.util.module_from_spec(spec)
spec.loader.exec_module(AL)
NGINX = (REPO / "deploy/proxy/templates/default.conf.template").read_text()


def lists(**kw):
    return {p: [{"address": a} for a in kw.get(p, [])] for p in ip_allow.PLACES}


def test_the_places_are_the_same_everywhere():
    assert tuple(AL.PLACES) == ip_allow.PLACES == setup.ALLOW_PLACES
    for p in ip_allow.PLACES:
        assert f"geo $eax_deny_{p}" in NGINX and f"/eax-proxy/allow/{p}.geo" in NGINX


@pytest.mark.parametrize("mod", [ip_allow, AL])
def test_allowed_and_refused_at_each_place(mod):
    L = lists(site=["10.1.0.0/16"], mcp=["10.1.2.0/24"], machine=["192.0.2.7"])
    assert mod.allowed(L, "site", "10.1.9.9") and not mod.allowed(L, "site", "203.0.113.5")
    assert mod.allowed(L, "mcp", "10.1.2.3") and not mod.allowed(L, "mcp", "10.1.9.9")       # both lists must say yes
    assert mod.allowed(L, "signin", "10.1.9.9")                                                # no list of its own
    assert mod.allowed(L, "machine", "192.0.2.7") and not mod.allowed(L, "machine", "10.1.9.9")   # its own list only
    assert mod.allowed(lists(), "admin", "203.0.113.5")                                       # no lists: everyone


@pytest.mark.parametrize("mod", [ip_allow, AL])
def test_this_machine_and_its_own_containers_are_always_allowed(mod):
    L = lists(site=["10.1.0.0/16"], admin=["10.1.1.1"])
    for a in ("127.0.0.1", "::1"):
        assert mod.allowed(L, "admin", a)
    assert mod.allowed(L, "admin", "172.18.0.5", ["172.18.0.0/16"])


def test_ipv6_and_bad_addresses():
    L = lists(site=["2001:db8::/32"])
    assert ip_allow.allowed(L, "site", "2001:db8::1") and not ip_allow.allowed(L, "site", "2001:dead::1")
    with pytest.raises(ip_allow.Refused, match="not an address"):
        ip_allow.clean({"lists": {"site": ["10.1.2.300"]}})
    with pytest.raises(ip_allow.Refused, match="No place"):
        ip_allow.clean({"lists": {"everywhere": ["10.0.0.1"]}})
    assert ip_allow.clean({"lists": {"site": ["10.1.2.3/16"]}})["lists"]["site"][0]["address"] == "10.1.0.0/16"


def test_a_change_that_would_lock_out_its_maker_is_refused():
    with pytest.raises(ip_allow.Refused, match="your own address"):
        ip_allow.guard(lists(site=["10.9.0.0/16"]), "203.0.113.5")
    with pytest.raises(ip_allow.Refused, match="admin"):
        ip_allow.guard(lists(admin=["10.9.0.1"]), "203.0.113.5")
    ip_allow.guard(lists(site=["203.0.113.0/24"], mcp=["10.0.0.1"]), "203.0.113.5")   # mcp is not the screen they use


def test_nginx_files_say_who_may_come_in():
    data = AL.clean({"lists": {"site": [{"address": "10.1.0.0/16", "name": "head office"}]},
                     "trusted": [{"address": "10.0.0.10"}]})
    files = AL.render(data, ["172.18.0.0/16"])
    assert set(files) == {f"{p}.geo" for p in AL.PLACES} | {"realip.conf"}
    site = files["site.geo"].splitlines()
    assert "default 1;" in site and any(x.startswith("10.1.0.0/16 0;") and "head office" in x for x in site)
    assert any(x.startswith("127.0.0.0/8 0;") for x in site) and any(x.startswith("172.18.0.0/16 0;") for x in site)
    assert files["mcp.geo"].rstrip().endswith("default 0;")                                 # no list: everyone
    assert "set_real_ip_from 10.0.0.10/32;" in files["realip.conf"] and "real_ip_header X-Forwarded-For;" in files["realip.conf"]


def test_a_forwarded_address_from_an_untrusted_source_is_ignored():
    files = AL.render(AL.clean({"lists": {}}), [])
    assert "set_real_ip_from" not in files["realip.conf"]       # without trusted balancers nginx keeps the real peer


def test_nginx_refuses_at_the_front_door_and_logs_it():
    for server in ("listen 80 default_server;", "listen 443 ssl default_server;", "server_name reports.", "server_name docs."):
        block = NGINX.split(server, 1)[1].split("location", 1)[0]
        assert "if ($eax_deny_site = 1)" in block, server
    cert = NGINX.split("listen 9443 ssl;", 1)[1].split("location", 1)[0]
    assert "if ($eax_deny_machine = 1)" in cert and "$eax_deny_site" not in cert
    assert "~^/api/v1/(admin|operations)/  admin;" in NGINX and "~^/auth/                       signin;" in NGINX
    assert "access_log /var/log/nginx/eax-refused.log eax_refused if=$eax_refused_log;" in NGINX
    assert "include /eax-proxy/allow/realip.conf;" in NGINX


def test_setup_makes_empty_lists_so_nginx_always_starts(tmp_path):
    assert setup.ensure_allow_files(tmp_path) is True
    assert all((tmp_path / f"{p}.geo").read_text().rstrip().endswith("default 0;") for p in setup.ALLOW_PLACES)
    (tmp_path / "site.geo").write_text("default 1;\n10.0.0.0/8 0;\n")
    assert setup.ensure_allow_files(tmp_path) is False and "10.0.0.0/8" in (tmp_path / "site.geo").read_text()


def test_apply_tests_nginx_and_puts_the_old_files_back_when_it_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(AL, "DIR", str(tmp_path))
    monkeypatch.setattr(AL, "LISTS", str(tmp_path / "lists.json"))
    monkeypatch.setattr(AL, "internal_networks", lambda p: ["172.18.0.0/16"])
    monkeypatch.setattr(AL, "proxy_container", lambda p: "abc")
    calls = []

    class R:
        def __init__(self, rc):
            self.returncode, self.stdout, self.stderr = rc, "", "bad"

    monkeypatch.setattr(AL, "_docker", lambda *a, **k: calls.append(a) or R(0))
    out = AL.apply({"lists": {"site": ["10.1.0.0/16"]}}, "eaexplorer", "ann")
    assert out["reloaded"] and ("exec", "abc", "nginx", "-s", "reload") in calls
    assert json.loads((tmp_path / "lists.json").read_text())["changed_by"] == "ann"
    good = (tmp_path / "site.geo").read_text()
    monkeypatch.setattr(AL, "_docker", lambda *a, **k: R(1 if "-t" in a else 0))
    with pytest.raises(ValueError, match="nginx did not accept"):
        AL.apply({"lists": {"site": ["10.2.0.0/16"]}}, "eaexplorer", "bob")
    assert (tmp_path / "site.geo").read_text() == good                                     # the old files back


def test_refusals_are_counted(monkeypatch):
    monkeypatch.setattr(AL, "proxy_container", lambda p: "abc")

    class R:
        returncode, stderr = 0, ""
        stdout = "t1\t203.0.113.5\tsite\t/\nt2\t203.0.113.5\tmcp\t/mcp\nt3\t198.51.100.1\tsite\t/x\n"

    monkeypatch.setattr(AL, "_docker", lambda *a, **k: R())
    out = AL.refused("eaexplorer")
    assert out["count"] == 3 and out["by_address"][0] == ("203.0.113.5", 2) and out["by_place"] == {"site": 2, "mcp": 1}


def test_a_credential_limited_to_its_addresses():
    assert ip_allow.credential_allows([], "203.0.113.5")
    assert ip_allow.credential_allows(["10.1.0.0/16"], "10.1.2.3") and not ip_allow.credential_allows(["10.1.0.0/16"], "10.2.0.1")
    assert ma.clean_addresses(["10.1.2.3/16", "10.1.0.0/16"]) == ["10.1.0.0/16"]
    with pytest.raises(ValueError):
        ma.clean_addresses(["nope"])
    src = (REPO / "services/api/eax/machine_access.py").read_text()
    assert "may only be used from" in src and "allowed_addresses" in (REPO / "services/api/migrations/sql/0078_r5_machine_addresses.sql").read_text()


def test_every_form_has_eax_allow_and_the_api_checks_the_lock_out():
    assert "|allow|" in (REPO / "eax.sh").read_text() and '"folders", "allow"' in (REPO / "eax.ps1").read_text()
    assert '"/app/allowlist.py"' in (REPO / "eaxcli/allow_cli.py").read_text()
    assert "### allow" in (REPO / "eaxcli/help.txt").read_text()
    admin = (REPO / "services/api/eax/api/admin.py").read_text()
    assert "ip_allow.guard(" in admin and '"/admin/allow"' in admin and "COPY allowlist.py" in (REPO / "services/ops/Dockerfile").read_text()
