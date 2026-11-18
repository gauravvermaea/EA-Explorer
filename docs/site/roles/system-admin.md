---
title: What EA Explorer has for System Admins
summary: You run the installation: who may sign in and what they may do, security, backups, updates, health and the machine itself.
---

## Who this is for

The people who run an EA Explorer installation. In EA Explorer these are the **Super Admin** (everything, including
settings and the delete-everything commands) and the **IT Admin** (running it: health, backups, updates, containers,
logs), helped by the **User Admin** (people and their roles) and the **Auditor** (sees everything a Super Admin sees,
changes nothing).

## What you have

Everything you need is under **System Admin** in the menu bar, and on the machine in one command, `eax`.

| Area | Where | What it gives you |
|---|---|---|
| Wizards | System Admin › Wizards | The common jobs guided step by step, each asking before it changes anything |
| Settings | System Admin › Settings | Application settings (currency, time zone, date formats), system settings (upload sizes, keep-for times, the parts in use, the site's purpose), the banner, branding, licences, and **Settings import and export** |
| People | System Admin › Users and roles | Who has which role, on the installation, each model and each project; how Keycloak roles and directory groups become EA Explorer roles |
| Security | System Admin › Security | Who may reach EA Explorer (IP allow lists per place) and multi-factor sign-in |
| Running | System Admin › Running | Health, alerts, the job queue, containers, logs, hosts, mounts, databases, secrets, site pairings, database maintenance, footprint, sizing and more |
| Backups | System Admin › Backups and restores | Backups now and on a schedule, restores, and disaster recovery |
| Updates | System Admin › Updates | Moving to a newer release, with a backup first and a way back |
| Tools | System Admin › Tools | The Command centre (every `eax` command from the browser, with schedules), Setup (the guides with your values filled in), the SQL window and the self-test |
| Machine access | System Admin › Machine access | Tokens, API keys and client certificates for other systems |

On the machine, `eax` starts, stops, backs up, restores, updates, tests and repairs EA Explorer, on Windows, Linux and
macOS (`.\eax` in PowerShell, `./eax.sh` elsewhere). `eax help` lists every command. Jenkins, if you start it
(`eax jenkins up`), gives a pipeline for each command.

## How it is put together

- **Containers**: EA Explorer runs as a set of Docker containers on one machine (or several, when scaled out): the
  screens, the API and its jobs, the database (PostgreSQL), sign-in (Keycloak), reports (Apache Superset), documents
  (Mayan EDMS), the drawn views (draw.io), the operations helper, backups, and a front door that every request passes
  through. System Admin › Running › Estate draws them.
- **People and roles**: people sign in through Keycloak, from its own accounts or your directory. Their **global roles**
  (Super Admin, IT Admin, User Admin, Auditor, Model Creator, Library Admin, Discovery Admin, Architecture Board, User)
  come from Keycloak; their **model roles** (Model Admin, Model Sub Admin, Committer, Architect, History Viewer, Report
  Viewer) and **project roles** (Project Admin, Lead Architect, Architect, Stakeholder and others) are given on each
  model's and project's People tab.
- **Where the data lives**: one PostgreSQL holds the repository and its parts in schemas of their own; documents,
  reports and the drawn views keep their own databases. Each can be moved to a server of its own
  (System Admin › Running › Databases).
- **The config file**: `work/eaexplorer.env` holds the settings the containers start with. Passwords and keys are
  separate files, one per container, never shown on screen (System Admin › Running › Secrets shows each by name, its
  age and when it is due).
- **Backups**: an infrastructure backup holds every database, the files, the config and the versions; an application
  backup holds one model. Both can be tagged, pinned, checked and restored whole or in part.

## Where to go next

- The guides for installing and running it: [Install and run](../install/index.html).
- Every command: `eax help` on the machine, or ? › Command line (eax) in EA Explorer.
- The API's own pages: `/api/docs` in your installation.
