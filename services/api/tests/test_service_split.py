"""R2.27 part 2 and R2.53 (owner, 13 Nov 2026: "Front door routes them"): the operations and personal data services are
containers of their own built from the API's code, each serving its prefix; the main API serves the rest."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[3]
API = REPO / "services/api/eax/api"


def _blueprints() -> dict[str, str]:
    out = {}
    for f in API.glob("*.py"):
        for name, prefix in re.findall(r'Blueprint\(\s*"([^"]+)",\s*__name__,\s*url_prefix="([^"]+)"', f.read_text()):
            out[name] = prefix
    return out


def test_who_serves_what():
    from eax import service_split as ss
    assert ss.wanted("operations", "operations") and not ss.wanted("operations", "core")
    assert ss.wanted("models", "core") and not ss.wanted("models", "operations") and not ss.wanted("models", "personal")
    assert all(ss.wanted(b, "all") for b in ("operations", "models", "personal", "deploys"))
    assert ss.wanted("health", "operations")


def test_every_blueprint_under_a_service_prefix_belongs_to_that_service():
    from eax import service_split as ss
    for name, prefix in _blueprints().items():
        for key, s in ss.SERVICES.items():
            if prefix.startswith(s["prefix"] + "/") or (prefix == s["prefix"] and key == "operations"):
                assert name in s["blueprints"], f"{name} ({prefix}) is under {key}'s prefix but not in its blueprints"
        for _key, s in ss.SERVICES.items():
            if name in s["blueprints"]:
                assert prefix == s["prefix"] or prefix.startswith(s["prefix"] + "/"), f"{name} must be under {s['prefix']}"


def test_every_part_is_served_by_the_api_unless_a_setting_gives_it_a_container(monkeypatch):
    """D677, R3.5-M1b (owner, 14 Nov 2026: "they should always live in api"): the operations and personal data parts are
    the API's again; a part goes to a container of its own only when its setting says so."""
    from eax import service_split as ss
    for k in ("EAX_API_INTERNAL_URL", "EAX_OPERATIONS_INTERNAL_URL", "EAX_PERSONAL_INTERNAL_URL"):
        monkeypatch.delenv(k, raising=False)
    assert ss.route("http://api:8000", "/api/v1/operations/deploys") == "http://api:8000"
    assert ss.route("http://api:8000", "/api/v1/me/notifications") == "http://api:8000"
    assert ss.route("http://api:8000", "/api/v1/me") == "http://api:8000"
    assert ss.route("https://eax.example", "/api/v1/operations/usage") == "https://eax.example"   # the front door routes
    monkeypatch.setenv("EAX_OPERATIONS_INTERNAL_URL", "http://ops-part:8120/")                 # one given its own
    assert ss.route("http://api:8000", "/api/v1/operations/deploys") == "http://ops-part:8120"
    assert ss.route("http://api:8000", "/api/v1/me/notifications") == "http://api:8000"
    from eax import health
    assert health._part_host("operations") == ("ops-part", 8120) and health._part_host("personal") == ("api", 8000)


def test_the_compose_file_runs_no_part_containers_and_the_front_door_sends_them_to_the_api():
    compose = yaml.safe_load((REPO / "docker-compose.yml").read_text())
    svc = compose["services"]
    assert "operations" not in svc and "personal" not in svc                      # removed (R3.5-M1b)
    assert svc["api"]["environment"]["EAX_SERVE"] == "${EAX_API_SERVE:-all}"
    env = svc["proxy"]["environment"]
    assert env["EAX_OPERATIONS_UPSTREAM"] == "${EAX_OPERATIONS_UPSTREAM:-api:8000}"
    assert env["EAX_PERSONAL_UPSTREAM"] == "${EAX_PERSONAL_UPSTREAM:-api:8000}"
    tpl = (REPO / "deploy/proxy/templates/default.conf.template").read_text()
    assert tpl.count("${EAX_OPERATIONS_UPSTREAM}") == 3 and tpl.count("${EAX_PERSONAL_UPSTREAM}") == 3   # still a setting
    entry = (REPO / "services/api/entrypoint.sh").read_text()
    assert "operations|personal)" in entry                                         # a part on its own: by configuration
    for name in ("laptop", "server"):
        assert "\nEAX_API_SERVE=all\n" in (REPO / f"deploy/templates/eaexplorer.{name}.env").read_text()


