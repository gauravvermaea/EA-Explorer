"""Site pairings and sync (Release 6.5, D749; see eax/pairing.py), and a git repository as one more place for packages
(eax/gitpackages.py).

Super Admins (System Admin › Site pairings):
GET    /pairings                         every pairing (sending and receiving), whether this site is a DR copy, its purpose
POST   /pairings                         pair with Site 2 {name, url, key, kind, send_mode, every_minutes, scope, trust}
POST   /pairings/keys                    Site 2: a pairing key to give Site 1 {name, note} (shown once)
GET    /pairings/certificate?url=        Site 2's certificate's SHA-256 (to compare before trusting a laptop's own)
PUT    /pairings/<p>                     {action: accept|refuse|stop|resume|change, commit_mode, send_mode, every_minutes, scope}
DELETE /pairings/<p>                     the pairing and its queue
GET    /pairings/<p>/batches             its batches, newest first
POST   /pairings/<p>/send                Site 1: sync now {scope?} (in the background; then sent within a minute)
POST   /sync-batches/<b>/commit          Site 2: a batch put in (in the background)
POST   /sync-batches/<b>/discard         Site 2: a batch not taken

Site 1 calling Site 2 (no person: the pairing key, "Authorization: Pairing <key>"):
POST   /sync/hello                       introduce the sending site
POST   /sync/batch                       one batch (the zip as the body; X-Eax-Seq, X-Eax-Sha256): answered at once
GET    /sync/status                      the pairing's state and what became of the last batches

Anyone who may download or upload the package (the repository's address, branch, user name and token typed each time):
POST   /git/push                         {repo, branch, username, token, source: model|project-backup, ...}
POST   /git/list                         {repo, branch, username, token, suffix}: the packages there
POST   /git/fetch                        {repo, branch, username, token, file}: the file, to upload as usual
"""

from __future__ import annotations

from flask import Response, g, request
from flask.views import MethodView
from flask_smorest import Blueprint, abort

from .. import audit
from .. import pairing as sp
from ..auth import require_auth
from ..db import get_engine, get_projects_engine
from ..metamodel_edit import EditError
from .models import Free, FreeIn

blp = Blueprint("pairing", __name__, url_prefix="/api/v1",
                description="Site pairings and sync (Release 6.5), and git as a place for packages")
SECURITY = [{"bearerAuth": []}]


def _run(fn, write: bool = True):
    try:
        with (get_engine().begin() if write else get_engine().connect()) as conn:
            return fn(conn)
    except EditError as exc:
        abort(exc.status, message=str(exc))


def _note(conn, action: str, ident: str, details: dict) -> None:
    audit.record(conn, actor=g.user.username, action=action, object_type="pairing", object_id=ident, source="api",
                 request_id=getattr(g, "request_id", None), details=details)


def _super() -> None:
    if "super-admin" not in (g.user.roles or ()):
        abort(403, message="Only a Super Admin pairs sites, sends or commits.")


@blp.route("/pairings")
class Pairings(MethodView):
    """/api/v1/pairings: GET every pairing (sending and receiving), whether this site is a DR copy and its purpose;
    POST pair with Site 2 (Super Admins)."""
    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth("system.operate")
    def get(self):
        """Every pairing (sending and receiving), whether this site is a DR copy and its purpose"""
        return _run(sp.listing, write=False)

    @blp.doc(security=SECURITY)
    @blp.arguments(FreeIn)
    @blp.response(201, Free)
    @require_auth("system.operate")
    def post(self, data):
        """Pair with Site 2 {name, url, key, kind (content|dr), send_mode, every_minutes, scope, trust} (Super Admins)"""
        def go(c):
            out = sp.pair(c, g.user, data or {})
            _note(c, "pairing.pair", str(out["id"]), {"name": out["name"], "url": out["peer_url"], "kind": out["kind"]})
            return out
        return _run(go)


@blp.route("/pairings/keys")
class PairingKeys(MethodView):
    """/api/v1/pairings/keys: POST a pairing key to give the sending site (Super Admins; shown once)."""
    @blp.doc(security=SECURITY)
    @blp.arguments(FreeIn)
    @blp.response(201, Free)
    @require_auth("system.operate")
    def post(self, data):
        """A pairing key to give the sending site {name, note} (Super Admins; shown once, only its hash kept)"""
        def go(c):
            out = sp.make_key(c, g.user, str((data or {}).get("name") or ""), str((data or {}).get("note") or ""))
            _note(c, "pairing.key", str(out["id"]), {"name": out["name"]})
            return out
        return _run(go)


@blp.route("/pairings/certificate")
class PairingCertificate(MethodView):
    """/api/v1/pairings/certificate: GET the SHA-256 of a site's certificate (?url=), to compare with what that site
    shows before trusting it (a laptop's own certificate)."""
    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth("system.operate")
    def get(self):
        """The SHA-256 of a site's certificate (?url=), to compare with what that site shows before trusting it"""
        _super()
        url = request.args.get("url", "")
        if not url.startswith("https://"):
            abort(400, message="Sites are paired over HTTPS only.")
        try:
            return {"url": url, "sha256": sp.certificate_of(url)}
        except OSError as exc:
            abort(502, message=f"That site did not answer: {exc}")


