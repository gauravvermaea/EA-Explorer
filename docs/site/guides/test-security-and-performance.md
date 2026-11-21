---
title: Security and performance testing
summary: The security suite, the attack test, the SonarQube scan and the benchmark: what each checks, how to run it and how to read it.
group: Running it
roles: system-admin
---

## Why do this

EA Explorer holds an organisation's architecture, so it must not let anyone read or change what they should not, and it
must stay quick when many people use it. Four tests check this: the security suite, which is part of every full test;
the attack test, which tries to break EA Explorer with tools made for that; the SonarQube scan of the code; and the
benchmark, which times EA Explorer under load. Each one runs in its own test data and leaves the rest alone. See
[[running-the-installation]].

**In TOGAF terms:** Outside the method: this keeps the tool that holds the Architecture Repository safe and quick, so
the architecture in it can be trusted. See [[ea-explorer-and-togaf]].

**The goal:** You know EA Explorer refuses what it should, has no known weakness left unanswered, and is as quick as the
last release.

> **Before you start** These tests need the Super Admin or IT Admin role and the machine EA Explorer runs on. Run the
> attack test only on a laptop or a test installation: it attacks the installation it runs on.

## The four tests at a glance

| Test | Command | How long | When it runs | What fails it |
| --- | --- | --- | --- | --- |
| Security suite | `eax test security` (also part of `eax test full`) | about 10 to 20 minutes | every full test, and by itself every Sunday at 03:20 | a high or critical finding not accepted in writing |
| Attack test | `eax test attack` (also part of `eax test full` from the command line) | an hour or more | every full test from the command line, on a laptop or a test installation (`--no-attack` leaves it out), or on its own | a high or critical finding not accepted in writing |
| SonarQube scan | `eax test sonar` (also the last step of `eax test full` from the command line) | depends on the machine; longest the first time | every full test from the command line (`--no-sonar` leaves it out), or on its own | an issue not accepted in writing |
| Benchmark | `eax test performance` | about 10 to 25 minutes | when you ask for it, and nightly in CI | slower than the last release by more than 10%, errors, or a container over its memory limit |

From Jenkins, the attack test is **eax-admin › Upkeep › attack-test**, and every test is the **eax › test**
pipeline with the test chosen in **what**.

**One command for everything but the benchmark.** From the command line, `eax test full` runs, in turn: `eax dev check`
(lint, the unit tests and their coverage, the documents), the self-test with the security suite and the attack test, the
backup and restore test, and the SonarQube scan. A step runs whatever the one before found, and a list of every step
ends it. `--no-dev-check`, `--no-attack` and `--no-sonar` leave one out. From the Self-test page, Full runs the self-test
only.

**One page for anyone to check.** The full test ends with a summary page, `work/tests/full-<time>/index.html`: a card a
step, with the code coverage of our own code as a ring, each card linking to its report. It is kept in the database
too: System Admin › Tools › Self-test › **Summary** shows every full test as cards, and `eax test summary` lists them.

