---
title: Silence a check during planned work
summary: Stop a check alerting for a while.
group: Running it
roles: system-admin
screen: #/admin/alerts
---

## Why do this

During maintenance some checks fail on purpose. Silencing them until a set time avoids false alarms; they come back by themselves.

The installation is built to look after itself as far as it can, and to ask before anything risky. These tasks are the decisions it leaves to you: what to run, when, and how far to trust a change.

**In TOGAF terms:** Outside the method: this keeps the tool that holds the Architecture Repository running. See [[ea-explorer-and-togaf]].

**The goal:** A check stays quiet during planned work.

> **Before you start** You need the Super Admin or IT Admin role.

## Steps

1. Open **System Admin › Running › Alerts** and the check.
2. **Silence** it until a time.
3. It starts alerting again by itself.
