---
title: Database changes and versions
summary: How the database changes with each release: migrations, the version, and the rules that keep upgrades safe.
group: The code
roles: platform-developer
---

## Why it is strict

Installations upgrade one release at a time from whatever they run, unattended. Every database change must apply
cleanly on top of every earlier one, keep the data, and be recorded, or an upgrade fails on someone's server.

## How

- Changes are **Alembic migrations** in `services/api/migrations/versions`, numbered in order; big SQL sits in
  `migrations/sql` beside its wrapper. A test checks every SQL migration is run and the chain is unbroken.
- **No logic in the database**: tables, columns, indexes and rows only. Triggers that stamp who and when and keep
  history are the long-standing exceptions.
- **The version**: `services/api/version.toml` holds it; a release's last migration writes it to
  `core.schema_versions`; the API warns when the two differ.
- A new migration usually needs `.\eax clean-run` on your machine to start from scratch, or `.\eax up` to upgrade.

## Read next

- [[release-it]]
