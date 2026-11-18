---
title: Copy settings to another site
summary: Export the admin settings to a file, and import them on another site, with every difference shown first.
group: Running it
roles: system-admin
---

## Why do this

Setting up a test, training or DR site to match production is quicker and safer by exporting and importing settings than by hand.

The installation is built to look after itself as far as it can, and to ask before anything risky. These tasks are the decisions it leaves to you: what to run, when, and how far to trust a change.

**In TOGAF terms:** Outside the method: this keeps the tool that holds the Architecture Repository running. See [[ea-explorer-and-togaf]].

**The goal:** Two sites are set up the same way.

> **Before you start** You need the Super Admin role on both sites.

## The ways to do it

1. On the first site: **System Admin › Settings › Settings import and export**. Tick the parts (for example system
   settings, branding, alerts, schedules) and **Export to a file**, or **Put on git**.
2. On the other site, the same page: **Choose a settings file** (or From git).
3. Every difference is shown: the value here and in the file. Nothing changes yet.
4. Tick what to take, then **Take**. A safety copy of the settings there is kept first, and each change goes in the
   audit trail.

On the machine: `eax settings export <file>` and `eax settings import <file>` (it shows the differences; add `--yes`
to take them).

## Check it worked

The page says how many were taken. The safety copy is listed below.

## If something goes wrong

- **Undo** on the safety copy puts the settings back as they were.
- Passwords, keys, certificates, people and content never travel in the file.

## Each task, one page

1. [Export settings to a file](../how-do-i/export-settings.md)
2. [Import settings from a file](../how-do-i/import-settings.md)

## Related

- [Set up a DR site](../guides/set-up-a-dr-site.md)
