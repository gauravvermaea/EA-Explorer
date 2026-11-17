"""Customer journey maps for the sample projects (R5.7-J1, D730; owner, 17 Nov 2026, 13:51: "a sample journey (current
and target state, linked to its model, removed with the samples like the rest) and a blank template with typical
stages"): laptop only, made once per project (a project with a journey already is left alone). Every name is
invented.

Protea Claims Transformation 2028 (sample): "Make a motor claim" today (agreed: every kind of part, the emotion at each
step, a persona, a kind of part of the project's own with a field, stages linked to the model's elements), and the
target in 2028 made from it and changed, so the two compare. Fynbos Pet Insurance launch (sample): a journey started
from the starter template, partly filled in (a draft).
"""

from __future__ import annotations

from sqlalchemy import text

# (stage, note, [(part, text, score or None, note)])
TODAY = [
    ("Have an accident", "The moment it happens", [
        ("step", "Has a minor collision on the way to work", -2, ""),
        ("step", "Swaps details with the other driver", -1, ""),
        ("touchpoint", "Nobody from Protea yet", None, ""),
        ("pain_point", "Does not know what to do first", None, ""),
        ("moment", "Being told what to do next, at once", None, "The first minutes shape the whole claim"),
        ("opportunity", "A 'what to do now' screen in the app", None, "")]),
    ("Report the claim", "First notice of loss", [
        ("step", "Phones the broker, who says to call the call centre", -1, ""),
        ("step", "Waits 25 minutes on the line", -2, ""),
        ("step", "Is sent a paper claim form", -1, ""),
        ("touchpoint", "Broker", None, ""), ("touchpoint", "Call centre", None, ""), ("touchpoint", "Claim form by post", None, ""),
        ("pain_point", "Tells the story three times", None, ""),
        ("opportunity", "Claim in the app with photos", None, "Could become a requirement")]),
    ("Assessment", "An assessor sees the car", [
        ("step", "Waits a week for the assessor", -2, ""),
        ("step", "The assessor visits and is helpful", 1, ""),
        ("touchpoint", "Assessor", None, ""),
        ("pain_point", "No news while waiting", None, ""),
        ("moment", "The assessor's visit", None, ""),
        ("opportunity", "Live claim tracking", None, "")]),
    ("Repair", "At a panel repairer", [
        ("step", "Takes the car to the repairer", 0, ""),
        ("step", "Gets a courtesy car", 1, ""),
        ("touchpoint", "Panel repairer", None, ""),
        ("pain_point", "Repair takes longer than promised", None, "")]),
    ("Settle", "Paid and closed", [
        ("step", "Pays the excess", -1, ""),
        ("step", "Gets the car back, repaired well", 1, ""),
        ("touchpoint", "Payment by card at the repairer", None, ""),
        ("moment", "The car handed back", None, "")]),
]
# the parts that change in 2028 (text in today's journey, new text, new score); the parts gone; the parts added
CHANGED = [("Phones the broker, who says to call the call centre", "Opens the app and starts a claim", 1),
           ("Waits 25 minutes on the line", "Adds photos and the other driver's details in five minutes", 1),
           ("Waits a week for the assessor", "Simple damage assessed from the photos the same day", 2),
           ("Pays the excess", "Excess taken from the payout, nothing to do", 1)]
GONE = ["Is sent a paper claim form", "Claim form by post", "Tells the story three times", "Call centre"]
ADDED = [("Report the claim", "touchpoint", "Protea app", None), ("Assessment", "step", "Sees the claim's status in the app", 1),
         ("Have an accident", "step", "Opens the app's 'what to do now' screen", 0)]
# which of the model's elements each stage links to: words in the element's name
LINKS = {"Report the claim": ["Claim", "Call Centre", "Customer"], "Assessment": ["Assess", "Claim"], "Repair": ["Repair", "Partner"],
         "Settle": ["Payment", "Settle"]}


def _p(name, roles=("user",)):
    from .. import permissions as perms
    return perms.Principal(name, tuple(roles))


def _find(g: dict, words: str) -> str:
    return next(i["id"] for s in g["stages"] for rows in s["parts"].values() for i in rows if i["text"].startswith(words))


