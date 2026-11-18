# Handover

The state of the work, for whoever picks it up next: a person or another AI with only this repository (R5.16; owner,
13 Nov 2026: "what happens if I need another ai to work on this"). **Updated at the end of every working session.**
Read [AGENTS.md](../AGENTS.md) first, run `eax dev check`, then read this.

Last updated: 18 Nov 2026, 22:xx. Release 7 closed as 7.0.0 (D786). Release 7.9 (error codes and the error guide,
D782, D787) is built and waiting for the owner to test and accept. The evening's working notes: docs/session-log.md.

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

## In progress

Release 7.9, built, waiting for the owner to test (D787). One list, services/api/eax/errors.json (60 codes,
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
- To close it when the owner accepts: version 7.9.0, migration 0109 (row in core.schema_versions), releases/7.9.0.md.

## Next

Release 7.9 accepted and closed (above). Then Release 8 (SonarQube, code coverage, Jenkins tested
end to end), Release 9 (videos) and Release 10 (scenario planning and game theory, D788: the futures, the other
players, options tested across both; to discuss one question at a time, starting with screens or MCP only). Small items from Release 7 are in docs/todo.md › Later: carried out of Release 7.

## Open questions

None.

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
