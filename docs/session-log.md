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

### 09:10 Last dev check failure: search index order (D798)
- Owner's 08:59 dev check: lint ok, documents ok, one test failed: assets/search-index.js out of date.
- Cause: sorting path objects is case-blind on Windows, so README.md (Install and run) moved after backups.md
  when the laptop built the site. Fixed with listed() in tools/build_website.py; two new tests (before and after).
- Owner: eax site build, then eax dev check (should be all green).

### 16:16 Dev check after D798: one failure left, the PDFs (D799)
- Owner's 16:13 dev check: lint ok, documents ok; 2,160 passed, 1 failed: the website test listed the 25 printed
  guide PDFs as left over. The search index now matched (D798 worked).
- Cause: the builder copied the PDFs into the site but did not count them as made. Fixed; two new tests (the first
  fails on the old builder). Owner: eax site build, then eax dev check.

### 16:49 Clean baseline
- Owner's dev check 16:48: lint ok, tests ok, documents ok (work/tests/dev-check-20261119-164842.log).
- Next: eax clean-restart --wait-all, eax test full, eax test sonar; then every Sonar issue fixed in one pass.

### 18:24 Full test running; SQL built from text accepted (D800)
- Owner: the full test has failures; no need for 100% to go on, work with what there is.
- Bandit in the run: 438 findings, 287 of them B608 (SQL built from text). Owner: accept them all. Done in both
  accepted lists (bandit:B608, python:S2077) with a test; the code-scan line counts only what is not accepted.

### 19:46 Full test result (run 20261119T152923Z)
- Self-test: 2,785 passed, 87 skipped, 20 warnings, 7 failed. Backup and restore test PASSED (35.3 minutes).
- Failed: GET /sync/status for every role (a test fault: it takes the pairing key; fixed, D801); reports VP-16 and
  SR-20 not loaded in 60 s and 'every report opens' timed out; pip-audit (dulwich 0.25.2); the security gate (169
  high or critical, mostly image packages: api, library, views, web nginx, drawio, ops, superset); the metamodel
  page saw a 503 from deploys/questions (the operations helper slow or busy).
- Coverage of the API: 41.2% of lines (the report's goal says 90; R8.1 agreed 80).

### 19:49 Order agreed (D802)
- Owner: Sonar first; coverage goal 90% on the code we write (R8.1 was 80% overall).
- Next: the owner runs eax test sonar; the AI fixes every issue in one pass, each tested before and after.

### 20:02 First eax test sonar: scan ok, report refused (D803)
- SonarQube Community Build 26.11.0: the scan took 12.5 minutes and succeeded; reading the results got HTTP 400.
- Cause: the old parameter names (componentKeys, projectKey). Fixed with a test; the owner runs eax test sonar again.

### 20:19 to 23:xx The SonarQube fixes (D804)
- Scan 20:07 (work/tests/sonar-20261119-200750): 504 issues (237 bugs, 84 vulnerabilities, 183 code smells), no hotspots.
- Owner: fix with these; Group B (106, would change what users see) accepted ("yes go for it").
- Fixed 299 without changing what EA Explorer does, each class with a before-and-after test; 2,016 existing tests give the
  same results before and after. Waiting for the owner: 99 proposed as by design (listed in D804).
- Owner next: eax up --build (API and web), eax dev check, eax test sonar.

### 21:24 Sonar scan after the fixes
- 232 issues (was 504), 106 accepted, 126 open: the 99 waiting for the owner and 27 from the fixes themselves: the
  screens' test keeps the old patterns (now read as a test: sonar.tests takes services/web/tests and deploy/drawio/tests),
  sys.exit(main()) of a main that returns nothing (now main()), the clipboard helper (no promise in a try or a condition)
  and the link scan's loop counter. Fixed; the owner runs eax test sonar again (no rebuild needed for the scan).

### 21:27 SonarQube's pages (D805)
- Owner: open SonarQube without running a test. Built: eax sonar open (pages at http://localhost:9000, this computer
  only, the last scan, nothing scanned), eax sonar close, and eax test sonar --open. Sign in as admin with the password
  in work/tests/sonar/admin.

### 20 Nov 04:58 eax sonar open: the test runner was older than the command (D805)
- The runner did not know "ready" (it printed its help): eax sonar open now builds the test runner first, as eax test
  sonar does. Test updated.

### 05:09 eax sonar open said open, the browser showed nothing (D805)
- docker port printed nothing, also after close and open: SonarQube ran without its port. eax sonar open now checks the
  port Docker gave it and fails with what to do when there is none. Owner reboots, then runs the checks: docker inspect
  (its port bindings), docker compose ... config sonarqube with the open file, and the same up --force-recreate.

### 20 Nov 21:11 The runs of the night (D806)
- Full test (19 Nov 21:25 to 20 Nov 06:31): 2,780 passed, 26 warnings, 8 failed: the same kinds as before the Sonar fixes
  (reports slow, dulwich, the images' packages, the 503 from deploys/questions) plus GET /projects/{project} as architect
  (no answer); backup and restore test failed (S1: the Architect sign-in 599; S6: jobs that ran twice). Coverage 41.1%.
- Dev check 05:08: 7 failed: 5 tests reading the eax command's text, stale after D805 (fixed); test_r8_sonar ran a stale
  compiled copy (its text is right); test_screen: a real bug, the refresh with a menu open (fixed, D806).

### 21:17 Coverage up (R8.1, D807)
- The 41% was the live run only; unit tests did not count. Owner: both combined. Built: dev check measures the unit tests
  (work/tests/unit-coverage.json), the full test joins them line by line with the live run. Next: the owner's runs give
  the joined figure by file; then tests where it is lowest.
### 21 Nov 06:26 SonarQube's pages work; R8.3 closed; backup and restore (D808, D809)
- Owner: the SonarQube website bug is fixed (eax sonar open shows the pages). R8.3, Jenkins tested end to end, closed (D809).
- Backup and restore test of 20 Nov: S6's five jobs run twice all date from the night's full test, before the test began;
  S6 now reads only the test's own window. S1 keeps why a call had no answer (the Architect's 599 said nothing more).
  Test: test_r8_backup_restore_s6_window.py. The Architect's no answer (S1 and GET /projects/{project} in the full
  test) is looked at again with the reason from the next run.
