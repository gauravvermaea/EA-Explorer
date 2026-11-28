"""eax test backup-cases (and in eax test full, after the backup and restore test): model and project backups and
restores, case by case, through the eax commands a person types (owner, 28 Nov 2026, 09:05: "I need very very detailed
test suite to test backups and restores are working from command line using the commands including model and project
zip backups with finger printing"; 09:08: "after a backup is done its zip file should be checked ... try schedule backup
test. You can say backup 10 seconds from now, let it backup make changes and restore the backup to ensure scheduled
backups work"; D971).

Every step runs a real eax command through this machine's own launcher (as eax test commands does) and waits for it;
between the commands the API container's helper (python -m eax.testing.backup_cases) makes the test's content, takes
fingerprints and makes changes. A model's fingerprint holds its metamodel (with the standard versions, D965), entities,
values, relationships, drawn views, KPIs and icons, without database ids, so a model restored as a new model is
compared with the one it came from; a project's holds its steps, document classes, stakeholders, key questions,
canvases, documents, models and each document file's SHA-256. Unlike the backup and restore test (B1/B2), a case that
fails does not stop the others: each is a result.

The cases (the report says each one's result, with why):
  C0  the fingerprints are stable: taken twice with nothing done, the same
  C1  eax app-backup (everything): made, every file checked as it was written, eax check-backup agrees, the test's
      models and project are in it
  C2  a model restored as a new model from the application backup (eax restore-model <run> <file> --new): the same as
      the model it came from
  C3  eax model-backup: one model's own backup, checked; restored as a new model (eax restore-model model ...): the same
  C4  the model changed (added, renamed, deleted, related) and put back over itself from its own backup (--over): as it
      was, ids kept; a restore log written (eax restore-log)
  C5  the same backup put back over itself again: the same again
  C6  a child model restored as a new model: the same as the child
  C7  the root metamodel backed up (eax model-backup) and restored as a new root: its metamodel the same, with the
      ArchiMate version of every item (D965, D969)
  C8  eax project-backup and eax restore-project --new: the project back with its steps, classes, stakeholders, key
      questions, canvases, documents and each document's file (SHA-256)
  C9  eax app-backup --models ... --projects ... then the models and project changed, the child model deleted and a model
      made: eax restore-app puts the models and project back, makes the deleted model again and leaves the new one as it is
  C8  (also) the project changed and put back over itself from its own file (eax restore-project --over)
  C10 a copy of a good file brought from elsewhere, and one as made before fingerprints, both restore (eax restore-model
      uploaded ...); files that are not good backups are refused, by eax check-backup and by eax restore-model, and
      nothing changes: not a zip, a zip without backup.json, cut short, from a newer release, changed after it was made;
      an unknown backup for restore-app; a path for check-backup
  C11 the scheduled application backup (the Backups page's schedule, set to the coming minute): it runs, its files check
      out, the model changed and put back from it
  C12 a scheduled eax command (eax schedule add --once ... -- app-backup ...): it runs, then eax restore-app from it
      puts the changed model back
  C13 the restores' records removed (eax delete-restore)
  C14 no password, key or token in any command's output
  C15 the test leaves nothing: its models, projects and backups removed, the schedules and keep as they were, and every
      backup that is not the test's is still there, the same size

The report: work/tests/backup-cases-<time>/report.md and report.json.
"""

from __future__ import annotations

import json
import re
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .backup_restore import config_secrets, run_in, secrets_in
from .command_tests import run_one
from .core import EAX, ROOT, WORK, log_only, say

API = ["exec", "-T", "api", "python", "-m", "eax.testing.backup_cases"]
LONG, SHORT = 3600, 900          # seconds allowed: a whole application backup, anything else
SCHEDULE_WAIT = 300              # seconds to wait for a scheduled backup to run and finish


def file_for(listing: str, guid: str) -> str:
    """The backup file of a model or project (by the start of its guid) in eax check-backup's listing (pure)."""
    g = (guid or "")[:8]
    for line in listing.splitlines():
        m = re.search(r"\b(ok |BAD)\s+(\S+\.eax(?:backup|project)\.zip)\b", line)
        if m and g and g in m.group(2):
            return m.group(2)
    return ""


