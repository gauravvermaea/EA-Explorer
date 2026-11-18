---
title: Read a model in Excel
summary: The model's tables live in Excel, refreshed when you choose.
group: Taking data out
roles: user, developer
screen: #/metamodel/{m}/odata
---

## Why do this

Excel can read a model's OData feed and refresh it when you choose, so your own analysis works on current data without exporting files. See [[bringing-data-in-and-out]].

The architecture is most useful where decisions are made, which is often outside EA Explorer: in reports, spreadsheets, other systems. Data leaves in the shapes those places need, from the same trusted model.

**In TOGAF terms:** Communicating the architecture: views and data for stakeholders and other systems. See [[ea-explorer-and-togaf]].

**The goal:** The model's tables are live in Excel.

## Steps

1. Open the model, **Reports › OData**, and copy the address.
2. In Excel: **Data › Get Data › From Other Sources › OData feed**; paste the address.
3. Sign in with **Basic**: your user name and password, or your user name and a token as the password.
4. Choose the entity types (tables); **Load**.
