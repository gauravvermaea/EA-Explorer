"""API writes of the self-test (D577): changes that really save, area by area, only inside the run's own fixtures
(self_test_<id>_1 and _2, the run's project, and things named self_test_<id> that the check itself removes again), plus
the same writes refused for a role without the right.

Each check is one result named "write <area>: <what>", so the report's coverage counts writes by area. A positive write
passes when the API answers as it should; a refused write passes when it answers 401 or 403 (a 400 before the rights
are checked is a warning: the refusal is right, but for the wrong reason). Nothing here touches anyone's real content."""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from collections.abc import Callable

from .. import httpopen

Record = Callable[..., None]
REFUSED = {401, 403}


def call(base: str, method: str, path: str, token: str | None, body: dict | None = None,
         timeout: int = 60) -> tuple[int, dict | str]:
    """One call with a JSON body; the answer as JSON when it is JSON."""
    data = json.dumps(body if body is not None else {}).encode() if method.upper() in ("POST", "PUT", "PATCH") else None
    from ..service_split import route
    base = route(base, path)            # a service's path goes to its own container (R2.27 part 2, R2.53)
    req = urllib.request.Request(base + path, data=data, method=method.upper(),
                                 headers={"Content-Type": "application/json", "Accept": "application/json",
                                          **({"Authorization": f"Bearer {token}"} if token else {})})
    try:
        with httpopen.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", "replace")
            status = r.status
    except urllib.error.HTTPError as exc:
        try:
            raw = exc.read().decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            raw = ""
        status = exc.code
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return 599, f"no answer: {exc}"
    try:
        return status, json.loads(raw) if raw else {}
    except ValueError:
        return status, raw[:1500]


# a project's upload goes on to Documents, which the API waits on for up to 300 s (mayan.upload): the run waits longer
# than that, so a slow Documents answers late rather than "no answer" (run 16: 599 after 120 s)
UPLOAD_WAIT = 330


def upload(base: str, path: str, token: str | None, name: str, content: bytes, timeout: int = UPLOAD_WAIT) -> tuple[int, dict | str]:
    """One multipart upload (field "file"), as the screens and eax import send a delivery."""
    boundary = "eaxselftest" + str(int(time.time() * 1000))
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{name}\"\r\n"
            "Content-Type: application/octet-stream\r\n\r\n").encode() + content + f"\r\n--{boundary}--\r\n".encode()
    from ..service_split import route
    base = route(base, path)
    req = urllib.request.Request(base + path, data=body, method="POST",
                                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}", "Accept": "application/json",
                                          **({"Authorization": f"Bearer {token}"} if token else {})})
    try:
        with httpopen.urlopen(req, timeout=timeout) as r:
            raw, status = r.read().decode("utf-8", "replace"), r.status
    except urllib.error.HTTPError as exc:
        raw, status = exc.read().decode("utf-8", "replace"), exc.code
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return 599, f"no answer: {exc}"
    try:
        return status, json.loads(raw) if raw else {}
    except ValueError:
        return status, raw[:1500]


def ident(answer) -> str | None:
    """The id of what a write made: id, guid or ident, at the top or one level down (entity, survey, credential...)."""
    if not isinstance(answer, dict):
        return None
    for k in ("id", "guid", "ident"):
        if isinstance(answer.get(k), str) and answer[k]:
            return answer[k]
        if isinstance(answer.get(k), int) and not isinstance(answer.get(k), bool):   # a principle's id is a number
            return str(answer[k])
    for v in answer.values():
        if isinstance(v, dict):
            for k in ("id", "guid", "ident"):
                if isinstance(v.get(k), str) and v[k]:
                    return v[k]
    return None


def judge(status: int, ok: set[int], refused: bool, refused_also: set[int] | None = None) -> tuple[str, str]:
    """passed, warning or failed for one write (also used by the unit tests); refused_also: other codes that refuse
    here (404 where a thing the person may not read is not shown to exist)."""
    if refused:
        if status in REFUSED or status in (refused_also or set()):
            return "passed", f"refused ({status})"
        if status == 400:
            return "warning", "400: refused, but before the rights were checked"
        return "failed", f"{status}: should have been refused"
    if status in ok:
        return "passed", f"{status}"
    if status >= 500 or status == 599:
        return "failed", f"{status}: server error"
    return "failed", f"{status}: expected {', '.join(map(str, sorted(ok)))}"


def plan(ids: dict[str, str], sid: str) -> list[dict]:
    """The writes, in order: area, what, method, path, body, who (a role, or the role refused), ok codes, and what to keep
    from the answer (save) for later steps ({name} in a path or body). Unit tested: every path is inside the fixtures."""
    m, other, p, ent = ids.get("model"), ids.get("other_model"), ids.get("project"), ids.get("entity")
    tag = f"self_test_{sid}"
    w: list[dict] = []
    if m:
        w += [
            dict(area="content", what="create an entity", method="post", path=f"/api/v1/models/{m}/content/entities",
                 body={"entity_type": "ApplicationComponent", "name": f"{tag} API application",
                       "description": "made by the self-test"}, who="model-admin", ok={200, 201}, save="entity"),
            dict(area="content", what="edit its description", method="patch",
                 path=f"/api/v1/models/{m}/content/entities/{{entity}}", body={"description": "changed by the self-test"},
                 who="model-admin", ok={200}),
            dict(area="content", what="refused: create as a Report Viewer", method="post",
                 path=f"/api/v1/models/{m}/content/entities",
                 body={"entity_type": "ApplicationComponent", "name": f"{tag} refused"}, who="report-viewer", refused=True),
            dict(area="relationships", what="add a relationship", method="post", path=f"/api/v1/models/{m}/content/relationships",
                 body={"relationship_type": "Association", "source": "{entity}", "target": ent}, who="model-admin",
                 ok={200, 201}, save="relationship", needs=["entity"] + ([] if ent else ["fixture entity"])),
            dict(area="relationships", what="refused: add as a Report Viewer", method="post",
                 path=f"/api/v1/models/{m}/content/relationships",
                 body={"relationship_type": "Association", "source": "{entity}", "target": ent}, who="report-viewer", refused=True),
            dict(area="relationships", what="remove it", method="delete",
                 path=f"/api/v1/models/{m}/content/relationships/{{relationship}}", who="model-admin", ok={200, 204}),
            dict(area="content", what="delete the entity", method="delete", path=f"/api/v1/models/{m}/content/entities/{{entity}}",
                 who="model-admin", ok={200, 204}),
            dict(area="content", what="commit the changes", method="post", path=f"/api/v1/models/{m}/changes/commit",
                 body={"message": f"{tag} API writes"}, who="model-admin", ok={200, 201, 409}),
            dict(area="metamodel", what="add a pick list", method="post", path=f"/api/v1/models/{m}/metamodel/changes",
                 body={"op": "pick_list.create", "name": f"{tag} list", "values": ["One", "Two"]}, who="model-admin", ok={200}),
            dict(area="metamodel", what="refused: change it as an Architect", method="post",
                 path=f"/api/v1/models/{m}/metamodel/changes",
                 body={"op": "pick_list.create", "name": f"{tag} refused", "values": ["One"], "dry_run": True},
                 who="architect", refused=True),
            dict(area="drawn views", what="refused: commit a view as a Report Viewer", method="post",
                 path=f"/api/v1/models/{m}/drawn-views/commit", body={}, who="report-viewer", refused=True),
        ]
    if other:
        w += [
            dict(area="merge requests", what="send the child for merge", method="post",
                 path=f"/api/v1/models/{other}/merge-requests", body={"note": f"{tag} API write"}, who="super-admin",
                 ok={200, 201, 202, 409}),
            # 404 is a refusal here: a model the person may not read is not shown to exist ("or you may not read it")
            dict(area="merge requests", what="refused: send as a Report Viewer", method="post",
                 path=f"/api/v1/models/{other}/merge-requests", body={"note": "refused"}, who="report-viewer", refused=True,
                 refused_also={404}),
        ]
    if m and other:
        # a gap analysis and a common analysis between the run's two models, kept in its first (owner, 12 Nov 2026: making
        # a gap analysis said "column domain does not exist"); both run in the background, so their task is followed
        both = [{"kind": "model", "id": other}, {"kind": "model", "id": m}]
        w += [
            dict(area="analyses", what="make a gap analysis", method="post", path="/api/v1/gaps",
                 body={"store_in": m, "name": f"{tag} gap analysis", "baseline": both[0], "target": both[1], "template": "all"},
                 who="super-admin", ok={200, 201, 202}, save="gaptask", save_at="task",
                 until={"path": "/api/v1/tasks/{gaptask}", "status": ["done"], "seconds": 300}),
            dict(area="analyses", what="make a common analysis", method="post", path="/api/v1/commons",
                 body={"store_in": m, "name": f"{tag} common analysis", "sides": both},
                 who="super-admin", ok={200, 201, 202}, save="commontask", save_at="task",
                 until={"path": "/api/v1/tasks/{commontask}", "status": ["done"], "seconds": 300}),
            dict(area="analyses", what="refused: make a gap analysis with no role", method="post", path="/api/v1/gaps",
                 body={"store_in": m, "name": f"{tag} refused", "baseline": both[0], "target": both[1]},
                 who="no-role", refused=True, refused_also={404}),
        ]
    if m:
        # a delivery really loaded, accepted and undone (D583): the test data's good delivery (testbench/data)
        w += [
            dict(area="imports", what="add an import source", method="post", path=f"/api/v1/models/{m}/import-sources",
                 body={"name": f"{tag} API source", "description": "made by the self-test"}, who="model-admin", ok={200, 201},
                 save="source"),
            dict(area="imports", what="upload a delivery", method="post", path="/api/v1/import-sources/{source}/deliveries",
                 data="deliveries/good.xlsx", who="model-admin", ok={200, 201, 202}, save="load", save_at="load",
                 until={"path": "/api/v1/loads/{load}", "status": ["previewed"], "seconds": 300}),
            dict(area="imports", what="refused: accept it as a Report Viewer", method="post", path="/api/v1/loads/{load}/accept",
                 body={}, who="report-viewer", refused=True, needs=["load"]),
            dict(area="imports", what="accept it (committed as the load)", method="post", path="/api/v1/loads/{load}/accept",
                 body={}, who="model-admin", ok={200, 202}, needs=["load"],
                 until={"path": "/api/v1/loads/{load}", "status": ["added"], "seconds": 180}),
            dict(area="imports", what="undo the load", method="post", path="/api/v1/loads/{load}/undo", body={},
                 who="model-admin", ok={200}, needs=["load"]),
            dict(area="imports", what="refused: add an import source as a Report Viewer", method="post",
                 path=f"/api/v1/models/{m}/import-sources", body={"name": f"{tag} refused"}, who="report-viewer", refused=True),
        ]
    if p:
        w += [
            dict(area="projects", what="refused: change the iteration with no role", method="post",
                 path=f"/api/v1/projects/{p}/iteration", body={"iteration": "full"}, who="no-role", refused=True),
        ]
        w += project_workspace(p, tag)
    if m:
        w += platform_writes(m, other, sid, tag)
        w += model_extras(m, ent, sid, tag)
        w += job_starters(m, other, p, tag)
    if p:
        w += project_extras(p, tag)
    w += admin_extras(sid, tag)
    w += [
        dict(area="surveys", what="create a draft survey", method="post", path="/api/v1/surveys",
             body={"title": f"{tag} survey", "description": "made by the self-test"}, who="super-admin", ok={200, 201},
             save="survey"),
        dict(area="surveys", what="delete it", method="delete", path="/api/v1/surveys/{survey}", who="super-admin",
             ok={200, 204}),
        dict(area="surveys", what="refused: create as a Report Viewer", method="post", path="/api/v1/surveys",
             body={"title": f"{tag} refused"}, who="report-viewer", refused=True),
        # the run's accounts are themselves credentials, and credentials are made only by a person signed in
        # (eax/api/machine_access.py): so even the Super Admin's test token is refused
        dict(area="machine access", what="refused: a credential cannot make a credential", method="post",
             path="/api/v1/machine-access/credentials", body={"kind": "token", "name": f"{tag} write check", "days": 1},
             who="super-admin", refused=True),
        dict(area="machine access", what="refused: a client certificate with no role", method="post",
             path="/api/v1/machine-access/credentials", body={"kind": "certificate", "name": f"{tag} refused"},
             who="no-role", refused=True),
    ]
    if ids.get("risky") and m:                       # only when the run asks for it (--risky, D927), last of all
        w += risky_writes(m, ids.get("model_name") or "", sid, tag)
    return w


