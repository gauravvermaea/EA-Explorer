# Handover

The state of the work, for whoever picks it up next: a person or another AI with only this repository (R5.16; owner,
13 Nov 2026: "what happens if I need another ai to work on this"). **Updated at the end of every working session.**
Read [AGENTS.md](../AGENTS.md) first, run `eax dev check`, then read this.

Last updated: 21 Nov 2026, 21:10. **Release 8 is accepted and closed (D839)**: SonarQube scanning, coverage
measured (57.7%, self-test only), the attack test, Jenkins, the full test's summary page; its SonarQube fixes are now
R12.17. Bugs are in Release 12 (D820), the documents in Release 13 (D821); Release 9 is next: R9.4 to R9.11 (D826 to
D834, D838). Last built: the website's Questions page and How do I under Documentation (D838); the ? menu was removed and brought back the next morning (D840); the
owner runs `.\eax site pdfs`, `.\eax site build` and a clean rebuild. The video list (R9.1) is a Sheet of 269 videos:
https://claude.ai/artifact/Q8wQGUwysndaMamrCuPVa1

**Pick up here (the owner's full test of 21 Nov 2026, 16:24 to about 20:20, after a clean restart):**
- Dev check: 2,288 passed, 3 failed, then pytest-cov INTERNALERROR (two coverage measurers; fixed, R12.7): the 3
  failures were not named and no unit coverage saved. Next: the owner runs `.\eax dev check` again (no rebuild).
- Self-test run 6 (work/tests/20261121T142504Z): 2,797 passed, 5 failed, 28 warnings, 89 skipped. Failed: 4 in reports
  (VP-25 and VP-15 not loaded in 60 s, DR-03 no chart, "every report opens" page crashed), probably memory: the
  installation peaked at 11.1 GB on an 11.6 GB Docker host with swap full (memory.md); and the security gate.
- Security gate: 182 high or critical. 21 by design or false matches accepted in writing by the owner (D835,
  security_accepted.json, until 21 May 2027, each kept to its file). The other 161 are package updates for R12.4:
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
- Built today, to take effect at the next clean restart: R12.6 (no test container left running) and the D835
  acceptances (in the api image). Then: fix the 3 unit failures and the 4 report failures (Release 12).
**The owner moves to the next release with these bugs open (21 Nov 2026, 20:34: "no more testing I will move to next
release"; D836)**, every one in Release 12 of docs/build-phases.md: R12.1 (why the morning's full test stopped, part
done), R12.2 (two slow reports, the Architect's project page), R12.3 (jobs deferred twice), R12.4 (the 161 package
updates), R12.5 (coverage to 90%), R12.8 (3 unit tests), R12.9 (4 reports), R12.10 (SonarQube after a clean restart),
R12.11 (certs switch's remembered choice), R12.12 (28 warnings), R12.13 (today's work not yet run on the owner's
installation), R12.14 (dms and reports-init shown with a problem; D837), R12.15 (the final coverage figure on screen), R12.16 (two SonarQube scans at once), R12.17 (every SonarQube issue, from Release 8; D839). Before calling anything fixed: a test that fails without it, and the owner's run that shows it.
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

- R9.3: how the documents reach the API (above); asked when Release 9 comes up.

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
