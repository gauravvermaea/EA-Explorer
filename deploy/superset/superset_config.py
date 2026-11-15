"""Superset settings for EA Explorer. Every value comes from eaexplorer.env.

Sign-in: through Keycloak (OIDC). Users are created on first sign-in and their Superset role
follows their Keycloak realm roles (AUTH_ROLES_MAPPING, re-checked at every sign-in).
Break-glass: set EAX_SUPERSET_AUTH=db in eaexplorer.env to sign in with the local admin.

Superset 6.1.0 (R4.7, D680), with Flask-AppBuilder 5: every setting here was checked against it (6.1's config.py
and UPDATING.md for 5.0, 6.0 and 6.1): none of the removed or renamed settings is used, the charts are its current
ECharts and v2 types, and the sign-in below works the same.
"""

import os
from urllib.parse import quote

from flask import g, redirect, request
from flask_appbuilder import expose
from flask_appbuilder.security.manager import AUTH_DB, AUTH_OAUTH
from flask_appbuilder.security.views import AuthOAuthView
from flask_appbuilder.utils.base import get_safe_redirect
from superset.security import SupersetSecurityManager


def env(name, default=""):
    return os.environ.get(name, default).strip()


HOST = env("EAX_HOSTNAME", "localhost")
PORT = env("EAX_HTTPS_PORT", "443")
PUBLIC = f"https://{HOST}" if PORT == "443" else f"https://{HOST}:{PORT}"
REALM = env("EAX_KEYCLOAK_REALM", "eaexplorer")   # chosen at the first install
KC_PUBLIC = f"{PUBLIC}/auth/realms/{REALM}/protocol/openid-connect"
KC_INTERNAL = f"http://keycloak:8080/auth/realms/{REALM}/protocol/openid-connect"

# ---- Core
SECRET_KEY = env("EAX_SUPERSET_SECRET_KEY")
SQLALCHEMY_DATABASE_URI = (
    f"postgresql+psycopg2://superset:{quote(env('EAX_SUPERSET_DB_PASSWORD'), safe='')}"
    f"@{env('EAX_SUPERSET_DB_HOST') or 'db'}:{env('EAX_SUPERSET_DB_PORT') or '5432'}/superset"   # R2.50
)
SQLALCHEMY_TRACK_MODIFICATIONS = False

# ---- Behind the nginx proxy, over HTTPS
ENABLE_PROXY_FIX = True
PROXY_FIX_CONFIG = {"x_for": 1, "x_proto": 1, "x_host": 1, "x_port": 1, "x_prefix": 1}
PREFERRED_URL_SCHEME = "https"
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_SAMESITE = "Lax"
TALISMAN_ENABLED = False  # headers are set by the proxy

# ---- Caches in Superset's own PostgreSQL database (no Valkey/Redis)
# SupersetMetastoreCache keeps cached values in the metadata database, so nothing is lost on restart
# and no separate cache service is needed.
_db_cache = {"CACHE_TYPE": "SupersetMetastoreCache", "CACHE_DEFAULT_TIMEOUT": 300}
CACHE_CONFIG = {**_db_cache, "CACHE_KEY_PREFIX": "superset_"}
DATA_CACHE_CONFIG = {**_db_cache, "CACHE_KEY_PREFIX": "superset_data_"}
FILTER_STATE_CACHE_CONFIG = {**_db_cache, "CACHE_KEY_PREFIX": "superset_filter_", "CACHE_DEFAULT_TIMEOUT": 86400}
EXPLORE_FORM_DATA_CACHE_CONFIG = {**_db_cache, "CACHE_KEY_PREFIX": "superset_explore_", "CACHE_DEFAULT_TIMEOUT": 86400}

