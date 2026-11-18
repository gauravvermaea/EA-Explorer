---
title: Export settings to a file
summary: The settings you tick, in one file for another site.
group: Running it
roles: system-admin
screen: #/admin/settings-transfer
---

## Why do this

Setting up a new environment the same as an existing one by hand is slow and error-prone. Exporting the settings you tick gives one file another site can import, seeing every difference before it takes them. No content, people or secrets are ever in it.

The installation is built to look after itself as far as it can, and to ask before anything risky. These tasks are the decisions it leaves to you: what to run, when, and how far to trust a change.

**In TOGAF terms:** Outside the method: this keeps the tool that holds the Architecture Repository running. See [[ea-explorer-and-togaf]].

**The goal:** This site's settings are in a file another site can import.

> **Before you start** You need the Super Admin role.

## Steps

1. Open **System Admin › Settings import and export**.
2. Tick the parts.
3. **Export**: download it, or put it on git.
