"""The OData feed checked on the running installation, in the API suite of every full test (owner, 28 Nov 2026, 09:00:
"Also do we have tests for odata?"; 09:05: "add these"; D972).

The feed (eax/odata.py) is read as Power BI or Excel reads it, over HTTP as the run's Super Admin, on the run's own model
(self_test_<id>_1), and what it says is compared with the database:

  the service document     answers, lists Entities, Relationships and a table for each entity type the model uses
  $metadata                is XML that parses, with an EntitySet for every table of the service document and the
                           standard columns (Id, DisplayId, Name, Description, ...) on Entities
  the rows                 Entities, ApplicationComponent, Capability and Relationships hold as many rows as the
                           database has (committed, not deleted), with the same names
  $filter                  eq, contains() and startswith(), and and or, give the rows those conditions pick from all rows
  $orderby, $select        Name desc puts the rows in that order; $select=Name gives Id and Name only
  $top, $skip, $count      a page is that slice of the rows; $count says how many there are with the filter
  refusals                 a filter it cannot read (400, saying why), a column that is not there (400), a table that is
                           not there (404), $top that is not a number (400), nobody signed in (401), and a person without
                           the model (403 or 404, never its rows)
  the governance feed      its service document answers
One result each: "odata: ...".
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Callable

from sqlalchemy import text

from .. import httpopen

Record = Callable[..., None]
ODATA = "/api/v1/odata"


def get(base: str, path: str, token: str | None, timeout: int = 120) -> tuple[int, str]:
    """One GET of the feed: its status and its whole answer as text."""
    from ..service_split import route
    req = urllib.request.Request(route(base, path) + path,
                                 headers={"Accept": "application/json", **({"Authorization": f"Bearer {token}"} if token else {})})
    try:
        with httpopen.urlopen(req, timeout=timeout) as r:     # noqa: S310 - the installation's own API
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, exc.read().decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            return exc.code, ""
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return 599, f"no answer: {exc}"


def _json(body: str) -> dict:
    try:
        out = json.loads(body)
        return out if isinstance(out, dict) else {}
    except ValueError:
        return {}


def q(path: str, **args: str) -> str:
    """A feed path with its query options, encoded as a client sends them (pure)."""
    return path + ("?" + urllib.parse.urlencode(args, safe="$,'()") if args else "")


def db_rows(engine, model: str) -> dict[str, list[str]]:
    """What the feed should show, from the database: the entities' names (all, and by type code) and the relationships'
    count (both ends there)."""
    with engine.begin() as conn:
        conn.execute(text("SELECT set_config('eax.rls_bypass', 'on', true)"))
        ents = conn.execute(text("""SELECT t.code, e.name FROM core.entities e JOIN core.entity_types t ON t.id = e.entity_type_id
                                     JOIN core.models m ON m.id = e.model_id
                                    WHERE m.guid = CAST(:g AS uuid) AND NOT e.is_deleted AND NOT t.is_connector"""),
                            {"g": model}).all()
        rels = conn.execute(text("""SELECT count(*) FROM core.relationships r JOIN core.models m ON m.id = r.model_id
                                      JOIN core.entities s ON s.id = r.source_entity_id AND NOT s.is_deleted
                                      JOIN core.entities t ON t.id = r.target_entity_id AND NOT t.is_deleted
                                     WHERE m.guid = CAST(:g AS uuid) AND NOT r.is_deleted"""), {"g": model}).scalar()
    out: dict[str, list[str]] = {"*": sorted(n for _c, n in ents), "#rel": [""] * int(rels or 0)}
    for c, n in ents:
        out.setdefault(c, []).append(n)
    return out


def run(base: str, tokens: dict[str, str], ids: dict[str, str], record: Record, log, engine) -> dict[str, int]:
    """Every check (see the module); the counts of passed and failed."""
    counts = {"passed": 0, "failed": 0, "skipped": 0}
    token, model = tokens.get("super-admin", ""), ids.get("model", "")

    def rec(name: str, ok: bool | None, detail: str = "", t0: float = 0.0) -> None:
        outcome = "passed" if ok else "skipped" if ok is None else "failed"
        counts[outcome] += 1
        record(f"odata: {name}", outcome, str(detail)[:1500], int((time.time() - t0) * 1000) if t0 else 0)

    if not token or not model:
        rec("the model's feed", None, "the run has no Super Admin or no model")
        return counts
    log("odata: the run's model through its OData feed, compared with the database")
    feed = f"{ODATA}/models/{model}/"
    t0 = time.time()
    s, body = get(base, feed, token)
    doc = _json(body)
    tables = [t.get("name") for t in doc.get("value") or []]
    want = {"Entities", "Relationships", "ApplicationComponent", "Capability"}
    rec("the service document lists the model's tables", s == 200 and want <= set(tables),
        f"{s}: {len(tables)} tables" + (f"; missing {', '.join(sorted(want - set(tables)))}" if s == 200 else f" {body[:200]}"), t0)

    t0 = time.time()
    s, body = get(base, feed + "$metadata", token)
    try:
        root = ET.fromstring(body.encode("utf-8"))
        ns = {"e": "http://docs.oasis-open.org/odata/ns/edm"}
        sets = [x.get("Name") for x in root.iter("{http://docs.oasis-open.org/odata/ns/edm}EntitySet")]
        props = [p.get("Name") for et in root.findall(".//e:EntityType", ns) if et.get("Name") == "Entities"
                 for p in et.findall("e:Property", ns)]
        ok = s == 200 and set(sets) == set(tables) and {"Id", "DisplayId", "Name", "Description", "EntityType"} <= set(props)
        rec("$metadata is XML with every table and the standard columns", ok,
            f"{s}: {len(sets)} entity sets, {len(props)} columns on Entities", t0)
    except ET.ParseError as exc:
        rec("$metadata is XML with every table and the standard columns", False, f"{s}: not XML ({exc})", t0)

    truth = db_rows(engine, model)
    for table, key in (("Entities", "*"), ("ApplicationComponent", "ApplicationComponent"), ("Capability", "Capability")):
        t0 = time.time()
        s, body = get(base, q(feed + table, **{"$count": "true"}), token)
        d = _json(body)
        names = sorted(r.get("Name") for r in d.get("value") or [])
        want_names = sorted(truth.get(key) or [])
        rec(f"{table} holds the model's rows, as the database has them", s == 200 and names == want_names
            and d.get("@odata.count") == len(want_names),
            f"{s}: {len(names)} rows, count {d.get('@odata.count')}; the database has {len(want_names)}", t0)
    t0 = time.time()
    s, body = get(base, q(feed + "Relationships", **{"$count": "true"}), token)
    d = _json(body)
    rec("Relationships holds the model's relationships", s == 200 and d.get("@odata.count") == len(truth["#rel"]),
        f"{s}: {d.get('@odata.count')}; the database has {len(truth['#rel'])}", t0)

    _, body = get(base, feed + "ApplicationComponent", token)
    rows = _json(body).get("value") or []
    names = [r.get("Name") or "" for r in rows]
    first = names[0] if names else ""
    for label, flt, pick in (
            ("eq", f"Name eq '{first}'", lambda n: n == first),
            ("contains()", "contains(Name,'application')", lambda n: "application" in n.lower()),
            ("startswith()", "startswith(Name,'Self-test')", lambda n: n.lower().startswith("self-test")),
            ("and / or", f"Name eq '{first}' or startswith(Name,'Self-test duplicate')",
             lambda n: n == first or n.lower().startswith("self-test duplicate"))):
        t0 = time.time()
        s, body = get(base, q(feed + "ApplicationComponent", **{"$filter": flt, "$count": "true"}), token)
        d = _json(body)
        got = sorted(r.get("Name") for r in d.get("value") or [])
        want_f = sorted(n for n in names if pick(n))
        rec(f"$filter with {label} picks the rows it should", s == 200 and got == want_f and bool(want_f)
            and d.get("@odata.count") == len(want_f), f"{s}: {len(got)} rows, {len(want_f)} expected ({flt})", t0)
    t0 = time.time()
    s, body = get(base, q(feed + "ApplicationComponent", **{"$orderby": "Name desc", "$select": "Name"}), token)
    d = _json(body).get("value") or []
    got = [r.get("Name") for r in d]
    rec("$orderby Name desc and $select=Name", s == 200 and got == sorted(names, key=lambda n: n.lower(), reverse=True)
        and all(set(r) == {"Id", "Name"} for r in d), f"{s}: {len(got)} rows, columns {sorted(set().union(*[set(r) for r in d])) if d else []}", t0)
    t0 = time.time()
    s, body = get(base, q(feed + "ApplicationComponent", **{"$top": "2", "$skip": "1"}), token)
    got = [r.get("Name") for r in _json(body).get("value") or []]
    rec("$top=2 and $skip=1 give that slice of the rows", s == 200 and got == names[1:3], f"{s}: {got} expected {names[1:3]}", t0)

    for label, path, status in (
            ("a filter it cannot read is refused, saying why", q(feed + "Entities", **{"$filter": "Name eqq 'x'"}), 400),
            ("a column that is not there is refused", q(feed + "Entities", **{"$select": "NoSuchColumn"}), 400),
            ("a table that is not there is refused", feed + "NoSuchTable", 404),
            ("$top that is not a number is refused", q(feed + "Entities", **{"$top": "many"}), 400)):
        t0 = time.time()
        s, body = get(base, path, token)
        said = (_json(body).get("error") or {}).get("message") if isinstance(_json(body).get("error"), dict) else ""
        rec(label, s == status and bool(said), f"{s} (expected {status}): {said or body[:150]}", t0)
    t0 = time.time()
    s, _body = get(base, feed + "Entities", None)
    rec("nobody signed in gets 401", s == 401, f"{s}", t0)
    other = tokens.get("no-role") or ""
    if other:
        t0 = time.time()
        s, body = get(base, feed + "Entities", other)
        rec("a person without the model gets none of its rows", s in (403, 404) or (s == 200 and not _json(body).get("value")),
            f"{s}", t0)
    else:
        rec("a person without the model gets none of its rows", None, "this run has no account without the model")
    t0 = time.time()
    s, body = get(base, f"{ODATA}/governance/", token)
    rec("the governance feed's service document answers", s == 200 and bool(_json(body).get("value")), f"{s}", t0)
    return counts
