---
title: Find what an error code means
summary: Look up a code such as EAX-AUTH-001: what it means, its usual cause and what to do.
group: Running it
roles: system-admin
screen: #/admin/health
---

## Why do this

Every problem EA Explorer finds has a code of the form `EAX-AREA-NNN`. The code is the quickest way from "something is wrong" to "this is what to do": it is the same in the screens, the API, the logs, health, alerts and `eax status`, and it never changes its meaning. See [[running-the-installation]].

The installation is built to look after itself as far as it can, and to ask before anything risky. These tasks are the decisions it leaves to you: what to run, when, and how far to trust a change.

**In TOGAF terms:** Outside the method: this keeps the tool that holds the Architecture Repository running. See [[ea-explorer-and-togaf]].

**The goal:** You know what the problem is and what to do next.

> **Before you start** Anyone can look a code up; putting it right usually needs the Super Admin or IT Admin role.

## Steps

1. Find the code: at the end of an error message in brackets, in **System Admin › Running › Health** or **› Alerts**, or in `eax status`.
2. Look it up in the **Error codes** guide (Documentation › Website › Guides), or on the machine run `eax errors <code>`, for example `eax errors EAX-AUTH-001`.
3. Do what it says, in order. If the problem stays, run `eax diag` and send its report with the code.