def project_workspace(p: str, tag: str) -> list[dict]:
    """The project workspace's writes (R14.5, batch 1; owner, 25 Nov 2026, 12:12: "Please build both API and screens"):
    each area made, changed, read back and removed inside the run's own project (self_test_<id>_3), as its Architect
    (who contributes); removals as the Super Admin; and for each area the same write refused for the Report Viewer, who is
    the project's Stakeholder and only reads it. Background work (a tag brought back, the documents' zip) is followed to
    the end of its task (owner, 10:58: "triggering bg jobs using api and looking for results")."""
    b = f"/api/v1/projects/{p}"
    a, su, rv = "architect", "super-admin", "report-viewer"

    def wr(area, what, method, path, who=a, body=None, ok=None, **kw):
        return dict(area=area, what=what, method=method, path=path, who=who, body=body, ok=ok or {200, 201}, **kw)

    def refused(area, path, body):
        return dict(area=area, what="refused: add as the project's Stakeholder (Report Viewer)", method="post", path=path,
                    body=body, who=rv, refused=True)

    w = [
        # tasks (D298) and the project's own task statuses
        wr("project tasks", "add a task", "post", f"{b}/tasks", body={"title": f"{tag} task", "notes_html": "<p>made by the self-test</p>"},
           save="ptask"),
        wr("project tasks", "change its status", "put", f"{b}/tasks/{{ptask}}", body={"status": "Done"}, ok={200}),
        wr("project tasks", "delete it", "delete", f"{b}/tasks/{{ptask}}", who=su, ok={200, 204}),
        wr("project tasks", "add a status of the project's own", "post", f"{b}/task-statuses", body={"name": f"{tag}_status"},
           ok={200, 201}),
        wr("project tasks", "remove that status", "delete", f"{b}/task-statuses?name={tag}_status", who=su, ok={200, 204}),
        refused("project tasks", f"{b}/tasks", {"title": f"{tag} refused"}),
        # the stakeholder matrix (D294) and its discussion notes
        wr("project stakeholders", "add a stakeholder", "post", f"{b}/stakeholders",
           body={"name": f"{tag} stakeholder", "power": "High", "interest": "Low", "concerns": "made by the self-test"}, save="pstake"),
        wr("project stakeholders", "change it", "put", f"{b}/stakeholders/{{pstake}}", body={"interest": "High"}, ok={200}),
        wr("project stakeholders", "put them in order", "post", f"{b}/stakeholders/order", body={"order": ["{pstake}"]}, ok={200}),
        wr("project stakeholders", "note a discussion", "post", f"{b}/stakeholders/{{pstake}}/notes",
           body={"title": f"{tag} discussion", "html": "<p>what was discussed</p>"}, save="pnote"),
        wr("project stakeholders", "change the note", "put", f"{b}/stakeholder-notes/{{pnote}}", body={"title": f"{tag} discussion, changed"},
           ok={200}),
        wr("project stakeholders", "delete the note", "delete", f"{b}/stakeholder-notes/{{pnote}}", who=su, ok={200, 204}),
        wr("project stakeholders", "take the stakeholder out", "delete", f"{b}/stakeholders/{{pstake}}", who=su, ok={200, 204}),
        refused("project stakeholders", f"{b}/stakeholders", {"name": f"{tag} refused"}),
        # key questions: asked, answered, accepted by the project's Stakeholder, opened again, removed
        wr("project key questions", "ask a key question", "post", f"{b}/key-questions", body={"question": f"{tag} what do we decide?"},
           save="pkq"),
        # read back as the key questions tab reads it (run 12: the tab said "Key question added." and listed none)
        wr("project key questions", "the project, read again, holds the question", "get", b, ok={200},
           shows=f"{tag} what do we decide?"),
        wr("project key questions", "the key questions, read again, hold it", "get", f"{b}/key-questions", ok={200},
           shows=f"{tag} what do we decide?"),
        wr("project key questions", "change who asked it", "put", f"{b}/key-questions/{{pkq}}", body={"asked_by": "the self-test"}, ok={200}),
        wr("project key questions", "answer it, pointing to a page", "post", f"{b}/key-questions/{{pkq}}/answer",
           body={"answer": "<p>answered by the self-test</p>", "links": [{"url": "#/projects", "label": "the projects"}]}, ok={200}),
        wr("project key questions", "the Stakeholder accepts the answer", "post", f"{b}/key-questions/{{pkq}}/decide",
           who=rv, body={"decision": "accepted", "note": "accepted by the self-test"}, ok={200}),
        wr("project key questions", "open it again", "post", f"{b}/key-questions/{{pkq}}/reopen", body={"note": "opened again by the self-test"},
           ok={200}),
        wr("project key questions", "remove it", "delete", f"{b}/key-questions/{{pkq}}", who=su, ok={200, 204}),
        refused("project key questions", f"{b}/key-questions", {"question": f"{tag} refused"}),
        # Business Model Canvases (D344): a canvas, an item, a working copy, the two compared, exported, removed
        wr("project canvases", "make a canvas", "post", f"{b}/canvases", body={"name": f"{tag} canvas", "kind": "current"}, save="pcanvas"),
        wr("project canvases", "describe it", "put", f"{b}/canvases/{{pcanvas}}", body={"description": "made by the self-test"}, ok={200}),
        wr("project canvases", "add an item", "post", f"{b}/canvases/{{pcanvas}}/items",
           body={"block": "key_partners", "text": f"{tag} partner"}, save="pcitem"),
        wr("project canvases", "change the item", "put", f"{b}/canvas-items/{{pcitem}}", body={"note": "changed by the self-test"}, ok={200}),
        wr("project canvases", "make a working copy", "post", f"{b}/canvases/{{pcanvas}}/copy", body={"kind": "working"}, save="pcanvas2"),
        wr("project canvases", "compare the two", "get", f"{b}/canvases/{{pcanvas}}/compare/{{pcanvas2}}", ok={200}),
        wr("project canvases", "export it for draw.io", "get", f"{b}/canvases/{{pcanvas}}/export?format=drawio", ok={200}),
        wr("project canvases", "remove the item", "delete", f"{b}/canvas-items/{{pcitem}}", who=su, ok={200, 204}),
        wr("project canvases", "remove the working copy", "delete", f"{b}/canvases/{{pcanvas2}}", who=su, ok={200, 204}),
        wr("project canvases", "remove the canvas", "delete", f"{b}/canvases/{{pcanvas}}", who=su, ok={200, 204}),
        refused("project canvases", f"{b}/canvases", {"name": f"{tag} refused"}),
        # customer journey maps: a journey, a stage, a step, a copy, the two compared, exported, removed
        wr("project journeys", "make a journey", "post", f"{b}/journeys", body={"name": f"{tag} journey"}, save="pjourney"),
        wr("project journeys", "give it a persona", "put", f"{b}/journeys/{{pjourney}}", body={"persona": "a customer"}, ok={200}),
        wr("project journeys", "add a stage", "post", f"{b}/journeys/{{pjourney}}/stages", body={"name": f"{tag} stage"}, save="pjstage"),
        wr("project journeys", "change the stage", "put", f"{b}/journey-stages/{{pjstage}}", body={"note": "changed by the self-test"}, ok={200}),
        wr("project journeys", "add a step to the stage", "post", f"{b}/journeys/{{pjourney}}/items",
           body={"stage": "{pjstage}", "part": "step", "text": f"{tag} step", "score": 1}, save="pjitem"),
        wr("project journeys", "change the step", "put", f"{b}/journey-items/{{pjitem}}", body={"note": "changed by the self-test"}, ok={200}),
        wr("project journeys", "make a working copy", "post", f"{b}/journeys/{{pjourney}}/copy", body={"kind": "working"}, save="pjourney2"),
        wr("project journeys", "compare the two", "get", f"{b}/journeys/{{pjourney}}/compare/{{pjourney2}}", ok={200}),
        wr("project journeys", "export it for draw.io", "get", f"{b}/journeys/{{pjourney}}/export?format=drawio", ok={200}),
        wr("project journeys", "remove the step", "delete", f"{b}/journey-items/{{pjitem}}", who=su, ok={200, 204}),
        wr("project journeys", "remove the stage", "delete", f"{b}/journey-stages/{{pjstage}}", who=su, ok={200, 204}),
        wr("project journeys", "remove the working copy", "delete", f"{b}/journeys/{{pjourney2}}", who=su, ok={200, 204}),
        wr("project journeys", "remove the journey", "delete", f"{b}/journeys/{{pjourney}}", who=su, ok={200, 204}),
        refused("project journeys", f"{b}/journeys", {"name": f"{tag} refused"}),
        # principles, standards, the organisation
        wr("project principles", "add an area", "post", f"{b}/principle-areas", body={"name": f"{tag} area"}, ok={200}),
        wr("project principles", "add a principle", "post", f"{b}/principles",
           body={"name": f"{tag} principle", "area": f"{tag} area", "statement": "<p>made by the self-test</p>"}, save="pprinciple"),
        wr("project principles", "change it", "put", f"{b}/principles/{{pprinciple}}",
           body={"name": f"{tag} principle", "rationale": "<p>changed by the self-test</p>"}, ok={200}),
        wr("project principles", "remove it", "delete", f"{b}/principles/{{pprinciple}}", who=su, ok={200, 204}),
        wr("project principles", "remove the area", "post", f"{b}/principle-areas", body={"name": f"{tag} area", "remove": True}, ok={200}),
        refused("project principles", f"{b}/principles", {"name": f"{tag} refused"}),
        wr("project standards", "add a standard", "post", f"{b}/standards", body={"name": f"{tag} standard", "area": "Technology"},
           save="pstandard"),
        wr("project standards", "change it", "put", f"{b}/standards/{{pstandard}}", body={"name": f"{tag} standard", "status": "Active",
                                                                                         "source": "the self-test"}, ok={200}),
        wr("project standards", "take it out", "delete", f"{b}/standards/{{pstandard}}", who=su, ok={200, 204}),
        refused("project standards", f"{b}/standards", {"name": f"{tag} refused"}),
        wr("project organisation", "add a person", "post", f"{b}/organisation", body={"name": f"{tag} person", "role": "Reviewer"},
           save="pperson"),
        wr("project organisation", "change their role", "put", f"{b}/organisation/{{pperson}}", body={"name": f"{tag} person",
                                                                                                   "role": "Lead reviewer"}, ok={200}),
        wr("project organisation", "take them out", "delete", f"{b}/organisation/{{pperson}}", who=su, ok={200, 204}),
        refused("project organisation", f"{b}/organisation", {"name": f"{tag} refused"}),
        # the governance log: a record, sent for approval (nobody signs off in the run's project: 409 says so), its history,
        # a kind of the project's own, removed
        wr("project governance", "log a risk", "post", f"{b}/governance", body={"kind": "Risk", "title": f"{tag} risk"}, save="prisk"),
        wr("project governance", "change it", "put", f"{b}/governance/{{prisk}}", body={"owner": "the self-test"}, ok={200}),
        wr("project governance", "send it for approval", "post", f"{b}/governance/{{prisk}}/approval",
           body={"action": "send", "note": "the self-test"}, ok={200, 409}),
        wr("project governance", "read its history", "get", f"{b}/governance/{{prisk}}/history", ok={200}),
        wr("project governance", "take it out", "delete", f"{b}/governance/{{prisk}}", who=su, ok={200, 204}),
        wr("project governance", "add a kind of record", "post", f"{b}/governance", body={"new_kind": {"name": f"{tag} kind"}}, ok={200, 201}),
        wr("project governance", "remove that kind", "post", f"{b}/governance", body={"remove_kind": f"{tag} kind"}, ok={200, 201}),
        refused("project governance", f"{b}/governance", {"kind": "Risk", "title": f"{tag} refused"}),
        # the project's calendar and a tracking sheet of its own (D325)
        wr("project calendar", "add an event", "post", f"/api/v1/calendars/{p}", body={"topic": f"{tag} event", "starts_on": "2026-12-01"},
           save="pevent"),
        wr("project calendar", "change it", "put", f"/api/v1/calendars/{p}/events/{{pevent}}", body={"notes": "changed by the self-test"},
           ok={200}),
        wr("project calendar", "download it as a calendar file", "get", f"/api/v1/calendars/{p}/ics", ok={200}),
        wr("project calendar", "delete it", "delete", f"/api/v1/calendars/{p}/events/{{pevent}}", who=su, ok={200, 204}),
        refused("project calendar", f"/api/v1/calendars/{p}", {"topic": f"{tag} refused", "starts_on": "2026-12-01"}),
        wr("project tracking sheets", "make a sheet", "post", f"/api/v1/tracking-sheets/{p}",
           body={"name": f"{tag} sheet", "columns": ["Name", "Owner"]}, save="psheet"),
        wr("project tracking sheets", "read it", "get", f"/api/v1/tracking-sheets/{p}/{{psheet}}", ok={200}),
        wr("project tracking sheets", "describe it", "put", f"/api/v1/tracking-sheets/{p}/{{psheet}}", body={"description": "the self-test"},
           ok={200}),
        wr("project tracking sheets", "download it as Excel", "get", f"/api/v1/tracking-sheets/{p}/{{psheet}}/xlsx", ok={200}),
        wr("project tracking sheets", "delete it", "delete", f"/api/v1/tracking-sheets/{p}/{{psheet}}", who=su, ok={200, 204}),
        refused("project tracking sheets", f"/api/v1/tracking-sheets/{p}", {"name": f"{tag} refused"}),
        # the repository's tags: one made, read, brought back in the background (the task followed to its end), removed;
        # and the documents' zip made in the background
        wr("project repository", "tag the repository", "post", f"{b}/repo-tags", body={"name": f"{tag} tag"}, save="ptag"),
        wr("project repository", "read the tag", "get", f"{b}/repo-tags/{{ptag}}", ok={200}),
        wr("project repository", "bring the repository back to the tag (in the background)", "post", f"{b}/repo-tags/{{ptag}}/revert",
           who=su, ok={200, 202}, save="ptagtask", save_at="task",
           until={"path": "/api/v1/tasks/{ptagtask}", "status": ["done"], "seconds": 300}),
        wr("project repository", "upload a file to the project", "post", f"{b}/other-uploads", data="deliveries/good.xlsx",
           ok={200, 201}, save="pupload", save_from="uploads.0.id"),
        wr("project repository", "the project's uploads", "get", f"{b}/other-uploads", ok={200}, shows="good.xlsx"),
        wr("project repository", "name the upload", "put", f"{b}/other-uploads/{{pupload}}", body={"title": f"{tag} file"},
           ok={200}),
        wr("project repository", "replace it with a second version", "post", f"{b}/other-uploads/{{pupload}}/replace",
           data="uploads/document-v2.pdf", ok={200, 201}),
        wr("project repository", "the documents' zip (in the background)", "get", f"{b}/repo-zip?background=true", ok={200, 202},
           save="pziptask", save_at="task", until={"path": "/api/v1/tasks/{pziptask}", "status": ["done"], "seconds": 300}),
        wr("project repository", "remove the tag", "delete", f"{b}/repo-tags/{{ptag}}", who=su, ok={200, 204}),
        wr("project repository", "delete the upload", "delete", f"{b}/other-uploads/{{pupload}}", who=su, ok={200, 204}),
        refused("project repository", f"{b}/repo-tags", {"name": f"{tag} refused"}),
    ]
    return w


