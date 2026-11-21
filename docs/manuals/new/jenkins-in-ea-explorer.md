---
title: Opening Jenkins from EA Explorer
summary: System Admin › Tools › Jenkins opens Jenkins in a new tab.
new: restated for the printed guides from D780 and the jenkins command's help (owner, 18 Nov 2026)
---

## Where it is

**System Admin › Tools › Jenkins** opens Jenkins in a new tab, at the address `eax jenkins up` prints:
`http://<your EA Explorer address>:8088` unless `EAX_JENKINS_PORT` says otherwise.

## Signing in

Jenkins has its own account, printed by `eax jenkins up`, which works whatever state EA Explorer is in. With
`EAX_JENKINS_SIGNIN=keycloak` people sign in with EA Explorer instead (Super Admins and IT Admins); the own account is
kept for when Keycloak is down.

## Running a pipeline

Open **eax**, the command you want, **Build with parameters**. The pipelines are written from the eax command's own
help, so every command has one, and a new command gets its pipeline by itself (`eax jenkins pipelines` writes them
again after an update). Admin tasks are grouped: starting and stopping, the environment's status and error codes, getting
back in, certificates, backup and DR, settings and upkeep. A pipeline that changes everything (a restore, an update, a wipe, a DR tool) asks for the
installation's name before it runs, and no job is ever stopped without a person.

## The environment's status and error codes

The admin tasks under **Status and error codes** tell you how the environment is from Jenkins, without a command line:

- **status**: every container, the disks, then every problem with its error code (`EAX-AREA-NNN`) and what to do.
- **problems**: only the problems, each with its code and what to do.
- **error-code**: what one code means, its usual cause and what to do. Put the code in **CODE** (for example
  `EAX-AUTH-001`), an area (`BAK`) or a word (`backup`); leave it empty for every code.

The run's console output is the same as `eax status` and `eax errors` on the machine. The Error codes guide lists every
code.

## Testing from Jenkins

Under **Upkeep**, **smoke-test** runs the smoke test (every role signs in, every area answers) and **attack-test** runs
the attack test (`eax test attack`): the security suite, then tools that try to break EA Explorer, each brought up to
date first. The attack test takes an hour or more and runs only on a laptop or on an installation marked as a test one
(`EAX_ATTACK_ALLOWED=yes`); its report is in `work/tests/<run>` on the machine. Every other test is under **eax**, the
`test` pipeline, with the test chosen in **what**. After an update, `eax jenkins pipelines` writes the pipelines again,
so a new one shows.

## How it runs

Jenkins runs in its own stack beside EA Explorer. A small agent on the machine (port 8091, with its own token) runs each
command exactly as it would be typed; on Windows it runs with no window, so nobody can close a run halfway. `eax jenkins
down` stops Jenkins and the agent and keeps the jobs' history.
