---
title: Read a model in Power BI or Excel
summary: The model's OData feed: every entity type as a table, read only, with your permissions.
group: Taking data out
roles: developer, user
---

## Why do this

The model's OData feed lets Power BI and Excel read it directly, so your own reports stay current without exports. See [[bringing-data-in-and-out]].

The architecture is most useful where decisions are made, which is often outside EA Explorer: in reports, spreadsheets, other systems. Data leaves in the shapes those places need, from the same trusted model.

**In TOGAF terms:** Communicating the architecture: views and data for stakeholders and other systems. See [[ea-explorer-and-togaf]].

**The goal:** Your own reports read the model live.

## The ways to do it

1. Open the model, **Reports › OData**, and copy the address
   (`https://<your EA Explorer address>/api/v1/odata/models/<model id>/`).
2. **Excel**: Data › Get Data › From Other Sources › OData feed; paste the address. **Power BI**: Get data › OData feed.
3. Sign in with **Basic**: your EA Explorer user name and password, or your user name and a token as the password (the
   way for single sign-on users).
4. Choose the entity types (tables) and load.

## Each task, one page

1. [Read a model in Excel](../how-do-i/read-a-model-in-excel.md)
2. [Read a model in Power BI](../how-do-i/read-a-model-in-power-bi.md)

## Related

- [Get a token or an API key](../how-do-i/get-a-token-or-api-key.md)