### 07:00 Dev check: 2,215 passed, 1 failed; unit tests cover 42.6% (D810)
- The failure: test_r8_dev_check_in_runner expected -x last; D807 put the coverage flags after it. Test updated.
- Coverage: the job runners and the MCP server were never measured (0% for the MCP modules). They now start the
  probe as the API does. Next: the files where the joined coverage is lowest, once the unit figures by file are read.
### 09:40 Release 11 planned (D811)
- Owner: templates for Government, Agile and Digital Transformation projects, with model templates; more from the TOGAF
  Series Guides; a printed project types guide; the Architect's Bible. Written as R11 to R11.7, not built.
### 09:51 Release 11 narrowed (D812)
- Information and organization maps in A and B from the model; business scenarios in Requirements Management, with the
  project; nothing from the Leader's Guide; the Bible a new guide. Data and security proposed, waiting on the owner.
### 09:58 Release 11: data and security templates in; everything in the bases (D813)
- Risk and security architecture, and Data architecture and governance, written into R11.4. A business scenario is a
  document or points to a model item. R11.8: every new capability lives in the project base and root metamodels.
### 09:59 Release 11 from the TOGAF Standard only (D814)
- Every template item from TOGAF 10 (fundamental content and Series Guides), traced to its source; Government generic,
  no country variant; no outside control catalogue.
### 10:05 Release 11 from the Open Group documents (D815)
- Owner has The Open Group's permission. GRM into the library for the Government template (corrects D814); DPBoK's
  levers and contexts for Digital Transformation; risk and security phase by phase from G152; R11.9 links, not copies.
### 10:08 The Bible's three worked examples (D816)
- Fynbos Mutual digital transformation, Ridgeview City Council citizen services (GRM), Karoo Re risk and security; each a
  shipped sample project.
### 10:20 Release 10 AI only (D818)
- Scenario planning wizard started in words for a project or model, run by the AI; results in a read-only tab.
  Executive summary written as a Claude doc.
### 10:22 Full test of 21 Nov; Release 8.5 for bug fixes (D819)
- Backup and restore passed, 100 of 100 (D808 confirmed). The self-test stopped in the reports suite with no report.
- Owner: bugs go to a release of their own, Release 8.5 (R8.5.1 to R8.5.4); now coverage with the results there are.
  R8.2 (attack test) is half built in the working copy, not on the laptop.
### 10:26 Release 8.5 becomes Release 12, stabilisation (D820)
- Bugs, failing tests and the rest of the coverage go to Release 12, the last. Now: coverage tests here, then R8.2.
### 10:40 The attack test built (D817); Release 13 for documents (D821)
- `eax test attack`: the runner's scope and token, the helper's five tools brought up to date first, their reports
  judged by the security gate, forged tokens in the security suite, migration 0110. A laptop only.
- Guide 26 and the website guide "Security and performance testing"; docs/testing.md and the help updated.
- Release 13 after Release 12: every document checked and updated.
### 10:50 Release 12 fixes while the attack test runs; attack-test in Jenkins (D822)
- R12.1: the runner's output and the helper's lines kept on disk as they come; token files always deleted.
- R12.2: the 503 was a late answer counted against the next page; fixed in the page sweep. Slow reports and the
  Architect's project page still to do. Jenkins: eax-admin › Upkeep › attack-test.