# ---- Sign-in through Keycloak
AUTH_TYPE = AUTH_DB if env("EAX_SUPERSET_AUTH") == "db" else AUTH_OAUTH
AUTH_USER_REGISTRATION = True
AUTH_USER_REGISTRATION_ROLE = "Gamma"
AUTH_ROLES_SYNC_AT_LOGIN = True
READER = "EA Explorer reports"   # may read the report datasets, for the models they have (eax_reports_init.py, D138)
AUTH_ROLES_MAPPING = {
    # Keycloak's global roles (phase 3.1). Only the Super Admin is a Superset Admin; IT Admins and
    # Keycloak Admins see no content (D98). Everyone else reads the reports of the models they have.
    "eax-super-admin": ["Admin"],
    "eax-it-admin": ["Gamma"],
    "eax-keycloak-admin": ["Gamma"],
    "eax-audit": ["Gamma", READER],      # the Auditor reads every model's reports, changes none (R5.22)
    "eax-user-admin": ["Gamma", READER],
    "eax-model-creator": ["Gamma", READER],
    "eax-library-admin": ["Gamma", READER],
    "eax-user": ["Gamma", READER],
}
OAUTH_PROVIDERS = [
    {
        "name": "keycloak",
        "icon": "fa-key",
        "token_key": "access_token",
        "remote_app": {
            "client_id": "superset",
            "client_secret": env("EAX_SUPERSET_OIDC_SECRET"),
            "client_kwargs": {"scope": "openid email profile"},
            # The browser goes to the public address; Superset talks to Keycloak internally.
            "authorize_url": f"{KC_PUBLIC}/auth",
            "access_token_url": f"{KC_INTERNAL}/token",
            "api_base_url": f"{KC_INTERNAL}/",
            "jwks_uri": f"{KC_INTERNAL}/certs",
        },
    }
]


class EaxOAuthView(AuthOAuthView):
    """Sign-in through Keycloak that keeps `next` for someone already signed in (the owner's test, 14 Nov 2026, 21:28:
    "When I click on a specific report I am not taken to it. Instead I am taking to this dashboard"). Every report link
    in EA Explorer is /login/keycloak?next=/superset/dashboard/<slug>/; Flask-AppBuilder sends a person already signed
    in to the home page and drops `next`, so here they go where the link points (a path on this site only)."""

    @expose("/login/")
    @expose("/login/<provider>")
    def login(self, provider=None):
        wanted = request.args.get("next", "")
        if g.user is not None and g.user.is_authenticated and wanted:
            return redirect(get_safe_redirect(wanted))
        return super().login(provider)


class KeycloakSecurityManager(SupersetSecurityManager):
    """Reads the user and their realm roles from Keycloak's userinfo endpoint."""

    authoauthview = EaxOAuthView

    def oauth_user_info(self, provider, response=None):
        if provider != "keycloak":   # Flask-AppBuilder's own (in 5.x oauth_user_info is only set when not overridden)
            return self.get_oauth_user_info(provider, response)
        data = self.appbuilder.sm.oauth_remotes[provider].get("userinfo").json()
        return {
            "username": data.get("preferred_username", ""),
            "first_name": data.get("given_name", ""),
            "last_name": data.get("family_name", ""),
            "email": data.get("email", ""),
            "role_keys": data.get("roles", []),
        }


CUSTOM_SECURITY_MANAGER = KeycloakSecurityManager


def FLASK_APP_MUTATOR(app):  # noqa: N802 - the name Superset looks for
    """After a clean restart the browser can still hold a session cookie for a person the new Superset does not
    have; Flask-AppBuilder's user loader then fails with a 500 error on every page. Wrap the loader so such a
    cookie counts as signed out, and the person simply signs in again through Keycloak."""
    lm = getattr(app, "login_manager", None)
    loader = getattr(lm, "_user_callback", None)
    if loader is None:
        return

    def safe_loader(user_id):
        try:
            return loader(user_id)
        except (AttributeError, TypeError, ValueError):
            return None

    lm._user_callback = safe_loader

# the roles list on Superset's Settings page is a screen of its own since Superset 6.0 and needs the security API
# (Superset's UPDATING.md for 6.0); on by default in 6.1, said here so a change of default never hides it
FAB_ADD_SECURITY_API = True

# ---- Features
# ENABLE_TEMPLATE_PROCESSING: model access uses {{ current_username() }} (D138)
FEATURE_FLAGS = {"DASHBOARD_RBAC": True, "EMBEDDED_SUPERSET": False, "ENABLE_TEMPLATE_PROCESSING": True}
# links in report tables (Open in EA Explorer)
HTML_SANITIZATION = True
SQLLAB_CTAS_NO_LIMIT = True


# ---- EA Explorer's report designer (phase 24, D434): /eax/designs/<guid>/open makes a design's dataset and opens the chart
# builder. A failure to load it never stops Superset: only the designer's Open button is affected.
try:
    import sys as _sys

    _sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from eax_designer import bp as _eax_designer

    BLUEPRINTS = [_eax_designer]
except Exception as _exc:  # noqa: BLE001
    print(f"EA Explorer WARNING: the report designer page is not available: {_exc}")
