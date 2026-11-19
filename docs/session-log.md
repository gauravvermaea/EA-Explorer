# Session log (running notes)

The working notes of the current session, written **as we go** so that any AI picking up the work can carry on
(owner, 18 Nov 2026, 19:22: "keep a file moving forward so that the session context and discussion is kept in the
folder so that if the AI agent gets lost it gets picked from there"). Read this after CLAUDE.md, AGENTS.md and
docs/handover.md. docs/handover.md stays the end-of-session summary; this file is the live log.

## Session of 18 Nov 2026 (evening), Release 7: documentation

### Where we were (recovered at 19:00)
- The earlier session (Claude Code) was lost. Last commit 16:15 "Started with documentation". Work done after it
  (site pages ~17:00, screenshots 18:05 to 18:13, D776 to D780 at 18:33) was on disk; the owner has checked it in.
- Release 7 state: the website is built (R7.1, D776 to D779): role guides, 281 How do I pages, 22 Guides, Concepts,
  Integrate, Platform, a page for each of the 145 reports. Videos moved to Release 9, Jenkins testing to R8.3 (D780).
- R7.7 still to do: GitHub Pages publishing, docs per version, deep technical dives.
- docs/handover.md is stale (says 17 Nov, Release 5.7): to be updated at the end of this session.

### The owner's asks, in order (19:11 and 19:23: "check documentation fix it and then work on pdfs")
1. **Check the How do I screenshots against what each page asks; fix wrong pictures.**
   Found: `eax site shots` (services/api/eax/testing/site_shots.py) only opens each page's address (D777: it only
   opens pages). 281 pages, only 159 distinct screens; 180 pages share a picture with another page (13 on
   #/metamodel/{m}/import, 9 on views, 7 on #/mcp/tools...). The picture does not show the tab, dialog or wizard step
   the task is about. Fix: per-task actions in the shot list (open the tab, the dialog), which changes D777's
   "only opens pages" rule: to confirm with the owner.
2. **Build 24 professional PDF guides** (cover, purpose, table of contents; people print and keep them), from the
   content already made; **ask the owner before writing any new content**. Whether they go on the site: decided later.
   The list:
   1. Overview: capabilities, roles, who does what
   2. System architecture and platform developer guide
   3. Install guide
   4. System admin guide, with How do I
   5. Day-to-day operations, with How do I
   6. Tuning and optimisation guide
   7. Administrator guide for models, with How do I
   8. Administrator guide for projects, with How do I
   9. Architects' guide, with How do I
   10. Industry expert guide: how do I make an industry model
   11. Developer guide: examples making connectors and other things they can do
   12. DR guide
   13. Setting up site pairing for hot-hot DR
   14. Emergency guides: reset passwords, I can't get in, rotating keys
   15. EAX command guide
   16. Jenkins guide
   17. Example project end to end with EA Explorer
   18. Guide to test the installation
   19. Guide to test backup and DR, by hand and with the commands
   20. Upgrade guide: from a git release, or getting the latest code by hand and upgrading
   21. Troubleshooting guide for admins: logs, error codes
   22. AI and MCP user guide
   23. Setting up Keycloak with AD, Entra, OAuth (Google) or your own provider
   24. Security best practice guide

### Progress
- 19:20 owner zipped docs/ (docs.zip, 46 MB) and services/web/src (src.zip) for the AI to read.
- 19:22 this file started (docs/session-log.md).

### 1. The How do I pictures: what is wrong (checked 18 Nov, evening)

Checked all 281 pages against their 281 pictures (front matter `screen:`, the steps' bold labels against the web
source, and the pictures themselves read one by one and measured).

**Three faults:**

1. **Four pictures were taken while the page was still loading** (`see-the-project-report`, `upload-project-files`,
   `read-the-documentation`, `see-whats-new`: "Loading..." and nothing else), and a dozen more show a page only part
   drawn. `site_shots.py` waits for `networkidle` and then 1.5s; a screen that keeps polling (the heartbeat every 20s)
   never goes idle, so the wait ends early. **Fix:** wait until the page has drawn (no "Loading" text left in the main
   panel), then a settling pause, and say so in the log.
2. **180 of the 281 pages share a picture with another page** (159 distinct screens): the picture shows the screen the
   task starts on, not the tab, sub-page or dialog the task is about. 13 pages all show `#/metamodel/{m}/import`.
   **Fix, in two parts:** (a) most sub-pages *are* addressable - the import tabs are `/import/loads`, `/deliveries`,
   `/discovery`, `/git`; views are `/views/{code}`; changes, quality, grid and entry all take a sub-path - so the page's
   `screen:` becomes the precise address and nothing is clicked (D777 holds); (b) where a task is about a dialog or a
   wizard step there is no address, so the page gets a new `do:` line (open a tab by its name, open a dialog by its
   button) which `eax site shots` follows before taking the picture. It still never saves, deletes or runs anything:
   the labels it may click are checked against a deny-list first.
3. **14 of the 409 bold labels in the steps are not in the product** (`Make it the latest version`, `Send for review`,
   `Mark answered`, `Do again`, `Relate to`, `Type attributes`, `What is this?`, `From Other Sources`,
   `Wizards, Model from a metamodel workbook`, `A principle that refines another`, `Open Keycloak`; and `Add user`,
   `Assign role`, `Allowed addresses`, which are Keycloak's own labels and right as they are). **Fix:** correct each to
   the label the screen shows.

### 19:43 to now: the cloud chat took over again (owner: "no you override"), the folder connected to it
- Kept Claude Code's findings above and its site_shots.py (waits for the screen; `do:` with tab and open).
- Added to site_shots.py: `follow "words"` (go to a link's address), `pick "words"` (a card such as a setup guide),
  and OPENERS (buttons read in the web code that only open a dialog: Bring data in, Take data out, + Add a source,
  Copy as my model's view). test_r7_1_website.py updated for D781 (the old "two clicks only" test would have failed).
- 47 How do I pages given their exact screen and `do:` line (entity tasks via `#/search?q=Claims%20Platform` and
  `follow "Claims Platform"`; drawn views via `follow "Claims application landscape"`; machine-only tasks show their
  setup guide). Labels fixed: Make this the latest, Refine it, Change in Keycloak. D781 written in decisions.md.
- **Still to check with the owner:** `Relate to`, `Do again`, `What is this?`, `Send for review` (the right label
  depends on how those screens behave). Pages that still share a picture but show the right screen were left alone
  (Secrets, Alerts, Backups, Restores, Security, the AI tiles...).
- **The owner runs:** `.\eax site build` then `.\eax site shots` (all pictures again, not --missing), then
  `.\eax site build`; then reads work/tests/site-shots.log for "nothing called ...".
- **Next: the 24 PDF guides** (task 2 above).

### 19:57 Release 7.9 added (error codes and the error guide, D782)
- R7.9-E1 (error codes, one list; `eax status` gives each problem's code and what to do) and R7.9-E2 (the error guide).
  Guide 21 has no messages table because of it.

### 20:30 The 24 printed guides built (D783)
- docs/manuals/manuals.json (the 24 guides, their chapters and sources), tools/build_manuals.py (the builder),
  docs/manuals/new/ (new content: Keycloak with Entra ID / Google / OIDC / SAML; Jenkins from inside EA Explorer).
- `eax site pdfs [--only ID]` (eaxcli/site_cli.py, help.txt) prints them in the test runner into work/manuals.
- Owner's answers (19:5x): new Keycloak sections yes; hot standby (not hot-hot); Jenkins built normally, no "untested"
  note; messages table replaced by Release 7.9.
- Preview PDFs (659 pages, no pictures yet: a box marks each) copied to work/manuals/preview.
- **The owner runs:** `.\eax site build`, `.\eax site shots`, `.\eax site build`, then `.\eax site pdfs`.
- **Known in the source docs (not changed):** command-line-and-console.md still says deploys go to AWS, Azure and
  DigitalOcean and that "phase 36 ... brings a key vault" (both dropped, D746/D744); release-process.md names D373/D417
  in its text; testing.md has two bold phrases with * inside; security-r3.md table rows are labelled by story (R2.24, R4.7).
- **Still open:** the four labels to confirm (Relate to, Do again, What is this?, Send for review); PDFs on the site or not.

### 20:34 Pictures off the website, kept in the PDFs (D784)
- tools/build_website.py: no pictures on the pages, none copied into the site. The PDFs keep them.
- The pictures could not be copied over the file bridge fast enough (7 of 10 per call). GitHub's latest commit is 14:51,
  before the pictures were taken: waiting for the owner to push, then the AI takes docs/site/shots from GitHub.
- 20:39 changed: **pictures on both** the website and the PDFs (owner confirmed). build_website.py put back as it was.
  The owner is running `eax site shots`; then `eax site build` and `eax site pdfs`.

### 20:58 The 24 PDFs printed with pictures, on the owner's laptop: "ok they look good"
- In work/manuals (work/manuals/preview, the earlier ones without pictures, can go).
- site_shots.py: each do: step waits up to 15 s for its link (search results and drawn views arrive late).
- **Still open:** the four drawn-view pages show the Custom views list (the link "Claims application landscape" was
  not found: check which drawn views the demo model has); see-the-containers may be half drawn (26 s to load); the four
  labels to confirm (Relate to, Do again, What is this?, Send for review); the stale lines in the source docs (above).
- Next: the owner commits and pushes; update docs/handover.md at the end of the session.

### 21:00 to 21:30 The printed guides in the documentation; Release 7 closed as 7.0.0 (D785, D786)
- `eax site pdfs` now writes the PDFs to **documents/** (repo root, in git, with README.md) and then rebuilds the website.
- Website: **Printed guides** in the top bar (printed-guides/index.html), the PDFs copied into site/<version>/manuals with
  manuals.json; home page (docs/site/index.md) has a Printed guides section.
- App: Documentation › Printed guides (PDF) (#/documentation?guides=1, in the top Documentation menu and the ? menu),
  and a Printed guides card at the top of the Documentation page; reads /site/<version>/manuals/manuals.json.
- Release 7 closed: version 7.0.0, migration 0108 (+ wrapper), releases/7.0.0.md, build-phases rows, todo Later items,
  handover updated.
- **The owner runs to test:** `.\eax site pdfs` (PDFs into documents/, website rebuilt with them), then `.\eax up`
  (migration 0108, the new web image), then check: Documentation › Printed guides (PDF), and /site/ › Printed guides.
- Next: Release 7.9 (error codes), one question at a time.

### 21:40 to 22:30 Release 7.9 built: error codes and the error guide (D787)
- Owner's answers: codes **EAX-AREA-NNN**; **every** problem gets one; shown in **System Admin health and alerts, the logs,
  the API** and `eax status`.
- One list: services/api/eax/errors.json (60 codes; meaning, cause, what to do; match keys http / health / alert /
  stack). eax/errors.py reads it: for_status, for_health, for_alert, for_container, problems(); `python -m eax.errors`.
- API: guards and handlers set their own code (PART-001, MNT-001, DR-001, PDATA-001, API-101, API-102, API-500); an
  after-request step stamps every other error answer by its status, adds `to_do`, the header X-EAX-Error-Code, and one
  log line with `error_code`.
- Health and Alerts pages show the code and what to do; apiFetch puts the code after the message.
- `eax status` lists the problems (eaxcli/problems.py); `eax status problems` only them; eax.ps1/eax.sh call eaxpy.
- Error guide: tools/error_guide.py -> docs/site/guides/error-codes.md; built with the site; chapter in printed guide 21.
- Test: tests/test_r7_9_error_codes.py (11 tests; 9 run here, the API one and the alerts one need the image).
- **The owner runs to test:** `.\eax up` (new api and web images), `.\eax status`, `.\eax test`,
  `.\eax site build`, `.\eax site pdfs`.

### 23:13 Release 10 added: scenario planning and game theory (D788)
- Owner: "add a new release on scenario planning and game theory". Placed as **Release 10**, after the videos (Release 9).
- Builds on phase 27.1 (scenario models, what-ifs, assessments through MCP; D364, D490 to D495). Stories in
  build-phases.md: R10 (epic), R10.1 the futures (driving forces, critical uncertainties, scenarios, signposts), R10.2
  game theory (players, options, payoffs; best replies, dominant options, stable outcomes; games in turn), R10.3 options
  tested across futures and players (robust, least regret; recorded with the scenario assessment), R10.4 sample, help,
  guide.
- To discuss before building, one question at a time: screens or MCP only (D364 said no scenario screens); where they
  are kept; which methods; how numbers are given; the release number. Not built until the owner says.

### 23:25 to 23:50 Release 7.9: help, website, printed guides, eax errors and Jenkins (D789)
- `eax errors [<code-or-words>...]` (eaxcli/problems.py find, errors_main; main.py, eax.ps1 and eax.sh hand it to eaxpy; help.txt).
- Jenkins: eax-admin › Status and error codes: status, problems, error-code (CODE field) (eaxcli/jenkins.py ADMIN_TASKS;
  the admin status task moved there from Start and stop).
- On-screen help: Health and Alerts entries in services/web/src/help/catalogue.json.
- Website: How do I pages find-what-an-error-code-means and see-every-problem-from-the-machine; the Error codes guide now
  has the usual shape (Why do this, goal, TOGAF, Each task, one page; the codes under The codes); Check the health and
  alerts links them. docs/command-line-and-console.md has eax errors; the Jenkins printed-guide page has the folder.
- Printed guide 21: the two pages and `help:commands=status,errors,logs,diag`.
- Tests: tests/test_r7_9_error_codes.py now 16 (14 run here; the API answer and the alert keys need the image).
- **The owner runs:** `.\eax up`, `.\eax test`, `.\eax site build`, `.\eax site shots --missing` (the two new pages),
  `.\eax site pdfs`, `.\eax jenkins pipelines` (the new Jenkins folder), then `.\eax errors EAX-AUTH-001`.

### 23:45 The error code guide as printed guide 25 (D790)
- The owner saw 24 PDFs in documents/ and no error code guide. Added guide 25, Error code guide (manuals.json), made from
  the two How do I pages, `eax status`/`eax errors` help, the Jenkins section and the Error codes page. The covers say
  "Guide N of 25" from the list (tools/build_manuals.py), the README, website and app say the count from the list.
- The owner runs: `.\eax site pdfs` (makes all 25 into documents/ and the website), then `.\eax up`.

### 23:56 to 00:05 Guide 25 printed; Release 7.9 closed as 7.9.0 (D791)
- The owner ran `eax site pdfs`: 25 PDFs in documents/ (guide 25, 17 pages, every code; guide 21 with the codes).
- Owner, 00:01: "ok lets release 7.9". Version 7.9.0, migration 0109 (+ wrapper), releases/7.9.0.md, build-phases
  (Release 7.9 row; R7.9, E1, E2 accepted), D791, handover.
- The owner runs: `.\eax up` (migration 0109), `.\eax site pdfs` (covers say 7.9.0), `.\eax up` again, then git.
- Next: Release 8, one question at a time.

### 00:06 to 00:30 Release 8 begun: the SonarQube scanner (D792)
- Owner: "build Release 8"; answers: newest SonarQube + Sonar way; fixes all at once; every fix tested before and after
  (run tests, scan, fix, test, nothing broken).
- Built: `eax test sonar [--keep|--reset]` in every form (eaxcli/sonar.py, main.py, eax.ps1, eax.sh, help.txt,
  commands.py), eax/testing/sonar.py (prepare, report), sonarqube and sonar-scanner in the test profile,
  sonar-project.properties, sonar_accepted.json, ContainerConsole purposes, eax status ignores them.
- Tests: tests/test_r8_sonar.py (10, all pass here with a stand-in SonarQube).
- The owner runs: `.\eax dev check`, `.\eax test full` (baseline), `.\eax test sonar`; then the AI fixes from
  work/tests/sonar-<time>/issues.json.

### 05:45 Non-essential containers kept down (D793)
- Owner: sonar and other non-essential containers must not come up in regular operation. Found: testrunner-service
  (platform profile) running on the laptop (started 13 h before; its restart policy brings it back with Docker), and
  an exited testrunner. Now eax up (end of start-later) and eax down remove sonarqube, sonar-scanner, k6,
  testrunner-service, and testrunner unless a test is running; all three forms. Test: test_r8_no_extras_running.py.

### 06:40 Clean restart instead of a backup; dev check in the test runner (D794)
- Owner: a clean restart (no backup). eax test sonar now starts SonarQube afresh by itself when its admin password's
  copy went with work/ (exit 3 from prepare, then reset and retry).
- eax dev check on the laptop: no ruff, no pytest in eax's Python. Now lint and tests run in the test runner with the
  repository mounted when they are missing here (eaxcli/dev_cli.py; test_r8_dev_check_in_runner.py).

### 07:09 to 08:40 The baseline (dev check) and its repair (D795)
- dev check now runs in the test runner (D794), collects every test file and saves work/tests/dev-check-<time>.log.
- Baseline 07:54: 25 failed, 1 file not loading, 6 lint; 2,133 passed. Owner: fix them all first (08:01).
- Fixed (see D795): scan volumes, estate, command-text tests, docstrings, capabilities 7.9.0, lint; old viewpoint files
  removed (owner runs git rm); eax.sh CR; CI security job and nightly performance; issue/PR templates; python-docx
  (a real fault: the Word report); setup check without Docker; two tests isolated; test bench workbooks by value.
- Checked here on a clone of the repository with the changes: ruff clean; every test that can run without the
  database packages passes, but for the two website tests that need eax site build.

### 08:31 Story R9.3: MCP reads all the documentation (D796)
- Owner: "Add a story for MCP to have access to all the docs". Added as R9.3 (Release 9, learning): list, search and
  read every document through MCP, read only; NOT FOR AI USE never served. To discuss before building.
- 08:59 owner: documents and PDFs to everyone (D797); R9.3 updated. Next question: how the documents reach the API.
- 08:59 owner: "Release 9 is fine" for R9.3.