def platform_writes(m: str, other: str | None, sid: str, tag: str) -> list[dict]:
    """The rest of the API's writes (R14.5, batch 2; owner, 25 Nov 2026, 14:12: "build all i will test everything in
    one go"): a model's tags, comparisons, backups, people and batch changes; a merge planned (never applied); the
    metamodel draft's round of review; background jobs started and followed to their end; the admin pages that measure
    or check; settings saved back unchanged (read first: same_as); the self-test's own reads of this run. All inside the
    run's own models (self_test_<id>_1 and _2) or the run's own names; each area refused for a role that may not."""
    a, ma, su, rv = "architect", "model-admin", "super-admin", "report-viewer"
    M = f"/api/v1/models/{m}"
    who = {"architect": f"svc-self-test-{sid}-architect"}

    def wr(area, what, method, path, by=su, body=None, ok=None, **kw):
        return dict(area=area, what=what, method=method, path=path, who=by, body=body, ok=ok or {200, 201}, **kw)

    def bg(save):                                   # a task started in the background, followed to its end
        return {"save": save, "save_at": "task", "until": {"path": "/api/v1/tasks/{" + save + "}", "status": ["done"],
                                                           "seconds": 300}}

    w = [
        # a model's tags (D192): one in the background and one at once, changed, read, compared, brought back, removed
        wr("model tags", "tag the model (in the background)", "post", f"{M}/tags", ma, {"name": f"{tag} tag bg"}, {200, 202},
           **bg("tagtask")),
        wr("model tags", "find that tag", "get", f"{M}/tags", ma, ok={200}, save="tagbg", find={"name": f"{tag} tag bg"}),
        wr("model tags", "tag the model at once", "post", f"{M}/tags?wait=true", ma, {"name": f"{tag} tag"}, {200, 201, 202},
           save="mtag"),
        wr("model tags", "describe the tag", "patch", f"{M}/tags/{{mtag}}", ma, {"description": "changed by the self-test"}, {200}),
        wr("model tags", "download the tag", "get", f"{M}/tags/{{mtag}}/download", ma, ok={200}),
        wr("model tags", "compare the two tags (in the background)", "post", "/api/v1/compare", ma,
           {"left": {"kind": "tag", "id": "{tagbg}"}, "right": {"kind": "tag", "id": "{mtag}"}}, {200, 202}, **bg("cmptask")),
        wr("model tags", "the fields the comparison offers", "post", "/api/v1/compare/fields", ma,
           {"left": {"kind": "tag", "id": "{tagbg}"}, "right": {"kind": "model", "id": m}}, {200}),
        wr("model tags", "compare a tag with the model now, at once", "post", "/api/v1/compare?wait=true", ma,
           {"left": {"kind": "tag", "id": "{tagbg}"}, "right": {"kind": "model", "id": m}}, {200}),
        wr("model tags", "the comparison as Excel (in the background)", "post", "/api/v1/compare/download", ma,
           {"left": {"kind": "tag", "id": "{tagbg}"}, "right": {"kind": "model", "id": m}}, {200, 202}, **bg("cmpxtask")),
        wr("model tags", "bring the model back to the tag (in the background; nothing changed since)", "post",
           f"{M}/tags/{{mtag}}/restore", ma, {"note": "the self-test"}, {200, 202}, **bg("restoretask")),
        wr("model tags", "remove the tag", "delete", f"{M}/tags/{{mtag}}", ma, ok={200, 204}),
        wr("model tags", "remove the other tag", "delete", f"{M}/tags/{{tagbg}}", ma, ok={200, 204}),
        dict(area="model tags", what="refused: tag as a Report Viewer", method="post", path=f"{M}/tags?wait=true",
             who=rv, body={"name": f"{tag} refused"}, refused=True),
        # a model's own backups (made on the model page): one made in the background, pinned, unpinned, deleted
        wr("model backups", "back up the model (in the background)", "post", f"{M}/backups", ma, {"note": f"{tag}"}, {200, 202},
           save="mbtask", until={"path": "/api/v1/tasks/{mbtask}", "status": ["done"], "seconds": 300}),   # the task itself
        wr("model backups", "find the backup", "get", f"{M}/backups", ma, ok={200}, save="mbfile", find={"where": "model"},
           find_key="file"),
        wr("model backups", "pin it", "post", f"{M}/backups/{{mbfile}}/pin", ma, {"pinned": True}, {200}),
        wr("model backups", "unpin it", "post", f"{M}/backups/{{mbfile}}/pin", ma, {"pinned": False}, {200}),
        wr("model backups", "delete it", "post", f"{M}/backups/{{mbfile}}/delete", ma, ok={200}),
        dict(area="model backups", what="refused: back up as a Report Viewer", method="post", path=f"{M}/backups",
             who=rv, body={"note": tag}, refused=True),
        # the backup schedules: saved back as they are
        wr("backup schedules", "save the application schedule unchanged", "put", "/api/v1/admin/backups/schedules/application",
           body={}, ok={200}),
        wr("backup schedules", "save the infrastructure schedule unchanged", "put",
           "/api/v1/admin/backups/schedules/infrastructure", body={}, ok={200}),
        dict(area="backup schedules", what="refused: change as an Architect", method="put",
             path="/api/v1/admin/backups/schedules/application", who=a, body={}, refused=True),
        # changes sent in a batch (D165), and a merge planned from the run's other model (never applied)
        wr("model changes", "send changes in a batch", "post", f"{M}/changes/batch", ma,
           {"changes": [{"op": "entity.create", "args": {"data": {"entity_type": "ApplicationComponent",
                                                                  "name": f"{tag} batch application"}}}]}, {200}),
        dict(area="model changes", what="refused: a batch as a Report Viewer", method="post", path=f"{M}/changes/batch",
             who=rv, body={"changes": [{"op": "entity.create", "args": {"data": {"entity_type": "ApplicationComponent",
                                                                                 "name": f"{tag} refused"}}}]}, refused=True),
        # a metamodel draft's round of review: made, commented, sent back, resubmitted, rejected, opened again, rejected
        wr("metamodel drafts", "draft changes to the model's metamodel", "post", "/api/v1/metamodel-drafts", ma,
           {"kind": "changes", "target": m, "name": f"{tag} draft"}, save="mdraft"),
        wr("metamodel drafts", "comment on it", "post", "/api/v1/metamodel-drafts/{mdraft}/comments", ma,
           {"body": "a comment from the self-test"}, {200, 201}),
        wr("metamodel drafts", "send it back for changes", "post", "/api/v1/metamodel-drafts/{mdraft}/send-back", su,
           {"note": "the self-test sends it back"}, {200}),
        wr("metamodel drafts", "resubmit it", "post", "/api/v1/metamodel-drafts/{mdraft}/resubmit", ma, {"note": ""}, {200}),
        wr("metamodel drafts", "reject it", "post", "/api/v1/metamodel-drafts/{mdraft}/reject", su,
           {"reason": "the self-test rejects it"}, {200}),
        wr("metamodel drafts", "open it again", "post", "/api/v1/metamodel-drafts/{mdraft}/reopen", su, {"note": ""}, {200}),
        wr("metamodel drafts", "reject it for good", "post", "/api/v1/metamodel-drafts/{mdraft}/reject", su,
           {"reason": "the self-test is done with it"}, {200}),
        dict(area="metamodel drafts", what="refused: draft as a Report Viewer", method="post", path="/api/v1/metamodel-drafts",
             who=rv, body={"kind": "changes", "target": m, "name": f"{tag} refused"}, refused=True),
        # background jobs: the job runner's heartbeat asked for and followed to its end
        wr("background jobs", "ask the job runner for a heartbeat", "post", "/api/v1/jobs/heartbeat", su, {"note": tag}, {200, 202},
           save="hbjob", save_from="job_id",
           until={"path": "/api/v1/jobs/{hbjob}", "status": ["succeeded"], "seconds": 300}),
        wr("background jobs", "save the job slots unchanged", "put", "/api/v1/jobs/slots", body={}, ok={200}),
        dict(area="background jobs", what="refused: change the slots as an Architect", method="put", path="/api/v1/jobs/slots",
             who=a, body={}, refused=True),
        # the admin pages that measure or check, and settings saved back as they are
        wr("admin", "save the settings unchanged", "put", "/api/v1/admin/settings", body={}, ok={200}),
        wr("admin", "save the resource history's settings unchanged", "put", "/api/v1/admin/resources/settings", body={},
           ok={200}),
        wr("admin", "take a resource sample", "post", "/api/v1/admin/resources/sample", ok={200}),
        # not here: the log sizes (saving them can write the config file) and the allow lists (saving them reloads the
        # front door): left to their screens' journeys, which read them only
        # a day of the API's logs kept on disk, then its errors read (the day is needed: run 13 answered 400 without it)
        wr("admin", "the API's kept log files", "get", "/api/v1/admin/logs/files?service=api", ok={200}, save="logday",
           save_from="files.0.day", optional=True),
        wr("admin", "read a day of the API's logs", "get", "/api/v1/admin/logs/read?services=api&day={logday}&level=error",
           ok={200}),
        wr("admin", "the web server's log files", "get", "/api/v1/admin/logs/web/files", ok={200}),
        wr("admin", "check the database's integrity (in the background)", "post", "/api/v1/admin/db-integrity", body={},
           ok={200, 202}),
        wr("admin", "measure the database for optimisation", "post", "/api/v1/admin/optimisation", body={}, save="optreport"),
        wr("admin", "the optimisation report as Excel", "get", "/api/v1/admin/optimisation/{optreport}/xlsx", ok={200}),
        wr("admin", "a sizing estimate (not saved)", "post", "/api/v1/admin/sizing", body={"users": 50, "models": 10}, ok={200}),
        # a saved estimate read three ways, when the installation has one (the run saves none: nothing deletes one)
        wr("admin", "the saved sizing estimates", "get", "/api/v1/admin/sizing", ok={200}, save="sizing",
           save_from="saved.0.id", optional=True),
        wr("admin", "a saved estimate as JSON", "get", "/api/v1/admin/sizing/{sizing}/json", ok={200}),
        wr("admin", "a saved estimate as Excel", "get", "/api/v1/admin/sizing/{sizing}/xlsx", ok={200}),
        wr("admin", "a saved estimate's compose override", "get", "/api/v1/admin/sizing/{sizing}/override", ok={200}),
        # the database's upkeep, looked at and planned only: the locks, a check, what a tidy would do, and the two
        # previews asked of what is not there (nothing compacted, no session stopped: their confirmations are never sent)
        wr("database upkeep", "who blocks whom", "get", "/api/v1/admin/db-maintenance/locks", ok={200}),
        wr("database upkeep", "check every database now", "post", "/api/v1/admin/db-maintenance/check", body={}, ok={200}),
        wr("database upkeep", "what a tidy would do", "post", "/api/v1/admin/db-maintenance/tidy", body={"dry_run": True},
           ok={200}),
        wr("database upkeep", "a compact preview of a table that is not there", "post",
           "/api/v1/admin/db-maintenance/compact-preview", body={"database": f"self_test_{sid}", "table": "none"}, ok={400}),
        wr("database upkeep", "a stop preview of a session that is not there", "post",
           "/api/v1/admin/db-maintenance/stop-preview", body={"pid": 0}, ok={400}),
        dict(area="database upkeep", what="refused: check as an Architect", method="post",
             path="/api/v1/admin/db-maintenance/check", who=a, body={}, refused=True),
        wr("admin", "check a config file's text", "post", "/api/v1/admin/config-file/check", body={"text": ""},
           ok={200, 400}),
        wr("admin", "export the settings", "post", "/api/v1/admin/settings-transfer/export", body={}, ok={200}),
        dict(area="admin", what="refused: change the settings as an Architect", method="put", path="/api/v1/admin/settings",
             who=a, body={}, refused=True),
        # alerting: a check of the run's own, its levels changed, silenced a minute, removed
        wr("alerting", "add a check of the run's own", "post", "/api/v1/admin/alerting/custom",
           body={"key": f"self-test-{sid}", "name": f"{tag} check", "kind": "sql", "target": "SELECT 1", "warning": 5,
                 "critical": 10}, ok={200}),
        wr("alerting", "change its levels", "post", f"/api/v1/admin/alerting/custom:self-test-{sid}/config",
           body={"warning": 6, "critical": 12}, ok={200}),
        wr("alerting", "silence it for a minute", "post", "/api/v1/admin/alerting/silence",
           body={"key": f"custom:self-test-{sid}", "minutes": 1, "reason": "the self-test"}, ok={200}),
        wr("alerting", "remove it", "post", f"/api/v1/admin/alerting/custom:self-test-{sid}/delete", body={}, ok={200}),
        dict(area="alerting", what="refused: add a check as an Architect", method="post", path="/api/v1/admin/alerting/custom",
             who=a, body={"key": f"self-test-{sid}-no", "kind": "sql", "target": "SELECT 1"}, refused=True),
        # the SQL window: one read-only query, rolled back (refused where the window is off or asks for a login)
        wr("sql window", "run a read-only query", "post", "/api/v1/sql/query", body={"database": "", "sql": "SELECT 1"},
           ok={200, 400, 404}),
        wr("sql window", "explain it", "post", "/api/v1/sql/explain", body={"database": "", "sql": "SELECT 1"},
           ok={200, 400, 404}),
        dict(area="sql window", what="refused: a query as an Architect", method="post", path="/api/v1/sql/query", who=a,
             body={"database": "", "sql": "SELECT 1"}, refused=True, refused_also={404}),
        # role mappings: one of the run's own (a Keycloak role nobody has) given and taken away
        wr("role mappings", "map a Keycloak role to Auditor", "post", "/api/v1/role-mappings",
           body={"keycloak_role": f"self_test_{sid}_role", "app_role": "auditor"}, ok={200, 201}, save="rmap"),
        wr("role mappings", "take the mapping away", "delete", "/api/v1/role-mappings/{rmap}", ok={200, 204}),
        dict(area="role mappings", what="refused: map as an Architect", method="post", path="/api/v1/role-mappings", who=a,
             body={"keycloak_role": f"self_test_{sid}_no", "app_role": "auditor"}, refused=True),
        # the service desk: a request raised (Something else), talked about, a file added and read, its priority set by
        # the desk, and cancelled by the one who asked (requests are never deleted: cancelled is where a test's ends)
        wr("service desk", "raise a request", "post", "/api/v1/service-desk/tickets", by=a,
           body={"type": "other", "title": f"{tag} request", "priority": "low", "fields": {"what": f"{tag}: nothing, a test"}},
           ok={200, 201}, save="ticket", save_from="id"),
        wr("service desk", "read it", "get", "/api/v1/service-desk/tickets/{ticket}", by=a, ok={200}, shows=f"{tag} request"),
        wr("service desk", "comment on it", "post", "/api/v1/service-desk/tickets/{ticket}/comment", by=a,
           body={"note": f"{tag} comment"}, ok={200, 201}),
        wr("service desk", "add a file to it", "post", "/api/v1/service-desk/tickets/{ticket}/files", by=a,
           data="deliveries/good.xlsx", ok={200, 201}, save="ticketfile", save_from="id"),
        wr("service desk", "download the file", "get", "/api/v1/service-desk/tickets/{ticket}/files/{ticketfile}", by=a,
           ok={200}),
        wr("service desk", "the desk sets its priority", "post", "/api/v1/service-desk/tickets/{ticket}/priority",
           body={"priority": "normal"}, ok={200}),
        dict(area="service desk", what="refused: cancel another's request as a Report Viewer", method="post",
             path="/api/v1/service-desk/tickets/{ticket}/cancel", who=rv, body={"note": "no"}, refused=True,
             refused_also={404}),
        wr("service desk", "cancel it", "post", "/api/v1/service-desk/tickets/{ticket}/cancel", by=a,
           body={"note": f"{tag}: done with"}, ok={200}),
        wr("service desk", "my requests, cancelled ones too", "get", "/api/v1/service-desk/tickets?view=mine&status=all", by=a,
           ok={200}, shows=f"{tag} request"),
        # the self-test's own reads, of this run (its controls are left out of the goal, D926)
        wr("self-test", "find this run", "get", "/api/v1/admin/tests", ok={200}, save="thisrun", find={"state": "running"}),
        wr("self-test", "this run's report so far", "get", "/api/v1/admin/tests/{thisrun}/report", ok={200}),
        wr("self-test", "this run's report as Excel", "get", "/api/v1/admin/tests/{thisrun}/report?format=xlsx", ok={200}),
        wr("self-test", "this run's log file", "get", "/api/v1/admin/tests/{thisrun}/files/run.log", ok={200, 404}),
        wr("self-test", "this run as it stands", "get", "/api/v1/admin/tests/{thisrun}?outcome=failed", ok={200}),
        wr("self-test", "this run, watched as it happens", "get", "/api/v1/admin/tests/{thisrun}/live?after=0&from=0", ok={200}),
        wr("self-test", "a screenshot this run does not have", "get", "/api/v1/admin/tests/{thisrun}/screenshot/1",
           ok={404}),
        wr("self-test", "save the runner's settings unchanged", "put", "/api/v1/admin/tests/settings", body={},
           ok={200, 503}),
        dict(area="self-test", what="refused: the runs' list as a Report Viewer", method="get", path="/api/v1/admin/tests",
             who=rv, refused=True),
    ]
    if other:
        OM = f"/api/v1/models/{other}"
        w += [
            wr("model people", "give the run's Architect a role on the other model", "post", f"{OM}/people",
               body={"username": who["architect"], "role": "report-viewer"}, ok={200, 201}),
            wr("model people", "take the role away", "delete", f"{OM}/people/{who['architect']}?role=report-viewer",
               ok={200, 204}),
            dict(area="model people", what="refused: give a role as an Architect", method="post", path=f"{OM}/people", who=a,
                 body={"username": who["architect"], "role": "report-viewer"}, refused=True, refused_also={404}),
            # as the Super Admin: the first model's Model Admin may not read the second (run 14: "No model ..., or you
            # may not read it"), and a merge reads the model it comes from
            wr("model merges", "plan a merge from the run's second model (in the background; never applied)", "post",
               f"{M}/merges", su, {"source_model": other}, {200, 202}, **bg("mergetask")),
            dict(area="model merges", what="refused: plan a merge as a Report Viewer", method="post", path=f"{OM}/merges",
                 who=rv, body={"source_model": m}, refused=True, refused_also={404}),
            wr("model tags", "compare the run's two models", "post", "/api/v1/compare?wait=true", su,
               {"left": {"kind": "model", "id": m}, "right": {"kind": "model", "id": other}}, {200}),
        ]
    return w


