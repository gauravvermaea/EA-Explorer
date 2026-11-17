import os

import pytest

# Point the API at a database port nothing listens on, so tests never touch a real database.
os.environ.setdefault("EAX_DB_HOST", "127.0.0.1")
os.environ.setdefault("EAX_DB_PORT", "1")
os.environ.setdefault("EAX_DB_PASSWORD", "test")
os.environ.setdefault("EAX_HOSTNAME", "localhost")
os.environ.setdefault("EAX_HTTPS_PORT", "443")


@pytest.fixture()
def client():
    from eax.app import create_app

    app = create_app(testing=True)
    return app.test_client()


# Tests never call GitHub (R5.6-U1): the published releases come from a stand-in a test sets, else nothing is offered.
FAKE_RELEASES = [
    {"tag_name": "v0.19.0", "name": "EA Explorer 0.19.0", "body": "notes 0.19.0", "published_at": "2026-01-01T00:00:00Z",
     "draft": False, "prerelease": False},
]


@pytest.fixture(autouse=True)
def _no_github(monkeypatch):
    try:
        import sys
        from pathlib import Path
        root = str(Path(__file__).resolve().parents[3])
        if root not in sys.path:
            sys.path.insert(0, root)
        from eaxcli import releases as R
    except Exception:  # noqa: BLE001 - a test without the eaxcli folder
        return
    real = getattr(R, "_real_get_json", None) or R._get_json
    monkeypatch.setattr(R, "_real_get_json", real, raising=False)       # for the test of the reading itself
    monkeypatch.setattr(R, "_get_json", lambda url, timeout=20: list(FAKE_RELEASES) if "page=1" in url else [])


# Certificate mode and password mode (R6-C1; owner, 17 Nov 2026, 21:07): a test marked certificate_mode runs only when
# the installation uses certificates (EAX_AUTH_MODE=certificate), one marked password_mode only when it uses passwords;
# otherwise it is skipped, saying why.
def pytest_configure(config):
    config.addinivalue_line("markers", "certificate_mode: runs only when EAX_AUTH_MODE=certificate, skipped otherwise")
    config.addinivalue_line("markers", "password_mode: runs only when EAX_AUTH_MODE=password (the default), skipped otherwise")


def pytest_collection_modifyitems(config, items):
    mode = "certificate" if (os.environ.get("EAX_AUTH_MODE") or "").strip().lower() == "certificate" else "password"
    for item in items:
        if "certificate_mode" in item.keywords and mode != "certificate":
            item.add_marker(pytest.mark.skip(reason="the installation uses passwords (EAX_AUTH_MODE): a certificate mode test"))
        if "password_mode" in item.keywords and mode != "password":
            item.add_marker(pytest.mark.skip(reason="the installation uses certificates (EAX_AUTH_MODE): a password mode test"))
