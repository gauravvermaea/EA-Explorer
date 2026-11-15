# Handover

The state of the work, for whoever picks it up next: a person or another AI with only this repository (R5.16; owner,
13 Nov 2026: "what happens if I need another ai to work on this"). **Updated at the end of every working session.**
Read [AGENTS.md](../AGENTS.md) first, run `eax dev check`, then read this.

Last updated: 15 Nov 2026, Release 5 released (5.0.0).

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

Release 5 released as 5.0.0 (owner, 15 Nov 2026, 19:31; D702): R5.1 the optimisation report, R5.2 IP allow lists,
R5.3 multi-factor sign-in, R5.4 where the data lives, R5.6 to R5.8 logs and the web log, R5.9 alerts, R5.10 signed
deployments, R5.11 and R5.27 the service desk (groups, every request to the Super Admins, who assign it), R5.12
database maintenance, R5.14 to R5.16 the code documented and this handover, R5.17 security testing, R5.18 performance
testing (only when asked for, never in the full test: R5.29), R5.19 the sizing estimate, R5.20 the live browser,
R5.21 the version review, R5.22 the Auditor role, R5.26 log files rolling at a size set on the Logs page (100 KB).
Fixed while testing: R5.23 (the Reports image's Pillow, accepted until 1 Feb 2027, D699), R5.24 (the front door's
configuration), R5.25 (MFA off still asked for a code), R5.28 (a duplicate index).

## In progress

Nothing.

## Next

Release 5.5: enterprise discovery and R5.5.1 decision records and dispensations (docs/build-phases.md), discussed
with the owner one question at a time before building. Then Release 5.6 (backup and restore), Release 6.

## Open questions

None.

## The laptop and GitHub

- The owner's repository: `C:\Users\gaura\Github\EA-Enterpise`, branch `main` (the work); releases on `rc` and
  `release` with tags (docs/release-process.md).
- Changes are copied to the laptop when it is linked, then the owner commits and pushes.
- Everything of Release 5 is on the laptop (15 Nov 2026).

## The trial (R5.16)

To check this handover works: give a fresh assistant only this repository and a small task (for example "add a help
entry for a new button and its test"); it should read AGENTS.md and this file, run `eax dev check`, make the change
with its test, and say which rebuild it needs. Whatever it got wrong is a gap to fix in these documents.

## Where things are

[architecture.md](architecture.md) (how it is built), [functional-description.md](functional-description.md) (what it
does, and where), [decisions.md](decisions.md), [build-phases.md](build-phases.md), [todo.md](todo.md),
`releases/<version>.md`.