def said(output: str, label: str) -> str:
    """The value after "<label>: " in a command's output (pure)."""
    m = re.search(rf"^{re.escape(label)}:\s*(\S+)", output or "", re.M)
    return m.group(1) if m else ""


def restore_id(output: str) -> str:
    """The restore's record in "Log: work/backups/restores/<id>/restore.log" (pure)."""
    m = re.search(r"restores/([A-Za-z0-9._-]+)/restore\.log", output or "")
    return m.group(1) if m else ""


def once_at(zone, now: datetime | None = None) -> str:
    """A time for eax schedule add --once: the coming minute (two when this one is nearly over), in the zone (pure)."""
    now = (now or datetime.now(UTC)).astimezone(zone)
    at = (now + timedelta(minutes=2 if now.second >= 40 else 1)).replace(second=0, microsecond=0)
    return at.strftime("%Y-%m-%dT%H:%M")


class Cases:
    """The results, the commands' outputs (for C14) and the report."""

    def __init__(self, folder: Path, api=None, eax=None, clock=time.time, sleep=time.sleep):
        self.folder, self.clock, self.sleep = folder, clock, sleep
        self.api = api or (lambda cmd, state: run_in(API, [cmd], state))
        self.eax = eax or (lambda args, seconds: run_one(args, seconds)[:2])
        self.results: list[dict] = []
        self.outputs: list[str] = []
        self.commands: list[dict] = []
        self.restores: list[str] = []
        self.started = clock()

    def rec(self, case: str, name: str, ok: bool | None, detail: str = "") -> bool:
        """A result: printed, logged and kept for the report (ok None: skipped, with why)."""
        self.results.append({"case": case, "name": f"{case} {name}", "ok": ok, "detail": str(detail)[:1500]})
        mark = "ok  " if ok else "skip" if ok is None else "FAIL"
        say(f"  {mark} {case} {name}{': ' + str(detail)[:240] if detail and not ok else ''}",
            "green" if ok else "yellow" if ok is None else "red")
        log_only(f"backup-cases: {mark} {case} {name}: {detail}")
        return bool(ok)

    def run(self, args: list[str], seconds: int = SHORT) -> tuple[int, str]:
        """One eax command, as a person types it; its exit code and output (kept for C14)."""
        line = " ".join([EAX, *args])
        say(f"  $ {line}", "cyan")
        t0 = self.clock()
        code, out = self.eax(args, seconds)
        self.outputs.append(out or "")
        self.commands.append({"command": line, "exit": code, "seconds": round(self.clock() - t0, 1),
                              "tail": (out or "").strip()[-600:]})
        rid = restore_id(out)
        if rid and rid not in self.restores:
            self.restores.append(rid)
        return code, out or ""

    def helper(self, cmd: str, state: dict) -> dict:
        """One command of the API container's helper (eax.testing.backup_cases): its JSON answer."""
        out = self.api(cmd, state)
        return out if isinstance(out, dict) else {"error": "no answer"}

    def same_model(self, case: str, name: str, before: dict, guid: str, keys: bool = False, only: str = "") -> bool:
        """A result: the model now has the fingerprint it had (keys: its ids too; only="metamodel": that part only)."""
        fp = self.helper("fingerprint", {"models": [guid]}).get("models", {}).get(guid, {"missing": True})
        diff = self.helper("compare", {"kind": "model", "before": before, "after": fp, "keys": keys, "only": only})
        d = diff.get("differences")
        if d is None:
            return self.rec(case, name, False, diff.get("error") or "the comparison did not answer")
        return self.rec(case, name, not d, "; ".join(d) or f"{sum(v for v in fp.get('counts', {}).values() if isinstance(v, int))} rows compared")

    def same_project(self, case: str, name: str, before: dict, guid: str, whole: bool = False, tries: int = 1) -> bool:
        """A result: the project now has the fingerprint it had (whole: every table too), asked again while its
        documents are still being put back."""
        d, fp = None, {}
        for i in range(tries):        # the documents come back once the repository is built (a minute or two)
            fp = self.helper("fingerprint", {"projects": [guid]}).get("projects", {}).get(guid, {"missing": True})
            d = self.helper("compare", {"kind": "project", "before": before, "after": fp, "whole": whole}).get("differences")
            if d == [] or i == tries - 1:
                break
            self.sleep(30)
        if d is None:
            return self.rec(case, name, False, "the comparison did not answer")
        return self.rec(case, name, not d, "; ".join(d) or f"{fp.get('file_count', 0)} document file(s) compared")