**Keeping only the summaries.** The detailed files (reports, logs, videos, the scanners' reports and screenshots) take
room; the summaries do not. `eax test prune all` (or `--older-than 14`, or one run, or `full-3`) deletes only those
files, as do *Keep summary only* on the Self-test page's History and *Clean up now* on System Admin › Command centre ›
Schedules, where the logs can be cleaned up too and the test files every night. `eax test delete` still deletes a run
for good, its summary too.

Every run's report is in `work/tests/<run>/report.html`, and on System Admin › Tools › Self-test › History. The Security
tab there shows the findings over time; the Performance tab shows the benchmark's times against the last release.

## The security suite

It checks the front door's security headers and cookies, that the passwords are files and not settings, how the services
sign in to the database, the Python packages for known weaknesses (pip-audit), the code (bandit), secrets committed by
mistake, and the packages' licences. Then it makes the attacks EA Explorer was reviewed against: a source pointed at
the cloud's metadata address or at EA Explorer's own containers, a setting that leaks a secret, reading another
model's or project's content, a header claiming to be someone else, an upload that is not what it says, and tokens no
one signed (unsigned, long expired, with the signature or the claims changed, or rubbish). Last, the operations helper
runs an OWASP ZAP scan of the front door, a ZAP scan of the API signed in as the run's Architect, and Trivy on every
EA Explorer image.

## The attack test

The attack test is the security suite and more: tools built to break web applications, each brought up to date before
it runs. Without a network it uses the last version pulled and says so in the report; a tool that is not there at all
is left out, with a warning.

| Tool | Black box or white box | What it does |
| --- | --- | --- |
| OWASP ZAP full scan | black box | finds every page through the front door, then tries every active rule on each (injection, cross-site scripting, path traversal and the rest), as someone not signed in |
| Schemathesis | black box | reads EA Explorer's own API description and sends thousands of malformed and edge-case requests, signed in as the run's Architect; a server error, or an answer that breaks the description, is a finding |
| Nuclei | black box | its community's templates (misconfigurations, exposed panels, known weaknesses) against the ports of every container |
| Semgrep | white box | its maintained rule sets on the source: Python, JavaScript and React, Dockerfiles, secrets and the OWASP Top Ten |
| Gitleaks | white box | every secret that ever reached git, in the whole history |

**What it may touch.** The fuzzing reads anything in the run's own test data, and writes only to the run's own test
models, project and elements. It never deletes, and never calls the admin, operations, backup, restore or download
paths. Nuclei leaves out every template that could knock a service over. Only a laptop is attacked without asking;
another installation must be marked as a test one with `EAX_ATTACK_ALLOWED=yes` in its config file, or the test refuses
to start.

**What you get.** One result for the tools' versions, one result for each tool (how many findings it had, by severity),
and the security gate's verdict across all of them. Each tool's own report stays in the run's folder:

| File | From |
| --- | --- |
| `attack-tools.json` | each tool's image and version, and whether it was the newest |
| `zap-full.json` | the ZAP full scan |
| `schemathesis/` and `schemathesis.log` | the fuzzing |
| `nuclei.jsonl` | Nuclei, one finding a line |
| `semgrep.json` | Semgrep |
| `gitleaks.json` | Gitleaks (the secrets themselves are hidden) |

## The SonarQube scan

`eax test sonar` scans the whole repository with SonarQube: bugs, vulnerabilities, security hotspots and code smells, at
every severity. The report is `work/tests/sonar-<time>/report.md`, every issue by file and line. `eax sonar open`
starts SonarQube with its own pages at http://localhost:9000 on this computer, to look at the last results without
scanning again; `eax sonar close` stops it.

## The benchmark

`eax test performance` fills the run's test model to a fixed size (`--size small`, `medium` or `large`), times every
read that matters one person at a time, then runs k6 with many people at once (`--users`, for `--minutes`). Every
container's memory and CPU is sampled while it runs. A run that passes becomes the baseline for the next release.

## When something is found

1. Open the run's report and find the finding: the tool, what it found and where.
2. Fix it, with a test that fails before the fix and passes after it. A fix must not change what people see or do.
3. If it cannot be fixed that way, or is not a real problem, it can be accepted in writing, only with the owner's
   approval: an entry in `services/api/eax/testing/security_accepted.json` (or `sonar_accepted.json` for SonarQube)
   with the finding's id, where it is, the reason, who agreed and a date after which it fails again.
4. Run the test again.

SQL built from text is accepted for good (D800), for bandit, SonarQube and Semgrep alike.

## Each task, one page

1. [Run the self-test](../how-do-i/run-the-self-test.md)
2. [Watch a self-test as it runs](../how-do-i/watch-a-self-test.md)
3. [Clear the self-test's data](../how-do-i/clear-test-data.md)
