"""Reports on Apache Superset 6.1.0 (Release 4, R4.7, D680; owner, 14 Nov 2026: "upgrade super set to latest version",
"Straight to 6.1.0"). Superset 4.1.2 to 6.1.0 crosses 5.0 and 6.0; each check below is a change in Superset's
UPDATING.md (5.0.0, 6.0.0, 6.1.0) or its 6.1.0 source that could have broken EA Explorer's reports.

Checked against Superset 6.1.0's own source on 14 Nov 2026 (tag 6.1.0; Flask-AppBuilder 5.0.2): the Docker image keeps
its Python packages in /app/.venv installed with uv, without psycopg2 or Authlib; the chart types below are in its
VizType list; the PostgreSQL functions below are its DISALLOWED_SQL_FUNCTIONS; Flask-AppBuilder 5 still calls a security
manager's own oauth_user_info and keeps get_oauth_user_info, find_role, add_role, add_permission_view_menu,
add_permission_role, find_user, update_user and `fab create-admin`; ImportDashboardsCommand(contents, overwrite=True),
get_contents_from_bundle, SqlaTable.fetch_metadata, Database.get_sqla_engine (a context manager),
RowLevelSecurityFilter (filter_type, clause, group_key, roles, tables), the jinja current_username(),
SupersetMetastoreCache and every setting superset_config.py sets are all still there."""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[3]
SUPERSET = REPO / "deploy" / "superset"
VERSION = "apache/superset:6.1.0"

# the chart types Superset 6.1.0 has (superset-ui-core VizType) that the reports use
VIZ_61 = {"table", "pivot_table_v2", "echarts_timeseries_bar", "echarts_timeseries_line", "graph_chart", "sankey_v2",
          "treemap_v2", "bubble_v2"}
# removed in 5.0 (legacy charts; Event Flow and Sankey Loop without a replacement)
LEGACY = {"area", "bar", "dist_bar", "event_flow", "heatmap", "histogram", "line", "sankey", "sankey_loop"}
# settings and feature flags removed or renamed in 5.0, 6.0 and 6.1
REMOVED = ["AUTH_OID", "THEME_OVERRIDES", "HORIZONTAL_FILTER_BAR", "CSV_UPLOAD_MAX_SIZE", "DISABLE_LEGACY_DATASOURCE_EDITOR",
           "DASHBOARD_CROSS_FILTERS", "ALERT_REPORTS_EXECUTE_AS", "THUMBNAILS_EXECUTE_AS", "SUPERSET_WEBSERVER_DOMAINS",
           "GLOBAL_ASYNC_QUERIES_REDIS_CONFIG", "SHARE_QUERIES_VIA_KV_STORE", "KV_STORE", "CUSTOM_FONT_URLS",
           "IMG_UPLOAD_FOLDER", "IMG_UPLOAD_URL", "USE-ANALAGOUS-COLORS", "x_axis_sort_series"]
# Superset 6.0 refuses these PostgreSQL functions in SQL it runs (DISALLOWED_SQL_FUNCTIONS)
DISALLOWED_PG = ["current_database", "current_schema", "current_user", "session_user", "current_setting", "version",
                 "inet_client_addr", "inet_client_port", "inet_server_addr", "inet_server_port", "pg_read_file", "pg_ls_dir",
                 "pg_read_binary_file", "database_to_xml", "database_to_xmlschema", "query_to_xml", "query_to_xmlschema",
                 "table_to_xml", "table_to_xml_and_xmlschema", "query_to_xml_and_xmlschema", "table_to_xmlschema",
                 "pg_sleep", "pg_terminate_backend"]


def test_every_place_names_superset_6_1_0():
    assert f"ARG SUPERSET_IMAGE={VERSION}" in (SUPERSET / "Dockerfile").read_text()
    compose = (REPO / "docker-compose.yml").read_text()
    assert compose.count(f"SUPERSET_IMAGE: ${{EAX_IMAGE_SUPERSET:-{VERSION}}}") == 2       # reports-init and reports
    for kind in ("laptop", "server"):
        assert f"\nEAX_IMAGE_SUPERSET={VERSION}\n" in (REPO / f"deploy/templates/eaexplorer.{kind}.env").read_text()
    assert "superset:4." not in compose


def test_the_drivers_go_where_superset_5_and_later_look():
    """Superset 5 moved its packages into /app/.venv (uv); the system's pip would install psycopg2 and Authlib where
    Superset never imports them, and the reports would not start. An older image still uses pip."""
    df = (SUPERSET / "Dockerfile").read_text()
    assert "if [ -x /app/.venv/bin/python ]; then" in df
    assert "uv pip install --no-cache --python /app/.venv/bin/python $NEED;" in df
    assert "NEED='psycopg2-binary>=2.9,<3 Authlib>=1.3,<2'" in df
    assert "import psycopg2, authlib" in df                                              # the build fails if they are missing
    assert df.rstrip().endswith("USER superset")


def test_no_setting_superset_removed_is_used():
    config = (SUPERSET / "superset_config.py").read_text()
    code = "\n".join(line for line in config.splitlines() if not line.lstrip().startswith("#"))
    for name in REMOVED:
        assert name not in code, name
    assert "FAB_ADD_SECURITY_API = True" in config                                        # the roles list (6.0)


def test_sign_in_falls_back_to_flask_appbuilders_own():
    """Flask-AppBuilder 5 sets oauth_user_info only when a security manager does not define it; ours does, so a
    provider other than Keycloak goes to get_oauth_user_info (super().oauth_user_info would be None there)."""
    config = (SUPERSET / "superset_config.py").read_text()
    assert "return self.get_oauth_user_info(provider, response)" in config
    assert "super().oauth_user_info" not in config
    assert '"role_keys": data.get("roles", []),' in config and "CUSTOM_SECURITY_MANAGER = KeycloakSecurityManager" in config