def _ok(code: int, out: str, *words: str) -> tuple[bool, str]:
    """A command that should work: exit 0 and the words in its output (pure)."""
    low = out.lower()
    missing = [w for w in words if w.lower() not in low]
    if code != 0:
        return False, f"exit {code}: {' '.join(out.strip().splitlines()[-2:])[-300:]}"
    if missing:
        return False, f"its output does not say {', '.join(missing)}"
    return True, ""


def _refused(code: int, out: str, *words: str) -> tuple[bool, str]:
    """A command that should be refused: a non-zero exit and one of the words in its output (pure)."""
    low = out.lower()
    if code == 0:
        return False, "it was not refused (exit 0)"
    if words and not any(w.lower() in low for w in words):
        return False, f"refused (exit {code}) but without saying why: {' '.join(out.strip().splitlines()[-2:])[-200:]}"
    return True, f"refused (exit {code})"


def run(c: Cases) -> dict:
    """Every case, one after another (see the module)."""
    st = c.helper("start", {"by": "eax test backup-cases", "folder": str(c.folder), "version": ""})
    if st.get("error"):
        c.rec("C0", "the test's models and project made", False, st["error"])
        return st
    for m in st.get("made") or []:
        if not m["ok"]:
            c.rec("C0", f"made: {m['what']}", False, m.get("detail"))
    ids, sid = st["ids"], st["sid"]
    m1, m2, proj = ids.get("model", ""), ids.get("other_model", ""), ids.get("project", "")
    prefix = f"brc-{sid}"
    base = {"token": st["token"], "sid": sid, "run_id": st["run_id"], "schedules_saved": st.get("schedules_saved")}
    made_models: dict[str, str] = {}
    made_projects: dict[str, str] = {}
    root_guid = ""
    others0 = c.helper("others", {"prefix": prefix, "models": [m1, m2], "projects": [proj]}).get("files")
    try:
        fp0 = c.helper("fingerprint", {"models": [m1, m2], "projects": [proj] if proj else []})
        fp0b = c.helper("fingerprint", {"models": [m1, m2], "projects": [proj] if proj else []})
        F1, F2 = fp0["models"][m1], fp0["models"][m2]
        P0 = (fp0.get("projects") or {}).get(proj) if proj else None
        diff = c.helper("compare", {"kind": "model", "before": F1, "after": fp0b["models"][m1], "keys": True}).get("differences")
        c.rec("C0", "the fingerprints are stable", diff == [], "; ".join(diff or []) or
              f"{F1['counts'].get('entities')} entities, {F1['counts'].get('relationships')} relationships, "
              f"{F1['counts'].get('allowed')} allowed relationships")

        # C1: everything
        code, out = c.run(["app-backup", f"{prefix}-all"], LONG)
        ok, why = _ok(code, out, "every file checked")
        c.rec("C1", "eax app-backup (everything), every file checked as it was written", ok, why)
        run_all = said(out, "Run")
        code, listing = c.run(["check-backup", run_all or f"{prefix}-all"])
        ok, why = _ok(code, listing, "checked out")
        c.rec("C1", "eax check-backup: the application backup checks out", ok, why)
        f1, f2 = file_for(listing, m1), file_for(listing, m2)
        fp_ = file_for(listing, proj) if proj else ""
        c.rec("C1", "the test's models and project are in it", bool(f1 and f2 and (fp_ or not proj)),
              f"model 1: {f1 or 'missing'}; model 2: {f2 or 'missing'}; project: {fp_ or ('missing' if proj else 'none')}")

        # C2: a model as a new model from the application backup
        if f1:
            name = f"self_test_{sid}_brc_from_app"
            code, out = c.run(["restore-model", run_all, f1, "--new", name, "--yes"])
            ok, why = _ok(code, out)
            c.rec("C2", "eax restore-model <run> <file> --new", ok, why)
            new = c.helper("find", {"models": [name]})["models"].get(name, "")
            made_models[new] = name
            c.same_model("C2", "the new model is the same as the one backed up", F1, new)

        # C3: the model's own backup, as a new model
        code, out = c.run(["model-backup", m1, f"{prefix}-own"])
        ok, why = _ok(code, out, "file checked")
        c.rec("C3", "eax model-backup, the file checked as it was written", ok, why)
        own = said(out, "File")
        code, o2 = c.run(["check-backup", own]) if own else (1, "no file")
        ok, why = _ok(code, o2, "checked out")
        c.rec("C3", "eax check-backup <file>: the model backup checks out", ok, why)
        if own:
            name = f"self_test_{sid}_brc_from_own"
            code, out = c.run(["restore-model", "model", m1, own, "--new", name, "--yes"])
            ok, why = _ok(code, out)
            c.rec("C3", "eax restore-model model <model> <file> --new", ok, why)
            new = c.helper("find", {"models": [name]})["models"].get(name, "")
            made_models[new] = name
            c.same_model("C3", "the new model is the same as the one backed up", F1, new)

            # C4: changed, then put back over itself
            ch = c.helper("change_model", {**base, "model": m1})
            c.rec("C4", "the model changed after the backup", bool(ch.get("ok")), "; ".join(
                f"{m['what']}: {m['detail']}" for m in ch.get("made") or [] if not m["ok"]) or ch.get("error", ""))
            changed = c.helper("fingerprint", {"models": [m1]})["models"][m1]
            d = c.helper("compare", {"kind": "model", "before": F1, "after": changed}).get("differences")
            c.rec("C4", "the fingerprint sees the changes", bool(d), "; ".join(d or []) or "no difference seen")
            code, out = c.run(["restore-model", "model", m1, own, "--over", "--yes"])
            ok, why = _ok(code, out)
            c.rec("C4", "eax restore-model model <model> <file> --over", ok, why)
            c.same_model("C4", "the model is as it was when backed up", F1, m1)
            c.same_model("C4", "its entities and relationships keep their ids and display IDs", F1, m1, keys=True)
            rid = restore_id(out)
            code, log = c.run(["restore-log", rid]) if rid else (1, "no restore id in the output")
            ok, why = _ok(code, log, "restore")
            c.rec("C4", "the restore's log is written (eax restore-log)", ok, why)

            # C5: the same again
            code, out = c.run(["restore-model", "model", m1, own, "--over", "--yes"])
            ok, why = _ok(code, out)
            c.rec("C5", "the same backup put back over itself again", ok, why)
            c.same_model("C5", "the model is the same again", F1, m1)

        # C6: the child model as a new model
        if f2:
            name = f"self_test_{sid}_brc_child"
            code, out = c.run(["restore-model", run_all, f2, "--new", name, "--yes"])
            ok, why = _ok(code, out)
            c.rec("C6", "the child model restored as a new model", ok, why)
            new = c.helper("find", {"models": [name]})["models"].get(name, "")
            made_models[new] = name
            c.same_model("C6", "the same as the child model", F2, new)

        # C7: the root metamodel, with its standard versions
        root_guid = c.helper("find", {"models": ["ArchiMate 4"]})["models"].get("ArchiMate 4", "")
        if root_guid:
            R0 = c.helper("fingerprint", {"models": [root_guid]})["models"][root_guid]
            code, out = c.run(["model-backup", root_guid, f"{prefix}-root"])
            ok, why = _ok(code, out, "file checked")
            c.rec("C7", "the root metamodel backed up", ok, why)
            rf = said(out, "File")
            name = f"self_test_{sid}_brc_root"
            code, out = c.run(["restore-model", "model", root_guid, rf, "--new", name, "--yes"]) if rf else (1, "no file")
            ok, why = _ok(code, out)
            c.rec("C7", "the root metamodel restored as a new root", ok, why)
            new = c.helper("find", {"models": [name]})["models"].get(name, "")
            made_models[new] = name
            c.same_model("C7", "its metamodel is the same, with the ArchiMate version of every item", R0, new, only="metamodel")
        else:
            c.rec("C7", "the root metamodel", None, "no model called ArchiMate 4 here")

        # C8: a project's own backup, as a new project
        if proj and P0:
            code, out = c.run(["project-backup", proj, f"{prefix}-proj"])
            ok, why = _ok(code, out, "file checked")
            c.rec("C8", "eax project-backup, the file checked as it was written", ok, why)
            pf = said(out, "File")
            code, o2 = c.run(["check-backup", pf]) if pf else (1, "no file")
            ok, why = _ok(code, o2, "checked out")
            c.rec("C8", "eax check-backup <file>: the project backup checks out", ok, why)
            name = f"self_test_{sid}_brc_project"
            code, out = c.run(["restore-project", proj, pf, "--new", name, "--yes"]) if pf else (1, "no file")
            ok, why = _ok(code, out)
            c.rec("C8", "eax restore-project <project> <file> --new", ok, why)
            newp = c.helper("find", {"projects": [name]})["projects"].get(name, "")
            made_projects[newp] = name
            c.helper("register", {**base, "models": {}, "projects": {newp: name}})
            c.same_project("C8", "the new project is the same, with its documents' files", P0, newp, tries=6)
            if pf:                                   # C8b: the project changed, then put back over itself from its own file
                c.helper("change_project", {**base, "project": proj, "canvas": ids.get("canvas", "")})
                code, out = c.run(["restore-project", proj, pf, "--over", "--yes"])
                ok, why = _ok(code, out)
                c.rec("C8", "eax restore-project <project> <file> --over", ok, why)
                c.same_project("C8", "the project is back as it was over itself, with its documents' files", P0, proj, tries=6)
        else:
            c.rec("C8", "a project's own backup", None, "no project was made for the test")

        # C9: part of the application, then restore-app
        args = ["app-backup", f"{prefix}-part", "--models", f"{m1},{m2}"] + (["--projects", proj] if proj else [])
        code, out = c.run(args)
        ok, why = _ok(code, out, "every file checked")
        c.rec("C9", "eax app-backup --models ... --projects ...", ok, why)
        run_part = said(out, "Run")
        c.helper("change_model", {**base, "model": m1})
        if proj:
            c.helper("change_project", {**base, "project": proj, "canvas": ids.get("canvas", "")})
        dm = c.helper("delete_model", {**base, "model": m2})
        c.rec("C9", "the child model deleted", not dm.get("error"), dm.get("error", ""))
        after_name = f"self_test_{sid}_brc_after"
        nm = c.helper("new_model", {**base, "name": after_name})
        N0 = c.helper("fingerprint", {"models": [nm.get("model", "")]})["models"].get(nm.get("model", ""), {"missing": True})
        code, out = c.run(["restore-app", run_part or f"{prefix}-part", "--yes"], LONG)
        ok, why = _ok(code, out)
        c.rec("C9", "eax restore-app <run>", ok, why)
        c.same_model("C9", "the changed model is back as it was", F1, m1)
        m2_again = c.helper("find", {"models": [F2.get("name", "")]})["models"].get(F2.get("name", ""), "")
        made_models[m2_again] = F2.get("name", "")
        c.same_model("C9", "the deleted model is made again, the same", F2, m2_again)
        c.same_model("C9", "a model made after the backup stays as it is", N0, nm.get("model", ""))
        if proj and P0:
            c.same_project("C9", "the project is back as it was (its steps, canvas, stakeholders, documents)", P0, proj, tries=6)
            c.same_project("C9", "every table of the project is back as it was", P0, proj, whole=True)

        # C10: files that are not good backups
        good = f"{run_part}/models/{file_for(c.run(['check-backup', run_part])[1], m1)}" if run_part else ""
        before = c.helper("fingerprint", {"models": [m1]})["models"][m1]
        forged = c.helper("forge", {**base, "good": good}).get("files") or {}
        why_words = ("did not check out", "not an ea explorer", "newer", "not restored", "damaged", "cannot", "not a readable")
        for case in ("copy", "old"):              # good files: one brought from elsewhere, one from before fingerprints
            file = forged.pop(case, "")
            if not file:
                continue
            code, out = c.run(["check-backup", file])
            ok, why = _ok(code, out, "checked out")
            c.rec("C10", f"eax check-backup passes the {case} file", ok, why)
            name = f"self_test_{sid}_brc_good_{case}"
            code, out = c.run(["restore-model", "uploaded", file, "--new", name, "--yes"])
            ok, why = _ok(code, out)
            c.rec("C10", f"eax restore-model uploaded <{case} file> --new", ok, why)
            new = c.helper("find", {"models": [name]})["models"].get(name, "")
            made_models[new] = name
            c.same_model("C10", f"the model from the {case} file is the same as the one backed up", F1, new)
        for case, file in forged.items():
            code, out = c.run(["check-backup", file])
            ok, why = _refused(code, out, "not ok")
            c.rec("C10", f"eax check-backup finds the {case} file not right", ok, why)
            name = f"self_test_{sid}_brc_bad_{case.replace('-', '_')}"
            code, out = c.run(["restore-model", "uploaded", file, "--new", name, "--yes"])
            ok, why = _refused(code, out, *why_words)
            c.rec("C10", f"eax restore-model refuses the {case} file", ok, why)
            leftover = c.helper("find", {"models": [name]})["models"].get(name, "")
            if leftover:
                made_models[leftover] = name
            c.rec("C10", f"no model made from the {case} file", not leftover, f"a model {name} was made" if leftover else "")
        code, out = c.run(["restore-app", f"{prefix}-no-such-backup", "--yes"])
        ok, why = _refused(code, out, "no application backup")
        c.rec("C10", "eax restore-app refuses a backup that does not exist", ok, why)
        code, out = c.run(["check-backup", "../manifest.json"])
        ok, why = _refused(code, out, "not a path", "file name")
        c.rec("C10", "eax check-backup refuses a path", ok, why)
        c.same_model("C10", "nothing changed while the files were refused", before, m1, keys=True)

        # C11: the scheduled application backup (Administration > Backups)
        sched = c.helper("schedule_next", {**base, "tag": f"{prefix}-sched"})
        c.rec("C11", "the application backup scheduled for the coming minute", not sched.get("error"),
              sched.get("error") or f"{sched.get('cron')} ({sched.get('zone')})")
        found = _wait_run(c, f"{prefix}-sched")
        c.helper("schedule_reset", base)
        c.rec("C11", "the scheduled backup ran and finished", bool(found), (found or {}).get("name") or "none within five minutes")
        if found:
            code, out = c.run(["check-backup", found["name"]])
            ok, why = _ok(code, out, "checked out")
            c.rec("C11", "its files check out", ok, why)
            mf = file_for(out, m1)
            c.helper("change_model", {**base, "model": m1})
            code, out = c.run(["restore-model", found["name"], mf, "--over", "--yes"]) if mf else (1, "the model is not in it")
            ok, why = _ok(code, out)
            c.rec("C11", "the changed model put back from the scheduled backup", ok, why)
            c.same_model("C11", "the model is as it was", F1, m1)

        # C12: a scheduled eax command
        from .schedules import zone
        at = once_at(zone(ROOT))
        sname = f"{prefix}-schedule"
        code, out = c.run(["schedule", "add", sname, "--once", at, "--", "app-backup", f"{prefix}-cmd", "--models", m1])
        ok, why = _ok(code, out)
        c.rec("C12", f"eax schedule add ... --once {at} -- app-backup ...", ok, why)
        found = _wait_run(c, f"{prefix}-cmd") if ok else None
        c.run(["schedule", "remove", sname])
        c.rec("C12", "the scheduled command ran and its backup finished", bool(found), (found or {}).get("name") or "none within five minutes")
        if found:
            c.helper("change_model", {**base, "model": m1})
            code, out = c.run(["restore-app", found["name"], "--yes"], LONG)
            ok, why = _ok(code, out)
            c.rec("C12", "eax restore-app from the scheduled command's backup", ok, why)
            c.same_model("C12", "the model is as it was", F1, m1)

        # C13: the restores' records
        gone = [rid for rid in list(c.restores) if c.run(["delete-restore", rid])[0] == 0]
        c.rec("C13", "the restores' records removed (eax delete-restore)", len(gone) == len(c.restores),
              f"{len(gone)} of {len(c.restores)} removed")
    except Exception as exc:  # noqa: BLE001 - a case that broke the run: said, then the clean-up still runs
        c.rec("C?", "the cases ran to the end", False, f"{type(exc).__name__}: {exc}")
    finally:
        c.helper("register", {**base, "models": {k: v for k, v in made_models.items() if k}, "projects": {}})
        values = config_secrets(WORK / "eaexplorer.env") + [st.get("token") or ""]
        leaked = secrets_in("\n".join(c.outputs), values)
        c.rec("C14", "no password, key or token in any command's output", not leaked, ", ".join(leaked))
        own_models = [g for g in [m1, m2, *made_models] if g]          # the test's own: their backup folders go
        mine = {"prefix": prefix, "models": own_models, "shared_models": [root_guid] if root_guid else [],
                "projects": [g for g in [proj, *made_projects] if g]}
        fin = c.helper("finish", {**base, "results": c.results, **mine})
        left = c.helper("files_of", mine)
        names = [f"self_test_{sid}_1", f"self_test_{sid}_2", *made_models.values()]
        still = [n for n, g in (c.helper("find", {"models": names, "projects": [f"self_test_{sid}_3", *made_projects.values()]})
                                .get("models") or {}).items() if g]
        leftovers = [k for k in ("runs", "models", "shared", "projects", "uploaded") if left.get(k)]
        others1 = c.helper("others", {"prefix": prefix, "models": [m1, m2], "projects": [proj]}).get("files")
        gone_ = sorted(set(others0 or []) - set(others1 or []))
        new_ = sorted(set(others1 or []) - set(others0 or []))
        c.rec("C15", "no one else's backup was touched (the same files, the same sizes, before and after)",
              others0 is not None and not gone_ and not new_,
              "; ".join([f"gone: {', '.join(gone_[:5])}"] * bool(gone_) + [f"new: {', '.join(new_[:5])}"] * bool(new_))
              or f"{len(others0 or [])} files")
        c.rec("C15", "the test leaves nothing behind", not fin.get("error") and not leftovers and not still,
              fin.get("error") or fin.get("purge_error") or fin.get("schedules_error") or
              "; ".join([f"backups left: {', '.join(leftovers)}"] * bool(leftovers) + [f"models left: {', '.join(still)}"] * bool(still))
              or f"removed: {json.dumps(fin.get('removed') or {})}")
    return st


