"""People's skills (owner, 9 Nov 2026, D353).

* Each user adds their own skills on their profile (My profile): free tags, with the tags others use offered as they type.
* The Skills repository lists **every EA Explorer user** (the people in Keycloak, not names typed into projects; when
  Keycloak is not answering it says so: nobody can sign in then anyway), with
  their skills, by skill and by person. Everyone signed in reads it.
* A project's Organisation tab shows a linked user's skills from their profile; it no longer keeps skills of its own.
* Beside the free tags (Release 12, R12.8; D879: "TOGAF roles and skill levels are added beside the existing skills";
  TOGAF Series Guides: Architecture Skills Framework, G198, and Architecture Roles and Skills, G249): each person may
  say which architect roles they hold, and their proficiency, 1 to 4, in each of the eight categories of architecture
  skill. The role names, the categories and the level names are the guides'; the descriptions are EA Explorer's own.
"""

from __future__ import annotations

from . import personal as P
from . import projects as pj
from .metamodel_edit import EditError

_rows, _one = pj._rows, pj._one
MAX_SKILLS, MAX_LEN = 40, 60
HIDDEN = {"system", "break-glass", "service-account-eaexplorer-api"}


# ---------------------------------------------------------------- TOGAF roles and skill levels (Release 12, R12.8)
TOGAF_ROLES = ["Chief Architect", "Enterprise Architect", "Business Architect", "Data Architect", "Application Architect",
               "Technology Architect", "Solution Architect"]
# (key, name, what it takes in, in our words)
CATEGORIES = [
    ("application", "Application", "Designing, building and joining applications: their structure, interfaces and security"),
    ("architecture", "Architecture", "Modelling, building blocks, principles, patterns, migration planning and governance"),
    ("business", "Business", "How the organisation works: its strategy, business cases, processes and capabilities"),
    ("change", "Change", "Leading business change, and project and programme management"),
    ("data", "Data", "Analysing, exchanging and managing data"),
    ("generic", "Generic", "Leadership, team work, communication and dealing with people"),
    ("legal", "Legal", "The law that bears on the work: data protection, contracts, procurement"),
    ("technology", "Technology", "Infrastructure: computing, storage, networks and platforms"),
]
LEVELS = {1: ("Background", "Knows the basics; leans on specialists"),
          2: ("Aware", "Handles the issues with specialists' support"),
          3: ("Knowledgeable", "Knows enough detail to decide well; asks specialists in hard cases"),
          4: ("Expert", "Deep, practical experience")}


def togaf() -> dict:
    """The roles, categories and levels, for the screens and the AI."""
    return {"roles": TOGAF_ROLES, "categories": [{"key": k, "name": n, "covers": c} for k, n, c in CATEGORIES],
            "levels": [{"level": n, "name": a, "means": b} for n, (a, b) in LEVELS.items()]}


def clean_togaf(roles, levels) -> tuple[list[str], dict[str, int]]:
    """Roles from the list, and a level 1 to 4 for each category given (none: not said)."""
    given = [str(r) for r in (roles or [])]
    unknown = [r for r in given if r not in TOGAF_ROLES]
    if unknown:
        raise EditError(f"No TOGAF role {', '.join(unknown)}: one of {', '.join(TOGAF_ROLES)}.")
    roles = [r for r in TOGAF_ROLES if r in set(given)]
    out: dict[str, int] = {}
    keys = {k for k, _n, _c in CATEGORIES}
    for k, v in (levels or {}).items():
        if k not in keys:
            raise EditError(f"No skill category {k}: one of {', '.join(sorted(keys))}.")
        if v in (None, "", 0, "0"):
            continue
        try:
            n = int(v)
        except (TypeError, ValueError) as exc:
            raise EditError("A skill level is 1 Background, 2 Aware, 3 Knowledgeable or 4 Expert.") from exc
        if n not in LEVELS:
            raise EditError("A skill level is 1 Background, 2 Aware, 3 Knowledgeable or 4 Expert.")
        out[k] = n
    return roles, out


def clean(skills) -> list[str]:
    """Tags as kept: trimmed, single spaces, at most 60 characters, no repeats (ignoring case), at most 40."""
    if isinstance(skills, str):
        skills = skills.split(",")
    out: dict[str, str] = {}
    for k in skills or []:
        k = " ".join(str(k).split())[:MAX_LEN]
        if k and k.lower() not in out:
            out[k.lower()] = k
    if len(out) > MAX_SKILLS:
        raise EditError(f"At most {MAX_SKILLS} skills.")
    return list(out.values())


def of(conn, usernames) -> dict[str, list[str]]:
    """The skills of several people, by name."""
    names = sorted({(u or "").lower() for u in usernames if u})
    if not names:
        return {}
    return {r["username"]: list(r["skills"] or []) for r in P.rows(
        conn, "SELECT username, skills FROM personal.user_skills WHERE username = ANY (CAST(:u AS text[]))", u=names)}


