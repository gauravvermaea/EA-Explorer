---
title: Data in and out: integration
summary: The ways data reaches EA Explorer from other systems and leaves it for them, and why everything is reviewed first.
group: Bringing data in
roles: developer, model-admin, user
---

## Why integrate

Much of what the architecture needs is already known elsewhere: the application list in a service management tool,
the servers in a configuration database, the teams in HR. Typing it in again is slow and goes stale. Integration
brings it in on a schedule, and sends the architecture back out to the tools people already use for reporting.

## Ways in

- **Excel**: download a sheet with the model's own columns and drop-downs, fill it, load it ([[load-data-from-excel]]).
- **Deliveries**: another system drops a file in a folder; it waits as a delivery for a person to review
  ([[send-data-with-a-delivery]], [[set-up-a-delivery-source]]).
- **Python or the API**: a script pushes the data ([[push-data-with-python]], [[call-the-rest-api]]).
- **OData feeds**: EA Explorer reads a feed your organisation already has ([[read-an-odata-feed-from-another-system]]).
- **AI discovery**: your AI assistant reads documents and proposes what it finds ([[discover-the-enterprise-with-ai]]).

Whatever the way, what arrives is **reviewed before it counts**: new, changed and problem rows are shown, and a
Committer accepts or declines. That review is what keeps automated data from quietly corrupting the model.

## Ways out

Excel and CSV files, a whole-model package, OData for Power BI and Excel, the REST API and webhooks
([[take-data-out-with-the-guide]], [[receive-webhooks]]).

## Read next

- [[data-quality]]
- [[get-a-token-or-api-key]]
