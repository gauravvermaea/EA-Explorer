"""System Admin > Jenkins opens Jenkins (the owner, 18 Nov 2026, 18:26: "make it a menu item to open in admin. It will just
open the jenkins URL"). The address is the one eax jenkins up prints: http://<EAX_HOSTNAME>:<EAX_JENKINS_PORT, 8088>."""

from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
MENU = (REPO / "services/web/src/menu.js").read_text(encoding="utf-8")


def test_the_api_gives_the_jenkins_address_eax_prints(monkeypatch):
    from eax.config import jenkins_url
    monkeypatch.setenv("EAX_HOSTNAME", "ea.example.org")
    monkeypatch.delenv("EAX_JENKINS_PORT", raising=False)
    assert jenkins_url() == "http://ea.example.org:8088"
    monkeypatch.setenv("EAX_JENKINS_PORT", "9090")
    assert jenkins_url() == "http://ea.example.org:9090"
    # the same formula as eax jenkins up (eaxcli/jenkins.py, jenkins_url)
    assert "f\"http://{setting('EAX_HOSTNAME', 'localhost')}:{setting('EAX_JENKINS_PORT', '8088')}\"" in \
        (REPO / "eaxcli/jenkins.py").read_text(encoding="utf-8")
    api = REPO / "services/api/eax/api"
    assert '"jenkins": jenkins_url()' in (api / "me.py").read_text(encoding="utf-8")
    assert "    jenkins = fields.String(" in (api / "schemas.py").read_text(encoding="utf-8")


def test_system_admin_has_jenkins_opening_that_address():
    system = MENU[MENU.index('key: "system"'):MENU.index('key: "docs"')]
    assert 'label: "Jenkins ↗", href: myInfo()?.jenkins' in system
