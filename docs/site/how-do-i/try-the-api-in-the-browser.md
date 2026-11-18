---
title: Try the API in the browser
summary: Every API call described, to try with your own sign-in.
group: Access for systems
roles: developer, platform-developer
screen: /api/docs
---

## Why do this

The API page describes every call, what it takes and what it returns, and lets you try it with your own sign-in. It is the quickest way to get an integration right. See [[bringing-data-in-and-out]].

Systems that talk to EA Explorer need identities of their own, limited to what they do, so their access can be watched and stopped without affecting people. This is part of keeping integration safe as well as useful.

**In TOGAF terms:** Outside the method: this keeps the repository connected to the systems that feed it, so the Architecture Repository stays current. See [[ea-explorer-and-togaf]].

**The goal:** You see and try every API call before writing a script.

## Steps

1. Open `https://<your EA Explorer address>/api/docs` (or, as a Super Admin, **System Admin › Self-test**, **API harness**).
2. Pick a call; fill in its values.
3. **Try it**; copy the call for your script.
