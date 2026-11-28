"""Application backups and model restores from the command line (phase 8.4, D227), for when the screens cannot be used.

Run in the api container by the eax command:
    .\\eax app-backup [tag]              every model, and every project with its documents, backed up now
    .\\eax restore-model                 choose an application backup, a model in it, then: as a new model or over itself
    .\\eax restore-model <run> <file> [--new "<name>" | --over] [--yes]
    .\\eax restore-app [run|tag|latest] [--yes]   every model of an application backup put back over itself; models no
                                         longer there are made again; models made since stay as they are (D233)
                                         then every project in it over itself, with its documents (owner, 7 Nov 2026)
    .\\eax model-backup <model> [why]   one model backed up now, as its Model Admin does on the model page (D970)
    .\\eax restore-model model <model> <file> [--new "<name>" | --over] [--yes]   from one of that model's own backups
    .\\eax project-backup <project> [why]   one project backed up now, with its models and documents (D970)
    .\\eax restore-project <project|run> <file> [--new "<name>" | --over] [--yes]   a project from one of its own backups,
                                         or from an application backup (run): as a new project, or over itself
    .\\eax check-backup [latest|all|<run>|<tag>|<file>]   a backup's files checked: each zip, its fingerprint, its
                                         contents (D968); 1 when any is not right
Every backup is also checked as soon as it is written: a file that does not check out is not kept.
Every restore is recorded with its log in work/backups/restores (listed by .\\eax restores and on Administration >
Restores). It runs as the system with the Super Admin's rights, so whoever runs it on the server must be trusted to.
"""

from __future__ import annotations

import sys

from . import backups as bk
from . import permissions as perms
from .db import get_engine
from .metamodel_edit import EditError

SYSTEM = perms.Principal("eax-command", (perms.SUPER_ADMIN,))


def _ask(prompt: str, choices: list[str] | None = None) -> str:
    while True:
        try:
            answer = input(prompt).strip()
        except EOFError:
            return ""
        if not choices or answer in choices:
            return answer
        print(f"  Type one of: {', '.join(c or '(empty)' for c in choices)}")


def _pick(rows: list, label) -> int | None:
    for i, r in enumerate(rows, 1):
        print(f"  {i:>3}  {label(r)}")
    n = _ask(f"Which (1-{len(rows)}, empty to stop)? ", [""] + [str(i) for i in range(1, len(rows) + 1)])
    return int(n) - 1 if n else None


def _list_option(args: list[str], name: str) -> list[str]:
    """--models a,b (or --projects ...): the names or ids given, [] when the option is not there (pure)."""
    if name in args and args.index(name) + 1 < len(args):
        return [x.strip() for x in args[args.index(name) + 1].split(",") if x.strip()]
    return []


def backup(args: list[str] | str) -> int:
    """eax app-backup [tag] [--models <a,b>] [--projects <p,q>]: an application backup now (of everything, or only the
    models and projects named, D970), its folder said."""
    args = [args] if isinstance(args, str) else list(args)
    models, projects = _list_option(args, "--models"), _list_option(args, "--projects")
    if projects and not models:
        print("--projects goes with --models (the models backed up with them); without either, everything is backed up.")
        return 2
    tag = next((a for i, a in enumerate(args) if not a.startswith("--") and (i == 0 or args[i - 1] not in ("--models", "--projects"))), "")
    with get_engine().begin() as conn:
        guids = []
        for m in models:
            bk._bypass(conn, True)
            try:
                guids.append(str(bk.repo.get_model(conn, m)["id"]))
            except bk.repo.NotFound:
                print(f"No model {m}: nothing backed up.")
                return 1
        msg, out = bk.application_backup(conn, SYSTEM, tag or "eax-command", models=guids or None, projects=projects or None)
    print(msg)
    print(f"Folder: work/backups/application/{out['name']}")
    print(f"Run: {out['name']}")
    return 0 if not out.get("failed") else 1


