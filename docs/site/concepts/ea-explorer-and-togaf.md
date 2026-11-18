---
title: EA Explorer and the TOGAF Standard
summary: How each part of EA Explorer maps to the TOGAF Standard, so you know where any task sits in the method.
group: The practice
roles: user, executive, project-admin, model-admin, industry-modeller, system-admin, developer
---

## Why map them

The TOGAF Standard, from The Open Group, is the most widely used framework for enterprise architecture. It describes
a method (the ADM), what that method produces (the content framework), where it is kept (the Architecture Repository),
how reuse works (the Enterprise Continuum) and what an architecture practice needs to run (the architecture
capability). EA Explorer is built around those ideas, so each part of the tool has a place in the standard. Knowing
the place tells you why a task exists and when in the work it matters.

You do not need to know the standard to use EA Explorer; the [[enterprise-architecture|introduction]] and
[[the-adm]] give what you need. But if you do know it, this page is your map.

## The map

| In the TOGAF Standard | In EA Explorer |
| --- | --- |
| Architecture Development Method (ADM) | Every project's phases and steps, tailored per project ([[the-adm]]) |
| Preliminary phase: the architecture capability | Principles library, project templates, the organisation's charter, skills, maturity, the board |
| Phase A: Architecture Vision | Charter, scope, stakeholders, key questions, sponsor's approval |
| Phases B, C, D: Business, Information Systems, Technology | Models and their views: baseline and target content by domain |
| Phase E: Opportunities and Solutions | Gap analyses and work packages |
| Phase F: Migration Planning | Migration plans, transition models, the roadmap |
| Phase G: Implementation Governance | Compliance reviews, dispensations, the governance log |
| Phase H: Architecture Change Management | Change requests, new cycles, merging agreed change into the baseline |
| Requirements Management | Requirements in the models and the repository, through every phase |
| Content framework and content metamodel | Metamodels; the TOGAF content metamodel is one of the roots ([[metamodels]]) |
| Deliverables, artifacts, building blocks | Project deliverables (documents), views (artifacts), entities (building blocks) |
| Architecture Repository | The Repository & Content Framework menu ([[architecture-repository]]) |
| Enterprise Continuum: from foundation to organisation-specific | Root metamodels, library and industry models, your own models ([[industry-models]]) |
| Architecture views and viewpoints | Standard views and your own ([[views-and-reports]]) |
| Stakeholder management | Stakeholders, their map and their key questions ([[stakeholders-and-key-questions]]) |
| Architecture governance and the board | Governance log, sign-off, the architecture board ([[governance-and-sign-off]]) |
| Architecture maturity | EA capability maturity assessments |

## What sits outside the standard

Some parts of EA Explorer are about running the tool rather than the method: sign-in and roles, backups and recovery,
secrets, updates, integration and AI. Their pages say so; they serve the practice by keeping the repository safe,
current and connected. See [[running-the-installation]].
