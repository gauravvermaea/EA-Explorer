---
title: EA Explorer
summary: A free, open-source enterprise architecture repository you run yourself: models, views, reports, projects and AI, in one place.
---

EA Explorer keeps your organisation's architecture in one repository: the capabilities, value streams, processes,
applications, data and technology, how they relate, and how they change over time. People draw views and run reports
from it, architecture projects follow the TOGAF ADM with it, and your own AI assistant can read, analyse and change it
with your permissions.

It is free and open source (AGPL-3.0), with no charge per user, per object or per module, and it runs where you choose:
a laptop, one server, or a machine in your cloud.

## Start with your role

Each page says what EA Explorer has for you, how it is put together, and the tasks you will do, with a How do I page
for each.

| You are | Start here |
|---|---|
| **System Admin**: you run the installation | [What EA Explorer has for System Admins](roles/system-admin.md) |
| **Model Admin**: you look after models and their metamodels | [What EA Explorer has for Model Admins](roles/model-admin.md) |
| **Project Admin**: you run architecture projects | [What EA Explorer has for Project Admins](roles/project-admin.md) |
| **A practising architect**: you find, change, draw and report on the architecture | [What EA Explorer has for practising architects](roles/user.md) |
| **An industry model maker**: you build reference models for an industry | [What EA Explorer has for industry model makers](roles/industry-modeller.md) |
| **A developer**: you bring data in and take it out | [What EA Explorer has for developers](roles/developer.md) |
| **An executive**: you sponsor and decide on architecture work | [What EA Explorer has for executives](roles/executive.md) |
| **A platform developer**: you change EA Explorer itself | [What EA Explorer has for platform developers](roles/platform-developer.md) |

## Understand the ideas

[Concepts](concepts/index.html) explain the thinking behind the work: what enterprise architecture is for, the
TOGAF ADM, metamodels and models, the kinds of project and their goals, governance, data quality, and how each part of
EA Explorer maps to the TOGAF Standard ([[ea-explorer-and-togaf]]). Every page links to the others, as in a wiki.

## Find a task

[How do I](how-do-i/index.html) lists every task, one page each, step by step. Each page prints cleanly or saves as a
PDF: press **Print or save as PDF** at the top of the page.

[Guides](guides/index.html) take a topic from start to end (making a model, restoring, merging a child model, a DR
site): how its tasks fit together, each task linked to its own How do I page.

## Printed guides

[Printed guides](printed-guides/index.html) has the same content as 24 guides to print and keep, each a PDF with a
cover, what it is for, who it is for, a table of contents and a picture of every screen: an overview of EA Explorer
and its roles; a guide for each role (System Admins, Model Admins, Project Admins, architects, industry model makers,
developers and platform developers); installing, day-to-day operations, tuning, upgrades, troubleshooting and
security; backups, disaster recovery, site pairing and emergencies; the eax command, Jenkins, AI and MCP, and
Keycloak with your own directory; and an example project from start to finish. They are also in the repository, in
the documents folder, and in EA Explorer under Documentation › Printed guides.

## For developers

[Integrate](integrate/index.html) is for developers connecting other systems: connectors, formats, deliveries, push
sources, OData in and out, reports, webhooks, the API and MCP. [Platform](platform/index.html) is for developers working
on EA Explorer itself: running it locally, debugging, testing and releasing.

## Install it

[Install and run](install/index.html) has a guide for each set-up: a laptop, a server, any server over SSH, backups,
restores, a DR site, moving machines, certificates and more. In EA Explorer the same guides are on
System Admin › Tools › Setup, where you give your own values (the server's name, where the files are) and every command
is filled in for you.

## What is in the box

- **The metamodel**: ArchiMate 4 and the TOGAF 10 content metamodel built in, or your own; edited, versioned, reviewed
  and pushed down to the models that use it.
- **Models**: entities and relationships entered in forms and grids, loaded from Excel or CSV, or delivered by other
  systems; private until committed; tagged, compared, copied, split and merged back.
- **Views and diagrams**: networks, impact, capability maps and heat maps, matrices, value stream maps, roadmaps and 49
  standard views, all drawn from the repository when you open them; your own drawn views in the built-in draw.io.
- **Reports**: 30 standard reports and dashboards, your own in the report designer, KPI trends, data quality, and an
  OData feed for Power BI and Excel.
- **Projects**: architecture projects from 14 templates on the TOGAF 10 library (13 phases, 116 steps, 171 deliverables
  and artifacts), with stakeholders, key questions, principles, sign-off and documents.
- **AI**: connect your own AI assistant through MCP; it works as you, with your permissions, and every change it
  proposes waits for your yes.
- **Running it**: one command (`eax`) for everything, backups and restores, updates, health and alerts, a DR site kept
  in step, and Jenkins pipelines for the operations.

## Videos

Short videos for each role are on the [EA Explorer YouTube channel](https://www.youtube.com/@ea-explorer-os). See
[Videos](videos.md).