@blp.route("/pairings/<pid>")
class Pairing(MethodView):
    """/api/v1/pairings/{pid}: PUT accept, refuse, stop (on a DR copy: take over), resume or change a pairing; DELETE
    remove it with its queue (Super Admins)."""
    @blp.doc(security=SECURITY)
    @blp.arguments(FreeIn)
    @blp.response(200, Free)
    @require_auth("system.operate")
    def put(self, data, pid):
        """{action: accept|refuse|stop|resume|change, commit_mode, send_mode, every_minutes, scope} (Super Admins)"""
        data = data or {}
        def go(c):
            out = sp.decide(c, g.user, pid, str(data.get("action") or ""), data)
            _note(c, f"pairing.{data.get('action')}", pid, {k: data.get(k) for k in ("commit_mode", "send_mode", "every_minutes")
                                                           if k in data})
            return out
        return _run(go)

    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth("system.operate")
    def delete(self, pid):
        """Remove a pairing with its queue (Super Admins)"""
        def go(c):
            out = sp.remove(c, g.user, pid)
            _note(c, "pairing.remove", pid, {})
            return out
        return _run(go)


@blp.route("/pairings/<pid>/batches")
class PairingBatches(MethodView):
    """/api/v1/pairings/{pid}/batches: GET the pairing's batches, newest first."""
    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth("system.operate")
    def get(self, pid):
        """The pairing's batches, newest first"""
        return {"batches": _run(lambda c: sp.batches(c, pid), write=False)}


@blp.route("/pairings/<pid>/send")
class PairingSend(MethodView):
    """/api/v1/pairings/{pid}/send: POST sync now (Site 1, Super Admins): the batches are made in the background and
    sent within a minute."""
    @blp.doc(security=SECURITY)
    @blp.arguments(FreeIn)
    @blp.response(202, Free)
    @require_auth("system.operate")
    def post(self, data, pid):
        """Sync now {scope?: the entire site, or chosen models and projects} (Site 1, Super Admins)"""
        _super()
        p = _run(lambda c: sp._shape(sp._one(c, pid)), write=False)
        if p["side"] != "sender" or p["status"] != "accepted":
            abort(409, message="Only an accepted pairing on the sending site syncs.")
        from ..jobs import app as jobs_app
        from ..jobs import sync_enqueue
        with jobs_app.open():
            sync_enqueue.defer(pairing=pid, by=g.user.username, scope=(data or {}).get("scope"))
        with get_engine().begin() as c:
            _note(c, "pairing.send", pid, {"scope": (data or {}).get("scope") or "as set"})
        return {"queued": True, "message": "Making the batches in the background; they go within a minute. The batches list shows each."}


@blp.route("/sync-batches/<bid>/<action>")
class SyncBatchAction(MethodView):
    """/api/v1/sync-batches/{bid}/{action}: POST commit (in the background) or discard a batch received here (Super
    Admins)."""
    @blp.doc(security=SECURITY)
    @blp.response(202, Free)
    @require_auth("system.operate")
    def post(self, bid, action):
        """commit (in the background) or discard a batch received here (Super Admins)"""
        _super()
        if action == "discard":
            def go(c):
                out = sp.discard(c, g.user, bid)
                _note(c, "pairing.discard", bid, {})
                return out
            return _run(go)
        if action != "commit":
            abort(404, message="commit or discard.")
        from ..jobs import app as jobs_app
        from ..jobs import sync_commit
        with jobs_app.open():
            sync_commit.defer(batch=bid, by=g.user.username)
        with get_engine().begin() as c:
            _note(c, "pairing.commit", bid, {})
        return {"queued": True, "message": "Committing in the background: the batch says what was done with each item."}


# ---------------------------------------------------------------- Site 1 calling Site 2 (the pairing key, no person)
def _key() -> str:
    h = request.headers.get("Authorization", "")
    if not h.startswith("Pairing "):
        abort(401, message="A pairing key is needed (Authorization: Pairing <key>).")
    return h[len("Pairing "):].strip()


@blp.route("/sync/hello")
class SyncHello(MethodView):
    """/api/v1/sync/hello: POST the sending site introduces itself with the pairing key made here (no person)."""
    @blp.arguments(FreeIn)
    @blp.response(200, Free)
    def post(self, data):
        """The sending site introduces itself with the pairing key made here {sender, kind} (no person)"""
        return _run(lambda c: sp.hello(c, _key(), data or {}))