### 13:10 The first attack run; the full test does everything but the benchmark (D823)
- Attack run: every tool ran; no fuzzing server errors; every attack refused; gate failed on 190 (168 Trivy).
- Fixed: nan-injection, the menu's PowerShell, defusedxml, dulwich 1.2.5. The rest: the rebuild, or the owner's word.
- `eax test full` (command line): dev check, self-test with attack, backup and restore, SonarQube; --no-* to leave out.
### 13:25 Code coverage as a ring (D824)
- The report and the Self-test page: a ring of our own code first, with a ring each for this run and the unit tests.
### 13:45 The full test's summary page; the summaries kept; cleaning up (D825)
- `eax test full` ends with work/tests/full-<time>/index.html, a card a step, kept in tests.full_tests (migration 0111);
  Self-test › Summary and `eax test summary` show it.
- `eax test prune` and the web delete only the detailed files; the summaries, counts and results stay.
- Command centre › Schedules › Scheduled upkeep: clean up the logs, the test files and old runs now; the test files
  every night when chosen.
### 14:20 Switching password and certificate sign-in from the screen: R9.4 (D826)
- Planned for Release 9: an API for the mode and one to switch behind the maintenance page, checked and undone on
  failure; a panel on System Admin › Secrets; `eax test auth-switch` in the full test. Not built.
### 14:25 Themes: limit the choice, people's own, download to share: R9.5 (D827)
- Planned for Release 9: an allowed list on Branding; a setting (off) for people's own themes from My profile, made in
  the designer or uploaded; Download CSS beside every theme. Not built.
### 14:28 No ? for help, the menu only: R9.6 (D828)
- Planned for Release 9: the ? menu and the pop-ups' ? go; Help and documentation (the Documentation menu) gets Help
  for this page first; F1, the panel and the tooltips stay; every test and document updated. Not built.
### 14:32 Force a person's authenticator set-up from the user list: R9.7 (D829)
- Planned for Release 9: select people on Users, Set up the authenticator again; signed out at once, emailed, audited;
  the phone part tested manually from a checklist. Not built.
### 14:45 A scenario planning guide; a version on every guide (D830)
- R10.4: a printed guide of its own, Scenario planning with your AI, and the website Guide.
- R13.1: each guide versioned (1, 2, 3, with date), raised only on a change, in the file name; old versions removed;
  the website keeps the current version's folder only. Not built.
### 15:04 The website and repository found on Google: R9.8 (D831)
- Planned for Release 9: sitemap, robots, canonical and Open Graph tags, structured data, stable addresses, the in-app
  copy noindex, the README and GitHub settings, Search Console by the owner. Not built.
### 16:37 A Releases page to download each release: R9.9 (D832)
- Planned for Release 9: the newest release with downloads, installs and checksums; every release linked to its
  GitHub release; candidates apart. Not built.
### 17:05 Stray test containers and the dev check's coverage error fixed (D833; R12.6, R12.7)
- Owner's full test 16:24: dev check 2,288 passed, 3 failed, then pytest-cov INTERNALERROR (two measurers); no unit
  coverage saved. Self-test run 6 at 2,706 results, none failed, at 16:48.
- Scanners now named, labelled, removed at their time limit and swept; eax up and down remove leftovers; the full test
  checks none is left. The probe never starts under pytest --cov.
- AGENTS.md: the website is built again whenever a PDF or guide changes.
### 20:16 The DR drill in the full test, and the full test from Jenkins: R9.10 (D834)
- Planned for Release 9: the drill last, after SonarQube; the smoke test run on the DR copy, then the DR copy
  stopped but kept and this installation started again; Full test in Jenkins' eax-admin folder. Not built.
### 20:35 The full test of 21 Nov read; 21 by-design findings accepted (D835)
- Self-test 2,797 passed, 5 failed (4 reports, probably memory: 11.1 GB of 11.6 GB, swap full; the gate); backup and
  restore passed; attack refused everything; SonarQube did not finish (its admin password lost with the clean
  restart); coverage 57.7% from the self-test alone.
- 21 findings accepted until 21 May 2027, each to its file; the 161 package updates stay for R12.4.
- docs/handover.md has the whole picture and the next steps for the next AI.
### 20:40 Testing stops; the known bugs listed in Release 12 (D836)
- R12.8 to R12.13 added (3 unit tests, 4 reports, SonarQube after a clean restart, certs switch, 28 warnings, today's
  work not yet run). The handover lists every open one.