def restore_model(args: list[str]) -> int:
    """eax restore-model: one model restored from an application backup (or an uploaded file), as a new model or over
    itself."""
    runs = [r for r in bk.list_application()["runs"] if r.get("status") in ("ok", "partial")]
    uploaded = bk.list_application()["uploaded"]
    where, name, file = "application", "", ""
    positional = [a for a in args if not a.startswith("--") and a not in _option_values(args)]
    model_guid = ""
    if len(positional) >= 3 and positional[0] == "model":          # one of a model's own backups (D970)
        with get_engine().begin() as conn:
            bk._bypass(conn, True)
            model_guid = str(bk.repo.get_model(conn, positional[1])["id"])
        where, name, file = "model", "", positional[2]
    elif len(positional) >= 2:
        name, file = positional[0], positional[1]
        where = "uploaded" if name == "uploaded" else "application"
    else:
        if not runs and not uploaded:
            print("No application backup to restore from: make one with .\\eax app-backup")
            return 1
        print("Application backups (work/backups/application):")
        choices = [("application", r) for r in runs] + [("uploaded", u) for u in uploaded]
        i = _pick(choices, lambda x: f"{bk.human(x[1].get('created', ''))}  {x[1].get('tag') or 'uploaded: ' + x[1]['model']['name']}"
                  f"  ({len([m for m in x[1].get('models') or [] if m.get('status') == 'ok']) or 1} model(s))")
        if i is None:
            return 1
        where, chosen = choices[i]
        if where == "uploaded":
            name, file = "", chosen["file"]
        else:
            name = chosen["name"]
            models = [m for m in chosen.get("models") or [] if m.get("status") == "ok"]
            print(f"Models in {chosen.get('tag')}:")
            j = _pick(models, lambda m: f"{m['name']}  ({m.get('kind')}, {(m.get('counts') or {}).get('entities', 0)} entities)")
            if j is None:
                return 1
            file = models[j]["file"]
    try:
        path = bk.path_of(where, name, file, model_guid)
        info, z = bk.read_file(path)
    except EditError as exc:
        print(f"Not restored: {exc}")
        return 1
    z.close()
    mode = "over" if "--over" in args else "new" if "--new" in args else ""
    if not mode:
        print(f"  1  as a new model (a draft, next to {info['model']['name']})")
        if where != "uploaded" and info["model"].get("kind") != "template":
            print(f"  2  over {info['model']['name']} (it goes back to how it was in this backup; what it is now is backed up first)")
        mode = {"1": "new", "2": "over"}.get(_ask("How (1 or 2)? ", ["1", "2"]), "new")
    new_name = args[args.index("--new") + 1] if "--new" in args and args.index("--new") + 1 < len(args) else ""
    if mode == "new" and not new_name and "--yes" not in args:
        new_name = _ask(f"Name of the new model (empty: '{info['model']['name']} (restored ...)'): ")
    if "--yes" not in args:
        what = f"over {info['model']['name']}" if mode == "over" else f"as the new model '{new_name or info['model']['name'] + ' (restored ...)'}'"
        if _ask(f"Restore {file} {what}? Type RESTORE to go on: ") != "RESTORE":
            print("Nothing restored.")
            return 1
    try:
        with get_engine().begin() as conn:
            msg, out = bk.restore(conn, SYSTEM, {"where": where, "name": name, "file": file,
                                                 "model": model_guid or info["model"]["id"],
                                                 "mode": mode, "new_name": new_name, "target": model_guid or info["model"]["id"]})
    except EditError as exc:
        print(f"Not restored: {exc}")
        return 1
    print(msg)
    print(f"Log: work/backups/restores/{out['restore']}/restore.log")
    return 0


