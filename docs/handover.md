# Handover

The state of the work, for whoever picks it up next: a person or another AI with only this repository (R5.16; owner,
13 Nov 2026: "what happens if I need another ai to work on this"). **Updated at the end of every working session.**
Read [AGENTS.md](../AGENTS.md) first, run `eax dev check`, then read this.

Last updated: 18 Nov 2026, 21:xx, Release 7 accepted and closed as 7.0.0 (owner, 21:00: "Then lets accept this release
and we can move on"; D786). Now: no release in build. Next: Release 7.9 (error codes and the error guide, D782),
discussed with the owner one question at a time before it is built. The evening's working notes: docs/session-log.md.

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

Nothing.

## Next

Release 7.9: R7.9-E1 (error codes, one list; `eax status` gives each problem's code and what to do) and R7.9-E2 (the error
guide, made from the same list). Not built until the owner says. Then Release 8 (SonarQube, code coverage, Jenkins tested
end to end) and Release 9 (videos). Small items from Release 7 are in docs/todo.md › Later: carried out of Release 7.

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