def model_extras(m: str, ent: str | None, sid: str, tag: str) -> list[dict]:
    """A model's own KPIs, report designs, saved grid views and favourites, data quality and publishing (R14.5, batch 3;
    owner, 25 Nov 2026, 16:20: "Please add more test cases to acheive this goal"): each made, changed, read back and
    removed inside the run's first model (self_test_<id>_1); each area refused for a role that may not."""
    a, ma, rv = "architect", "model-admin", "report-viewer"
    M = f"/api/v1/models/{m}"
    spec = {"entity_type": "{rdtype}", "columns": ["name"]}

    def wr(area, what, method, path, by=ma, body=None, ok=None, **kw):
        return dict(area=area, what=what, method=method, path=path, who=by, body=body, ok=ok or {200, 201}, **kw)

    w = [
        # the model's own KPIs (Model Admins): a count of applications, renamed, read back in the trends, no longer kept
        wr("model KPIs", "add a KPI of the model's own", "post", f"{M}/kpis/definitions",
           body={"name": f"{tag} kpi", "kind": "count", "entity_type_code": "ApplicationComponent",
                 "description": "made by the self-test"}, save="kpi"),
        wr("model KPIs", "change it", "put", f"{M}/kpis/definitions/{{kpi}}",
           body={"name": f"{tag} kpi changed", "kind": "count", "entity_type_code": "ApplicationComponent"}, ok={200}),
        wr("model KPIs", "read it back in the trends", "get", f"{M}/kpis", ok={200}, shows=f"{tag} kpi changed"),
        wr("model KPIs", "stop keeping it", "post", f"{M}/kpis/definitions/{{kpi}}/delete", ok={200}),
        dict(area="model KPIs", what="refused: add a KPI as a Report Viewer", method="post", path=f"{M}/kpis/definitions",
             who=rv, body={"name": f"{tag} refused", "kind": "count", "entity_type_code": "ApplicationComponent"},
             refused=True, refused_also={404}),
        # the report designer: a type with a report view found, a design previewed, kept, changed and deleted by its maker
        wr("report designs", "find a type the designer offers", "get", f"{M}/report-designer", a, ok={200}, save="rdtype",
           find={"code": "ApplicationComponent", "has_view": True}, find_key="code"),
        wr("report designs", "preview a design", "post", f"{M}/report-designs/preview", a, {"spec": spec}, {200}),
        wr("report designs", "keep the design", "post", f"{M}/report-designs", a, {"name": f"{tag} design", "spec": spec},
           save="design"),
        wr("report designs", "change it", "put", f"{M}/report-designs/{{design}}", a,
           {"name": f"{tag} design changed", "spec": spec}, {200}),
        dict(area="report designs", what="refused: change another's design as a Report Viewer", method="put",
             path=f"{M}/report-designs/{{design}}", who=rv, body={"name": f"{tag} refused", "spec": spec}, refused=True,
             refused_also={404}),
        wr("report designs", "delete it", "post", f"{M}/report-designs/{{design}}/delete", a, ok={200}),
        # saved grid views and favourites (each person's own)
        wr("saved views", "save a grid view", "post", "/api/v1/me/saved-views",
           body={"name": f"{tag} view", "view_kind": "entity_grid", "model": m, "target": "ApplicationComponent",
                 "config": {}}, save="sview"),
        wr("saved views", "change it", "post", "/api/v1/me/saved-views",
           body={"id": "{sview}", "name": f"{tag} view changed", "view_kind": "entity_grid", "config": {}}, ok={200}),
        wr("saved views", "read it back", "get", f"/api/v1/me/saved-views?model={m}&kind=entity_grid", ok={200},
           shows=f"{tag} view changed"),
        wr("saved views", "mark it a favourite", "post", "/api/v1/me/favourites",
           body={"kind": "view", "id": "{sview}", "favourite": True, "label": f"{tag} view"}, ok={200}),
        wr("saved views", "read the favourites", "get", "/api/v1/me/favourites", ok={200}),
        wr("saved views", "unmark it", "post", "/api/v1/me/favourites",
           body={"kind": "view", "id": "{sview}", "favourite": False, "label": ""}, ok={200}),
        dict(area="saved views", what="refused: delete another's view as an Architect", method="delete",
             path="/api/v1/me/saved-views/{sview}", who=a, refused=True),
        wr("saved views", "delete it", "delete", "/api/v1/me/saved-views/{sview}", ok={200, 204}),
        # data quality (D245): measured in the background, one entity and one type rechecked, a rule previewed
        wr("data quality", "measure the model (in the background)", "post", f"{M}/quality/run", ok={200, 202}),
        wr("data quality", "the measurements asked for", "get", f"{M}/quality/jobs", ok={200}),
        wr("data quality", "recheck every application (in the background)", "post",
           f"{M}/quality/types/ApplicationComponent/recheck", ok={200, 202}),
        wr("data quality", "preview a naming rule", "post", f"{M}/quality/rules/preview",
           body={"code": "ST-1", "name": f"{tag} rule", "kind": "naming", "entity_type": "ApplicationComponent",
                 "spec": {"pattern": ".+"}}, ok={200}),
        dict(area="data quality", what="refused: leave a field out as an Architect", method="post",
             path=f"{M}/quality/leave-out", who=a, body={"item": "field:description", "entity_type": "*"}, refused=True,
             refused_also={404}),
        # the model's sheets made (in the background, and an empty template at once), and an Excel load: uploaded,
        # previewed, its columns mapped, then deleted before it is added (nothing reaches the model)
        wr("sheets and loads", "the model's sheets (in the background)", "post", f"{M}/sheets", a,
           {"types": ["ApplicationComponent"], "format": "xlsx"}, {200, 202}, save="shtask", save_at="task",
           until={"path": "/api/v1/tasks/{shtask}", "status": ["done"], "seconds": 300}),
        wr("sheets and loads", "an empty template at once", "post", f"{M}/sheets?wait=true", a,
           {"types": ["ApplicationComponent"], "format": "xlsx", "blank": True}, {200}),
        wr("sheets and loads", "load an Excel file", "post", f"{M}/loads", a, ok={200, 201, 202}, data="deliveries/good.xlsx",
           save="loadid", save_from="load.id"),
        wr("sheets and loads", "its preview", "get", "/api/v1/loads/{loadid}", a, ok={200},
           until={"path": "/api/v1/loads/{loadid}", "status": ["previewed"], "seconds": 300}),
        wr("sheets and loads", "map its columns as they are", "post", "/api/v1/loads/{loadid}/mapping", a, {"mapping": {}},
           {200, 202}),
        wr("sheets and loads", "the model's loads", "get", f"{M}/loads", a, ok={200}),
        # the metamodel as packages read it, and a move to another framework asked about (never made)
        wr("metamodel", "the model's metamodel as one document", "get", f"{M}/metamodel-spec", a, ok={200},
           shows="entity_types"),
        wr("metamodel", "a framework move asked with a map that is not JSON", "get",
           f"{M}/framework-preview?target={m}&map=not-json", a, ok={400}),
        wr("metamodel", "a framework move to a framework that is not one", "get",
           f"{M}/framework-preview?target=self_test_{sid}", a, ok={400, 404}),
        dict(area="metamodel", what="refused: the metamodel with no role", method="get", path=f"{M}/metamodel-spec",
             who="no-role", refused=True, refused_also={404}),
        dict(area="sheets and loads", what="refused: delete it as a Report Viewer", method="delete",
             path="/api/v1/loads/{loadid}", who=rv, refused=True, refused_also={404}),
        wr("sheets and loads", "delete the load before it is added", "delete", "/api/v1/loads/{loadid}", a, ok={200, 204}),
        # publishing: asked for and withdrawn (409: already published or already waiting; never approved here)
        wr("publishing", "the model's publishing state", "get", f"{M}/publishing", ok={200}),
        wr("publishing", "ask for it to be published", "post", f"{M}/request-publish", body={"note": tag}, ok={200, 409}),
        wr("publishing", "withdraw the request", "post", f"{M}/withdraw-publish-request", body={"note": tag},
           ok={200, 409}),
        dict(area="publishing", what="refused: ask as a Report Viewer", method="post", path=f"{M}/request-publish", who=rv,
             body={"note": tag}, refused=True, refused_also={404, 409}),
    ]
    if ent:
        w.insert(w.index(next(x for x in w if x["what"] == "the measurements asked for")) + 1,
                 wr("data quality", "recheck one entity now", "post", f"{M}/entities/{ent}/quality/recheck", ok={200}))
    return w