def _bundled_charts(tmp_path) -> list[dict]:
    from eax.setup import superset_reports as sr
    from eax.setup import superset_sample
    charts = []
    for z in sr.build_report_bundles(tmp_path, "secret", "eaexplorer", "https://ea.example.org"):
        with zipfile.ZipFile(z) as zf:
            charts += [yaml.safe_load(zf.read(n)) for n in zf.namelist() if "/charts/" in n]
    charts += [v for k, v in superset_sample.bundle_files("secret").items() if k.startswith("charts/")]
    return charts


def test_every_report_chart_is_a_type_superset_6_1_has(tmp_path):
    charts = _bundled_charts(tmp_path)
    assert len(charts) > 50
    used = {c["viz_type"] for c in charts}
    assert used <= VIZ_61, used - VIZ_61
    assert not used & LEGACY
    for c in charts:
        assert c["params"]["viz_type"] == c["viz_type"] and "x_axis_sort_series" not in c["params"], c["slice_name"]


def test_the_sql_superset_runs_uses_no_function_it_refuses():
    """The datasets' own SQL (virtual datasets, the heat maps' bands) is run by Superset, which since 6.0 refuses
    functions that reveal the server; the views behind them run in the database and are not checked."""
    from eax.setup import superset_reports as sr
    sql = [sr.heat_sql(name) for name in sr.HEAT] + [s for s, _ in sr.VIRTUAL.values()]
    for text_ in sql:
        low = text_.lower()
        for fn in DISALLOWED_PG:
            assert not re.search(rf"\b{fn}\b", low), (fn, text_[:80])


def test_the_report_bundles_still_import_as_version_1():
    from eax.report_defs import REPORTS
    from eax.setup import superset_reports as sr
    files = sr.bundle(REPORTS[0], "secret", "eaexplorer", "https://ea.example.org")
    meta = files["metadata.yaml"]
    assert meta["version"] == "1.0.0" and meta["type"] == "Dashboard"
    importer = (SUPERSET / "eax_import_reports.py").read_text()
    assert "from superset.commands.dashboard.importers.dispatcher import ImportDashboardsCommand" in importer
    assert "ImportDashboardsCommand(contents, overwrite=True).run()" in importer   # then its datasets (D946)


def _config_with_stand_ins(monkeypatch):
    """superset_config.py loaded with stand-ins for Flask-AppBuilder and Superset (neither is installed here)."""
    import importlib.util
    import sys
    import types
    calls = {}

    class AuthOAuthView:
        def login(self, provider=None):
            calls["parent"] = provider
            return "keycloak sign-in"

    def expose(url="/", methods=("GET",)):
        def wrap(f):
            f._urls = [*getattr(f, "_urls", []), (url, methods)]
            return f
        return wrap
    mods = {"flask_appbuilder": types.SimpleNamespace(expose=expose),
            "flask_appbuilder.security": types.ModuleType("x"),
            "flask_appbuilder.security.manager": types.SimpleNamespace(AUTH_DB=0, AUTH_OAUTH=4),
            "flask_appbuilder.security.views": types.SimpleNamespace(AuthOAuthView=AuthOAuthView),
            "flask_appbuilder.utils": types.ModuleType("x"),
            "flask_appbuilder.utils.base": types.SimpleNamespace(
                get_safe_redirect=lambda u: u if u.startswith("/") and not u.startswith("//") else "/superset/welcome/"),
            "superset": types.ModuleType("x"),
            "superset.security": types.SimpleNamespace(SupersetSecurityManager=object)}
    for k, v in mods.items():
        monkeypatch.setitem(sys.modules, k, v)
    spec = importlib.util.spec_from_file_location("eax_superset_config_test", SUPERSET / "superset_config.py")
    cfg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cfg)
    return cfg, calls


def test_a_report_link_opens_its_dashboard_when_already_signed_in(monkeypatch):
    """The owner, 14 Nov 2026, 21:28: "When I click on a specific report I am not taken to it. Instead I am taking to
    this dashboard". Every report link is /login/keycloak?next=/superset/dashboard/<slug>/; Flask-AppBuilder 5 sends a
    person already signed in to the home page and drops next. Now they go to the dashboard; a link elsewhere does not."""
    import flask
    cfg, calls = _config_with_stand_ins(monkeypatch)
    assert cfg.KeycloakSecurityManager.authoauthview is cfg.EaxOAuthView
    assert ("/login/<provider>", ("GET",)) in cfg.EaxOAuthView.login._urls             # the route stays registered
    app = flask.Flask("t")
    signed_in = type("U", (), {"is_authenticated": True})()
    with app.test_request_context("/login/keycloak?next=/superset/dashboard/eax-sr01-application-inventory/"):
        flask.g.user = signed_in
        r = cfg.EaxOAuthView().login("keycloak")
        assert r.status_code == 302 and r.location.endswith("/superset/dashboard/eax-sr01-application-inventory/")
    with app.test_request_context("/login/keycloak?next=//evil.example.org/"):
        flask.g.user = signed_in
        assert cfg.EaxOAuthView().login("keycloak").location.endswith("/superset/welcome/")
    with app.test_request_context("/login/keycloak?next=/superset/dashboard/x/"):
        flask.g.user = None                                                             # not signed in: Keycloak first
        assert cfg.EaxOAuthView().login("keycloak") == "keycloak sign-in" and calls["parent"] == "keycloak"