def restore_all(args: list[str]) -> int:
    """eax restore: the whole application restored from one of its backups, asked first."""
    runs = [r for r in bk.list_application()["runs"] if r.get("status") in ("ok", "partial")]
    if not runs:
        print("No application backup to restore from: make one with .\\eax app-backup")
        return 1
    want = next((a for a in args if not a.startswith("--")), "")
    if want:
        low = want.lower()
        hits = runs[:1] if low in ("latest", "newest") else [r for r in runs if low in (r["name"].lower(), str(r.get("tag") or "").lower())]
        if not hits:
            print(f"No application backup named or tagged '{want}': .\\eax backups lists them.")
            return 1
        run = hits[0]
    else:
        print("Application backups (work/backups/application):")
        i = _pick(runs, lambda r: f"{bk.human(r.get('created', ''))}  {r.get('tag')}  "
                                  f"({len([m for m in r.get('models') or [] if m.get('status') == 'ok'])} models, "
                                  f"{len([p for p in r.get('projects') or [] if p.get('status') == 'ok'])} projects)")
        if i is None:
            return 1
        run = runs[i]
    n = len([m for m in run.get("models") or [] if m.get("status") == "ok"])
    np = len([p for p in run.get("projects") or [] if p.get("status") == "ok"])
    print(f"Backup: {run['name']} (tag {run.get('tag')}, made {bk.human(run.get('created', ''))} by {run.get('by')}), {n} models"
          f"{f', {np} projects with their documents' if np else ''}.")
    print("Every model in it goes back to how it was in this backup (each one is backed up first, and kept as a tag);")
    print("models no longer there are made again; models made since stay as they are. Everyone is notified.")
    if np:
        print("Every project in it goes back as it was, with its documents: a document still in Documents gets the")
        print("backed-up file as its newest version (when it differs); one that is gone is put back. Projects made since stay.")
    if "--yes" not in args and _ask("Type RESTORE to go on: ") != "RESTORE":
        print("Nothing restored.")
        return 1
    try:
        from . import tasks as tk
        with tk.commits_after(), get_engine().begin() as conn:     # the projects commit after the models
            msg, out = bk.restore_application(conn, SYSTEM, run["name"])
    except EditError as exc:
        print(f"Not restored: {exc}")
        return 1
    print(msg)
    for f in out["failed"]:
        print(f"  Not restored: {f}")
    if out.get("project_ids"):          # the repositories and documents now, when Documents is up (else the minute job)
        from . import projects as pj
        from .db import get_projects_engine
        for pid in out["project_ids"]:
            try:
                print("  " + pj.build_repository(lambda: get_projects_engine().begin(), pid))
            except Exception as exc:  # noqa: BLE001 - the minute job tries again
                print(f"  Repository not built yet ({str(exc)[:120]}): it is built, and the documents put back, when Documents is up.")
    print(f"Log: work/backups/restores/{out['restore']}/restore.log")
    return 0 if not out["failed"] else 1


# ---------------------------------------------------------------- one model, one project, and checking (D968, D970)
def model_backup(args: list[str]) -> int:
    """eax model-backup <model> [why]: one model backed up now (its own backups, as on the model page)."""
    if not args:
        print("Which model? .\\eax model-backup <model name or id> [why]")
        return 2
    try:
        with get_engine().begin() as conn:
            bk._bypass(conn, True)
            msg, out = bk.model_backup(conn, SYSTEM, args[0], " ".join(args[1:]) or "eax model-backup")
    except (EditError, bk.repo.NotFound) as exc:
        print(f"Not backed up: {exc}")
        return 1
    print(msg)
    print(f"Model: {out['model']}")
    print(f"File: {out['file']}")
    print(f"SHA-256: {out['sha256']}")
    print(f"Restore it with: .\\eax restore-model model {out['model']} {out['file']} --new \"<name>\"")
    return 0


def project_backup(args: list[str]) -> int:
    """eax project-backup <project> [why]: one project backed up now, with its models and documents."""
    if not args:
        print("Which project? .\\eax project-backup <project name or id> [why]")
        return 2
    from . import project_backup as pb
    from .background import _projects_beside
    try:
        with get_engine().begin() as conn, _projects_beside(conn) as pc:
            bk._bypass(conn, True)
            msg, out = pb.backup(conn, pc, SYSTEM, args[0], " ".join(args[1:]) or "eax project-backup")
    except EditError as exc:
        print(f"Not backed up: {exc}")
        return 1
    print(msg)
    print(f"Project: {out['project']}")
    print(f"File: {out['file']}")
    print(f"SHA-256: {out['info'].get('sha256', '')}")
    print(f"Restore it with: .\\eax restore-project {out['project']} {out['file']} --new \"<name>\"")
    return 0


def _project_path(first: str, file: str):
    """A project backup's file: in an application backup (first is its run) or one of the project's own backups."""
    from . import project_backup as pb
    from . import projects as pj
    from .background import _projects_beside
    if any(r["name"] == first for r in bk.list_application()["runs"]):
        return bk.path_of("application", first, file)
    with get_engine().begin() as conn, _projects_beside(conn) as pc:
        guid = str(pj.project_row(pc, first)["guid"])
    return pb.path_of(guid, file)


