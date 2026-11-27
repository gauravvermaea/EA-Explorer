# What EA Explorer does today (version 14.5.0)

One page for anyone weighing EA Explorer up: what is **built and in the box today**, area by area, and what is still
**planned**, with its build phase. "Planned" adds to what is already there; it does not mean an area is missing.
Every phase in detail: [build-phases.md](build-phases.md). Decisions: [decisions.md](decisions.md).

| Area | Today |
| --- | --- |
| Cost and licence | Free and open source (AGPL-3.0); no charge per user, per object or per module. Self-hosted: one laptop, one server or your cloud |
| Metamodel and standards | ArchiMate 4 and the TOGAF 10 content metamodel built in; your own metamodels, edited, versioned, reviewed and pushed down to the models that use them |
| Diagrams and visual analysis | Over a dozen kinds of picture drawn from the repository itself, so they are never out of date; each can be saved as a drawn view |
| Reports and BI | 30 standard reports and 49 views (each as diagram, catalogue, heat map, matrix and relationship list), roadmaps, value stream maps, gap, comparison and common analysis, quality dashboards; Apache Superset for your own |
| AI | Bring your own AI: an MCP server with about 140 tools and 11 guided prompts; enterprise discovery run by your AI (discovery projects, sources of every kind, Found in, runs tagged before and after, NOT FOR AI respected); your own language model reads, analyses, cleans up and changes models (copy, dedupe, override the parent, every model wizard), previewing every change for your yes and tagging first, as you and with your permissions; every call in an AI activity log |
| Collaboration and governance | Private changes until committed, conflicts at commit, child models merged back, reviews and approvals, sign-off with a quorum, stakeholder acceptance of answers, a full change log |
| Projects (TOGAF ADM) | Architecture projects from 14 templates, the TOGAF 10 library (13 phases, 116 steps, 171 deliverables and artifacts), key questions, Business Model Canvases, customer journey maps (5.7), the Architecture Repository |
| Documents and libraries | Document management (Mayan EDMS) inside projects, the reference library, the enterprise and project libraries with search |
| Integration | A REST API (OpenAPI), signed webhooks, Excel and CSV in and out with mappings, model packages, the MCP server; discovery: OData feeds read, pushes taken and documents read by AI, proposed as deliveries to review (Release 3, in progress) |
| Operations | One command (`eax`, full screen or numbered menu) and a console, start-up in two tiers, health, tagged backups and restores, every service switchable, a file explorer in every container |

## New in Release 8 (8.0.0, released 22 Nov 2026)

EA Explorer **tests itself harder**: `eax test full` runs the dev check, the self-test, an **attack test** that tries to
break it (OWASP ZAP, Schemathesis, Nuclei, Semgrep, Gitleaks), the backup and restore test and a **SonarQube** scan, and
writes one **summary page**; code coverage is measured and shown as a ring; test containers never stay running. On the
website, a **Questions** page by role with quick steps, the guide to read and the video; How do I under Documentation.

## New in Release 7.9 (7.9.0, released 19 Nov 2026)

Every problem has an **error code** (`EAX-AREA-NNN`) with what it means and what to do: in the API's answers, the logs,
System Admin's health and alerts, the screens' error messages and `eax status`; `eax errors <code>` explains one, and
Jenkins answers it too. The **error code guide** is on the website and printed guide 25.

## New in Release 7 (7.0.0, released 18 Nov 2026)

The documentation: the website with its How do I pages and guides, opened from the app, and **25 printed guides** as
PDFs (cover, purpose, contents) in the repository's documents folder, on the website and under Documentation.

## New in Release 5.6 (5.6.0, released 16 Nov 2026)

The backup and restore test (`eax test backup-restore`, last in `eax test full`): a backup B1, a project and models with
content of every kind, a backup B2; B1 restored leaves none of it, B2 restored brings all of it back, every database's
rows and every file's checksum compared, then sign-in, search, new work, the jobs and the documents checked; one step
after another from eax itself, on the installation after one typed confirmation. The restore drills (onto a new
machine, once a month) as documents with a PDF. Job priorities: low-priority recurring jobs miss a turn when the queue
is too full, each skip counted. Updates and deployments offer only the published GitHub Releases, in a drop-down with
their notes, never the main branch. See [releases/5.6.0.md](../releases/5.6.0.md).