def _wait_run(c: Cases, tag: str) -> dict | None:
    """The application backup with this tag, once it has finished (or None after SCHEDULE_WAIT seconds)."""
    end = c.clock() + SCHEDULE_WAIT
    while c.clock() < end:
        runs = c.helper("runs", {"prefix": tag}).get("runs") or []
        done = [r for r in runs if r.get("status") in ("ok", "partial")]
        if done:
            return done[0]
        c.sleep(10)
    return None


def report(c: Cases) -> dict:
    """report.json and report.md; the summary returned."""
    c.folder.mkdir(parents=True, exist_ok=True)
    failed = [r for r in c.results if r["ok"] is False]
    rep = {"passed": not failed and bool(c.results), "minutes": round((c.clock() - c.started) / 60, 1),
           "counts": {"passed": sum(1 for r in c.results if r["ok"]), "failed": len(failed),
                      "skipped": sum(1 for r in c.results if r["ok"] is None)},
           "results": c.results, "commands": c.commands}
    (c.folder / "report.json").write_text(json.dumps(rep, indent=1, default=str), encoding="utf-8")
    md = ["# eax test backup-cases", "",
          f"{'PASSED' if rep['passed'] else 'FAILED'} in {rep['minutes']} minutes: {rep['counts']['passed']} passed, "
          f"{rep['counts']['failed']} failed, {rep['counts']['skipped']} skipped.", "",
          "| Case | Result | Detail |", "|---|---|---|"]
    md += [f"| {r['name']} | {'pass' if r['ok'] else 'skip' if r['ok'] is None else 'FAIL'} | "
           f"{str(r['detail']).replace('|', '/')[:300]} |" for r in c.results]
    md += ["", "## The commands run", "", "| Command | Exit | Seconds |", "|---|---|---|"]
    md += [f"| `{x['command']}` | {x['exit']} | {x['seconds']} |" for x in c.commands]
    (c.folder / "report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return rep


def main(args: list[str]) -> int:
    """eax test backup-cases: the cases, one after another; it asks nothing."""
    folder = WORK / "tests" / f"backup-cases-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"
    say(f"Backup and restore cases: model and project backups through the eax commands; the report goes to "
        f"{folder.relative_to(ROOT)}. The test makes its own models and project, and removes them at the end.", "cyan")
    c = Cases(folder)
    run(c)
    rep = report(c)
    say(f"Backup and restore cases {'PASSED' if rep['passed'] else 'FAILED'} in {rep['minutes']} minutes "
        f"({rep['counts']['passed']} passed, {rep['counts']['failed']} failed). Report: {(folder / 'report.md').relative_to(ROOT)}",
        "green" if rep["passed"] else "red")
    return 0 if rep["passed"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
