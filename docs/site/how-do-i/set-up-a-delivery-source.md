---
title: Set up a delivery source
summary: Another system sends its data to a model as deliveries, each previewed and accepted by a Committer.
group: Bringing data in
roles: model-admin, developer
---

> **Before you start** You need Model Admin on the model. For a system that sends through the API, a service account
> with a token (System Admin › Machine access).

## Steps

1. Open the model, **Import and export › Deliveries**.
2. Add a **source**: its name, its folder, whether its values win over EA Explorer's, who is told, and optionally the
   service account that sends it.
3. The system then sends deliveries in the Excel or CSV format, by a folder, the API or an upload (see the related
   page).
4. Each delivery is previewed (new, changed, kept, unchanged, problems) and waits. A Committer, Model Sub Admin or
   Model Admin **accepts** it (committed as their load, undone like any load) or **declines** it.

## Related

- [Send data with a delivery](send-data-with-a-delivery.md)
- [Push data with Python](push-data-with-python.md)