## New in Release 5.5 (5.5.0, released 16 Nov 2026)

Enterprise discovery run by your own AI through MCP: discovery projects with a target model and sources of every kind
(mailboxes, folders, FTP, SFTP, SharePoint, Git, wikis, ticket systems and the CMDB, Teams and Slack, database schemas,
cloud storage and accounts, recordings), sign-ins tested then forgotten, a Discovery Admin role, every element's Found
in, runs tagged before and after, NOT FOR AI USE respected, "may be the same as" flags, overdue runs alerted.
Architecture decision records and dispensations in the organisation's Governance Log with an Architecture Board, linked
to elements, with expiry warnings and a report (OData). The Live browser full screen. See
[releases/5.5.0.md](../releases/5.5.0.md).

## New in Release 5.1 (5.1.0, released 16 Nov 2026)

A stabilisation release: the job queue on screen and safe to look after (System Admin › Running › Jobs and `eax jobs`:
what runs and waits in words, Kill, Cancel, Move, job slots, job history; jobs left by a stopped runner cleared), the
bugs of 5.0.0 fixed, a Jobs suite in the self-test and each area's passed and failed on its cards. See
[releases/5.1.0.md](../releases/5.1.0.md).

## New in Release 5 (5.0.0, released 15 Nov 2026)

Security at the front door (IP allow lists per place, multi-factor sign-in as a setting, the Auditor role, signed
deployments), alerts, logs and the web log, database maintenance, the optimisation report, server sizing, where the
data lives, the service desk, automated security and performance testing, the tests' browsers watched live, and every
part of the code documented. See [releases/5.0.0.md](../releases/5.0.0.md).

## New in 4.0.0 (Release 4)

- **Reports** on Apache Superset 6.1.0; a model's report links open their dashboard directly; a self-test suite signs in to
  Reports as people do and opens every dashboard (R4.1, R4.7).
- **AI (MCP)** is a menu of its own; Super Admins and IT Admins can run the installation through MCP: its state, what is
  slowing it down, logs, backups and restores, the number of servers and archiving, each change previewed and confirmed
  (R4.20, R4.22).
- **Project steps** in your own order within a phase (R4.21).
- Release notes: [../releases/4.0.0.md](../releases/4.0.0.md).

