# Handover

The state of the work, for whoever picks it up next: a person or another AI with only this repository (R5.16; owner,
13 Nov 2026: "what happens if I need another ai to work on this"). **Updated at the end of every working session.**
Read [AGENTS.md](../AGENTS.md) first, run `eax dev check`, then read this.

Last updated: 25 Nov 2026, morning. **Release 14 is accepted and closed, 14.0.0** (D922): stabilisation; after a clean restart the dev check (2,646 passed), backup and restore, SonarQube (nothing to fix), the security gate (none failing) and the DR drill (9 minutes to recover) pass, and the self-test passes but for one known check, every report opens (R14.5.19). Releases 9 to 13 accepted earlier (13.0.0, D900; 12.0.0 closed as unstable, D897). The order now: **14.5** (coverage, journeys for every screen, then the reports made fast), **22** (upgrading a running installation, D913 to D919), **21** (deploy), **15** to **20** (documents, pictures and website, the books, the videos with the Videos page R20.1, D920).
command-line option documented (accepted), **14** stabilisation (the bugs, R14.n, were R12.n), **15** the documents, **16** every picture and the website (D873), the books **17**
(project types), **18** (the Architect's Bible, D861, D862) and **19** (scenario planning), **20** the videos. Until Release 16 no
documentation for users changes (D850). Push after each change (D853).

**Release 9, to be run by the owner in one go (22 Nov 2026: "build all these I will test eevrything in one go")**:
`.\eax clean-restart` (docker-compose.yml, the api, web and ops images changed), `.\eax jenkins up`, `.\eax test
jenkins` (R9.13), `.\eax test commands` (R9.14), `.\eax images` (R9.12), the hand checks of R9.7 in
docs/manual-tests.md, the themes (R9.5: System admin > Branding, then My look), an MCP client asking docs_search
(R9.3), and last `.\eax test full` (R9.10: the DR drill is now its last step; hours). What fails goes to Release 14.
Known before the run: R14.18 (four Jenkins pipelines that can never run, found by eax test jenkins).

**Pick up here (25 Nov 2026, Release 14.5 under way):**
- The measures are set (D926): the API (eax/api/) to 90%, the screens to 90%, both warnings under the bar; background
  jobs shown on their own; what one installation cannot test is left out and listed. The full summary page has a
  "Not covered yet" card. Baseline (run 10, 11:25): API 78.6% (80.0% with the self-test's controls out), jobs 50.4%,
  screens 49 of 215.
- Run 12 (25 Nov 2026, 13:42): API 83.3%, jobs 53.7%, screens 77.3%; its failures fixed in the testing code (D926).
  Open: the key questions tab lists none after "Key question added." (a likely product bug, to discuss once the next run
  says whether the server or the screen holds it back); the menu bar journey's "Wizards" once (a menu left open).
  The app's Summary screen and coverage pictures now show the API, the jobs and the screens (web: needs `eax up`).
- Everything built (the owner tests it in one go): the API's writes in api_writes.project_workspace
  (the project's 12 areas) and api_writes.platform_writes (models, tags, compare, backups, drafts, jobs, admin,
  alerting, SQL window, role mappings, people, the self-test's reads); the journeys in ui_flows.PROJECT_JOURNEYS (12)
  and ui_flows.AREA_JOURNEYS (6, one an area, about 115 screens). Next: the owner runs
  `.\eax test full --detailed --suite api --suite ui --suite jobs`; the failures are read (testing code may be fixed;
  a bug in the product is discussed first); then the figures against the bars, from the "Not covered yet" card.
- Batch 3 built (25 Nov 2026, after run 12; D926): api_writes.model_extras, project_extras and admin_extras (12 more
  areas); 14 more routes left out with why; the area journeys cut into parts of four screens (ui_flows.in_parts);
  an overall coverage ring (the API and the screens counted equally) over the two. Tests: test_r14_5_8, test_r14_5_9.
- The risky suite built (D927): `.\eax test full --risky` adds api_writes.risky_writes and ui_flows.RISKY_JOURNEYS;
  their routes (run.RISKY_RUNS) and the restores page count only in such a run. Never a restart, the installation
  down, the secrets or a full restore. Not yet run by the owner.
- Batch 4 built (D928): unit tests with stand-ins for every background task, every job of the job runner (the nightly and
  weekly ones too), `eax jobs` and the task functions (test_r14_5_11 to 14); the self-test starts more background tasks
  through the API and follows them (api_writes.job_starters, test_r14_5_15). Not yet run by the owner.
- Run 13 (25 Nov 2026, 16:48) stopped by the owner during the journeys (he needed the laptop). Its API part: 3 failures:
  the logs read needs a day (fixed: a kept day found first); the project's documents' zip and the merge plan from the
  child model failed in the background (both passed or failed differently in run 12; the runner now writes the task's
  own message, so the next run says why). Two more journeys for the screens no journey opened in run 12 (admin security,
  deploy plan, maturity, service-desk catalogue; a project's analysis, charter, home and other documents).
- Run 14 (25 Nov 2026, 18:30): API 83.9%, screens 83.9% (177 of 211), jobs 84.8%. The API was restarted at 16:43 by an
  out-of-memory change log export (a product bug, fixed: it streams, D929), which failed most of the 50 and the negative
  tests; the testing code's own failures fixed (D929). Next: the owner rebuilds (`.\eax up`) and runs the full test again.
- Run 15 (25 Nov 2026, 22:09): API 86.6%, screens 86.7% (183 of 211), jobs 85.2%; no restart. A package with data
  failed (KeyError 'metamodel_versions'; fixed, D930); Documents was still starting (the run now waits for it). Open
  to discuss: the key questions tab does not show a question just added.
- Run 16 (26 Nov 2026, 04:26): API 86.8%, screens 87.7% (185 of 211), jobs 85.6%; 8 failed. Key questions and principles
  passed (not a bug: Documents was starting in run 15). Fixed (D931): the package without data (dev check), and the
  testing code's load 202, upload wait, library placeholder, charter as Super Admin, the wizard's address. More cases:
  database upkeep plans, sizing reads, this run read, a service desk request, the metamodel spec, six screens only read.
  Open: the organisation tab showed no form for the Architect (passed in run 15); the next failure says what the page
  showed. Next: the owner rebuilds (`.\eax up`) and runs the full test again.
- Documents showed its administrator's password on its sign-in page (Mayan's first-start notice): the API now deletes
  the notice when it reads Documents' token, and the security suite fails if a password is on the page (D932). The owner
  may rotate that password. After the full run: create some documents from the application and test them (owner, 08:26).
- Run 17 (D933): API none failed; API 87.3%, screens 86.7%. Nine project tabs failed in one twelve-minute window when
  the API was not answering (memory: 10.3 GB of 11.6 GB, swap full); reports timed out. A failure now says how fast the
  API answered. To decide with the owner: Docker's memory, or fewer suites in one run.
- D934: the coverage target is 85% (API, screens, overall); no more coverage work: fix bugs, then the release is accepted.
  Fixed: Keycloak test users left behind (sign-in ran out). Reports (D936): the test's browser stalled, not Reports;
  a page that never opens fails one dashboard, a fresh page every 10; the rolled-out import line is skipped, not warned.
- Run 18 (D939): fixed the DR-01 dependencies function (x.layer, migration 0124) and the logs files 500 (a file
  compressed while listed); testing code: choices waited for, script errors say their page. Open: the project page slow
  to open under the full run (12 to 25 s); "s.map is not a function" on a project tab (the next run says which).
- D940: run 18 hung on a call from the reports' browser page (now given up after 60 s); "layer" checked: only the
  internal names (core.layers, layer_id) are left, by D391; DR-01's function says domain (0124).
- D942: a stall watchdog in the runner: 15 minutes with no check or log line records "stalled at <step>" and closes the
  test browsers so the run goes on; 15 more and the run ends as an error, closed cleanly. Reaches the runner after `eax up`.
- D943: run 19 (run 18's failures again): 3 project journeys failed, the project page 35 s on "Loading..." and its
  Library tab after it. The API had two workers of one request each; now 8 threads a worker (EAX_API_THREADS). Needs
  `eax up`, then the failed checks again. Still open: "s.map is not a function" (the charter journey, not in run 19).
- D944: a repeat opens only the report dashboards it repeats (run 19 opened all of them as two people, about 90 minutes,
  to record six); a full run is unchanged.
- D945: Stop is seen at the next check (every 10 s at most), not only at the next log line; Stopped is no longer
  an Exception a suite swallows.

**Earlier (25 Nov 2026, Release 14 closed):**
- Next is Release 14.5. Start with the coverage bar, to be discussed with the owner (R14.5.1, R14.5.2); then the use cases in
  the browser (R14.5.3) and the journeys for the 180 screens no journey uses (R14.5.7 to R14.5.18, docs/release-14.5-journeys.md);
  after the coverage work, the reports (R14.5.19: the queries measured and made fast, the check made lighter; the test browser
  reached 6.6 GB and the host paged).
- Open small items: the repeat run's progress counter leaves out what a repeat adds ("26 of about 26" while two checks wait);
  the PDF test reads whole 600 KB documents (to shorten); the drill's leftovers on the owner's laptop (remove-copy, delete-backup).
- Until Release 22: never clean-restart a server (it deletes every database without asking; R22.13).

**Earlier (kept for the record):**
**Pick up here (the owner's full test of 21 Nov 2026, 16:24 to about 20:20, after a clean restart):**
- Dev check: 2,288 passed, 3 failed, then pytest-cov INTERNALERROR (two coverage measurers; fixed, R14.7): the 3
  failures were not named and no unit coverage saved. Next: the owner runs `.\eax dev check` again (no rebuild).
- Self-test run 6 (work/tests/20261121T142504Z): 2,797 passed, 5 failed, 28 warnings, 89 skipped. Failed: 4 in reports
  (VP-25 and VP-15 not loaded in 60 s, DR-03 no chart, "every report opens" page crashed), probably memory: the
  installation peaked at 11.1 GB on an 11.6 GB Docker host with swap full (memory.md); and the security gate.
- Security gate: 182 high or critical. 21 by design or false matches accepted in writing by the owner (D835,
  security_accepted.json, until 21 May 2027, each kept to its file). The other 161 are package updates for R14.4:
  Superset 151 (124 in linux-libc-dev, the kernel headers, to remove from the image; pyasn1, urllib3, jaraco.context),
  web 7 (nginx 1.30.7, libxml2), ops 2 (Go libraries in the Docker CLI), backup 1 (libxml2).
- Attack test: all five scanners at their newest, every attack and forged token refused; ZAP full 2 medium,
  Schemathesis 317 medium (no 5xx), Nuclei 9 low, Semgrep 113 high and 86 medium, Gitleaks 7 high.
- Backup and restore: passed in 40.1 min (restore 6.3 min).
- SonarQube did not finish: the clean restart lost work/tests/sonar/admin, the test reset SonarQube and the log stops
  while preparing it; so no summary page either (it is written at the very end). Next: `.\eax test sonar`.
- Code coverage: 57.7% of 56,584 lines from the self-test alone (api 75.7%, seed 72.8%, core 52.2%), not joined with
  the unit tests; coverage.json keeps the lines run file by file, so it can be joined with the next dev check's
  unit-coverage.json without another full test. Biggest gaps: projects.py, model_ops.py, pairing.py, quality.py,
  project_backup.py, project_work.py, metamodel_edit.py.
- Built today, to take effect at the next clean restart: R14.6 (no test container left running) and the D835
  acceptances (in the api image). Then: fix the 3 unit failures and the 4 report failures (Release 14).
**The owner moves to the next release with these bugs open (21 Nov 2026, 20:34: "no more testing I will move to next
release"; D836)**, every one in Release 12 of docs/build-phases.md: R12.1 (why the morning's full test stopped, part
done), R14.2 (two slow reports, the Architect's project page), R14.3 (jobs deferred twice), R14.4 (the 161 package
updates), R14.5 (coverage to 90%), R14.8 (3 unit tests), R14.9 (4 reports), R14.10 (SonarQube after a clean restart),
R14.11 (certs switch's remembered choice), R14.12 (28 warnings), R14.13 (today's work not yet run on the owner's
installation), R14.14 (dms and reports-init shown with a problem; D837), R14.15 (the final coverage figure on screen), R14.16 (two SonarQube scans at once), R14.17 (every SonarQube issue, from Release 8; D839). Before calling anything fixed: a test that fails without it, and the owner's run that shows it.
Working notes: docs/session-log.md.

## How the owner works

The working rules, written once (AGENTS.md has them in full):

- **Write code only.** The owner runs Docker, installs software and runs git; never install or run things for him.
  Commit or push only when he asks; give him the git commands.
- **Discuss before building, one question at a time.** Build only what was asked; bugs before features.
- **A test for every fix** (D599): it fails without the fix and passes with it.
- **Say which rebuild a change needs** (`eax up`, or a clean rebuild for new migrations, realm or config changes).
- **`eax.ps1`, `eax.sh`, `eaxcli/` and `eaxcli/help.txt` in step** (D331); `eax.ps1` and `help.txt` ASCII only;
  help summaries at most 102 characters.
- **Never name another EA platform or vendor** (D114); keep "Meridian"; no copyrighted text; documents marked
  "NOT FOR AI USE OR AUTOMATED PROCESSING" are not read.
- **No logic in the database** (D248): tables and rows in migrations only.
- **Definition of done** (D550): tests, current documents (decisions, capabilities, help, release notes), no file over
  50 MB.
- **The key vault (OpenBao) stays switched off** until the owner gives its details.

## What was just done

Release 6 closed as 6.7.0 (D774). Release 7, the documentation, closed as 7.0.0 (D786; migration 0108; releases/7.0.0.md):
the website (tools/build_website.py, docs/site; served at /site/<version>, D776 to D779), 281 How do I pages each with the
picture of its screen (`eax site shots`, eax/testing/site_shots.py; a page's `do:` line opens a tab, a link, a card or a
dialog first, D781), and the 24 printed guides (docs/manuals/manuals.json, tools/build_manuals.py, `eax site pdfs`; the PDFs
in documents/, on the website under Printed guides and in EA Explorer under Documentation › Printed guides, D783 to D785).
Release 7.9 (error codes) was added as the next release (D782).

## Done in Release 7.9 (closed as 7.9.0, D791)

Error codes (D787). One list, services/api/eax/errors.json (60 codes,
EAX-AREA-NNN, each with meaning, cause and what to do; eax/errors.py reads it):
- **The API**: every error answer has `error_code` and `to_do` beside `message`, and the header X-EAX-Error-Code (an
  after-request step in eax/app.py; the guards and handlers that know the problem set their own code).
- **The logs**: the line about an error answer, and the server-error line, carry `error_code` (eax/logging_setup.py).
- **System Admin › Health and › Alerts**: each check not up and each open alert shows its code and what to do
  (health.check_all, alerts.overview; the alert's notification and email name the code).
- **The screens**: an error message ends with its code in brackets (auth.js apiFetch).
- **`eax status`**: after the containers and disks, every problem with its code and what to do (eaxcli/problems.py;
  inside the api container `python -m eax.errors`); `eax status problems` the problems only. eax.ps1 and eax.sh call
  eaxpy for it (D331).
- **The error guide**: tools/error_guide.py writes docs/site/guides/error-codes.md from the list (`eax site build` does
  it each time); it is a Guide on the website and the last chapter of printed guide 21 (Troubleshooting).
- **`eax errors <code>`** explains a code; **Jenkins** › eax-admin › Status and error codes gives the environment's
  status, the problems and a code's meaning (D789). On-screen help, two How do I pages, guide 21 and the Jenkins guide
  describe them.
- Test: services/api/tests/test_r7_9_error_codes.py. A new code goes in errors.json, then `python tools/error_guide.py`.

## In progress

Release 8 (D792). Built: `eax test sonar` (eaxcli/sonar.py; eax/testing/sonar.py in the test runner; sonarqube and
sonar-scanner in docker-compose.yml's test profile; sonar-project.properties; eax/testing/sonar_accepted.json;
tests/test_r8_sonar.py). Sonar and the other test containers are removed in normal running (D793). `eax dev check`
runs ruff and pytest in the test runner when they are not installed (D794); it is all green (19 Nov, 16:48), after the
baseline repair (D795) and two website-builder fixes (D798 file order, D799 the PDFs). Next: the owner runs
`eax clean-restart --wait-all`, `eax test full` (the baseline) and `eax test sonar`;
the AI reads work/tests/sonar-<time>/issues.json and fixes everything in one pass, a test before and after for each
fix; then every test and the scan again. Still to discuss before their turn: R8.1 coverage, R8.2 attacks, R8.3 Jenkins.
R9.3 (MCP reads every document and printed guide, to everyone, D796, D797) waits for one answer: how the documents
reach the API (built into its image, or read from the website the web container serves).

## Next

Release 8 (every SonarQube issue fixed, 90% coverage of our own code, automated attack testing, Jenkins tested end to end),
one question at a time before it is built; then Release 9 (videos) and Release 10 (scenario planning and game
theory, D788). Small items: docs/todo.md › Later: carried out of Release 7.

## Open questions

- None open. (R9.3's question was answered: the documents are mounted into the api container, read-only.)

## The laptop and GitHub

- The owner's repository: `C:\Users\gaura\Github\EA-Enterpise`, branch `main` (the work); releases on `rc` and
  `release` with tags (docs/release-process.md).
- Changes are copied to the laptop when it is linked, then the owner commits and pushes.
- Everything to Release 7 is on the laptop (18 Nov 2026). This session worked through the Claude app with the folder
  connected (files only, no command line): the owner runs every eax command.

## The trial (R5.16)

To check this handover works: give a fresh assistant only this repository and a small task (for example "add a help
entry for a new button and its test"); it should read AGENTS.md and this file, run `eax dev check`, make the change
with its test, and say which rebuild it needs. Whatever it got wrong is a gap to fix in these documents.

## Where things are

[architecture.md](architecture.md) (how it is built), [functional-description.md](functional-description.md) (what it
does, and where), [decisions.md](decisions.md), [build-phases.md](build-phases.md), [todo.md](todo.md),
`releases/<version>.md`.
