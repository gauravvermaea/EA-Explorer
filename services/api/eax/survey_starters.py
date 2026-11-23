"""Ready-made surveys to start from (Release 12, R12.6; D879, D884): the four surveys of Release 12, each a draft made in
one step and changed in the survey designer as any survey (D884: "surveys work as today").

* **EA capability maturity (ACMM)**: the existing maturity assessment (eax/maturity.py, D377), in the shape of the
  ACMM the TOGAF Series Guide on architecture maturity models (G203) describes; started from the Maturity page.
* **Business capability assessment** (TOGAF Series Guide: Business Capabilities, G211): for each capability of a model
  (or each capability under one), how mature it is today, how mature it needs to be, how well it performs and how
  much it matters, and a comment: the answers behind a capability heat map. Answers change nothing in the model (D375).
* **Digital technology readiness** (TOGAF Series Guide: Digital Technology Adoption, a Guide to Readiness Assessment
  and Roadmap Development, G212): the guide's foundational, impact and sustaining factors, each rated, with a comment
  per group (D879: "Digital Technology Adoption is a readiness survey").
* **Data management**: how well the organisation manages its data, area by area, rated, with a comment per area.

The guides give the structure; every question is in EA Explorer's own words (the guides' text is not for
redistribution). Rules here (D248).
"""

from __future__ import annotations

from typing import Any

from . import repository as repo
from . import surveys as sv
from .metamodel_edit import EditError

MAX_CAPABILITIES = 40          # one section each (a survey has at most 40 sections)


def _rating(key: str, text: str, low: str, high: str, help_: str = "") -> dict:
    return {"key": key, "kind": "rating", "text": text, "help": help_, "min": 1, "max": 5, "low_label": low, "high_label": high}


def _comment(key: str, text: str = "Anything to add: what holds it back, or what would help") -> dict:
    return {"key": key, "kind": "long_text", "text": text}


# ---------------------------------------------------------------- digital technology readiness (G212)
# (group, what the group is, [(factor, the question in our words)])
READINESS = [
    ("Foundational factors", "What must be in place before digital technology can be adopted at all.", [
        ("Vision", "We have a clear, shared picture of what the digital technology is to do for us."),
        ("Sponsorship and direction", "Senior leaders sponsor the change and steer it."),
        ("IT capability", "Our IT people and platforms can take on the technology."),
        ("Culture", "Our people are open to new ways of working and to learning from trying."),
        ("Scope and scale", "We know where the technology will be used first, and how far it will go."),
        ("Business rationale", "The business case is understood: what it costs, what it gives back and why now."),
        ("Implementation approach", "We know how we will bring it in: in steps, with pilots, and who does what."),
    ]),
    ("Impact factors", "What makes the foundations work better.", [
        ("Business model adaptability", "Our business model can change to make the most of the technology."),
        ("Skills and competence", "We have, or can get, the skills the technology needs."),
        ("Technology maturity", "The technology itself is proven enough for the way we mean to use it."),
        ("Ecosystem", "Our partners, suppliers and customers are ready to work with us this way."),
        ("Governance and compliance", "We govern its use and keep within the rules that apply to us."),
    ]),
    ("Sustaining factors", "What keeps the benefits coming once it is in.", [
        ("Value realisation", "We measure the value it brings and act on what we find."),
        ("Policy and regulations", "Our policies, and the regulations we answer to, allow and support its use."),
        ("Funding and resources", "Funding and people are set aside to keep it going, not only to start it."),
    ]),
]


def readiness_spec() -> dict:
    """The digital technology readiness survey: one section per group of factors, each factor rated 1 to 5."""
    sections = []
    for gi, (group, what, factors) in enumerate(READINESS, 1):
        qs = [_rating(f"r{gi}_{fi}", f"{name}: {q}", "Not at all", "Fully", "1: not at all true today; 5: fully true today")
              for fi, (name, q) in enumerate(factors, 1)]
        qs.append(_comment(f"r{gi}_note"))
        sections.append({"key": f"readiness_{gi}", "title": group, "text": what, "questions": qs})
    sections.append({"key": "technology", "title": "The technology", "text": "",
                     "questions": [{"key": "tech_name", "kind": "text", "text": "Which digital technology are you thinking of?"}]})
    return {"sections": sections}


# ---------------------------------------------------------------- data management
DATA_AREAS = [
    ("Data governance", "Who decides about data is clear: owners and stewards are named and the rules are written down and kept."),
    ("Data quality", "We know how good our most important data is, measure it, and fix what is wrong at the source."),
    ("Metadata", "What our data means, where it comes from and where it goes is recorded and easy to find."),
    ("Master and reference data", "Customers, products and the other things we share across the business have one trusted version."),
    ("Data architecture", "We know which systems hold which data, and which one holds the master copy."),
    ("Data security and privacy", "Data is classified, protected as its class needs, and personal data is handled lawfully."),
    ("Integration and interoperability", "Data moves between systems in agreed, documented ways, not by hand."),
    ("Lifecycle and retention", "We know how long to keep each kind of data, and we archive and delete it on time."),
    ("Reporting and analytics", "Reports and analytics draw on trusted data, and people trust the numbers."),
    ("Data literacy and culture", "People understand the data they use and treat it as an asset."),
]


