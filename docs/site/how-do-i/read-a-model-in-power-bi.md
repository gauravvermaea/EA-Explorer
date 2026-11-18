---
title: Read a model in Power BI
summary: The model's tables live in Power BI, refreshed when you choose.
group: Taking data out
roles: user, developer
screen: #/metamodel/{m}/odata
---

## Why do this

Power BI can read a model's OData feed, so your organisation's own reports and dashboards show the architecture beside other business data. See [[bringing-data-in-and-out]].

The architecture is most useful where decisions are made, which is often outside EA Explorer: in reports, spreadsheets, other systems. Data leaves in the shapes those places need, from the same trusted model.

**In TOGAF terms:** Communicating the architecture: views and data for stakeholders and other systems. See [[ea-explorer-and-togaf]].

**The goal:** The model's tables are live in Power BI.

## Steps

1. Open the model, **Reports › OData**, and copy the address.
2. In Power BI Desktop: **Get data › OData feed**; paste the address.
3. Sign in with **Basic**: your user name and password, or your user name and a token as the password.
4. Choose the entity types (tables); **Load**.