### 20:50 Every open bug in Release 12 (D837); the How do I videos list
- The last open bug outside Release 12 (dms and reports-init on Containers, todo.md) moved as R12.14.
- A Sheet of 201 How do I videos from the printed guides (guides 04, 07, 08, 09, 10, 22), for R9.1.
### 21:00 Coverage, SonarQube, Release 8 closed (D838, D839)
- Coverage stays 57.7% (self-test only): no unit coverage was saved. Two SonarQube scans ran at once (the full test's
  and `eax test sonar`) and neither reached SonarQube (R12.16). The final joined figure on screen is R12.15.
- The Questions page and How do I under Documentation built and copied; the ? menu gone (D838, R9.11).
- The video Sheet corrected: 269 videos (was 201), 23 guides, about 347 minutes.
- Release 8 accepted and closed; its SonarQube fixes are R12.17 (D839).
### 22 Nov 2026, 07:40 The ? menu back (D840)
- Owner: "Bring back ?". The ? menu is on the top bar again, as before, with Questions added; Documentation keeps How
  do I. So the screenshots still match and need not be taken again for the menu.
### 07:40 to 07:50 Release 8 made ready to publish as 8.0.0; images every 3 months (D841)
- version.toml 8.0.0, migration 0112_release_8_0_0, releases/8.0.0.md, capabilities.md; `release.py check v8.0.0`
  consistent; the unit tests as before. The owner: certificate-mode test, then `eax site pdfs`, then tag v8.0.0.
- No fresh base images for this test; a clean restart will stop fetching them, and a check every 3 months: R9.12 (D841).
### 07:50 `eax down` failed with exit 1 (D842)
- The owner's clean restart stopped at down: Remove-Extras' docker format had double quotes, which Windows PowerShell
  5.1 drops. Fixed in eax.ps1 with a test; then the clean restart again (password mode for now).
- 07:52: the clean restart keeps fetching the newest images; the 3-monthly check is as well (D843, R9.12).
### 08:00 The website's version and build in its footer (D844)
- Footer "Version 8.0.0 · build <commit>": the build stamped when published (GitHub Pages) or from the app's heartbeat
  (inside EA Explorer); checked in a browser. Before the owner's `eax site pdfs`, so it is in the 8.0.0 website.
### 08:11 The Architect's Bible in parts (D845); the owner's shots and PDFs being checked
- R11.6: one PDF and one source file per part, each well under 25 MB, so each can go into git.
### 08:23 Pictures and PDFs checked; Release 14 for the pictures, guides and website (D846)
- 26 guides printed 08:11 to 08:15 (26 new); those opened say 8.0.0; the website lists 26 with the new footer and
  Questions. 233 of 283 pictures new; 48 project pictures skipped (from 18 Nov) and 2 API pictures blank: Release 14.
### 08:41 Certificate mode fails; Release 15 for it (D847)
- Clean restart in certificate mode: the API restarts with "could not load private key file /eax-certs/client.key";
  sign-in without roles; second tier not started. Likely the API user's group is not 10001 (Dockerfile). Not fixed:
  Release 15. Release 8 goes out in password mode, its notes say so.
- 08:46: static.yml left as it is (D848): the published site shows the version only; inside EA Explorer the build too.
### 09:10 to 09:50 Release 8 published as 8.0.0 (D849 to D851)
- Smoke test passed in password mode; committed and tagged v8.0.0; the GitHub release's text one paragraph.
- The push was very large (PDFs twice, a website folder per version, pictures): left as it is unless git cannot cope.
- No documentation for users changed until Release 14 (AGENTS.md). The self-test's hold seen in the owner's own
  browser is by design; the test's own browsers are not held (checked in run 1's output).
- 09:47: Release 9 narrowed to R9.3, R9.5, R9.7, R9.10, R9.12 (D852); R9.8, R9.9 to Release 14, R9.4 to Release 15,
  R9.6 dropped. Pushes more often: the git commands after each change (D853).
### 09:51 `eax test jenkins` and `eax test commands` (D854, R9.13, R9.14); building the rest of Release 9
- 10:00 R9.13 `eax test jenkins` and R9.14 `eax test commands` built and tested here; the Jenkins test's first run (with
  a stand-in Jenkins and the real agent code) found four pipelines that can never run: R12.18.