def project_extras(p: str, tag: str) -> list[dict]:
    """A project's placeholder views and its reference library's folders (R14.5, batch 3), as the project's Architect;
    refused for its Stakeholder (the Report Viewer)."""
    b = f"/api/v1/projects/{p}"
    a, rv = "architect", "report-viewer"
    return [
        dict(area="placeholder views", what="add a placeholder view", method="post", path=f"{b}/placeholder-views", who=a,
             body={"name": f"{tag} placeholder", "kind": "text", "description": "made by the self-test"}, ok={200, 201},
             save="phcode", save_from="code"),
        dict(area="placeholder views", what="rename it", method="put", path=f"{b}/placeholder-views/{{phcode}}", who=a,
             body={"name": f"{tag} placeholder changed"}, ok={200}),
        dict(area="placeholder views", what="remove it", method="delete", path=f"{b}/placeholder-views/{{phcode}}", who=a,
             ok={200, 204}),
        dict(area="placeholder views", what="refused: add as the project's Stakeholder", method="post",
             path=f"{b}/placeholder-views", who=rv, body={"name": f"{tag} refused", "kind": "text"}, refused=True),
        dict(area="reference folders", what="add a folder to Reference", method="post", path=f"{b}/reference/folders",
             who=a, body={"path": f"{tag} folder"}, ok={200, 201}, save="rfolder", save_from="folder"),
        dict(area="reference folders", what="read Reference", method="get", path=f"{b}/reference", who=a, ok={200}),
        dict(area="reference folders", what="take the folder away", method="post", path=f"{b}/reference/folders", who=a,
             body={"path": "{rfolder}", "delete": True}, ok={200, 201}),     # 201 in run 15
        dict(area="reference folders", what="refused: add as the project's Stakeholder", method="post",
             path=f"{b}/reference/folders", who=rv, body={"path": f"{tag} refused"}, refused=True),
    ]


