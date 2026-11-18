---
title: Read an OData feed from another system
summary: EA Explorer reads a feed your organisation already has and proposes it for a model.
group: Bringing data in
roles: developer, model-admin
screen: #/metamodel/{m}/import
---

## Why do this

If a system already publishes an OData feed, EA Explorer can read it on a schedule and propose what changed as a delivery, with no file handling. See [[bringing-data-in-and-out]].

Every route in ends the same way: what arrives is shown as new, changed, kept and problem rows, and a person decides. That review is what lets you automate feeds without losing control of the model.

**In TOGAF terms:** Supports the content of phases B, C and D (baseline architectures), keeping the Architecture Landscape current from the systems that already know it. See [[ea-explorer-and-togaf]].

**The goal:** Data another system already publishes reaches the model.

> **Before you start** You need a role on the model that may change content (Architect or higher). IT may need to list the feed's host in EAX_DISCOVERY_ALLOWED_HOSTS.

## Steps

1. Open the model, **Import and export › Discovery**, add an **OData feed** source with its address.
2. **Look**: it shows the sets and fields and suggests where each goes; correct and save the mapping.
3. Run it, on demand, daily or weekly; each run proposes what changed as a delivery.
