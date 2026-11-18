---
title: Restart every service
summary: Everyone is signed out for a minute or two.
group: Running it
roles: system-admin
screen: #/admin/system
do: open "Restart the system..."
---

## Why do this

A restart clears a stuck state. Everyone is signed out for a minute or two, so it warns first and you accept before it goes ahead. See [[running-the-installation]].

The installation is built to look after itself as far as it can, and to ask before anything risky. These tasks are the decisions it leaves to you: what to run, when, and how far to trust a change.

**In TOGAF terms:** Outside the method: this keeps the tool that holds the Architecture Repository running. See [[ea-explorer-and-togaf]].

**The goal:** Every service starts again cleanly.

> **Before you start** You need the Super Admin or IT Admin role.

## Steps

1. Open **System Admin › System settings**, **Restart the system**.
2. Read the warning about the maintenance page and accept it.
3. Confirm.
