---
title: Build your own reports on the feeds
summary: Dashboards in your organisation's own tools, on the live model: the approach, joining tables, refreshing.
group: Reading and reporting
roles: developer, user, executive
---

## Why your own reports

EA Explorer has 30 standard reports and a report designer. Your organisation may still want the architecture in the
tools it already uses, beside finance, risk or service data: a board pack in Power BI, a capability heat map in Excel,
a portfolio view in your data warehouse.

## The approach

1. Read the model's OData feed in your tool ([[odata-feeds]]).
2. Load the entity tables you need and the relationships table; join by the entity ids.
3. Build measures on attributes (cost, lifecycle dates, maturity) and filter by type, tag or level.
4. Set the refresh with a service account's key, so it does not depend on one person.
5. Publish in your tool as usual; EA Explorer's roles still decide what the feed shows.

## Ideas that work well

- Applications by lifecycle status and end-of-support date, coloured by risk.
- Capabilities with the cost of the applications that serve them.
- Projects from the governance feed: decisions waiting, dispensations expiring.
- KPIs over time, from the KPI history.

## Read next

- [[views-and-reports]]
