# Customer journey maps

Release 5.7, R5.7-J1 (owner, 16 Nov 2026 from 15:58, and 17 Nov 2026 13:50; D730). A customer journey map is
first-class in a project: a tab of its own, **Customer journeys**, beside the Business model canvas, in tables of its
own. Like the canvas it stands on its own: its links point out to model elements and change nothing in the models.

## What a project holds

| | |
|---|---|
| **Journeys** | Any number, each with a name, whose journey it is, a **kind** (Current state, Target state, Working copy, Scenario), a **status** (Draft, Agreed) and a description |
| **Stages** | The columns, left to right, each with a name and a note |
| **Parts** | Under each stage: **steps** (each with the emotion there), **touchpoints**, **pain points**, **moments that matter**, **opportunities**, and the project's own kinds |
| **Emotion** | A step's emotion from **-2 to +2 with faces**: 😣 very unhappy, 🙁 unhappy, 😐 neutral, 🙂 happy, 😄 very happy; drawn as a curve above the steps, zero being the line |
| **Personas** | Who the journey is about, for the whole journey |
| **Own kinds and fields** | A project adds kinds of part of its own (for example *Systems behind it*), each with fields (for example *Owner*), and extra fields on the standard kinds |
| **Links** | A stage (or a part) links to elements of the project's models: capabilities, value streams, business services, processes, applications, data, actors and roles (any type when asked); the element's name is kept with the link |
| **Lineage** | Stages and parts keep their lineage in every copy, so two journeys compare stage by stage and part by part |
| **History** | Every change: who, when, what |
| **Documents** | What it was built from (interviews, surveys, research): uploaded with it (kept in `00_Project/Customer journeys`) or a document of the project, linked |

## Working with journeys

* **＋ New journey**: start **blank**, or from the **starter template**'s typical stages (Become aware, Consider, Join or
  buy, Use, Get help, Stay or leave), to rename and change.
* **The grid**: the stages across, a row for each kind of part. Click a cell's ＋ to add a part, a part to change or
  remove it (a step's face too), and a stage's header to rename, move left or right, or remove it with its parts.
* **Emotion**: the row above the steps draws the curve through each step's face.
* **＋ link** under a stage finds elements of the project's models by name; × takes a link off.
* **Make a copy…**: a target state from the current state (or a working copy, a scenario), keeping the lineage.
* **Compare with…** any other journey of the project: each stage and part added (green), changed (amber, the old text
  and face crossed out) or removed (crossed out in red); the counts on top; **Swap** turns it round.
* **Copy to another project** (More…): with the same lineage; a part of a kind the other project lacks brings the kind.
* **Mark it agreed** / **make it a draft again**; any change to an agreed journey makes it a draft again.
* **Export**: PDF (A3, the grid with the emotion curve drawn with faces), PowerPoint (one slide: the stages as arrows,
  a box per kind of part, the curve), and **Open in draw.io** (the drawn view for presentations) — of a journey or of a
  comparison.
* An opportunity may become a requirement or a work package, by a person: nothing turns it into one by itself.

Anyone on the project sees the journeys; contributors change them; a frozen project's are read only.

## Sample data (laptop)

* Protea Claims Transformation 2028: **Make a motor claim (today)** (current state, agreed: five stages, every kind of
  part, the emotion at each step, two personas, a kind of the project's own with a field, stages linked to the claims
  model's elements, and the interview notes when Documents is up), and **Make a motor claim (2028)** (target state, made
  from it: steps changed with better faces, the paper form and the call centre gone, the app added, a new stage).
* Fynbos Pet Insurance launch: **Buy pet insurance**, started from the starter template and partly filled in.

They go with the sample projects, like the rest of the sample data.

## API

| | |
|---|---|
| `GET/POST /api/v1/projects/<id>/journeys` | list (and the kinds of part, faces, templates); a new journey `{name, kind, persona, description, template: blank \| starter}` |
| `GET …/journeys/elements?q=&type=` | elements of the project's models to link (type repeated; `all` for any) |
| `POST …/journey-kinds`, `DELETE …/journey-kinds/<code>` | a kind of the project's own `{label, fields, note}` or fields on a standard kind `{code, fields}`; remove |
| `GET/PUT/DELETE …/journeys/<jid>` | a journey with its stages, parts, links, personas, curve, documents and history; change `{name, kind, status, description, persona}`; remove |
| `POST …/journeys/<jid>/stages`, `/items`, `/links`, `/reorder`, `/copy`, `/copy-to`, `/documents` | a stage `{name, note, after}`; a part `{stage, part, text, note, score, fields}`; a link `{stage \| item, entity}`; `{stages}` or `{ids}`; a copy `{name, kind}`; to another project `{project}`; a document (multipart `file`, or `{document}`) |
| `GET …/journeys/<jid>/export?format=pdf\|pptx\|drawio[&compare=<jid>]` | the file |
| `GET …/journeys/<a>/compare/<b>` | the comparison |
| `PUT/DELETE …/journey-stages/<sid>`, `…/journey-items/<iid>`; `DELETE …/journey-links/<lid>` | change or remove a stage (with its parts) or a part; take a link off |

Tables (migration 0101): `proj.journeys`, `proj.journey_stages`, `proj.journey_items`, `proj.journey_links`,
`proj.journey_part_kinds`, `proj.journey_documents`, `proj.journey_events`; project backups carry them. Rules in
`eax/journeys.py` (D248); sample data in `eax/seed/sample_journeys.py`. MCP: `customer_journey` (list, a journey, a
comparison, elements to link) and `change_customer_journey` (new, stages, parts, links, a copy, the status), so a
person's own AI can draft a journey from their interviews or documents (documents marked NOT FOR AI are used by title
only, as everywhere).

## To test

1. Clean restart; Protea Claims Transformation 2028 (sample) › Business › **Customer journeys**: two journeys.
2. Open *Make a motor claim (today)*: the curve, the faces, every kind of part, the linked elements under the stages.
3. Click a step and change its face; the curve moves and the journey is a draft again.
4. Add a stage after *Settle*, move it left, rename it, remove it.
5. Add a kind of part of your own with a field, and a part of it with the field filled in.
6. **Compare with…** the 2028 journey: added, changed (old text and face crossed out) and removed; **Swap**.
7. Export the journey and the comparison as PDF and PowerPoint, and open one in draw.io.
8. ＋ New journey from the starter; ＋ link a stage to a capability.
9. As user_stakeholder: the journeys show, without the editing buttons.
