---
title: Acknowledge an alert
summary: Say you have seen it, so it stops repeating.
group: Running it
roles: system-admin
screen: #/admin/alerts
---

## Why do this

Alerts tell the System Admins that a check failed: a service down, a disk filling, backups late. Acknowledging says a person has seen it, so it stops repeating and nobody else starts on the same problem. The check keeps running, so the alert closes by itself when the cause is fixed. See [[running-the-installation]].

The installation is built to look after itself as far as it can, and to ask before anything risky. These tasks are the decisions it leaves to you: what to run, when, and how far to trust a change.

**In TOGAF terms:** Outside the method: this keeps the tool that holds the Architecture Repository running. See [[ea-explorer-and-togaf]].

**The goal:** The alert stops repeating, and others see someone is on it.

> **Before you start** You need the Super Admin or IT Admin role.

## Steps

1. Open **System Admin › Running › Alerts**.
2. Open the alert; **Acknowledge**, with a note if you like.
