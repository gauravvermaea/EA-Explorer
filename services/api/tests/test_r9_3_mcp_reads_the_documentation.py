"""R9.3 (D796, D797; owner, 19 Nov 2026: "Add a story for MCP to have access to all the docs"; "access of documents and
pdf to everyone"): the person's AI lists, searches and reads every document of the installation's own version, the
printed guides with their PDFs, the error codes and the on-screen help, through MCP, read only; a document marked NOT
FOR AI USE OR AUTOMATED PROCESSING is never listed, found or read."""

from __future__ import annotations

import asyncio
import base64
import importlib
import json
import sys
import types
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]


def _module():
    """eax.mcp_docs, with a stand-in for the MCP server when the real one cannot load here (its library needs more
    than this machine's test set-up gives); the tools are plain functions either way."""
    try:
        importlib.import_module("eax.mcp_server")
    except Exception:  # noqa: BLE001
        fake = types.ModuleType("eax.mcp_server")
        fake.mcp = types.SimpleNamespace(tool=lambda *a, **k: (lambda f: f))
        sys.modules["eax.mcp_server"] = fake
    sys.modules.pop("eax.mcp_docs", None)
    return importlib.import_module("eax.mcp_docs")


@pytest.fixture()
def docs(tmp_path, monkeypatch):
    """A folder laid out as the API's /data/docs: documents (one marked), a guide with its PDF, the screens' help."""
    (tmp_path / "docs" / "site" / "how-do-i").mkdir(parents=True)
    (tmp_path / "docs" / "manuals").mkdir()
    (tmp_path / "docs" / "operations.md").write_text(
        "# Operations\n\nRunning it.\n\n## Backups\n\nTake a backup with eax backup.\n\n### Pinning\n\nKeep one.\n\n"
        "## Restores\n\nRestore one model.\n", encoding="utf-8")
    (tmp_path / "docs" / "site" / "how-do-i" / "back-up-now.md").write_text("# Back up now\n\nA backup straight away.\n",
                                                                            encoding="utf-8")
    (tmp_path / "docs" / "secret-plan.md").write_text("# Plan\n\nNOT FOR AI USE OR AUTOMATED PROCESSING\n\nbackup x\n",
                                                      encoding="utf-8")
    (tmp_path / "docs" / "manuals" / "manuals.json").write_text(json.dumps({"manuals": [
        {"id": "05-day-to-day-operations", "title": "Day-to-day operations", "purpose": "Run it.",
         "chapters": [{"title": "Backups", "sources": ["page:docs/site/how-do-i/back-up-now.md", "howdoi:group=X"]}]}]}),
        encoding="utf-8")
    (tmp_path / "documents").mkdir()
    (tmp_path / "documents" / "EA-Explorer-05-day-to-day-operations.pdf").write_bytes(b"%PDF-1.7 a guide")
    (tmp_path / "help").mkdir()
    (tmp_path / "help" / "catalogue.json").write_text(json.dumps({
        "_about": "x", "page:#/admin/backups": {"what": "Every backup, and taking one now."},
        "page:#/projects/*/home": {"what": "A project's home."}, "button:Back up now": "A backup straight away."}),
        encoding="utf-8")
    monkeypatch.setenv("EAX_SHIPPED_DOCS", str(tmp_path))
    m = _module()
    monkeypatch.setattr(m, "_signed_in", lambda: None)
    return m


def test_a_marked_document_is_never_listed_found_or_read(docs):
    keys = {d["key"] for d in docs.documents()}
    assert "operations" in keys and "site~how-do-i~back-up-now" in keys and "secret-plan" not in keys
    assert not any(h["key"] == "secret-plan" for h in docs.search("backup"))
    assert "not for AI use" in docs.read("secret-plan")["error"]


def test_a_document_a_section_and_a_long_one_in_parts(docs, monkeypatch):
    whole = docs.read("operations")
    assert whole["title"] == "Operations" and whole["sections"] == ["Backups", "Pinning", "Restores"] and whole["next_start"] is None
    part = docs.read("operations", "Backups")
    assert part["text"].startswith("## Backups") and "Pinning" in part["text"] and "Restores" not in part["text"]
    assert docs.read("operations", "Nope")["sections"] == ["Backups", "Pinning", "Restores"]
    monkeypatch.setattr(docs, "PAGE", 10)
    first = docs.read("operations")
    assert len(first["text"]) == 10 and first["next_start"] == 10
    assert docs.read("operations", start=first["next_start"])["start"] == 10
    assert "error" in docs.read("no-such")


def test_error_codes_guides_and_their_pdf(docs):
    e = docs.read("EAX-AUTH-001")
    assert e["code"] == "EAX-AUTH-001" and e["to_do"]
    g = docs.read("guide:05-day-to-day-operations")
    assert g["pdf"] == "EA-Explorer-05-day-to-day-operations.pdf"
    assert g["chapters"] == [{"title": "Backups", "documents": ["site~how-do-i~back-up-now"]}]
    pdf = asyncio.run(docs.docs_pdf("05-day-to-day-operations"))
    assert base64.b64decode(pdf["base64"]) == b"%PDF-1.7 a guide" and pdf["link"].endswith("/manuals/EA-Explorer-05-day-to-day-operations.pdf")
    assert "error" in asyncio.run(docs.docs_pdf("99-none"))


def test_search_reaches_documents_error_codes_and_the_screens_help(docs):
    kinds = {h["kind"] for h in docs.search("backup")}
    assert {"document", "screen help", "error code"} <= kinds          # the backup error codes too
    assert any(h["kind"] == "error code" for h in docs.search("EAX-AUTH-001"))


def test_screen_help_by_key_by_words_and_by_pattern(docs):
    assert docs.screen("page:#/admin/backups")["help"]["what"].startswith("Every backup")
    assert docs.screen("Back up now")["key"] == "button:Back up now"            # the kind found by itself
    assert docs.screen("page:#/projects/abc-123/home")["key"] == "page:#/projects/*/home"
    assert "near" in docs.screen("nothing like it")


def test_the_tools_are_listed_read_only_and_for_everyone_signed_in(docs, monkeypatch):
    from eax import mcp_catalogue
    mcp_catalogue.tools.cache_clear() if hasattr(mcp_catalogue.tools, "cache_clear") else None
    mine = {t["name"]: t for t in mcp_catalogue.tools() if t["area"] == "EA Explorer's own documentation"}
    assert set(mine) == {"docs_list", "docs_search", "docs_read", "docs_pdf", "screen_help"}
    assert not any(t["changes"] for t in mine.values())
    src = (REPO / "services/api/eax/mcp_docs.py").read_text(encoding="utf-8")
    assert "require_" not in src and "permissions.can" not in src                 # no role needed (D797)
    monkeypatch.setattr(docs, "_signed_in", lambda: {"error": "Sign in required."})
    assert asyncio.run(docs.docs_list()) == {"error": "Sign in required."}      # but signed in


def test_the_api_has_the_guides_and_the_help_and_the_self_test_calls_the_tools():
    compose = (REPO / "docker-compose.yml").read_text(encoding="utf-8")
    assert "./documents:/data/docs/documents:ro" in compose
    assert "./services/web/src/help/catalogue.json:/data/docs/help/catalogue.json:ro" in compose
    assert "mcp_docs," in (REPO / "services/api/eax/mcp_server.py").read_text(encoding="utf-8")
    check = (REPO / "services/api/eax/testing/mcp_check.py").read_text(encoding="utf-8")
    assert '"words": "backup restore", "key": "readme", "guide": "01-overview"' in check and 'args["key"] = "page:#/"' in check