@blp.route("/sync/batch")
class SyncBatch(MethodView):
    """/api/v1/sync/batch: POST one batch from the sending site (the zip as the body; X-Eax-Seq, X-Eax-Sha256),
    answered at once: received, already had, or the number expected next."""
    @blp.doc(responses={"200": {"description": "received or already had"}, "409": {"description": "a gap: expect"}})
    def post(self):
        """One batch from the sending site (the zip as the body; X-Eax-Seq, X-Eax-Sha256), answered at once"""
        try:
            seq = int(request.headers.get("X-Eax-Seq") or "0")
        except ValueError:
            abort(400, message="X-Eax-Seq is the batch's number.")
        body = request.get_data(cache=False)
        status, out = _run(lambda c: sp.receive(c, _key(), seq, request.headers.get("X-Eax-Sha256", ""), body))
        return out, status


@blp.route("/sync/status")
class SyncStatus(MethodView):
    """/api/v1/sync/status: GET the pairing's state and what became of the last batches (the pairing key, no person)."""
    @blp.response(200, Free)
    def get(self):
        """The pairing's state and what became of the last batches (the pairing key, no person)"""
        return _run(lambda c: sp.status_for_peer(c, _key()), write=False)


# ---------------------------------------------------------------- git: one more place for packages
def _git(data: dict) -> tuple[str, str, str, str]:
    return (str(data.get("repo") or "").strip(), str(data.get("branch") or "").strip(),
            str(data.get("username") or "").strip(), str(data.get("token") or ""))


def _package_file(data: dict) -> tuple[bytes, str]:
    """The file the Download or the project's backup gives, made the same way and with the same rights."""
    source = data.get("source")
    if source == "model":
        from .. import model_ops as mo
        from .. import repository as repo
        fmt = "xlsx" if data.get("format") == "xlsx" else "zip"
        content = str(data.get("content") or "content")
        try:
            with get_engine().connect() as conn:
                body, name, _ct = mo.export_package(conn, str(data.get("model") or ""), fmt, g.user.username, content)
        except repo.NotFound as exc:
            abort(404, message=str(exc))
        except EditError as exc:
            abort(exc.status, message=str(exc))
        return body, name
    if source == "project-backup":
        from .. import project_backup as pb
        from .. import projects as pj
        try:
            with get_projects_engine().connect() as pc:
                p = pj.project_row(pc, str(data.get("project") or ""))
                pb.need_manage(pc, p, g.user)
                return pb.path_of(str(p["guid"]), str(data.get("file") or "")).read_bytes(), str(data.get("file"))
        except EditError as exc:
            abort(exc.status, message=str(exc))
    if source == "settings":                    # the settings file (Release 6.7, D755): Super Admins only
        _super()
        from .settings_transfer import settings_file
        return settings_file(data.get("parts"))
    abort(400, message="source is model (with model, format, content), project-backup (with project, file) or settings "
                       "(with parts).")
    raise AssertionError  # abort raises


@blp.route("/git/push")
class GitPush(MethodView):
    """/api/v1/git/push: POST a model's package or a project's backup put on a git repository (one commit, pushed)."""
    @blp.doc(security=SECURITY)
    @blp.arguments(FreeIn)
    @blp.response(200, Free)
    @require_auth()
    def post(self, data):
        """A model's package or a project's backup put on a git repository {repo, branch, username, token, source:
        model (model, format, content) | project-backup (project, file)}: one commit, pushed; the token is never kept"""
        from .. import gitpackages as gp
        data = data or {}
        body, name = _package_file(data)
        repo_url, branch, user, token = _git(data)
        try:
            out = gp.push(body, name, repo_url, branch, user, token, g.user.username)
        except EditError as exc:
            abort(exc.status, message=str(exc))
        with get_engine().begin() as c:
            audit.record(c, actor=g.user.username, action="git.push", object_type=str(data.get("source")),
                         object_id=str(data.get("model") or data.get("project") or ""), source="api",
                         request_id=getattr(g, "request_id", None), details={"repository": repo_url, "file": name})
        return out


@blp.route("/git/list")
class GitList(MethodView):
    """/api/v1/git/list: POST the packages in a git repository's eax-packages/ folder."""
    @blp.doc(security=SECURITY)
    @blp.arguments(FreeIn)
    @blp.response(200, Free)
    @require_auth()
    def post(self, data):
        """The packages in a git repository's eax-packages/ {repo, branch, username, token, suffix}"""
        from .. import gitpackages as gp
        data = data or {}
        try:
            return {"files": gp.listing(*_git(data), suffix=str(data.get("suffix") or ""))}
        except EditError as exc:
            abort(exc.status, message=str(exc))


@blp.route("/git/fetch")
class GitFetch(MethodView):
    """/api/v1/git/fetch: POST one package from a git repository, as a file (the screen then uploads it as usual)."""
    @blp.doc(security=SECURITY, responses={"200": {"description": "The file"}})
    @blp.arguments(FreeIn)
    @require_auth()
    def post(self, data):
        """One package from a git repository {repo, branch, username, token, file}: the file, uploaded as usual"""
        from .. import gitpackages as gp
        data = data or {}
        file = str(data.get("file") or "")
        try:
            body = gp.fetch(*_git(data), file)
        except EditError as exc:
            abort(exc.status, message=str(exc))
        return Response(body, mimetype="application/octet-stream", headers={"Content-Disposition": f'attachment; filename="{file}"'})
