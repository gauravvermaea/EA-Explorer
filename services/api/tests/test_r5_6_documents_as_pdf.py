"""R5.6: the restore drills as documents, and every document as a PDF (owner, 16 Nov 2026, 15:49: "Thease are documents
in the system to be read and made available for someone to manually do it. So document this for someone and also have
them available as pdf for download. Steps in comman line")."""
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
API = Path(__file__).resolve().parents[1]
REPO = API.parents[1]


def test_the_two_drills_are_documents_under_operations():
    os.environ["EAX_SHIPPED_DOCS"] = str(REPO)
    from eax import shipped_docs as D
    keys = {k: D.group_of(k) for k, _p in D._sources(D.root())}
    assert keys["backup-drill-new-machine"] == "Administration and operations"
    assert keys["backup-drill-monthly"] == "Administration and operations"
    for name in ("backup-drill-new-machine.md", "backup-drill-monthly.md"):
        text = (REPO / "docs" / name).read_text(encoding="utf-8")
        steps = re.findall(r"^\d+\. ", text, re.M)
        assert len(steps) >= 4 and "```" in text and "Check:" in text          # numbered command-line steps, each checked


def test_the_drills_use_only_commands_eax_has():
    """Every `eax <command>` in the drills is a command of eax's help."""
    help_ = (REPO / "eaxcli" / "help.txt").read_text(encoding="utf-8")
    known = {n for head in re.findall(r"^### ([a-z|-]+)", help_, re.M) for n in head.split("|")}   # stop|down: both
    for name in ("backup-drill-new-machine.md", "backup-drill-monthly.md", "backup-disaster-recovery.md"):
        text = (REPO / "docs" / name).read_text(encoding="utf-8")
        used = set(re.findall(r"`eax ([a-z-]+)", text)) | set(re.findall(r"^\s*eax ([a-z-]+)", text, re.M))
        assert used and used <= known, f"{name}: not commands of eax: {sorted(used - known)}"


def test_the_drills_make_a_pdf_and_any_document_could():
    os.environ["EAX_SHIPPED_DOCS"] = str(REPO)
    from eax import doc_pdf
    from eax import shipped_docs as D
    assert D.PDF_DOCS == {"backup-drill-new-machine", "backup-drill-monthly", "backup-disaster-recovery"}   # the drills and DR
    for k, p in D._sources(D.root()):
        t = p.read_text(encoding="utf-8")
        out = doc_pdf.pdf(D._title(t, k), t, "5.6.0", plain=k == "command-line-help")
        assert out.startswith(b"%PDF"), k


def test_markdown_is_escaped_and_lists_keep_their_numbers():
    from eax import doc_pdf
    assert doc_pdf.inline("<script>x</script> **b**") == "&lt;script&gt;x&lt;/script&gt; <b>b</b>"
    assert doc_pdf.inline("`a *b* c` and *i*") == '<font face="Courier">a *b* c</font> and <i>i</i>'
    flow = doc_pdf.flowables("3. three\n\n   ```\n   eax up\n   ```\n\n4. four\n")
    lists = [f for f in flow if type(f).__name__ == "ListFlowable"]
    assert [lst._start for lst in lists] == ["3", "4"]


def test_the_api_and_the_button_for_the_drills_only():
    api = (API / "eax/api/documentation.py").read_text()
    assert '@blp.route("/<string:key>/pdf")' in api and "doc_pdf.pdf(" in api and 'mimetype="application/pdf"' in api
    assert "if key not in D.PDF_DOCS:" in api                                     # any other document: 404
    page = (REPO / "services/web/src/Documentation.jsx").read_text()
    assert "{data.pdf && <button" in page and "Download PDF" in page
    os.environ["EAX_SHIPPED_DOCS"] = str(REPO)
    from eax import shipped_docs as D
    assert D.document("backup-drill-monthly")["pdf"] is True and D.document("operations")["pdf"] is False


def test_the_dr_document_covers_the_pack_the_move_and_the_dr_tool_in_the_web_and_as_a_pdf():
    """Owner, 16 Nov 2026, 22:07: "Please document in the application 1. How to create a DR pack (backup, version number,
    env file) 2. how to take it to another server 3. How to DR using the DR tool. Provide this in the DR document in web
    version and pdf"."""
    os.environ["EAX_SHIPPED_DOCS"] = str(REPO)
    from eax import doc_pdf
    from eax import shipped_docs as D
    keys = {k: D.group_of(k) for k, _p in D._sources(D.root())}
    assert keys["backup-disaster-recovery"] == "Administration and operations"
    doc = D.document("backup-disaster-recovery")
    assert doc["pdf"] and "Disaster recovery" in doc["title"]
    text = (REPO / "docs" / "backup-disaster-recovery.md").read_text(encoding="utf-8")
    for part in ("## 1. Create a DR pack", "### 1.1 The backup", "### 1.2 The version number", "### 1.3 The env file",
                 "## 2. Take the DR pack to another server", "## 3. Rebuild EA Explorer with the DR tool",
                 "## 4. The checksums and the fingerprint, explained", "## 5. Rehearse it: eax-drill",
                 "## 6. The commands, in full", "### eax dr-pack", "### eax-dr", "### eax-drill"):
        assert part in text, part
    assert "eax dr-pack" in text and ".\\eax-dr -Pack" in text and "./eax-dr.sh --pack" in text and ".\\dr\\eax-drill -Install" in text
    for opt in ("-Pack", "-Install", "-Backup", "-Version", "-Env", "-Project", "-Repo", "-Dr", "-Temp"):
        assert f"`{opt}`" in text, opt                                  # every option of the commands explained
    assert "PACK.sha256" in text and "fingerprint.json" in text
    assert len(re.findall(r"^\s*\d+\. ", text, re.M)) >= 10 and text.count("Check:") >= 7
    pdf = doc_pdf.pdf(doc["title"], text, "5.6.0")
    assert pdf.startswith(b"%PDF") and len(pdf) > 5000


def test_a_long_command_line_is_wrapped_in_the_pdf_never_cut_off():
    from eax import doc_pdf
    line = "  ./eax-dr.sh --backup <backup folder> --install <folder> --version <x.y.z> --env <file> [--project <name>] [--repo <link>]"
    out = doc_pdf.wrap_code([line])
    assert len(out) == 2 and all(len(x) <= doc_pdf.CODE_WIDTH for x in out)
    assert " ".join(x.strip() for x in out) == line.strip() and out[1].startswith("      ")
