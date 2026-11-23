"""R12.3 (D879, D887): the TOGAF Digital Business Reference Model in the library: four domains, ten core elements and
their parts, the DPBoK contexts and competencies, all Groupings (no new types), and the competencies that enable each
Digital Enablement pillar; the Digital transformation model template points to it."""

from eax.seed import industries as IND
from eax.seed import industry_dbrm as D
from eax.seed import model_templates as MT


def _by(key):
    return {k: (t, n, d, p) for k, t, n, d, p, _ in D.ENTITIES}[key]


def test_dbrm_is_registered_in_the_library():
    row = [m for m in IND.MODELS if m[0] == "dbrm"]
    assert len(row) == 1 and row[0][-1] == "Digital Business Reference Model (TOGAF DBRM)"


def test_dbrm_structure():
    keys = [k for k, *_ in D.ENTITIES]
    assert len(keys) == len(set(keys))
    assert {t for _, t, *_ in D.ENTITIES} == {"Grouping"}                       # no new types (D887)
    domains = [k for k in keys if "." not in k]
    assert [_by(k)[1] for k in domains] == ["Digital Domain", "Strategy Domain", "Structural Domain", "Operational Domain"]
    elements = [k for k in keys if k.count(".") == 1 and ".E" in k]
    assert len(elements) == 10
    competencies = [k for k in keys if ".K" in k]
    assert len(competencies) == 12 and len([k for k in keys if k.endswith(tuple(f".C{i}" for i in range(1, 5)))]) == 4


def test_every_child_is_aggregated_by_its_parent():
    agg = {(s, t) for s, r, t, _ in D.RELATIONSHIPS if r == "Aggregation"}
    for k, _, _, _, parent, _ in D.ENTITIES:
        assert (parent is None) or (parent, k) in agg, k


def test_each_digital_enablement_pillar_has_its_competencies():
    names = {k: n for k, _, n, *_ in D.ENTITIES}
    enabled = {names[t] for s, r, t, n in D.RELATIONSHIPS if r == "Association" and n == "enables"}
    assert enabled == {"Digital Principles and Strategy", "Digital Governance", "Digital Products and Services",
                       "Agile Digital Delivery Model", "Digital Platforms"}


def test_the_digital_model_template_points_to_it():
    digital = [t for t in MT.TEMPLATES if t[0] == "digital"][0]
    assert "Digital Business Reference Model (TOGAF DBRM)" in digital[2]
