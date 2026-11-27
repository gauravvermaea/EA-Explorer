"""Monte Carlo, the sample (Release 14.7, R14.7.6; D957, D962): laptop only, made once, on "Protea build or buy
(sample)", beside its scenario planning study. Every name and number is invented.

* **Policy platform roadmap** (roadmap confidence, in weeks): six work packages from discovery to go-live, the
  migration the widest; the vendor's two packages move together; the target 32 weeks and a milestone, "Pilot live".
* **Buy the policy suite: five-year case** (business case, ZAR): licences, implementation and run costs against
  savings and new premium; the licences and the run cost move together (the same vendor).
* **Platform risks** (risk exposure): four risks, two by the risk scale's levels and two with their own chance and loss,
  two with a lower chance after their controls; the amounts R5m and R20m.
* **Build or buy across the futures** (scenarios with chances): both options scored in the four futures as ranges, the
  futures weighted.

Each study is run once. Made through the same code the screen and the AI use (eax/monte_carlo_studies.py).
"""

from __future__ import annotations

from sqlalchemy import text

PROJECT = "Protea build or buy (sample)"

ROADMAP = [
    {"name": "Discovery and design", "low": 4, "likely": 6, "high": 10, "source": "The delivery plan, v2"},
    {"name": "Vendor set-up", "low": 3, "likely": 4, "high": 8, "after": ["Discovery and design"], "source": "Vendor's proposal"},
    {"name": "Product configuration", "low": 8, "likely": 10, "high": 18, "after": ["Vendor set-up"], "source": "Vendor's proposal"},
    {"name": "Data migration", "low": 6, "likely": 9, "high": 22, "after": ["Discovery and design"],
     "source": "Our last two migrations ran 40% over"},
    {"name": "Testing", "low": 4, "likely": 6, "high": 10, "after": ["Product configuration", "Data migration"]},
    {"name": "Go-live and handover", "low": 1, "likely": 2, "high": 4, "after": ["Testing"]},
]
CASE = [
    {"name": "Licences", "side": "cost", "low": 9_000_000, "likely": 10_000_000, "high": 12_500_000, "source": "Vendor quote"},
    {"name": "Implementation", "side": "cost", "low": 6_000_000, "likely": 8_000_000, "high": 14_000_000},
    {"name": "Running cost", "side": "cost", "low": 4_000_000, "likely": 5_000_000, "high": 7_000_000},
    {"name": "Savings on the old platform", "side": "benefit", "low": 15_000_000, "likely": 18_000_000, "high": 21_000_000},
    {"name": "New premium from digital sales", "side": "benefit", "low": 0, "likely": 6_000_000, "high": 15_000_000,
     "source": "Marketing's estimate"},
]
RISKS = [
    {"name": "Vendor goes out of business", "likelihood": 1, "impact": 4},
    {"name": "Migration loses policy history", "likelihood": 3, "impact": 3, "likelihood_after": 2},
    {"name": "Regulator delays the launch", "chance": 0.3, "low": 1_000_000, "likely": 3_000_000, "high": 8_000_000},
    {"name": "Key engineers leave", "chance": 0.4, "low": 500_000, "likely": 1_500_000, "high": 4_000_000, "chance_after": 0.2},
]
F = ("Slow and steady", "Rules race ahead", "Digital rush", "Fast on both fronts")
SCORES = [
    *[{"option": "Build in house", "future": f, "low": lo, "likely": li, "high": hi}
      for f, (lo, li, hi) in zip(F, ((5, 7, 9), (1, 3, 5), (3, 5, 8), (1, 2, 4)), strict=True)],
    *[{"option": "Buy the policy suite", "future": f, "low": lo, "likely": li, "high": hi}
      for f, (lo, li, hi) in zip(F, ((4, 6, 7), (5, 7, 9), (3, 6, 8), (5, 7, 8)), strict=True)],
]


def run() -> list[str]:
    """Loads the four sample studies, each run once."""
    from .. import monte_carlo_studies as ms
    from .. import permissions as perms
    from .. import projects as pj
    try:
        with pj.connections(True) as pc:
            p = pc.execute(text("SELECT id, guid::text AS g FROM proj.projects WHERE name = :n"), {"n": PROJECT}).mappings().first()
            if not p:
                return [f"Monte Carlo sample skipped: {PROJECT} is not there"]
            if pc.execute(text("SELECT 1 FROM proj.mc_studies WHERE project_id = :p LIMIT 1"), {"p": p["id"]}).first():
                return []
    except Exception as exc:  # noqa: BLE001 - an older database: nothing to do
        return [f"Monte Carlo sample skipped: {exc}"]
    who = perms.Principal("user_super_admin", ("super-admin",))
    token = perms.current.set(who)
    try:
        with pj.connections(True) as pc:
            g = p["g"]
            for name, kind, question, cur, unit, data in (
                ("Policy platform roadmap", "roadmap", "When will the new policy platform be live?", "", "weeks",
                 {"inputs": ROADMAP, "groups": [{"name": "The vendor", "members": ["Vendor set-up", "Product configuration"],
                                                 "strength": "strong"}],
                  "settings": {"target": 32, "milestones": [{"name": "Pilot live", "packages": ["Product configuration"], "by": 22}]}}),
                ("Buy the policy suite: five-year case", "business_case", "Does buying pay for itself in five years?", "ZAR", "",
                 {"inputs": CASE, "groups": [{"name": "The vendor's prices", "members": ["Licences", "Running cost"],
                                              "strength": "medium"}]}),
                ("Platform risks", "risk", "What could the platform's risks cost us in a year?", "ZAR", "",
                 {"inputs": RISKS, "settings": {"amounts": [5_000_000, 20_000_000]}}),
                ("Build or buy across the futures", "scenarios", "Which option is most likely the best?", "", "",
                 {"inputs": SCORES, "settings": {"weights": {F[0]: 0.2, F[1]: 0.3, F[2]: 0.3, F[3]: 0.2}}}),
            ):
                ms.create(pc, g, who, name, kind, question, cur, unit)
                ms.update(pc, g, who, name, data, by="ai")
                ms.run(pc, g, who, name)
        return [f"{PROJECT}: four Monte Carlo studies, each run once"]
    except Exception as exc:  # noqa: BLE001 - the sample never stops the rest
        return [f"Monte Carlo sample not made: {exc}"]
    finally:
        perms.current.reset(token)
