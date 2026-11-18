---
title: Send data with a delivery
summary: Your system writes the published Excel or CSV format; EA Explorer previews it for a Committer to accept.
group: Bringing data in
roles: developer
---

> **Before you start** The model's Model Admin has set up a delivery source for your system.

## Steps

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

## Related

- [Set up a delivery source](set-up-a-delivery-source.md)
- [Push data with Python](push-data-with-python.md)
