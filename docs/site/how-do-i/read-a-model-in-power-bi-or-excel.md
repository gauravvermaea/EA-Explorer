---
title: Read a model in Power BI or Excel
summary: The model's OData feed: every entity type as a table, read only, with your permissions.
group: Taking data out
roles: developer, user
---

## Steps

1. Open the model, **Reports › OData**, and copy the address
   (`https://<your EA Explorer address>/api/v1/odata/models/<model id>/`).
2. **Excel**: Data › Get Data › From Other Sources › OData feed; paste the address. **Power BI**: Get data › OData feed.
3. Sign in with **Basic**: your EA Explorer user name and password, or your user name and a token as the password (the
   way for single sign-on users).
4. Choose the entity types (tables) and load.

## Related

- [Get a token or an API key](get-a-token-or-api-key.md)