def test_the_whole_api_answers_every_part_health():
    from eax import service_split as ss
    assert ss.parts_served("all") == ["operations", "personal"]
    assert ss.parts_served("operations") == ["operations"] and ss.parts_served("core") == []
    app = (REPO / "services/api/eax/app.py").read_text()
    assert "service_split.wanted(blp.name)" in app and "for part in service_split.parts_served():" in app
    from eax import health
    assert health.check_operations in health.CHECKS and health.check_personal in health.CHECKS


def test_memory_settings_for_documents_and_keycloak():
    """R3.5 (the smoke test of 14 Nov 2026: Documents 1.9 to 2.6 GB): Mayan's workers and Keycloak's heap by setting."""
    svc = yaml.safe_load((REPO / "docker-compose.yml").read_text())["services"]
    dms = svc["dms"]["environment"]
    assert dms["MAYAN_GUNICORN_WORKERS"] == "${EAX_MAYAN_WEB_WORKERS:-2}"
    for w in "ABC":
        assert dms[f"MAYAN_WORKER_{w}_CONCURRENCY"] == "${EAX_MAYAN_WORKER_CONCURRENCY:-1}"
    assert svc["keycloak"]["environment"]["JAVA_OPTS_KC_HEAP"] == "${EAX_KEYCLOAK_HEAP:--Xms64m -Xmx512m}"
    laptop = (REPO / "deploy/templates/eaexplorer.laptop.env").read_text()
    server = (REPO / "deploy/templates/eaexplorer.server.env").read_text()
    assert "EAX_MAYAN_WORKER_CONCURRENCY=1" in laptop and "EAX_MAYAN_WORKER_CONCURRENCY=2" in server
    assert "EAX_KEYCLOAK_HEAP=-Xms64m -Xmx512m" in laptop and "EAX_KEYCLOAK_HEAP=-Xms256m -Xmx1024m" in server


def test_the_screens_and_tests_use_the_new_paths():
    for f in ("services/web/src/Deploy.jsx", "services/web/src/Updates.jsx", "services/api/eax/testing/run.py"):
        src = (REPO / f).read_text()
        assert not re.search(r"/api/v1/(deploys|updates)\b", src), f
    assert "route(base, path)" in (REPO / "services/api/eax/testing/api_matrix.py").read_text()


def test_who_am_i_stays_on_the_main_api_at_the_front_door():
    """Regression (owner, 13 Nov 2026: "My role has been removed"): nginx answers /api/v1/me with a 301 to the
    `location /api/v1/me/` of the personal service, which has no such route, so the screens read no roles. Every server
    block that sends /api/v1/me/ to the personal service has an exact /api/v1/me to the main API first."""
    import re
    conf = (Path(__file__).resolve().parents[3] / "deploy" / "proxy" / "templates" / "default.conf.template").read_text()
    blocks = re.split(r"\nserver \{", conf)
    with_personal = [b for b in blocks if "location /api/v1/me/ {" in b]
    assert with_personal
    for b in with_personal:
        exact = b[b.index("location = /api/v1/me {"):]
        assert b.index("location = /api/v1/me {") < b.index("location /api/v1/me/ {")
        assert "${EAX_API_UPSTREAM}" in exact[:exact.index("proxy_pass")], "who am I goes to the main API"


def test_the_screens_never_read_who_am_i_from_the_cache():
    """The other half of the regression: a cached 301 kept sending browsers to /api/v1/me/ after the proxy was fixed."""
    auth = (Path(__file__).resolve().parents[2] / "web" / "src" / "auth.js").read_text()
    assert auth.count('apiFetch("/api/v1/me", { cache: "no-store" })') == 2
    assert 'apiFetch("/api/v1/me")' not in auth