def admin_extras(sid: str, tag: str) -> list[dict]:
    """Webhooks, the sites list, job priorities, the API harness and an application backup's pin (R14.5, batch 3), as the
    Super Admin, each with the run's own names and removed again; each refused for the Architect. Nothing is sent: the
    webhook is off and its address and the site's are .invalid (never resolved). A priority is saved back as it is."""
    su, a = "super-admin", "architect"
    nowhere = f"https://self-test-{sid}.invalid"

    def wr(area, what, method, path, body=None, ok=None, **kw):
        return dict(area=area, what=what, method=method, path=path, who=su, body=body, ok=ok or {200, 201}, **kw)

    return [
        wr("webhooks", "add a webhook (switched off)", "post", "/api/v1/admin/webhooks",
           {"name": f"{tag} hook", "url": f"{nowhere}/hook", "kinds": [], "enabled": False}, save="hook"),
        wr("webhooks", "rename it", "patch", "/api/v1/admin/webhooks/{hook}", {"name": f"{tag} hook changed"}, {200}),
        wr("webhooks", "read the webhooks", "get", "/api/v1/admin/webhooks", ok={200}, shows=f"{tag} hook changed"),
        wr("webhooks", "its deliveries", "get", "/api/v1/admin/webhooks/{hook}/deliveries", ok={200}),
        wr("webhooks", "delete it", "delete", "/api/v1/admin/webhooks/{hook}", ok={200, 204}),
        dict(area="webhooks", what="refused: add as an Architect", method="post", path="/api/v1/admin/webhooks", who=a,
             body={"name": f"{tag} refused", "url": f"{nowhere}/no"}, refused=True),
        wr("sites", "add a site", "post", "/api/v1/sites", {"name": f"{tag} site", "url": nowhere, "note": "the self-test"},
           save="site"),
        wr("sites", "change its note", "put", "/api/v1/sites/{site}", {"note": "changed by the self-test"}, {200}),
        wr("sites", "remove it", "delete", "/api/v1/sites/{site}", ok={200, 204}),
        dict(area="sites", what="refused: add as an Architect", method="post", path="/api/v1/sites", who=a,
             body={"name": f"{tag} refused", "url": f"{nowhere}/no"}, refused=True),
        wr("job priorities", "find a kind of job as it ships", "get", "/api/v1/jobs/priorities", ok={200}, save="jptask",
           find={"changed": False}, find_key="task"),
        wr("job priorities", "and its level", "get", "/api/v1/jobs/priorities", ok={200}, save="jplevel",
           find={"changed": False}, find_key="level"),
        wr("job priorities", "save its level as it is", "put", "/api/v1/jobs/priorities/{jptask}", {"level": "{jplevel}"},
           {200}),
        dict(area="job priorities", what="refused: change a level as an Architect", method="put",
             path="/api/v1/jobs/priorities/{jptask}", who=a, body={"level": "{jplevel}"}, refused=True),
        # the test bench's read-only door (its state, the database checks it runs from outside); the rest is left out
        wr("test bench", "the installation's state for the test bench", "get", "/api/v1/admin/testbench/state", ok={200}),
        wr("test bench", "the database checks, from outside", "post", "/api/v1/admin/testbench/db-checks", body={}, ok={200},
           shows='"results"'),
        dict(area="test bench", what="refused: the database checks as an Architect", method="post",
             path="/api/v1/admin/testbench/db-checks", who=a, body={}, refused=True),
        wr("api harness", "one call as yourself", "post", "/api/v1/admin/api-harness/call",
           {"method": "get", "path": "/api/v1/me", "as": "me"}, {200}),
        wr("api harness", "save a case", "post", "/api/v1/admin/api-harness/cases",
           {"name": f"{tag} case", "method": "get", "path": "/api/v1/me", "as": "super-admin", "expect_status": 200},
           save="hcase"),
        wr("api harness", "read the cases", "get", "/api/v1/admin/api-harness/cases", ok={200}, shows=f"{tag} case"),
        wr("api harness", "delete the case", "delete", "/api/v1/admin/api-harness/cases/{hcase}", ok={200, 204}),
        dict(area="api harness", what="refused: a call as an Architect", method="post", path="/api/v1/admin/api-harness/call",
             who=a, body={"method": "get", "path": "/api/v1/me"}, refused=True),
        # an existing application backup pinned and unpinned (none made here: a new one would prune the oldest)
        wr("application backups", "find an application backup not pinned", "get", "/api/v1/admin/backups", ok={200},
           save="appbk", find={"format": "eax-application-backup/1", "pinned": False}, find_key="name", optional=True),
        wr("application backups", "pin it", "post", "/api/v1/admin/backups/application/{appbk}/pin", {"pinned": True}, {200}),
        wr("application backups", "unpin it", "post", "/api/v1/admin/backups/application/{appbk}/pin", {"pinned": False},
           {200}),
        dict(area="application backups", what="refused: pin as an Architect", method="post",
             path="/api/v1/admin/backups/application/{appbk}/pin", who=a, body={"pinned": True}, refused=True),
    ]


