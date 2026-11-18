---
title: Send data with a delivery
summary: Your system writes the published Excel or CSV format; EA Explorer previews it for a Committer to accept.
group: Bringing data in
roles: developer
---

## Why do this

Deliveries are how other systems feed EA Explorer without direct access: a file in an agreed shape, reviewed before it counts. See [[bringing-data-in-and-out]].

Every route in ends the same way: what arrives is shown as new, changed, kept and problem rows, and a person decides. That review is what lets you automate feeds without losing control of the model.

**In TOGAF terms:** Supports the content of phases B, C and D (baseline architectures), keeping the Architecture Landscape current from the systems that already know it. See [[ea-explorer-and-togaf]].

**The goal:** Another system's data reaches a model, reviewed.

> **Before you start** The model's Model Admin has set up a delivery source for your system.

## The ways to do it

1. Get the empty template: the model's **Import and export**, choose the types, tick **Empty template**, Excel or CSV
   set. It has exactly the columns and drop-down values the model accepts.
2. Write your data in it. Rows are matched by **type and name**: an existing entity of that type and name is updated,
   otherwise a new one is made. A delivery never deletes.
3. Deliver it, one of three ways:
   - **A folder**: drop the files in the source's `incoming` folder, then **Take dropped files** (or `eax import <source>`).
   - **The API**, as the source's service account:

```
curl -H "Authorization: Bearer <token>" -F file=@cmdb.zip https://<your EA Explorer address>/api/v1/import-sources/<source id>/deliveries
```

   - **An upload** on the Deliveries tab.
4. It waits for review: a Committer accepts or declines it.

## Each task, one page

1. [Download an empty template](../how-do-i/download-an-empty-template.md)
2. [Fill in a delivery template](../how-do-i/fill-in-a-delivery-template.md)
3. [Drop a file in the import folder](../how-do-i/drop-a-file-in-the-import-folder.md)
4. [Set up a delivery source](../how-do-i/set-up-a-delivery-source.md)
5. [Accept a delivery](../how-do-i/accept-a-delivery.md)
6. [Decline a delivery](../how-do-i/decline-a-delivery.md)

## Related

- [Set up a delivery source](../how-do-i/set-up-a-delivery-source.md)
- [Push data with Python](../how-do-i/push-data-with-python.md)
