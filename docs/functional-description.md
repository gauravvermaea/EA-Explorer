# EA Explorer: functional description

What EA Explorer does, area by area, and where in the code each part lives (R5.14; owner, 13 Nov 2026: "the code
documented in detail ... a detailed functional description"). It describes behaviour; the reasons are in
[decisions.md](decisions.md) (the D numbers), the list of features of the current version in
[capabilities.md](capabilities.md), and how it is built in [architecture.md](architecture.md). Every Python module,
class and function also says in its own docstring what it is for (a test keeps it so: `tests/test_r5_15_code_comments.py`).

## Purpose and people

EA Explorer is an open-source enterprise architecture repository: it holds an organisation's architecture as models
(elements and the relationships between them, described by a metamodel such as ArchiMate 4), runs architecture work as
projects that follow the TOGAF ADM, and turns both into views, reports, documents and answers for AI assistants.

People are known through Keycloak and given **global roles** there (Super Admin, IT Admin, User Admin, Model Creator,
Library Admin, Auditor and the rest, mapped to EA Explorer's in `eax/permissions.py`) and **roles per model**
(Model Admin, Model Sub Admin, Committer, Architect, History Viewer, Report Viewer) and **per project** (Project Admin,
Lead Architect, Architect, Stakeholder). Every API call is checked in `eax/auth.py` (`require_auth`) and again in the
database (row-level security). The **Auditor** sees everything a Super Admin sees, changes nothing and never sees a
secret (R5.22, D693).

## Models

**The metamodel** (`eax/metamodel_edit.py`, `eax/trees.py`, `eax/grids.py`): entity types in domains, relationship
types and the pairs they may join, attributes and pick lists, rules (mandatory, ranges, multiplicity). One change
publishes one metamodel version; a change is never blocked by content already there (D64). Root metamodels (Root,
ArchiMate 4) and reference models are shipped locked.

**Content** (`eax/content.py`, `eax/repository.py`, `eax/sheets.py`, `eax/loads.py`): elements and relationships
entered in forms, grids (paste from Excel), import sheets and CSV loads; checks warn and never block (D48).
Nothing is hard-deleted: every version of every row is kept in `history.row_versions`.

**Commits** (`eax/commits.py`): what a person changes stays theirs until it is committed (by a Committer); a commit can
be rolled back. **Tags** (`eax/tags.py`) freeze a model; a tag can be restored as the latest. **Compare and gap
analysis** (`eax/compare.py`, `eax/gaps.py`), **commons** (what several models share, `eax/commons.py`),
**merge** of a child into its parent (`eax/merge.py`, `eax/merge_back.py`), **dedupe** (`eax/dedupe.py`),
**push-down** of a parent's metamodel to its children (`eax/pushdown.py`), and the model wizards (split, extend,
freeze, detach, move, `eax/model_wizards.py`). **Packages** (zip or Excel) move a model between installations
(`eax/model_ops.py`). Slow work runs as **background tasks** (`eax/tasks.py`, `eax/background.py`).

**Quality** (`eax/quality.py`): completeness and rule scores per element and model, seals and exemptions.
**KPIs** (`eax/kpis.py`) are defined on attributes and trended.

### Diagrams and views

Views are data (`eax/views.py`): viewpoints VP-01 onwards and an organisation's own, shown as diagrams, catalogues,
heat maps, matrices and roadmaps. **Drawn views** (`eax/drawn_views.py`, the views service `services/views`) are
draw.io diagrams whose shapes are model elements: a change drawn is a change to the model, committed like any other.

## Projects

Architecture work as projects that follow the TOGAF ADM (`eax/projects.py`, `eax/project_work.py`): a project has
phases and their deliverables from the library (`eax/seed/project_library.py`), documents kept in Documents
(Mayan EDMS, `eax/mayan.py`) with versions and sign-off, its own models (baseline, target, scenarios,
`eax/scenarios.py`), scope and sponsor, stakeholders (`eax/stakeholders.py`), key questions (`eax/key_questions.py`),
governance records and the charter (`eax/governance.py`), canvases (`eax/canvases.py`), tasks
(`eax/project_tasks.py`), calendars (`eax/calendars.py`), iterations (`eax/iterations.py`) and its own reference
library (`eax/references.py`). The organisation's repository brings every project together (`eax/org_repository.py`).
A project can be backed up and restored on its own (`eax/project_backup.py`).
Release 12 adds: an Agile project's sprints (`eax/agile.py`, the Sprints tab), every project's plan with RACI, approval
gates, milestones and status (`eax/pm.py`, the Project plan tab), the risk register read from the Governance log and
the models (`eax/risk_register.py`), the model and project templates (`eax/seed/model_templates.py`,
`eax/seed/project_templates.json`), and the start-up scripts that bring existing projects and models up to date
(`project_upgrade_sql` in `eax/seed/project_library.py`, `model_upgrade_sql` in `eax/seed/build.py`). Their MCP tools
are in `eax/mcp_release12.py`.

## Documents and libraries

The enterprise reference library (`eax/reference_library.py`; an organisation's own guides come in as a zip, folders
kept, Release 12; the TOGAF guides EA Explorer follows are listed from `eax/guides.py`) and the library service (`services/library`: pages,
links and files in folders, with history); the documents shipped with each version (`eax/shipped_docs.py`), shown under
Documentation; sample templates (`eax/sample_documents.py`); industry packs (`eax/industry_packs.py`).

## Reports

**Reports** (Apache Superset, `eax/reports.py`, `eax/setup/superset_reports.py`) reads report views (`rpt.*`) through a
login that sees only what each person may (D138). The standard reports, KPI trends, heat maps and the report designer
(`eax/report_designer.py`). An **OData feed** per model (`eax/odata.py`) for other BI tools.

## AI and integration

The **MCP server** (`eax/mcp_server.py` and `eax/mcp_*.py`) lets an AI assistant read and change models, run analyses
and operate the installation, with the person's own rights; every call is recorded (AI activity, `eax/mcp_activity.py`).
**Discovery** (`eax/discovery.py`): OData feeds read, pushes taken, documents read by an AI engine, each run becoming a
**delivery** (`eax/deliveries.py`) previewed and accepted like a load. **Webhooks** (`eax/webhooks.py`) and **machine
access** (API keys, tokens, client certificates, `eax/machine_access.py`) for other systems.

## Collaboration

Notifications (`eax/notify.py`), requests between people (`eax/tickets.py`), the **service desk** with its catalogue
(R5.11, `eax/servicedesk.py`; R5.27: a group, then the request; every request to the Super Admins, who assign it), surveys and maturity assessments (`eax/surveys.py`, `eax/maturity.py`), saved views and
favourites (`eax/workspace.py`), skills (`eax/skills.py`).

## Operations

Run from System Admin, from `eax` on the command line and from MCP, all on the same functions:

- **Backups and restores**: application, infrastructure, model and project backups, scheduled and kept by rules
  (`eax/backups.py`, `eax/backup_schedule.py`, the backup container's scripts); restores guided and recorded.
- **Updates** from git, with a backup first and a roll back when they fail (`eaxcli/updater.py`); releases can be
  **signed** and checked before anything changes (R5.10, `eaxcli/signing.py`).
- **Health and alerts**: the health page (`eax/health.py`), container and host watching (`services/ops/hostwatch.py`),
  and the **alerts system** (R5.9, `eax/alerts.py`): checks with levels, hold, flapping, acknowledge, silence,
  escalation, email and webhooks.
- **Logs** (R5.6 to R5.8): every container's logs kept a day a file and rolled at 50 MB (`eaxcli/logkeep.py`), the web
  log of every call (`eax/weblog.py`), on System Admin › Logs.
- **Database maintenance** (R5.12, `eax/dbmaint.py`): every database checked daily and tidied nightly without locks;
  compacting, lock resolution and ending idle sessions after a preview.
- **Scaling** (several API servers, `services/ops/scaling.py`), the **resource history** (`eax/resources.py`), the
  **footprint** (`services/ops/footprint.py`), housekeeping and the archive (`eax/operations.py`, `eax/archive.py`).
- **The optimisation report** (R5.1, `eax/optimise.py`): monthly suggestions with their evidence, the people who made
  and look after each model or project, applied only with a person's yes, for a whole model or project.
- **Server sizing** (R5.19, `eax/sizing.py`): a best estimate of RAM, CPU and disk per server and per container.
- **Where the data lives** (R5.4, `eaxcli/datafolders.py`): one base folder with a folder per kind of data.

## Security

Sign-in through Keycloak (multi-factor as a setting, off by default, R5.3, `eax/keycloak_upkeep.py`), a break-glass
account for when Keycloak is down (`eax/api/break_glass.py`), **IP allow lists** at the front door per place (R5.2,
`services/ops/allowlist.py`, `eax/ip_allow.py`), the Content-Security-Policy and headers (D672), secrets never stored in
the database, discovery's addresses checked (D671), the Auditor role, and **automated security testing** (R5.17):
scheduled scans, code and secrets scanning, the attacks of Release 3 as tests, and a gate with accepted findings that
expire (`eax/testing/security_gate.py`, `eax/testing/codescan.py`, `eax/testing/attacks.py`).

## Self-test

The installation tests itself (`eax/testing/`), in test data of its own that it removes afterwards: smoke or full;
suites api (every endpoint as every role, writes, negative tests), ui (every page and journey in Chromium), db,
security, reports, **performance** (R5.18: the benchmark with k6 against the last release's baseline,
`eax/testing/benchmark.py`; only when asked for by name, never in the full test, R5.29), backup and restore. A run can be watched step by step, **its browsers live** (R5.20,
`eax/testing/screencast.py`), repeated for what failed, and reported as HTML and Excel. The outside **test bench**
(`testbench/`) runs the same checks from another machine and in CI.

## The command line

`eax` (`eax.ps1`, `eax.sh`, and the Python `eaxcli/`, kept in step, D331) starts, stops, updates, backs up, restores,
tests and looks after an installation; `eax help` lists every command, `eax dev check` is the first thing a newcomer
runs (R5.16, [handover.md](handover.md)).