def restore_project(args: list[str]) -> int:
    """eax restore-project <project|run> <file> [--new "<name>" | --over] [--yes]: a project back from a backup file, as a
    new project (the default) or over itself; its repository is built and its documents put back before it ends."""
    from . import project_backup as pb
    from . import projects as pj
    from .background import _projects_beside
    from .db import get_projects_engine
    positional = [a for a in args if not a.startswith("--") and a not in _option_values(args)]
    if len(positional) < 2:
        print("Usage: .\\eax restore-project <project or application backup> <file> [--new \"<name>\" | --over] [--yes]")
        print("The files: .\\eax backups, or the project's Back up and restore tab.")
        return 2
    try:
        path = _project_path(positional[0], positional[1])
        info, z = pb._read(path)
        z.close()
    except EditError as exc:
        print(f"Not restored: {exc}")
        return 1
    over = "--over" in args
    new_name = args[args.index("--new") + 1] if "--new" in args and args.index("--new") + 1 < len(args) else ""
    what = f"over {info['project']['name']}" if over else f"as the new project '{new_name or info['project']['name'] + ' (restored ...)'}'"
    if "--yes" not in args and _ask(f"Restore {path.name} {what}? Type RESTORE to go on: ") != "RESTORE":
        print("Nothing restored.")
        return 1
    try:
        from . import tasks as tk
        with tk.commits_after(), get_engine().begin() as conn, _projects_beside(conn) as pc:
            msg, out = pb.restore(conn, pc, SYSTEM, path, new_name, over=over, models_over=over)
    except EditError as exc:
        print(f"Not restored: {exc}")
        return 1
    print(msg)
    print(f"Project: {out['project']}")
    with get_projects_engine().begin() as pc:
        pid = pj.project_row(pc, out["project"])["id"]
    try:
        print("  " + pj.build_repository(lambda: get_projects_engine().begin(), pid))
    except Exception as exc:  # noqa: BLE001 - the minute job tries again
        print(f"  Repository not built yet ({str(exc)[:120]}): it is built, and the documents put back, when Documents is up.")
    return 0


def check(args: list[str]) -> int:
    """eax check-backup [latest|all|<run>|<tag>|<file>]: backups read and checked (D968); 1 when any is not right."""
    from . import backup_check as bc
    want = next((a for a in args if not a.startswith("--")), "latest")
    runs = bk.list_application()["runs"]
    targets: list[tuple[str, object]] = []
    if want in ("latest", "newest"):
        if not runs:
            print("No application backup to check yet: make one with .\\eax app-backup")
            return 0
        targets = [("run", bk.app_dir() / runs[0]["name"])]
    elif want == "all":
        targets = [("run", bk.app_dir() / r["name"]) for r in runs]
        for sub in ("models", "uploaded"):
            targets += [("file", f) for f in sorted((bk.app_dir() / sub).rglob(f"*{bk.SUFFIX}"))] if (bk.app_dir() / sub).is_dir() else []
        from . import project_backup as pb
        if pb.folder().is_dir():
            targets += [("file", f) for f in sorted(pb.folder().rglob(f"*{pb.SUFFIX}")) if "_uploads" not in f.parts]
    else:
        hits = [r for r in runs if want.lower() in (r["name"].lower(), str(r.get("tag") or "").lower())]
        if hits:
            targets = [("run", bk.app_dir() / hits[0]["name"])]
        elif "/" in want or "\\" in want or ".." in want:
            print("Give a backup's file name, not a path.")
            return 2
        else:
            found = [f for f in bk.root().rglob(want) if f.is_file()]
            if not found:
                print(f"No backup run, tag or file called {want}: .\\eax backups lists them.")
                return 1
            targets = [("file", found[0])]
    bad = 0
    for kind, target in targets:
        c = bc.check_run(target) if kind == "run" else bc.check_file(target)
        print(bc.words(c))
        for f in c.get("files") or []:
            print(f"    {'ok ' if f['ok'] else 'BAD'}  {f['file']}  {str(f.get('sha256') or '')[:16]}")
        bad += 0 if c["ok"] else 1
    print(f"{len(targets) - bad} of {len(targets)} backup(s) checked out" + (f"; {bad} did not." if bad else "."))
    return 1 if bad else 0


def _option_values(args: list[str]) -> set[str]:
    return {args[i + 1] for i, a in enumerate(args[:-1]) if a == "--new"}


def main(argv: list[str]) -> int:
    """python -m eax.backups_cli: the backup and restore commands, run as a Super Admin."""
    perms.current.set(SYSTEM)   # the database sees the command as a Super Admin (as the job runner sees the person)
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    if argv[0] == "backup":
        return backup(argv[1:])
    if argv[0] == "restore":
        return restore_model(argv[1:])
    if argv[0] == "restore-all":
        return restore_all(argv[1:])
    if argv[0] == "model-backup":
        return model_backup(argv[1:])
    if argv[0] == "project-backup":
        return project_backup(argv[1:])
    if argv[0] == "restore-project":
        return restore_project(argv[1:])
    if argv[0] == "check":
        return check(argv[1:])
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