- 10:20 R9.12 `eax images` built: every image (our Dockerfiles' bases and the others), the one here against the one
  published (buildx imagetools, nothing downloaded), the fixable findings of the last security test; a report in
  work/images; the schedule r9images every 3 months tells the admins when something is newer. Also in eax test commands.
- 10:40 R9.7 built: the Users page's Authenticator column, ticks and "Set up the authenticator again..."; the API
  (users.manage, new: User Admins and Super Admins); Keycloak's sessions ended; the hand checks in docs/manual-tests.md.
- 11:05 R9.5 built: the themes people may pick, their own themes (designer or upload) when switched on, Download CSS;
  routes under /api/v1/branding/my-... (never /api/v1/me, the personal service's prefix).
- 11:30 R9.3 built: the AI's documentation tools (docs_list, docs_search, docs_read, docs_pdf, screen_help); the API's
  /data/docs mount now has documents/ (the PDFs) and the help catalogue (docker-compose.yml: a clean restart).
- 12:10 R9.10 built: the DR drill last in `eax test full` (`--no-dr`), into folders beside the installation, the smoke test on the DR copy, then the DR copy stopped and kept and the installation started again and signed in to (the drill's new `--smoke-after` and `--then-back`); a DR drill card on the summary page; Jenkins › eax-admin › Upkeep › full-test (D855).
- 10:47 R12.19 fixed: ticking yourself on the Users list said My profile has your authenticator (it has not); it now says another admin, or a Super Admin on System Admin › Security. R9.7 is checked with a second user (mfatest).
- 10:55 R12.20: `eax access mfa-off <user>` now also takes back the request to set up a new authenticator; `eax access mfa-off --all` switches MFA off for everyone (the setting, Keycloak, every authenticator), no rebuild needed; Jenkins eax-admin › Get back in › mfa-off-for-everyone.
- 11:12 R12.21: eax test jenkins was not hung (2 Jenkins executors, about 6 s a probe: 122 in about 13 minutes); its wait now says so and shows the count every 30 seconds.
- 11:20 R12.22: eax test jenkins waited its full 30 minutes for the 4 probes the agent refuses (R12.18), which were never written in runs.log; the agent now records a refused probe with why, and the wait stops after 3 quiet minutes.
- 11:32 The owner's `eax test jenkins` (work/tests/jenkins-20261122T092029Z): 118 passed, 4 failed (the R12.18 pipelines, now reported at once as refused), 2 skipped (footprint: a choice field with an empty list; restore-model: takes no words), in about 12 minutes with its progress shown: R12.21 and R12.22 confirmed.
- 12:05 Release 16 added (D856): System Admin's menus and tabs regrouped (44 entries today), a System Admin home, and every command-line option in help.txt with a test (about 30 missing at a first count); built after Release 12, before Release 13.
- 12:10 Release 10 discussed: seven questions answered (D857). Not built until the owner says.
- 12:15 Release 11 discussed (D858): guides to Release 14; Agile sprints; structure-only model templates; more Series Guides to propose.
- 12:20 Release 11: the other nine TOGAF Series Guides all taken in (D859): R11.10 (DBRM, Microservices, Digital Technology Adoption, the EA capability) and R11.11 (building blocks, maturity models, roles and skills, project management).
- 12:16 Each book its own release (D860): 17 the project types guide, 18 the Architect's Bible, 19 Scenario planning with your AI; before Release 14, which stays last.
- 12:22 The Architect's Bible discussed (D861): teaches TOGAF fully, by the work, all architecture roles, the AI in its own chapter, Fynbos Mutual in full.
- 12:24 The Bible: an appendix of every screen; every file of every book under 25 MB, in as many volumes as needed, with a test (D862).
- 12:26 The Bible only after every project type is built and the project types guide (Release 17) is written; the order 10, 11, 12, 16, 13, 17, 18, 19, 14 already keeps it so.
- 12:28 R14.3 added (D863): a Features page on the website listing every feature, made from one list in the code, kept complete by a test; the last story of the last release.
- 14:05 Stabilisation (Release 12) moved after Release 16 (D864): the order is 10, 11, 16, 12, 13, 17, 18, 19, 14.
- 14:08 The videos (R9.1, R9.2) moved to Release 20 at the end (D865); Release 9 closes without them.
- 14:10 Release 15 (certificate mode) placed after Release 10 (D866): the order is 10, 15, 11, 16, 12, 13, 17, 18, 19, 14, 20.
- 15:10 Release 10 built (D867): migration 0113 (proj.sp_runs, proj.sp_signpost_marks), eax/game_theory.py, eax/scenario_planning.py, the MCP wizard (eax/mcp_scenario_planning.py, 10 tools and a prompt), the read-only Scenario planning tab and Project report section, the deck, the project backup, the Protea sample (two versions), the help; and R10.5 (D868): every MCP tool tried in the full test with its own card. Unit tests for the engine, the study and the MCP tools as an AI calls them.
- 14:40 Releases renumbered into the order they are built (D869): 10 to 20 in sequence; the bugs are R14.n.
- 19:25 Release 9 accepted (D870): version 9.0.0, migration 0114, releases/9.0.0.md; tag commands given.
- 19:30 Release 10 accepted (D871): version 10.0.0, migration 0115, releases/10.0.0.md; tag commands given. Next: Release 11, certificate mode.
- 19:40 README.md brought up to date (owner: "The md file on https://github.com/gauravvermaea/EA-Explorer is not being updated, it shwos release 8. Please fix it."): the status is 10.0.0, the release table lists 6 to 10 as accepted with their notes and 11 to 20 in their new order. From now on every release's acceptance updates the README's status and table too.
- 19:42 Certificate mode's cause confirmed on the owner's machine: the API runs as uid 10001 gid 999, its key is root:10001 0640, so it cannot read it (R11). eax diag wrote an empty report (R14.23).
- 19:55 R11.1 built (D872): groupadd --gid 10001/10002/10003 in the api, library and views images; eax certs check; tests.
- 20:00 Pictures and the website moved before the books (D873): 16 pictures and website, 17 to 19 the books, 20 the videos.
- 20:05 R14.24 added (D874): eax test soak, 8 hours by default, a realistic mix, four ways to fail; in Release 14 before the documents.
- 20:08 R11.1 passed the owner's run: in certificate mode the API was ready after 57 s; eax certs check: every service can read its key; reports still starting at the time.
- 20:12 eax certs check on the owner's machine: all seven services can read their keys (reports too). R11.1 closed.
- 20:20 The smoke test in certificate mode ran nothing: the test runner's image (Dockerfile.test) had the same group fault; fixed, and the test now checks every Dockerfile.
- 20:25 The smoke test in certificate mode, second run: the runner had the API's settings but not its certificates folder; the operations helper now mounts the api's folder (read only) into it.
- 20:45 R11.3 built (D875): Switch to certificates or passwords on System Admin › Secrets; eax certs switch remembers the choice (R14.11); clean-restart and clean-run take --certificate or --password.
- 20:50 R14.25 added (D876): every container pinned by version and digest to the tested set, published with each release, upgraded only after the three-monthly check and the owner's decision.
- 21:00 R11.5 built (D877): System Admin › Secrets puts the sign-in mode's part first and marks what is not used in that mode (the service database logins in certificate mode; the certificates in password mode).
- 21:05 Release 11 accepted (D878), published as 11.0.0: version.toml, migration 0116, releases/11.0.0.md, README. Next: Release 12, discussed guide by guide.
- 21:10 Release 12 settled guide by guide, first pass (D879): Government a model only; the EA capability a new project type; all six improvements to be done; gates and roadmap periods the architect's choice. Advice owed on risk and security, data, microservices and technology adoption.
- 21:50 Release 12 building (D880, D881): the new types, the GRM, the model and project templates, the views, Agile sprints and the samples, tested; the rest listed in D881. Written to disk with the 11.0.0 publish set.
- 23 Nov 06:30 The 11.0.0 publish set and Release 12 so far written to the laptop (62 files). R14.26 built (D882): the build number is the count of commits, one more with uncommitted changes.
- 23 Nov 08:45 The owner shared the TOGAF Series Guides. Sprints brought in line with G210 (D883, migration 0118). D884: existing projects updated by script; RACI chosen at setup. D885/R12.12: an organisation adds its own guides at setup.
- 23 Nov 09:30 Duplicate review (D887): the eight new types withdrawn; existing types carry the attributes; risk register = governance log; ACMM and Business Scenario reused. D888: Release 21, deploy in a Docker container or on distributed servers.
- 23 Nov 10:00 The owner: "continue, I will test everything in one go". The DBRM in the library (R12.3/R12.10, 72 Groupings; "Objectives" is a banned word, so "Targets"). Written to the laptop (7 files).
- 23 Nov 11:30 Base improvements built (D889): the Project plan tab (RACI and gates chosen at setup, phases planned, milestones, status, the roadmap's free period), maps always live, business scenarios in RM, building blocks in E and F (attribute and VP-58), existing projects and models brought up to date by script at start. The risk register (D890). Written to the laptop (30 files).
- 23 Nov 13:00 The ready-made surveys, TOGAF roles and skill levels, the guide references, the organisation's guides as a zip with a setup step, the samples' content, the Release 12 MCP tools, QR-02 renamed (D890, D891). Found and fixed while testing: the model upgrade now also gives existing models the places Release 12 gives existing attributes (Target and Measure on Requirement and the like). Every R12 row "built, to test". Next: the owner's test in one go (docs/handover.md says how).
- 23 Nov 12:00 The owner: "can you not write tests for screens?" Yes: six browser journeys for the Release 12 screens added to the self-test (D892); they run in `eax test full` or watched from Self-test.
- 23 Nov 13:45 The owner, in certificate mode: the industry packs waited for Documents for hours. Cause: the API could not sign in to Documents' database by certificate. Fixed (D893), with the real reason now shown on the start-up status.
- 23 Nov 14:05 The owner asked for a connectivity check in the smoke and full tests and in the heartbeat: built (D894), 24 connections made as the product makes them, on the Health page too. Found while testing: tests/test_logs_kept.py::test_backup_and_clean depends on the order files come back from the disk (not changed today): for Release 14.
- 23 Nov 15:25 The owner's full test sat at 24% for over an hour: the shipped-packs test was reading every page of the 500-page pack books. The owner: check only the first page of every document. Done (D895) for the loader and `eax packs`; the check of every shipped file now takes about a second.
- 23 Nov 18:30 The API would not start after a restart: the Release 12 model upgrade made a temporary table, which eax_migrator may not. Fixed (D896). The full test crawling: the test runner reads the code through Docker's share of the C: drive (about 26,000 file look-ups to load the tests) while Documents was reading the 97 pack files (OCR); not the test code.
- 23 Nov 20:50 The owner closes Release 12 as an unstable release (12.0.0, D897) after the smoke test; everything left is in Release 14 (R14.27 to R14.33), and Release 14 is accepted only when every test passes and coverage meets its target (R14.34).
- 23 Nov 21:40 Release 13 started: System Admin regrouped into seven groups with sub-menus and sub-tabs, every sub-tab with its own address (D898, R13.1, R13.2). capabilities.md's title says 12.0.0 (missed when Release 12 closed). Next: R13.4, every command-line option in help.txt.
- 23 Nov 21:55 R13.4 built (D899): every eax option in help.txt, the DR tools' --help, and a unit test that fails when an option is read but not documented. R13.3 (a System Admin home with tiles) still to settle with the owner; suggested dropped, the multi-level tabs doing its job.
- 23 Nov 22:00 The owner accepts Release 13 and closes it: 13.0.0 (D900). R13.3 dropped. Next: Release 14, stabilisation, accepted only when every test passes and coverage meets its target (R14.34).
- 23 Nov 21:45 Release 14 talked through (D901): Release 14 every test passing, fixes only; Release 14.5 coverage over 90% for the server and the screens (use cases in the browser, faked error answers, lines, no file under 60%); then Release 21, then 15. The owner runs a full test first as the baseline.
- 23 Nov 22:28 The overnight full test was starved by Documents' OCR of the pack files (dms at 400% CPU). R14.28 not built: the owner clears the OCR queue by hand on a laptop (the command is in R14.28).
- 23 Nov 22:40 `eax packs ocr [--clear]` (D902): Documents' OCR queue shown and cleared from eax, run by hand; R14.28 now that.
- 23 Nov 23:15 Documents' OCR off unless chosen (D903, R14.37): a System setting applied at start-up and when changed, and a first-run setup step; written while the overnight full test ran, at the owner's word.
- 23 Nov 23:40 D903 widened at the owner's word: its own Documents tab (System Admin › Settings), a night window with the pages held outside it, the progress every minute on the tab and in the header for everyone.
- 24 Nov 05:40 The overnight full test (started 22:07, the Release 14 baseline): dev check 9 failed of 2,542, self-test 3,080 passed and 18 failed, SonarQube 113 to fix, DR drill passed, backup and restore passed; coverage 43.3% unit and 59.1% live, not joined.
- 24 Nov 06:30 The owner: "start 1-4", "Please fix all bugs too". Fixed, each with a test (D904, R14.38, tests/test_r14_full_test_fixes.py): the MCP import cycle, the MCP probes' types, the SQL window's CONNECT, five foreign-key indexes (0122), .\eax in messages, the journeys after Release 13, the Phases address, ticks set not toggled, the guides link, mail over SSL, deploy's stage folder, the SSH key file, SonarQube's bugs, the website rebuilt. OCR any time or in a window (D905). The rest of SonarQube's list is waiting for the owner (R14.39); VP-21 and every report opens to be run again (OCR starved the run).
- 24 Nov 06:40 The owner: "I will test in the end please fix everything in bugs you can". Videos read: the skills journey (My profile showed saved roles unticked; a token account is not in the repository's list), the navigation journeys (icons on the group tabs; Wizards under Tools). Fixed with tests (D906): R14.31, R14.18, R14.16, R14.35, R14.23, R14.27 (copy in the runner, per-file progress, the check first, coverage joined), R14.33, R14.32 in part. R14.3 explained. R14.10 and R14.14 were done before.
- 24 Nov 07:20 The owner answered what was left, one question at a time (D907): SonarQube's 30 fixed and 67 accepted in writing, its findings on the full test's summary page; R14.3 accepted; Superset 6.1.0 is the newest, its findings accepted; the backup image on PostgreSQL 17.12; the warnings fixed where they could be (the maintenance page's CSP, the views check in certificate mode); R14.32 closed (no GitHub CI work, ever); EAX-OPS-002 added.
- 24 Nov 07:30 The owner: reports' time limit 120 seconds; images pinned by tag, no digests (D908). Every question on Release 14 answered.
- 24 Nov 14:00 The full test from 13:24: most journeys failed with /api/v1/models 500. Cause: a helper split out for SonarQube took the name of another function in repository.py (D909). Renamed, with a test for names defined twice; the click matcher narrowed (icons only, a sub-menu's arrow allowed); the OCR journey's Start button. To run again.
- 24 Nov 14:27 The owner: unit tests on a real database, not mocks, to be thought through after the last release (D910, in todo.md).
- 24 Nov 15:20 The owner tried https://laptop-ea: why it fails explained (certificate, its authority, Keycloak, the realm, the API's issuer; nginx is not in the way). Release 21 story R21.3 and its plan docs/release-21-addresses.md (D911); nothing changed.
- 24 Nov 18:40 Run 6 of the full test (3,086 passed, 5 failed) and the dev check (2,609 passed, 3 failed) read; the owner: "fix the 5 issues". Fixed with tests (D912): the System admin tile, the dialog's answer in a failed step, the plan journey in a Full cycle, Chromium off /dev/shm and a crashed Reports page failing only its dashboard, the owner: update the packages, accept nothing: web takes Alpine's nginx 1.30.7 and a fresh apk upgrade (web, ops); the ops plug-ins' two have no released fix yet; the launcher pins gained diag.
- 24 Nov 19:30 The owner: "0 errors ... Fix what you can". test_logs_kept fixed (its dates); warnings fixed: the Documentation headings, Reports' import line from the whole log, Bandit's 42 (an http-only opener for every address, the temporary folder, B323 under D835). Left: the ops image's two (no Docker release has the fix), and the warnings that are not bugs (D912).
- 24 Nov 19:35 The owner: production cannot take clean restarts, it needs proper upgrade paths. Release 22 added (R22.1 to R22.10, D913): the upgrade from the release before as the tested path, with rollback; nothing built.
- 24 Nov 19:40 The owner: Release 22 after 14.5. The order: 14, 14.5, 22, 21, 15, 16, 17, 18, 19, 20.
- 24 Nov 20:10 The full test ended: backup and restore passed; the DR drill and the restart failed on my web image change (nginx modules tied to 1.30.6), now fixed; SonarQube's five fixed. To run: up, then the DR drill and the full test again.
- 24 Nov 20:00 The owner: "accept the 2 issues": the ops image's two accepted to 2026-12-31 (D912).
- 24 Nov 20:30 The screens down after the clean restart (the maintenance page): the web container stopped on /tmp/nginx.pid left by nginx -t as root; /tmp emptied after the check (D912).
- 25 Nov 06:35 The full test of 24 Nov 21:37: dev check 1 failed (test_disks), self-test 3 (docs_list, every report opens, the plan journey's gate); the two time-outs raised and test_disks fixed (D912); the gate not yet explained. Backup and restore running, all passed so far.
- 25 Nov 06:50 The plan journey's gate explained and fixed: "choose B" ticked nothing (the RACI label holds "Per deliverable"); choose takes the exact label first (D912).
- 25 Nov 06:55 The screens no journey uses (180 of 207) put in Release 14.5 as R14.5.7 to R14.5.18 (D914, docs/release-14.5-journeys.md). Backup and restore passed (331 minutes); SonarQube scanning.
- 25 Nov 07:00 The owner: an in-place upgrade from the command line, from a folder or from git. R22.11 `eax update --from` added to Release 22 (D915); nothing built. The DR drill running (backup step).
- 25 Nov 07:05 The owner: upgrade testing, at least from the version before. R22.12 added (D916).
- 25 Nov 07:10 The owner: production must never be wiped. R22.13 added (D917): found that clean-restart does not ask on a server, the Versions check advises clean-restart, and the Command Centre can schedule a nightly one.
- 25 Nov 07:15 The owner set out the upgrade test and the upgrade package: R22.12 rewritten to his steps, R22.14 (the from-to package), R22.15 (the DR backup first, where the person says), R22.16 (the release candidate's mark) (D918).
- 25 Nov 07:35 The DR drill passed (9 minutes to recover). The owner: a nightly smoke and weekly full test; R22.17 added to Release 22 (D919). He is running up then test failed to confirm the four fixes.
- 25 Nov 08:05 The owner: a Videos page with the YouTube channel's playlists, dynamic, notifications for new videos, on the website and in the app: R20.1 (D920). A LinkedIn post and a YouTube title drafted for EA Explorer's industry content.
- 25 Nov 08:35 Self-test 8 (the failed checks of run 6 again): docs_list and the project plan journey passed; every report opens failed again (a page did not open in 5 minutes; the test browser 6.6 GB, the host paged). R14.5.19 added after the coverage stories (D921).
- 25 Nov 08:50 The dev check passed (2,646, none failed). The owner closed Release 14: version 14.0.0, migration 0123, releases/14.0.0.md, the README, the handover and the capabilities (D922). Next: Release 14.5.