## The main screens
Since R2.0 ([r2-0-menu.md](r2-0-menu.md), D586–D591) the top bar has two rows. Row 1: the **site picker** (● Local,
pinned at the left: Farm Admin's Sites and Connect to a site, Super Admins), **EA Explorer**, **Find a function or
content** (or **/** anywhere), the bell, and **Last model** and **Last project** side by side. Row 2: the main menus,
each a drop-down with sub-menus: **Architecture Work** (My projects and My models, listed when opened; Compare and
analyse; Merge requests; Change log; **Model library** and **Project library**, for everyone, D594), **Model Admin** (Wizards: click for the wizards page, or pick one from its
sub-menus; Models; Model hierarchy; Metamodel drafts; Model library), **Project Admin** (Wizards; Projects; Project bases;
Templates and libraries; Principles; Surveys and maturity), **Repository & Content Framework** (the **Architecture Repository** and its parts,
the **Content framework**: content metamodel, model hierarchy, metamodel drafts; the libraries) and **System Admin**
(Wizards, Settings, Users and roles, Running, Backups and restores, Updates, Tools, Machine access, AI
activity); then on the right the **Menu | Classic** toggle, **the person's own menu** (their name and role: Home, My
tasks, Surveys to answer, Notifications, Recent and pinned, Search everything, My profile and skills, My tokens and keys,
Sign out) and **?** (help for this page, every document, getting started, release notes, the command line, MCP, the
API). What a person may not use is not shown. **Classic** (the menus as they were in 1.0, kept for now: System admin,
Model admin, Project admin, Architecture work, Architecture repository, Reference library and Everything else, and the
older row below: Start, Models, Projects, Repository, Library, Enterprise library, Reference library, Compare, Gap
analysis, Common analysis, Change log, MCP, Administration and API; with ? Help, Documentation (How do I first) and Sign out).

## Documentation
- **Documentation** (beside your name, for everyone signed in): every document that ships with the version you run,
  grouped (getting started, using EA Explorer, administration and operations, command line, reference, release notes,
  design and decisions), each shown as a readable page with links between them, a search across all of them, and
  Download and Print or save as PDF (D550)
- The same documents in the **Enterprise library**, folder **EA Explorer documentation**, refreshed from the running
  version at every start, so they are always the documents of that version: new ones added, changed ones replaced,
  ones no longer shipped removed (D550)

## Finding your way
Built ([navigation.md](navigation.md), D478–D481; changed in R2.0, D589–D590):
- **The menu bar**: the nine-area menu across the top, and each page's tabs in groups, then tabs, then sub-tabs, with a
  breadcrumb. The Classic screens of 1.0 are gone (D603, D606); every page they reached is in the menu bar.
- **⋯ Actions** on each tab: what makes sense there and the person may do.
- **Right-click on any entity** (rows, cards, links): open, edit, graph, history, related, add to a view, delete.
- **Find, / or Ctrl+K**: any function (every menu item, with where it is in the menu; the page's tabs and actions; the
  help's pages) or content (models, projects, entities as you type), and Search everything; near spellings work.

## On-screen help
- **? Help** (top bar), **Documentation › How do I** or **F1** anywhere: a help panel beside the page for what is on the screen (the pop-up, the wizard step, the sub-tab, the tab, the page), with a search over all the help (D531)
- **?** on every pop-up; a short **tooltip** on every button, tab and field (D531)
- One help catalogue for all of it, and a test that fails the build when a screen has no help ([help-catalogue.md](help-catalogue.md), D530, D532)

## Cost and licence
- **AGPL-3.0, no licence fees**: every user, every model, every module. The open-source parts it uses are listed in
  [licences.md](licences.md).
- **Runs where you choose**: a laptop (Docker Desktop), one server, or your cloud; your database, your backups, your
  network. Nothing is sent anywhere unless you connect it.

## Metamodel and standards
Built:
- **ArchiMate 4** seeded in full, and **six EA Explorer extensions** for TOGAF business architecture (value stream
  stage, product lifecycle stage, business scenario, control, contract, measure), each marked as an extension (D345),
  in the ArchiMate 4 domains and colours, with the allowed relationships of the owner's ArchiMate 4 guide (D392, D393).
- **Relationship multiplicity** on allowed relationships (1, `*`, 0..1, 1..*), checked by the data quality checks (D395).
- **Relationship attributes** (D563, D564): defined per relationship type or per allowed relationship (e.g. Connection protocol and Port on Node - Association - Node only), edited as key : value on relationships and in drawn views, required ones checked by quality.
- **Line labels** in drawn views: `name (Type) [key:value …]`; naming a line never hides its type (D565).
- **The TOGAF 10 content metamodel**, and the TOGAF catalogues, matrices and diagrams given by views (D345).
- **Your own metamodels**: domains, entity types, attributes, pick lists, allowed relationships and validation rules,
  edited in screens or as a whole document; a **lean metamodel** to start small.
- **Link attributes** (D418): point an entity (a work package, a requirement...) at more detailed documents: one or
  more links, each with a note such as a version; any address (web, ftp, a repository document, an EA Explorer link),
  clickable where it is safe to be.
- **Versions**: every metamodel change is a published version with its note and differences; compare any two;
  **push a new version down** to the models built on it, forced or offered (phase 8.1).
- **Reviews**: a metamodel draft (by a person or a language model) waits for review, comments and approval (D115, D130).
- **Industry reference models**: Banking, Government, Healthcare, Logistics, Manufacturing, Minerals and Mining, Pharmaceuticals, Retail and Telecommunications reference models (phase 39, D470, D548: capabilities, value streams, services, processes, products, business objects and a starter application landscape, from the owner's industry packs) and Meridian Assurance, the insurance worked example (D549), beside the insurance reference model to capability level 4, and the model library to share. **Industry packs** (D546): each industry's book, workbook, metamodel Excel to study, templates, PowerPoints and ArchiMate 4 views, shipped in the repository, put into Documents at start-up and downloaded from tiles on the library's Pack tab (`eax packs`)
  your own as reference models.

Planned: ArchiMate exchange format in and out, and a conformance check (phases 33, 33.1); more industry models when the owner adds packs (39).

## Diagrams and visual analysis
Built — every picture is **drawn from the repository when you open it**, so it always shows the data as it is now:
- **Network** around an entity (1 to 3 steps), **domains** (strategy to technology, for traceability), **impact**
  (what an entity leads to or depends on, up to 6 steps) and **split** (both ways at once).
- **Hierarchy and capability maps** (nested boxes, level 1 to 4), coloured by any attribute as a **heat map**.
- **Relationship matrices** between any two types.
- **Value stream maps** (stages with the capabilities enabling each, coloured by maturity or criticality) and
  **roadmaps** (plateaus, work packages and deliverables on a timeline).
- **View diagrams** for all 49 views, and the **metamodel diagram**.
- **Business Model Canvases**, with differences between two shown in colour (D344).
- **Customer journey maps** (5.7, D730): stages, steps with how the person feels (-2 to +2, drawn as a curve), touchpoints, pain points, moments that matter, opportunities and your own kinds of part, linked to model elements; compared, exported to PDF, PowerPoint and draw.io.
- **Logo and branding** (5.7, D729): your logo and name in the top bar, four themes, your own as CSS.
- **A presentation deck with your own AI** (5.7, D731): MCP tools give a project's content with its sources, an outline, and views as PNG, SVG or data.
- Click any box to open the entity. Every picture **opens in our draw.io** (D585), and saves as SVG, PNG or CSV.

Built (0.16.0): **drawn views** (phases 28, 29, D354): views drawn in draw.io, inside EA Explorer, with the ArchiMate 4
notation from the model's own entities (a search panel to drag them in; placeholders realised later), **two-way sync**
(D413): relationships drawn on a view go into the model at once, committed as the person (only the allowed types; deleting
a line asks: hide it in the view or delete it from the model), the model's committers edit an entity or create one from a
placeholder in its form and commit it from the drawing, the person's uncommitted changes listed in the editor to edit,
discard or commit, and a view brought up to date with the model when opened (with a note) and watched while open; draw.io's
General, Misc and Basic palettes for notes, comments, text and arrows that never touch the model (D414); each save kept as a version (with a warning when someone saved since),
Resync with the model, And/Or junctions, entities' own icons, heat maps by an attribute, exports (PNG, SVG, PDF, .drawio),
*Save as a drawn view* on every generated picture (tidied, in the ArchiMate notation), any view copied (a drawn view, a
generated picture, or a standard view's definition as the model's own view), a view as a project's evidence (a link to
the live view or one version), a stencil of all the metamodel's types whose groups each person shows or hides, and MCP
tools to draw one. Creating an entity on the drawing shows the names already in the model (the same, reordered or near spellings) with *Use this one*, and asks before making a second of the same name and type; the drawing's searches find near spellings (D454). Every type drop-down on the drawing can be typed in to find a type, with near spellings (D540). The working space (D420): the stencil on the left and a resizable bottom panel (Find in the model,
Properties, Relationships, Allowed relationships, Uncommitted changes), each pinned or folded away, in three preset
layouts (Drawing, Editing, Canvas only) remembered for the person; a pop-up on every stencil drop (bind, create, or leave
as a placeholder); related entities and allowed relationships added next to the selected object in one click; draw.io's
Format panel removed so the drawing has the room. Every view is a draw.io file kept in a views service with its own database (D405 to D409).
Everything opens in our own draw.io (0.19.0, D585): every picture of a model, a Business Model Canvas and a .drawio document
offer **Open in draw.io**, a read-only scratch view in a tab of its own, kept nowhere: export it (.drawio, PNG, SVG, PDF) or
**Save as a drawn view** there. draw.io's **File › Export as** has **.drawio file** (uncompressed, named after the view) on
drawn views and scratch views alike.

## Reports and BI
Built:
- **30 standard reports** and audience dashboards in Apache Superset, each checked; heat maps and a model overview.
- **49 views**, each shown five ways (diagram, catalogue, heat map, matrix, relationships), with the TOGAF
  artifact each gives (D345).
- **Roadmaps, value stream maps, dependency and impact** (phase 8.2).
- **Compare** any two models or tags; **TOGAF gap analysis** with resolutions and work packages; **common analysis**
  across many models (phases 8.3, 13.0.5).
- **Data quality**: score, completeness, freshness, orphans, rules, trends, drilling to the entities (phase 12).
- **Project reports** and the project's completeness by phase.
- **Your own reports**: every entity type is a report view, so Superset (charts, dashboards, SQL) works on it directly.

- **KPI trends** (phase 24): a standard set per model (entities by type, applications by TIME and lifecycle, total
  cost, quality score, orphans, end-of-life technology) and each model's own KPIs (a count or a sum with a filter), kept
  on the 1st of each month and on every tag, on the model's KPIs tab and in report KR-01.
- **An OData feed** per model for Power BI and Excel: every entity type as a table, read only, signed in with your own
  user name and password (Basic), with your own permissions (phase 24).
- **A report designer**: choose a type, columns, related types and filters, see the first rows, and open it in the
  reporting tool's chart builder (phase 24). Scheduled reports are not offered (D365).

## AI (bring your own model)
Built ([mcp.md](mcp.md)):
- **Model operations from plain requests** (D458, phases 26/27): "make a copy of this model and remove all duplicates as
  you see fit", then "override its parent with it". Copy, dedupe, override the parent, refresh, merge requests, every
  model wizard and common analysis; every change is **previewed for your yes, then confirmed**, the model **tagged
  first**, and done with **your own rights** (a read-only credential only reads).
- **Analysis by an assistant**: impact of retiring something, application overlaps and TIME suggestions, cost by
  capability, end-of-life technology risk, single points of failure, heat maps, what changed since a tag, KPI trends;
  clean-up (bulk fixes, tidy names, orphans); Word reports into a project; principles and standards checks; surveys and
  maturity; usage questions for admins. Answers carry **links back** to the entities.
- **The AI activity log**: every call, your own or (admins) everyone's: the tool, the question, what it changed.
- **A remote connector**: add EA Explorer to an AI app and sign in through Keycloak in the browser (OAuth).
- **An MCP server** at `/mcp`, with **82 tools** and **3 guided prompts** (build a project, build a model, fill a
  model). Any model that speaks MCP works: hosted or local. None is shipped and nothing is sent to one unless you
  connect it.
- It works **as the person signed in**, with exactly their permissions.
- It **reads and analyses**: metamodels, entities, relationships, history at any point in time, paths and impact,
  search, views, value streams, roadmaps, comparisons, gap analyses, quality findings.
- It **builds**: models (empty, copies, children), entities and relationships in bulk, projects from templates,
  steps, documents' acceptance, key questions and their answers, Business Model Canvases.
- It **proposes, a person decides**: what it adds is the person's uncommitted change until committed; metamodel
  drafts and quality rules wait for review.

- **Plans scenarios** (phase 27.1, 0.18.0, [phase-27.1.md](phase-27.1.md)): the prompt *plan scenarios* compares a
  project's scenario models with its baseline (cost, applications, capabilities covered, end-of-life technology,
  risks, what each adds, changes and retires, the capabilities it touches, a suggested score), makes scenario models
  (the baseline tagged first), applies what-ifs ("retire X, replace it with Y") as the person's own uncommitted
  changes, and records the assessment as a Word document and a governance decision for approval; every change is
  previewed first and made only after a confirm. The project's **Scenarios** tab shows the comparison and the
  assessments.

Planned: proposals into a staging area across the whole repository (phases 26, 27).

## Collaboration and governance
Built:
- **Roles and permissions** through Keycloak (single sign-on), global and per model and per project.
- **People's skills**: each user adds their own on My profile; the Skills repository lists every user with theirs (D353).
- **Commits**: changes are private until committed; conflicts are shown at commit; roll back; Committer and History
  Viewer roles (phase 8).
- **Child models and merge back** (phases 19 and 20, 0.17.0): a child is sent for merge by its Model Admin; the
  changes are worked out three-way against the child's starting point (only the child's changes are sent; where both
  changed, a conflict); the parent's Model Admins and Committers accept or reject each change (a reason for each
  rejection), then merge it as one commit; a merge report in Word; then the child is frozen or refreshed from the parent.
  Split and merge models, propagate from parent to child (phases 8, 13.0.4).
- **Dedupe** (phase 21, 0.17.0): likely duplicates by name (near spellings) and by the same values in chosen attributes;
  compare side by side, choose the one kept and each field's value; relationships move to it; old IDs still find it;
  anyone who may change the model, committed like any change. Data entry warns when a new name looks like an existing one.
  Its own tab (Quality › Duplicates, 0.19.0): choose the type (type a few letters to find it), press Find duplicates; "No likely duplicates found" when there are none; download the result as Excel (D541).
- **Tags**: frozen snapshots to compare with, copy from or go back to.
- **Reviews and approvals**: metamodel drafts, quality rules, documents (approval by the sign-off people, with a
  quorum), the governance log (dispensations and decisions, with approval), project sign-off (D321).
- **Key questions**: each stakeholder question answered with links to the artifacts and accepted by the stakeholder (D341, D342).
- **Collecting data from people**: send stakeholders a sheet for their part of a model; review what comes back (WIZ-018).
- **Notifications and requests** (like tickets) between people, and **signed webhooks** to other systems (phase 8.1).
- **The change log**: every action, who, when, before and after; in its own database (phase 9).
- **Guided wizards** for the common jobs (phase 16.3).
- **Surveys** (phase 38.1, 0.17.0): a designer with sections, eight kinds of question and conditions; sent to people,
  global roles, models or projects through their task list and a link (never email); reminders, closing dates,
  anonymous surveys; results by question and Excel. Answers never change a model.
- **EA capability maturity** (phase 40, 0.17.0): assessments sent as surveys on nine architecture elements and six
  levels (in our own wording), scored per element and overall with targets and gaps, beside evidence EA Explorer
  measures itself, and a trend over assessments.

Planned: ownership and collaboration (22), portfolio, lifecycle and impact (23).

## Projects (TOGAF ADM)
Built (phase 13):
- **Architecture projects** from **14 templates** (transformation, as-is documentation, build or buy, cloud migration,
  acquisition and others), each with its models in roles (current, target, transition, scenario, reference, working copy).
- **The TOGAF 10 library**: 13 phases, 116 steps, 171 deliverables and artifacts, 51 repository folders.
- Scope, goals and outcomes, stakeholders and their map, **key questions**, principles, standards, the governance
  log, the charter, calendars and the Architecture Board, tracking sheets, tasks, sign-off.
- **The Architecture Repository**, the content framework and the standards information base.
- **Architecture principles as cards** (D607): by area, with statement, rationale and implications, enforced or optional, refinements and dispensations; Repository › Architecture principles and each project's Principles tab; edited on the card.
- **Business architecture**: the TOGAF Phase B artifacts with their views, and **Business Model Canvases**
  (current, target, working copies marked by hand, compare and make a new one) (D344, D345).
- **Project backups and restores**, with the project's documents, models and library.
- **ADM iteration types** (0.19.0, D571 to D574): each project's ADM cycle is a Full cycle or one of TOGAF's
  iterations (Architecture Capability, Development, Transition Planning, Governance) or a Custom set of phases, chosen
  and changed on the project page by anyone on it; phases left out are frozen (read only, never deleted) on the ADM
  wheel, the phase tabs and in the API; also in MCP, backups, templates and the report ([phase-iterations.md](phase-iterations.md)).
- **Other views and documents** (0.17.0): a project tab of ten sample templates (SWOT, customer journey map, value
  proposition canvas, one-page business plan, interview guide, decision record, business case, RAID log, lessons
  learned) in Word, PowerPoint or Excel, our own wording, to download and use; and the project's **own uploads**
  (D461): anyone on the project uploads files of any type (several at once, 50 MB each) with a title and description
  and downloads them; whoever uploaded one (or the Project Admin, Lead Architect or a Super Admin) replaces it, keeping
  the earlier file as an earlier version, or deletes it. Not deliverables: no sign-off, not in the repository table.

## Documents and libraries
Built:
- **Document management** (Mayan EDMS) inside each project's repository: versions, check-out, tags, acceptance,
  approval, archive.
- **The reference library**: standards, regulations and research, with search inside the documents (D300).
- **The enterprise library and project libraries**: simple pages, links into EA Explorer and the web, the odd file,
  one search box, history and undo; or point it at your own intranet instead (phase 15.2, D346 to D351).

## Integration
Built:
- **A REST API** for everything the screens do, documented with OpenAPI at `/api/docs`.
- **Signed webhooks** for what happens in EA Explorer (phase 8.1).
- **Excel and CSV**: sheets built for the types you choose (with drop-downs), loaded with a preview, column mappings
  and undo (phase 10.1); tracking sheets in and out (13.2).
- **Model packages** to move models between installations (phase 4).
- **The MCP server**, so assistants can connect EA Explorer to whatever else they reach.
- **Machine access** (phase 25, [phase-25.md](phase-25.md)): tokens, API keys and client certificates (mutual TLS on a port
  of its own) for people and service accounts, read or read-write per API area, optionally only some models or projects,
  expiry, revoke, last used, every call in the change log; they work for the API, the OData feed and MCP.

- **Published import formats and deliveries** (phase 34, [import-formats.md](import-formats.md)): the Excel format and the
  CSV format (one CSV per sheet plus master.csv), empty templates made on the fly; import sources per model; deliveries
  dropped in a source's folder (which IT may map to SFTP or a share) and taken on request (`eax import`), sent to the API
  by a service account, or uploaded; matched by type and name, only adding and changing, EA Explorer's values kept unless
  the source's win; previewed and accepted by a Committer as their committed load, or declined. The ArchiMate 4 exchange
  format once it is published.
- **A model from a metamodel workbook** (D419): any model's metamodel downloads as a workbook (types, attributes, allowed
  relationships with multiplicities, rules); fill or change it in Excel and make a new model from it, blank or added to
  an existing model.

- **Data discovery and ingestion** (Release 3 epic, on main; [discovery.md](discovery.md)): import sources that are an
  OData feed EA Explorer reads, an endpoint other systems push to, or documents the AI engine reads; the sets, fields
  and keys discovered and mapped to the model's types and attributes (suggested, a person confirms); on demand, daily or
  weekly, each run proposing only what changed as a delivery to preview and accept; near names suggested as matches;
  a push source's Python kit (a short documented script, requirements, venv steps and sample CSVs) to download;
  Import and export guided both ways by the Bring data in and Take data out wizards.

Not planned: connectors to particular products (they write the published formats or a feed EA Explorer reads), ETL and
outbound feeds.

## Operations
Built ([operations.md](operations.md), [command-line-and-console.md](command-line-and-console.md)):
- **One command**, `eax`, for Windows, Linux and macOS: start, stop, status, logs, health, backup, restore, services,
  passwords; and **`eax console`**, a menu for getting EA Explorer back up.
- **Banner** (System admin, D558): one message under the top bar for everyone or admins only, information, notice or
  urgent, with optional times; nothing shows unless an admin sets one.
- **Schedules** (System admin > Command centre, `eax schedule`, D559): eax commands that run by themselves in the
  installation's time zone, e.g. a nightly backup or a demo that resets every night; kept in persist/, so they survive
  resets (D558), proved by `eax test --reset-survival` (D561).
- **Command centre** (System admin, IT and Super Admins, D554): every eax command from the browser with a guided form,
  a **Console** that takes eax commands as typed and `eax console`'s menu (never a shell), and the history of every run
  with its output. Delete-everything commands for Super Admins only, behind the installation's name, "I understand"
  and a backup first. The same tabs on `eax deploy`'s page.
- **Start-up in two tiers**: people can sign in within a minute or two while the rest comes up.
- **Health** of every part in the header and on Heartbeat; the administration console with settings applied at once.
- **Backups**: tagged infrastructure backups (every database, files, certificate, configuration, versions), nightly
  and on demand, pinned, restored whole or in part; application backups of every model; project backups.
- **Every database has its own setting** (R2.50, D611): empty means the shared PostgreSQL; set one to move that
  database to a container or server of its own. System Admin › Databases and `eax databases` show where each lives
  and whether it answers; backups follow each one ([databases.md](databases.md)).
- **The self-test's data in its own database** (R2.28, D613): runs, results and screenshots apart from the
  architecture; tables made and kept in line at every start; `eax databases copy tests` moves earlier runs.
- **Operations data in its own database** (R2.27, D614); **persist/ emptied from the web or eax** (D618); **logs kept by day,
  backed up and cleaned** (D619); **the footprint measured** (D620); **the release
  and build at the top left** (D616).
- **Memory measured and recorded** (Release 3.5): `eax footprint --watch` and `eax measure` (start-up, smoke test, at
  rest, in use, full test, one summary); every self-test run watched; **the resource history** (D679): memory, CPU,
  disk and the database's cache of every container every 15 minutes, kept and charted on System Admin › Footprint
  (CSV, a shorter interval for a test, deleted by a Super Admin), `eax footprint --history`. The operations and
  personal data parts run inside the API container (D677); Documents' workers and Keycloak's heap are set per deployment.
- **Every optional service can be switched off** (reports, documents, draw.io, MCP, change log, backups, library),
  with a dated copy of the configuration kept.
- **Operations insight** (phase 35, [phase-35.md](phase-35.md)): who uses what and how often, models' use and size,
  idle models (a report only), stale work; Prometheus metrics at `/api/metrics`; database health.
- **Housekeeping** (phase 35.1): retention rules (keep, archive or delete after N days) with defaults that only archive,
  a nightly job that acts only after a confirmed dry run, and a searchable archive; old history versions removed only
  after an age a Super Admin sets, never those a tag, baseline or evidence needs.
- **Scaling out** (phase 36.3, [phase-36.3.md](phase-36.3.md)): API servers set on the web page, fixed or by rules;
  more hosts, a database standby, shared storage and the library on its own server, all with Docker Compose.
- **Testing** (phase 36.1, [testing.md](testing.md); simple since R2.0.1, D592, D593): two choices, the **Smoke test** or
  the **Full test** (every API endpoint as every role, the database, security, every page and journey in a browser),
  from System Admin › Tools › Self-test or `eax test` / `eax test full`. Each run removes the test data earlier runs
  left, starts its own test container, makes the data it needs, tests, reports (History; work/tests) and removes the
  container. **Run the failed ones again** (History, or `eax test failed`) repeats only what failed and shows each
  check then and now (D605). **Delete all test data** on the page, or `eax test clean`. CI also runs the test bench
  ([testbench.md](testbench.md)): install, upgrade, other browsers and load.
- **Deployment** (phase 36, [deployment.md](deployment.md)): `eax deploy`, a guided wizard in the console or a local
  web page, for five kinds: this laptop; a Linux server (on it, or from here over SSH, Docker installed if missing);
  AWS, Azure and DigitalOcean (the machine, a data disk, the firewall, a fixed address, off-site backup storage and DNS
  names created from your credentials, or a machine you have). Every password generated, `--plan` to see every
  command first, Retry or Back when a step fails. A stand-alone **installer** (eax-deploy) downloads the version you
  choose from the repository link, no copy of the repository or git needed. **Moving an installation** from one of
  its backups; **passwords kept in a key vault** too (`eax secrets`: a file, AWS Secrets Manager, Azure Key Vault);
  **Active Directory groups mapped to roles** (through Keycloak's LDAP federation or Entra ID group claims).
- **Deploy from the application** (System admin › Deploy, Super Admins and IT Admins; D555): a running installation
  deploys EA Explorer to another place (a server over SSH, or AWS, Azure or DigitalOcean): plan first, progress, Retry,
  Back or Quit, the log; run by the operations helper so it survives reloads; SSH keys and cloud credentials for the
  run only unless kept, never shown again; the history of every target. Fleets of installations: release 2.
- **Updates** (phase 36, [phase-36-updates.md](phase-36-updates.md)): System admin › Updates and `eax update` move to a
  newer published release from the repository's GitHub Releases (Prod and RC channels; forward only; never main), with a pinned full backup
  of the code, databases, files and configuration first, one release at a time, built on the host; a failed step stops
  for Retry or Roll back (`eax rollback`); now or at a time, with a banner beforehand and What's new afterwards.
- **Releases** (8.5, [release-process.md](release-process.md)): CI on every change, versioned releases with notes
  (`tools/release.py`), a supported-versions policy, and the administrators told when an update fails or a version is
  out of support.

Planned: deployment kinds and scripts, upgrades, test automation, scale-out ([story-load-balancing.md](story-load-balancing.md))
and real-time mirrors ([story-real-time-mirrors.md](story-real-time-mirrors.md)) (phases 35 to 37).