def togaf_of(conn, usernames) -> dict[str, dict]:
    """The TOGAF roles and skill levels of several people, by name (Release 12, R12.8)."""
    names = sorted({(u or "").lower() for u in usernames if u})
    if not names:
        return {}
    return {r["username"]: r for r in P.rows(conn, """SELECT username, togaf_roles, togaf_levels FROM personal.user_skills
                                                       WHERE username = ANY (CAST(:u AS text[]))""", u=names)}


def all_tags(conn) -> list[str]:
    """Every skill anyone has, spelled as most people spell it."""
    rows = P.rows(conn, """SELECT k, count(*) AS n FROM personal.user_skills, unnest(skills) AS k GROUP BY k""")
    best: dict[str, tuple[int, str]] = {}
    for r in rows:
        key = r["k"].lower()
        if key not in best or r["n"] > best[key][0]:
            best[key] = (r["n"], r["k"])
    return sorted((v[1] for v in best.values()), key=str.lower)


def mine(conn, user) -> dict:
    """The person's own skills, TOGAF roles and skill levels."""
    r = P.one(conn, "SELECT skills, togaf_roles, togaf_levels, modified_at FROM personal.user_skills WHERE username = :u",
              u=user.username.lower())
    return {"username": user.username.lower(), "skills": list((r or {}).get("skills") or []),
            "togaf_roles": list((r or {}).get("togaf_roles") or []), "togaf_levels": dict((r or {}).get("togaf_levels") or {}),
            "togaf": togaf(),
            "modified_at": str(getattr(r["modified_at"], "isoformat", lambda: r["modified_at"])()) if r and r.get("modified_at") else None,
            "suggestions": all_tags(conn)}


def set_mine(conn, user, skills, togaf_roles=None, togaf_levels=None) -> dict:
    """Sets the person's own skills; and their TOGAF roles and skill levels when given (left as they are otherwise)."""
    tags = clean(skills)
    P.run(conn, """INSERT INTO personal.user_skills (username, skills, modified_by) VALUES (:u, CAST(:s AS text[]), :u)
                    ON CONFLICT (username) DO UPDATE SET skills = EXCLUDED.skills, modified_by = EXCLUDED.modified_by,
                                                         modified_at = now()""", u=user.username.lower(), s=tags)
    out = {"skills": tags, "message": f"Your skills are saved ({len(tags)})." if tags else "Your skills are cleared."}
    if togaf_roles is not None or togaf_levels is not None:
        now = mine(conn, user)
        roles, levels = clean_togaf(now["togaf_roles"] if togaf_roles is None else togaf_roles,
                                    now["togaf_levels"] if togaf_levels is None else togaf_levels)
        P.run(conn, """UPDATE personal.user_skills SET togaf_roles = CAST(:r AS text[]), togaf_levels = CAST(:l AS jsonb)
                        WHERE username = :u""", u=user.username.lower(), r=roles, l=__import__("json").dumps(levels))
        out.update(togaf_roles=roles, togaf_levels=levels)
    return out


def _users() -> list[dict]:
    """Every user in the realm (Keycloak). Without Keycloak nobody can sign in anyway, so there is no fallback (owner,
    9 Nov 2026): the repository says the sign-in service is not answering."""
    from . import keycloak_admin as kc
    out, first = [], 0
    while True:
        try:
            page = kc.users(first=first, limit=100)
        except Exception as exc:  # noqa: BLE001
            raise EditError("The sign-in service (Keycloak) is not answering, so the list of users cannot be read.", 503) from exc
        out += page
        if len(page) < 100 or first > 5000:
            break
        first += 100
    return [{"username": u["username"], "name": u.get("name") or "", "enabled": u.get("enabled", True)} for u in out]


def repository(conn, user) -> dict:
    """The Skills repository: every user with their skills; and every skill with how many have it."""
    users = _users()
    users = [u for u in users if u["username"] and u["username"] not in HIDDEN and not u["username"].startswith("service-account-")]
    have = of(conn, [u["username"] for u in users])
    tg = togaf_of(conn, [u["username"] for u in users])
    for u in users:
        u["skills"] = have.get(u["username"], [])
        t = tg.get(u["username"].lower()) or {}
        u["togaf_roles"], u["togaf_levels"] = list(t.get("togaf_roles") or []), dict(t.get("togaf_levels") or {})
    counts: dict[str, list[str]] = {}
    for u in users:
        for k in u["skills"]:
            counts.setdefault(k.lower(), []).append(u["username"])
    tags = {t.lower(): t for t in all_tags(conn)}
    return {"users": sorted(users, key=lambda u: (u["name"] or u["username"]).lower()),
            "skills": sorted(({"skill": tags.get(k, k), "people": v} for k, v in counts.items()), key=lambda s: s["skill"].lower()),
            "without": sum(1 for u in users if not u["skills"]), "me": user.username.lower(),
            # by TOGAF role: who holds it; and by category, who is at each level (Release 12, R12.8)
            "togaf": togaf(), "by_role": {r: [u["username"] for u in users if r in u["togaf_roles"]] for r in TOGAF_ROLES},
            "by_category": {k: {str(n): [u["username"] for u in users if u["togaf_levels"].get(k) == n] for n in LEVELS}
                            for k, _n, _c in CATEGORIES}}