def run() -> list[str]:
    """Loads the sample journeys."""
    from .. import journeys as jy
    from .. import notify
    from .. import permissions as perms
    from .. import projects as pj

    said: list[str] = []
    la, ar = _p("user_lead_architect"), _p("user_architect")
    real_notify = notify.create
    notify.create = lambda *a, **k: None
    token = perms.current.set(_p("user_super_admin", ("super-admin",)))
    try:
        with pj.connections(True) as conn:
            def project(name):
                return conn.execute(text("""SELECT guid::text FROM proj.projects p WHERE name = :n
                                             AND NOT EXISTS (SELECT 1 FROM proj.journeys j WHERE j.project_id = p.id)"""), {"n": name}).scalar()
            pg = project("Protea Claims Transformation 2028 (sample)")
            if pg:
                k = jy.set_part_kind(conn, pg, la, {"label": "Systems behind it", "fields": ["Owner"],
                                                    "note": "The applications the person never sees"})["code"]
                today = jy.create(conn, pg, la, {"name": "Make a motor claim (today)", "kind": "current", "template": "blank",
                                                 "persona": "Thandi, a motor policyholder",
                                                 "description": "A motor claim as it runs today, from the claims workshop (sample)."})["id"]
                jy.add_item(conn, pg, la, today, {"part": "persona", "text": "Thandi, 34, commutes by car, insured through a broker"})
                jy.add_item(conn, pg, la, today, {"part": "persona", "text": "Her broker, who is the first person she calls"})
                stages = {}
                for name, note, parts in TODAY:
                    stages[name] = jy.add_stage(conn, pg, la, today, {"name": name, "note": note})["id"]
                    for part, t, score, n in parts:
                        jy.add_item(conn, pg, la, today, {"stage": stages[name], "part": part, "text": t, "score": score, "note": n})
                jy.add_item(conn, pg, la, today, {"stage": stages["Report the claim"], "part": k, "text": "Legacy claims system",
                                                  "fields": {"Owner": "Claims IT"}})
                linked = 0
                for stage, words in LINKS.items():
                    for w in words:
                        found = jy.elements(conn, pg, la, w)["elements"] or jy.elements(conn, pg, la, w, ["all"])["elements"]
                        if found:
                            jy.link(conn, pg, la, today, {"stage": stages[stage], "entity": found[0]["entity"]})
                            linked += 1
                            break
                jy.change(conn, pg, la, today, {"status": "agreed"})
                target = jy.copy(conn, pg, ar, today, {"name": "Make a motor claim (2028)", "kind": "target",
                                                       "description": "The claim after the transformation (sample)."})["id"]
                g = jy.get(conn, pg, ar, target)
                for old, new, score in CHANGED:
                    jy.change_item(conn, pg, ar, _find(g, old), {"text": new, "score": score})
                for words in GONE:
                    jy.remove_item(conn, pg, ar, _find(g, words))
                by_name = {s["name"]: s["id"] for s in g["stages"]}
                for stage, part, t, score in ADDED:
                    jy.add_item(conn, pg, ar, target, {"stage": by_name[stage], "part": part, "text": t, "score": score})
                jy.add_stage(conn, pg, ar, target, {"name": "Tell us how it went", "note": "A two-question survey in the app",
                                                     "after": by_name["Settle"]})
                try:                    # the documents behind it, when Documents is up
                    jy.add_document(conn, pg, la, today, {"note": "Five claimants interviewed"}, "Motor claim interviews.md",
                                    b"# Motor claim interviews (sample)\n\nFive policyholders who claimed this year, in their own words.\n")
                except Exception:  # noqa: BLE001 - Documents not up yet: the journey stands without it
                    pass
                said.append(f"Protea Claims Transformation 2028 (sample): 2 journeys, {linked} links to the model")
            pg = project("Fynbos Pet Insurance launch (sample)")
            if pg:
                j = jy.create(conn, pg, la, {"name": "Buy pet insurance", "kind": "target", "template": "starter",
                                             "persona": "A new dog owner",
                                             "description": "Started from the starter template; being filled in (sample)."})["id"]
                g = jy.get(conn, pg, la, j)
                s = {x["name"]: x["id"] for x in g["stages"]}
                first, second = list(s)[0], list(s)[1]
                jy.add_item(conn, pg, la, j, {"stage": s[first], "part": "step", "text": "Sees a leaflet at the vet", "score": 1})
                jy.add_item(conn, pg, la, j, {"stage": s[first], "part": "touchpoint", "text": "Vet's practice"})
                jy.add_item(conn, pg, la, j, {"stage": s[second], "part": "step", "text": "Compares two cover levels on the website", "score": 0})
                jy.add_item(conn, pg, la, j, {"stage": s[second], "part": "pain_point", "text": "Unsure what 'excess' means"})
                said.append("Fynbos Pet Insurance launch (sample): 1 journey from the starter template")
    finally:
        perms.current.reset(token)
        notify.create = real_notify
    return said
