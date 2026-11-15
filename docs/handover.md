# Handover

The state of the work, for whoever picks it up next: a person or another AI with only this repository (R5.16; owner,
13 Nov 2026: "what happens if I need another ai to work on this"). **Updated at the end of every working session.**
Read [AGENTS.md](../AGENTS.md) first, run `eax dev check`, then read this.

Last updated: 15 Nov 2026, Release 5 being built.

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

Release 5 built, story by story, with its tests (D685 to D698): R5.1 the optimisation report (with the names of each
model's and project's creator and admins), R5.2 IP allow lists, R5.3 multi-factor sign-in (a setting, off), R5.4 where
the data lives, R5.6 to R5.8 logs and the web log, R5.9 alerts, R5.10 signed deployments, R5.11 the service desk, R5.12
database maintenance, R5.14 and R5.15 every module, class and function documented (and a test that keeps it so), this
handover (R5.16), R5.17 automated security testing, R5.18 performance testing with k6, R5.19 the sizing estimate, R5.20
watching the self-test's browsers live, R5.21 the version review as a scheduled task (1 Feb, May, Aug and Nov),
R5.22 the Auditor role. Recorded for Release 5.5: R5.5.1 decision records and dispensations (notified on their end date).

## In progress

- Closing Release 5: version 5.0.0, its migration, release notes, the build-phases rows, the full test run by the
  owner with the automation, then the bugs it finds (D696: nothing carried forward).

## Next

The owner tests Release 5 with the automation (`eax test full`), the bugs found are fixed (each with its test), then
the release. Then Release 6 (docs/build-phases.md).

## Open questions

None waiting on the owner for Release 5. Decisions taken while building it without asking, to confirm when testing:
D698 (the security gate lists Trivy findings with no fix released instead of failing on them).

## The laptop and GitHub

- The owner's repository: `C:\Users\gaura\Github\EA-Enterpise`, branch `main` (the work); releases on `rc` and
  `release` with tags (docs/release-process.md).
- Changes are copied to the laptop when it is linked, then the owner commits and pushes.
- Not yet on the laptop: the Release 5 work of 15 Nov 2026 (to be copied at the end of the build).

## The trial (R5.16)

To check this handover works: give a fresh assistant only this repository and a small task (for example "add a help
entry for a new button and its test"); it should read AGENTS.md and this file, run `eax dev check`, make the change
with its test, and say which rebuild it needs. Whatever it got wrong is a gap to fix in these documents.

## Where things are

[architecture.md](architecture.md) (how it is built), [functional-description.md](functional-description.md) (what it
does, and where), [decisions.md](decisions.md), [build-phases.md](build-phases.md), [todo.md](todo.md),
`releases/<version>.md`.
