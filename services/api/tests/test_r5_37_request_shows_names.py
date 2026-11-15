"""R5.37: a service request shows the project and the model by name, not by identifier (owner, 15 Nov 2026:
"In access to project instead of name I am getting GUID")."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eax import servicedesk as sd  # noqa: E402

FORM = [{"name": "who", "kind": "person"}, {"name": "project", "kind": "project"}, {"name": "model", "kind": "model"},
        {"name": "role", "kind": "project-role"}]
P_GUID = "b46e0a38-0466-426d-acc6-3350e58164ce"
M_GUID = "11111111-2222-3333-4444-555555555555"


def test_project_and_model_shown_by_name(monkeypatch):
    monkeypatch.setattr(sd, "_project_names", lambda gs: {P_GUID: "Meridian Cloud Move"} if P_GUID in gs else {})
    monkeypatch.setattr(sd, "_model_names", lambda conn, gs: {M_GUID: "Meridian Estate"} if M_GUID in gs else {})
    out = sd.shown_fields(None, FORM, {"who": "Test User", "project": P_GUID, "model": M_GUID, "role": "architect"})
    assert out == {"who": "Test User", "project": "Meridian Cloud Move", "model": "Meridian Estate", "role": "architect"}


def test_something_gone_shows_as_given(monkeypatch):
    monkeypatch.setattr(sd, "_project_names", lambda gs: {})
    monkeypatch.setattr(sd, "_model_names", lambda conn, gs: {})
    assert sd.shown_fields(None, FORM, {"project": P_GUID})["project"] == P_GUID


def test_the_request_page_uses_the_names():
    src = (Path(__file__).resolve().parents[2] / "web" / "src" / "ServiceDesk.jsx").read_text(encoding="utf-8")
    assert "t.shown?.[k]" in src
    assert 's["shown"] = shown_fields(' in Path(sd.__file__).read_text(encoding="utf-8")