def data_spec() -> dict:
    """The data management survey: each area rated 1 to 5, then which to improve first and why."""
    qs = [_rating(f"d{i}", f"{area}: {q}", "Not at all", "Fully", "1: not at all true today; 5: fully true today")
          for i, (area, q) in enumerate(DATA_AREAS, 1)]
    return {"sections": [
        {"key": "areas", "title": "Data management today", "text": "How true is each statement of your part of the organisation today?",
         "questions": qs},
        {"key": "priorities", "title": "What matters most", "text": "",
         "questions": [{"key": "first", "kind": "multi", "text": "Which areas should be improved first?",
                        "options": [{"value": f"d{i}", "label": a} for i, (a, _q) in enumerate(DATA_AREAS, 1)]},
                       _comment("why", "Why those, and what would help most")]},
    ]}


# ---------------------------------------------------------------- business capabilities (G211)
def capabilities(conn, model: Any, under: Any = None) -> tuple[dict, list[dict]]:
    """The capabilities of a model the person may read (or those directly under one), by name."""
    m = repo.get_model(conn, model)
    if under:
        caps = sv._rows(conn, """
            SELECT c.guid::text AS id, c.name, c.description FROM core.relationships r
              JOIN core.relationship_types rt ON rt.id = r.relationship_type_id AND rt.code IN ('Composition', 'Aggregation')
              JOIN core.entities p ON p.id = r.source_entity_id AND p.guid::text = :u
              JOIN core.entities c ON c.id = r.target_entity_id AND NOT c.is_deleted
              JOIN core.entity_types t ON t.id = c.entity_type_id AND t.code = 'Capability'
             WHERE r.model_id = :m AND NOT r.is_deleted ORDER BY c.name""", m=m["_id"], u=str(under))
    else:
        caps = sv._rows(conn, """
            SELECT e.guid::text AS id, e.name, e.description FROM core.entities e
              JOIN core.entity_types t ON t.id = e.entity_type_id AND t.code = 'Capability'
             WHERE e.model_id = :m AND NOT e.is_deleted ORDER BY e.name""", m=m["_id"])
    return m, caps


def capability_spec(caps: list[dict]) -> dict:
    """The business capability assessment: one section per capability, its maturity now and needed, how it
    performs, how much it matters, and a comment."""
    sections = []
    for i, c in enumerate(caps, 1):
        sections.append({"key": f"cap_{i}", "title": c["name"], "text": (c.get("description") or "")[:500], "questions": [
            _rating(f"c{i}_now", "How mature is it today?", "Ad hoc", "Optimised"),
            _rating(f"c{i}_need", "How mature does it need to be?", "Ad hoc", "Optimised"),
            _rating(f"c{i}_works", "How well does it perform today?", "Poorly", "Very well"),
            _rating(f"c{i}_matters", "How much does it matter to the strategy?", "Little", "A great deal"),
            _comment(f"c{i}_note"),
        ]})
    return {"sections": sections}


# ---------------------------------------------------------------- the list and making a draft
STARTERS = {
    "acmm": ("EA capability maturity (ACMM)", "How mature the architecture practice is, element by element (the ACMM, TOGAF Series Guide G203).",
             "maturity"),
    "business-capability": ("Business capability assessment", "For each capability of a model: maturity today and needed, performance "
                            "and importance (TOGAF Series Guide G211). Choose the model, and if you like one capability to assess what is under it.",
                            "model"),
    "technology-readiness": ("Digital technology readiness", "How ready the organisation is to adopt a digital technology: the "
                             "foundational, impact and sustaining factors (TOGAF Series Guide G212).", ""),
    "data-management": ("Data management", "How well the organisation manages its data, area by area.", ""),
}


def listing() -> list[dict]:
    """The ready-made surveys, each with what it is and what it needs (a model, or the Maturity page)."""
    return [{"code": k, "title": t, "description": d, "needs": n} for k, (t, d, n) in STARTERS.items()]


def start(conn, user, code: str, d: dict) -> dict:
    """A draft survey made from a starting point ({model, under} for the business capability assessment)."""
    if code not in STARTERS:
        raise EditError(f"No such survey to start from: one of {', '.join(STARTERS)}.", 404)
    title, desc, needs = STARTERS[code]
    if needs == "maturity":
        raise EditError("Start an EA capability maturity assessment from the Maturity page: it is scored.", 409)
    if code == "business-capability":
        if not d.get("model"):
            raise EditError("Choose the model whose capabilities are assessed.")
        try:
            m, caps = capabilities(conn, d["model"], d.get("under"))
        except repo.NotFound as exc:
            raise EditError(str(exc), 404) from exc
        if not caps:
            raise EditError(f"{m['name']} has no capabilities{' under that one' if d.get('under') else ''} to assess.", 409)
        if len(caps) > MAX_CAPABILITIES:
            raise EditError(f"{m['name']} has {len(caps)} capabilities{' under that one' if d.get('under') else ''}: a survey takes "
                            f"{MAX_CAPABILITIES} at most. Choose a capability to assess what is under it.", 409)
        spec, title = capability_spec(caps), f"{title}: {m['name']}"
    else:
        spec = readiness_spec() if code == "technology-readiness" else data_spec()
    return sv.create(conn, user, {"title": (d.get("title") or title)[:200], "description": desc, "spec": spec})
