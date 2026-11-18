---
title: Backups, restores and disaster recovery
summary: What is backed up, the kinds of restore from one model to everything, and how a DR site keeps you running.
group: Backups and recovery
roles: system-admin, model-admin, project-admin
---

## Why it matters

The repository holds years of an organisation's thinking. Losing it, or a part of it, costs far more than the effort
of protecting it. A backup that has never been restored is a hope, not a backup; so EA Explorer restores its own
backups to check them.

## The layers

- **Tags and history** put back one model, or one entity, without any backup at all ([[go-back-to-a-tag]]).
- **Backups** of the databases, files and settings, on a schedule, pinned when they matter ([[set-a-backup-schedule]]).
- **Restores** from one model or project up to everything; a backup of now is always taken first
  ([[restore-a-backup]]).
- **A DR pack and a DR site**: everything needed to rebuild elsewhere, and a second site kept up to date that can take
  over ([[make-a-dr-pack]], [[set-up-a-dr-site]]).

## Read next

- [[take-and-check-a-backup]]
- [[run-a-restore-drill]]