def job_starters(m: str, other: str | None, p: str | None, tag: str) -> list[dict]:
    """Background tasks started through the API and followed to their end (R14.5, batch 4; owner, 25 Nov 2026, 17:01:
    "Yes please build 1 and 2"): the run's gap analysis looked into, compared again, downloaded (Word and Excel) and its two
    results compared; its common analysis compared again, its close names matched and downloaded; the change log exported;
    the run's project backed up, downloaded and the backup deleted; the run's model as a package; a second metamodel draft
    applied (one new metamodel version of the run's model, nothing in it changed); the model's family and a tag before a
    wizard. Each in the run's own data; each area refused for a role that may not."""
    su, ma, rv = "super-admin", "model-admin", "report-viewer"
    M = f"/api/v1/models/{m}"

    def wr(area, what, method, path, by=su, body=None, ok=None, **kw):
        return dict(area=area, what=what, method=method, path=path, who=by, body=body, ok=ok or {200, 201}, **kw)

    def bg(save, seconds=300):
        return {"save": save, "save_at": "task", "until": {"path": "/api/v1/tasks/{" + save + "}", "status": ["done"],
                                                           "seconds": seconds}}

    w: list[dict] = []
    if other:
        w += [
            # the gap analysis the run made earlier (analyses): looked into, compared again, downloaded, its results compared
            wr("gap analysis work", "find the run's gap analysis", "get", f"/api/v1/gaps?model={m}", ok={200}, save="gapid",
               find={"name": f"{tag} gap analysis"}),
            wr("gap analysis work", "open it", "get", "/api/v1/gaps/{gapid}", ok={200}, save="gapitem", save_from="items.0.id",
               optional=True),
            wr("gap analysis work", "a gap's detail", "get", "/api/v1/gaps/{gapid}/items/{gapitem}/detail", ok={200}),
            wr("gap analysis work", "note on the gap", "patch", "/api/v1/gaps/{gapid}/items/{gapitem}",
               body={"note": "noted by the self-test"}, ok={200}),
            wr("gap analysis work", "compare it again (in the background)", "post", "/api/v1/gaps/{gapid}/refresh", body={},
               ok={200, 202}, **bg("gaprtask")),
            wr("gap analysis work", "the work packages it suggests", "get", "/api/v1/gaps/{gapid}/migration-plan?by=domain",
               ok={200}),
            wr("gap analysis work", "download it as Word (in the background)", "get",
               "/api/v1/gaps/{gapid}/download?background=true&format=docx", ok={200, 202}, **bg("gapdtask")),
            wr("gap analysis work", "download it as Excel (in the background)", "get",
               "/api/v1/gaps/{gapid}/download?background=true&format=xlsx", ok={200, 202}, **bg("gapxtask")),
            wr("gap analysis work", "its newest result", "get", "/api/v1/gaps/{gapid}", ok={200}, save="runa",
               save_from="runs.0.id"),
            wr("gap analysis work", "and the one before", "get", "/api/v1/gaps/{gapid}", ok={200}, save="runb",
               save_from="runs.1.id", optional=True),
            wr("gap analysis work", "compare the two results", "get", "/api/v1/gap-runs/compare?a={runa}&b={runb}&format=json",
               ok={200}),
            wr("gap analysis work", "the comparison as Excel (in the background)", "get",
               "/api/v1/gap-runs/compare?a={runa}&b={runb}&background=true&format=xlsx", ok={200, 202}, **bg("gapctask")),
            wr("gap analysis work", "delete the earlier result", "delete", "/api/v1/gap-runs/{runb}", ok={200, 204}),
            dict(area="gap analysis work", what="refused: compare it again with no role", method="post",
                 path="/api/v1/gaps/{gapid}/refresh", who="no-role", body={}, refused=True, refused_also={404}),
            # the common analysis the run made earlier: compared again, close names matched, downloaded
            wr("common analysis work", "find the run's common analysis", "get", f"/api/v1/commons?model={m}", ok={200},
               save="comid", find={"name": f"{tag} common analysis"}),
            wr("common analysis work", "compare it again (in the background)", "post", "/api/v1/commons/{comid}/refresh",
               body={}, ok={200, 202}, **bg("comrtask")),
            # the run's two models have no close names to decide on: deciding none is refused in words (run 14)
            wr("common analysis work", "decide no close names: refused in words (in the background)", "post",
               "/api/v1/commons/{comid}/suggestions", body={"confirm": [], "reject": []}, ok={200, 202}, save="comstask",
               save_at="task", until={"path": "/api/v1/tasks/{comstask}", "status": ["failed"], "seconds": 300,
                                      "said": "Confirm or reject at least one suggestion."}),
            wr("common analysis work", "download it as Word (in the background)", "get",
               "/api/v1/commons/{comid}/download?background=true&format=docx", ok={200, 202}, **bg("comdtask")),
            dict(area="common analysis work", what="refused: compare it again with no role", method="post",
                 path="/api/v1/commons/{comid}/refresh", who="no-role", body={}, refused=True, refused_also={404}),
        ]
    w += [
        # the change log exported, in the background and at once
        wr("change log export", "export it as Excel (in the background)", "get",
           f"/api/v1/change-log/export?background=true&format=xlsx&model={m}", ok={200, 202}, **bg("cltask")),
        wr("change log export", "export it as CSV at once", "get", f"/api/v1/change-log/export?format=csv&model={m}", ok={200}),
        dict(area="change log export", what="refused: export with no role", method="get",
             path=f"/api/v1/change-log/export?format=csv&model={m}", who="no-role", refused=True, refused_also={404}),
        # the run's model as a package, in the background
        wr("model package", "the model as a package (in the background)", "get",
           f"{M}/package?background=true&format=zip&content=content", ma, ok={200, 202}, **bg("pkgtask")),
        wr("model package", "its metamodel as one workbook (in the background)", "get",
           f"{M}/package?background=true&format=xlsx&content=metamodel", ma, ok={200, 202}, **bg("pkgxtask")),
        dict(area="model package", what="refused: the package with no role", method="get",
             path=f"{M}/package?format=zip&content=content", who="no-role", refused=True, refused_also={404}),
        # a second draft of the run's model's metamodel, applied: one new metamodel version, nothing in it changed
        wr("metamodel draft applied", "draft the metamodel again", "post", "/api/v1/metamodel-drafts", ma,
           {"kind": "changes", "target": m, "name": f"{tag} draft applied"}, save="mdrafttwo"),
        wr("metamodel draft applied", "read the draft", "get", "/api/v1/metamodel-drafts/{mdrafttwo}", ma, ok={200},
           shows=f"{tag} draft applied"),
        wr("metamodel draft applied", "apply it (in the background)", "post", "/api/v1/metamodel-drafts/{mdrafttwo}/apply", su,
           {"version_label": "self-test", "description": "applied by the self-test"}, {200, 202}, **bg("mdatask")),
        dict(area="metamodel draft applied", what="refused: draft as a Report Viewer", method="post",
             path="/api/v1/metamodel-drafts", who=rv, body={"kind": "changes", "target": m, "name": f"{tag} refused"},
             refused=True, refused_also={404}),
        # the model wizards: the model's family, and a tag before a wizard changes it
        wr("model wizards", "the model's family", "get", f"{M}/wizards/family", ma, ok={200}),
        wr("model wizards", "tag the model before a wizard", "post", f"{M}/wizards/tag-first", ma, {"why": f"{tag} wizard"},
           {200, 201}),
        dict(area="model wizards", what="refused: tag first as a Report Viewer", method="post", path=f"{M}/wizards/tag-first",
             who=rv, body={"why": f"{tag} refused"}, refused=True, refused_also={404}),
    ]
    if p:
        P = f"/api/v1/projects/{p}"
        w += [
            # the run's project backed up in the background, downloaded and the backup deleted
            wr("project backups", "back the project up (in the background)", "post", f"{P}/backups",
               body={"why": f"{tag} project backup"}, ok={200, 202}, **bg("pbtask", 600)),
            wr("project backups", "find the backup", "get", f"{P}/backups", ok={200}, save="pbfile",
               find={"why": f"{tag} project backup"}, find_key="file"),
            wr("project backups", "download it", "get", f"{P}/backups/{{pbfile}}", ok={200}),
            dict(area="project backups", what="refused: back up as the project's Stakeholder", method="post",
                 path=f"{P}/backups", who=rv, body={"why": f"{tag} refused"}, refused=True),
            wr("project backups", "delete the backup", "delete", f"{P}/backups/{{pbfile}}", ok={200, 204}),
        ]
    return w


def risky_writes(m: str, model_name: str, sid: str, tag: str) -> list[dict]:
    """The risky suite's API writes (D927; owner, 25 Nov 2026, 16:37: "Build additional test suite from api and UI to
    allow running risky things ... they will run if and only if someone in full test enables risky option"; 16:41:
    "risky should not allow restart, allow installation down, roatate secrets, or allow full infrastructure restore.
    Model restore is ok, deleting anything like logs models etc is ok. We can assume they will run only testing not in a
    working emviornment"). Settings are saved back as they were read (same_as); deletions reach only what is older than
    ten years or a day in 2000, or the run's own; the run's first model is put back over itself from its own backup.
    Never: a restart (the job runner's included), a full backup or restore, the secrets, the front door's certificate."""
    su, a, ma = "super-admin", "architect", "model-admin"
    M = f"/api/v1/models/{m}"

    def wr(area, what, method, path, by=su, body=None, ok=None, **kw):
        return dict(area=area, what=what, method=method, path=path, who=by, body=body, ok=ok or {200, 201}, risky=True, **kw)

    def refused(area, path, body=None, method="post"):
        return dict(area=area, what="refused: as an Architect", method=method, path=path, who=a, body=body, refused=True,
                    risky=True)

    w = [
        # the logs: their sizes saved back as they are, backed up, those older than ten years deleted
        wr("risky: logs", "save the log sizes as they are", "put", "/api/v1/admin/logs/rolling", ok={200},
           same_as="/api/v1/admin/logs/rolling", keep=["file_kb", "docker_kb", "keep_days"]),
        wr("risky: logs", "back the logs up", "post", "/api/v1/admin/logs/backup", body={"tag": tag[:40]}, ok={200}),
        wr("risky: logs", "delete the logs older than ten years", "post", "/api/v1/admin/logs/clean", body={"days": 3650},
           ok={200}),
        wr("risky: logs", "the screens' debug log on for a minute", "post", "/api/v1/admin/logs/web-debug",
           body={"minutes": 1}, ok={200}),
        wr("risky: logs", "and off again", "post", "/api/v1/admin/logs/web-debug", body={"minutes": 0}, ok={200}),
        refused("risky: logs", "/api/v1/admin/logs/clean", {"days": 3650}),
        # the front door's allow lists saved back as they are (nginx takes them at once: a reload, not a restart)
        wr("risky: allow lists", "save the allow lists as they are", "put", "/api/v1/admin/allow", ok={200},
           same_as="/api/v1/admin/allow", keep=["lists", "trusted"]),
        refused("risky: allow lists", "/api/v1/admin/allow", {"lists": {}, "trusted": []}, "put"),
        # alerting: the test email to an address that cannot exist (409: mail not set up)
        wr("risky: alert email", "send the test email", "post", "/api/v1/admin/alerting/test-email",
           body={"to": f"self-test-{sid}@example.invalid"}, ok={200, 409}),
        refused("risky: alert email", "/api/v1/admin/alerting/test-email", {"to": "x@example.invalid"}),
        # the resource history of one day in 2000 deleted
        wr("risky: resource history", "delete a day of resource history in 2000", "delete",
           "/api/v1/admin/resources?from=2000-01-01&to=2000-01-02", ok={200, 204}),
        refused("risky: resource history", "/api/v1/admin/resources?from=2000-01-01&to=2000-01-02", method="delete"),
        # the job queue: stuck jobs cleared (no restart), finished jobs older than ten years deleted
        wr("risky: job queue", "clear the stuck jobs (no restart)", "post", "/api/v1/jobs/queue/clear-stuck",
           body={"restart": False}, ok={200}),
        wr("risky: job queue", "delete the finished jobs older than ten years", "delete",
           "/api/v1/jobs/queue/history?older_than_days=3650", ok={200, 204}),
        refused("risky: job queue", "/api/v1/jobs/queue/clear-stuck", {"restart": False}),
        # a second factor set up again: the run's own account with no role
        wr("risky: second factor", "reset the run's no-role account's second factor", "post", "/api/v1/people/mfa-reset",
           body={"usernames": [f"svc-self-test-{sid}-no-role"]}, ok={200}),
        refused("risky: second factor", "/api/v1/people/mfa-reset", {"usernames": [f"svc-self-test-{sid}-no-role"]}),
        # settings: exported, compared and taken back in unchanged ("nothing to take"); an undo of no copy refused
        wr("risky: settings transfer", "export the application settings", "post", "/api/v1/admin/settings-transfer/export",
           body={"parts": ["application"]}, ok={200}, save="stfile", save_whole=True),
        wr("risky: settings transfer", "compare the file with the installation", "post",
           "/api/v1/admin/settings-transfer/preview", body={"file": "{stfile}"}, ok={200}),
        wr("risky: settings transfer", "take the same settings in", "post", "/api/v1/admin/settings-transfer/import",
           body={"file": "{stfile}", "picks": {"application": "all"}}, ok={200}),
        wr("risky: settings transfer", "undo with no safety copy (refused, nothing changed)", "post",
           "/api/v1/admin/settings-transfer/undo", body={"copy": ""}, ok={400, 404, 409}),
        refused("risky: settings transfer", "/api/v1/admin/settings-transfer/import",
                {"file": "{}", "picks": {"application": "all"}}),
        # the run's first model backed up, put back over itself from that backup, and the backup deleted
        wr("risky: model restore", "back the model up (in the background)", "post", f"{M}/backups", ma, {"note": f"{tag} risky"},
           {200, 202}, save="rbtask", until={"path": "/api/v1/tasks/{rbtask}", "status": ["done"], "seconds": 300}),
        wr("risky: model restore", "find the backup", "get", f"{M}/backups", ma, ok={200}, save="rbfile",
           find={"where": "model", "why": f"{tag} risky"}, find_key="file"),
        dict(area="risky: model restore", what="refused: put it back as a Report Viewer", method="post",
             path="/api/v1/admin/backups/restore-model", who="report-viewer", risky=True, refused=True,
             body={"where": "model", "model": m, "file": "{rbfile}", "mode": "over", "confirm": model_name}),
    ]
    if model_name:
        w += [wr("risky: model restore", "put the model back over itself (in the background)", "post",
                 "/api/v1/admin/backups/restore-model",
                 body={"where": "model", "model": m, "file": "{rbfile}", "mode": "over", "confirm": model_name},
                 ok={200, 202}, save="rrtask",                    # the answer is the task itself (as a backup's)
                 until={"path": "/api/v1/tasks/{rrtask}", "status": ["done"], "seconds": 600})]
    w += [wr("risky: model restore", "delete the backup", "post", f"{M}/backups/{{rbfile}}/delete", ma, ok={200})]
    return w


def same_as(now: dict, keep: list[str] | None = None) -> dict:
    """The body that saves a setting back as it is: what GET answered, only the keys kept when given."""
    return {k: now.get(k) for k in keep if k in now} if keep else dict(now)


def pick(answer, path: str) -> str | None:
    """The value at a dotted path of an answer ("job_id", "items.0.key"), as text; None when there is none."""
    cur = answer
    for part in path.split("."):
        if isinstance(cur, list) and part.isdigit() and int(part) < len(cur):
            cur = cur[int(part)]
        elif isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    if isinstance(cur, bool) or cur is None or isinstance(cur, (dict, list)):
        return None
    return str(cur) if str(cur) else None


def find(answer, where: dict, key: str = "id") -> str | None:
    """The key of the first item (anywhere in the answer, depth first) whose fields equal all of where's."""
    if isinstance(answer, dict):
        if where and all(answer.get(k) == v for k, v in where.items()) and answer.get(key) not in (None, ""):
            return str(answer[key])
        items = answer.values()
    elif isinstance(answer, list):
        items = answer
    else:
        return None
    for x in items:
        got = find(x, where, key)
        if got:
            return got
    return None


def _fill(x, saved: dict[str, str]):
    if isinstance(x, str):
        for k, v in saved.items():
            x = x.replace("{" + k + "}", v)
        return x
    if isinstance(x, dict):
        return {k: _fill(v, saved) for k, v in x.items()}
    if isinstance(x, list):
        return [_fill(v, saved) for v in x]
    return x


def wait_for(base: str, token: str | None, until: dict, saved: dict[str, str], pause: float = 2.0) -> tuple[str, str]:
    """Waits for what a write started in the background (a preview, an accept) to reach a status."""
    path = _fill(until["path"], saved)
    end = time.time() + until.get("seconds", 120)
    last = ""
    while True:
        status, answer = call(base, "GET", path, token)
        got = (answer.get("status") or (answer.get("load") or {}).get("status")) if isinstance(answer, dict) else None
        last = str(got or status)
        if got in until["status"]:
            said = (answer.get("message") or "") if isinstance(answer, dict) else ""
            if until.get("said") and until["said"] not in str(said):       # the right status, but not for the reason
                return "failed", f"{last}, but it said {str(said)[:200]!r}, expected {until['said']!r}"
            return "passed", f"{last}" + (f": {said}" if until.get("said") else "")
        if got in ("failed", "declined") or status >= 400 or time.time() >= end:
            # what the task said (run 13: "stopped at failed" alone did not say why)
            why = (answer.get("message") or answer.get("error") or "") if isinstance(answer, dict) else ""
            return "failed", f"stopped at {last}, expected {' or '.join(until['status'])}" + (f": {str(why)[:300]}" if why else "")
        time.sleep(pause)


def run(base: str, tokens: dict[str, str], ids: dict[str, str], record: Record, area: str | None = None,
        only: set[str] | None = None) -> dict[str, int]:
    """Runs the writes (of one area, if given); a write whose role is not in this run, or that needs something an
    earlier write did not make, is skipped with the reason. Returns passed and failed counts. only: a repeat of these
    writes (R2.36): the writes run in order up to the last of them (a write needs what earlier ones made, in its own
    area or another), and the caller records only these."""
    sid = ids.get("sid", "")
    saved: dict[str, str] = {}
    counts = {"writes": 0, "passed": 0, "failed": 0}
    writes = plan(ids, sid)
    if only is not None:
        last = max((i for i, w in enumerate(writes) if f"write {w['area']}: {w['what']}" in only), default=-1)
        writes = writes[:last + 1]
    for w in writes:
        if area and area.lower() not in w["area"]:
            continue
        name = f"write {w['area']}: {w['what']}"
        token = tokens.get(w["who"])
        if not token:
            record(name, "skipped", f"no {w['who']} account in this run (--role)", 0)
            continue
        missing = [n for n in w.get("needs", []) if n not in saved and n != "fixture entity"]
        # a {name} left unfilled (not the JSON body's own braces: that skipped every write with a body, R2.0.1)
        if missing or re.search(r"\{[a-z_]+\}", json.dumps(_fill([w["path"], w.get("body")], saved))):
            record(name, "skipped", "an earlier write did not make what this one needs", 0)
            continue
        path, body = _fill(w["path"], saved), _fill(w.get("body"), saved)
        t0 = time.time()
        if w.get("same_as"):                         # a setting saved back as it is: read first, nothing changes
            got_status, now = call(base, "get", _fill(w["same_as"], saved), token)
            if got_status != 200 or not isinstance(now, dict):
                record(name, "failed", f"could not read {w['same_as']} to save it back unchanged ({got_status})", 0)
                counts["writes"] += 1
                counts["failed"] += 1
                continue
            body = same_as(now, w.get("keep"))
        if w.get("data"):
            from . import ui_flows
            try:
                status, answer = upload(base, path, token, w["data"].rsplit("/", 1)[-1], ui_flows.data_bytes(w["data"]))
            except OSError as exc:
                status, answer = 0, f"no test data file {w['data']}: {exc}"
        else:
            status, answer = call(base, w["method"], path, token, body)
        outcome, detail = judge(status, w.get("ok", {200}), w.get("refused", False), w.get("refused_also", set()))
        if outcome == "passed" and w.get("save"):
            if w.get("save_whole"):                    # the whole answer, as text (a settings file taken in again)
                got = answer if isinstance(answer, str) else json.dumps(answer)
            elif w.get("find"):                          # the id of the item in a list answer that matches
                got = find(answer, w["find"], w.get("find_key", "id"))
            elif w.get("save_from"):                   # a value at a path in the answer (job_id, a file's name)
                got = pick(answer, w["save_from"])
            else:
                got = ident(answer.get(w["save_at"]) if w.get("save_at") and isinstance(answer, dict) else answer)
            if got:
                saved[w["save"]] = got
            elif w.get("optional"):                     # nothing of the kind here: this and what needs it skipped
                record(name, "skipped", f"{status}, but there is none to use here", int((time.time() - t0) * 1000))
                continue
            else:
                outcome, detail = "failed", f"{status}, but the answer has no id"
        if outcome == "passed" and w.get("shows"):      # a read that must hold what an earlier write made
            want = _fill(w["shows"], saved)
            if want not in (answer if isinstance(answer, str) else json.dumps(answer, ensure_ascii=False)):
                outcome, detail = "failed", f"{status}, but the answer does not hold {want!r}"
        if outcome == "passed" and w.get("until"):
            outcome, detail = wait_for(base, token, w["until"], saved)
        counts["writes"] += 1
        counts[outcome] = counts.get(outcome, 0) + 1
        req = f"{w['method'].upper()} {path} as {w['who']}" + (f"  body {json.dumps(body)}" if body is not None else "")
        record(name, outcome, f"{detail} (as {w['who']})", int((time.time() - t0) * 1000),
               request=req if outcome != "passed" else "",
               response=(f"{status}\n{json.dumps(answer)[:1500] if not isinstance(answer, str) else answer}"
                         if outcome != "passed" else ""))
    return counts
