---
title: The ADM: how architecture work is done
summary: The TOGAF Architecture Development Method in plain words: its phases, why it is a cycle, and how a project tailors it.
group: Projects
roles: user, executive, project-admin, model-admin
---

## The idea behind it

The Architecture Development Method (ADM) is the core of the TOGAF Standard: a repeatable way of getting from "this is
how we work today" to "this is how we should work", with the reasons written down and the right people agreeing at
each step. Its central idea is that change is easier to get right when you first agree why you are changing and what
is in scope, then describe the business, the information and applications, and the technology, then plan the route,
and only then build, while watching that what is built still matches what was agreed.

It is a cycle, not a line. Each pass teaches something, the world moves on, and the next pass starts from a better
picture. Requirements sit in the middle of the cycle: every phase can raise them and every phase must respect them.

## The phases

| Phase | What it is for |
| --- | --- |
| Preliminary | Set up the architecture practice: who does it, the principles, the framework as tailored for you |
| A. Architecture Vision | Agree why and what: scope, stakeholders, goals, the sponsor's backing |
| B. Business Architecture | How the business works today and should work: capabilities, value streams, processes, organisation |
| C. Information Systems | The data and the applications, today and in the target |
| D. Technology Architecture | The platforms, infrastructure and networks underneath |
| E. Opportunities and Solutions | The gaps between today and the target, grouped into work packages |
| F. Migration Planning | The order of change: transition states and a roadmap |
| G. Implementation Governance | Watching delivery so it stays true to the architecture |
| H. Change Management | Deciding when a change is big enough to start a new cycle |
| Requirements Management | Holding every requirement through every phase |

## Iterations: not every project runs every phase

A project rarely needs every phase at full depth. The ADM groups the phases into iteration cycles: **Architecture
Capability** (Preliminary and A, setting up the practice), **Architecture Development** (B to F), **Transition
Planning** (E and F) and **Architecture Governance** (G and H). In EA Explorer you choose the cycle when you start a
project ([[choose-the-adm-cycle]]), then remove the steps that do not apply, with a reason, and add your own
([[tailor-the-adm-steps]]). Tailoring is expected; it is how the method fits your organisation.

## How EA Explorer carries it

Every project in EA Explorer follows the ADM: its phases, their steps, the deliverables each produces and who signs
them off. The models hold the content (baseline and target), the project holds the work around it (charter,
stakeholders, key questions, decisions), and sign-off records who agreed what and when. See [[projects-and-deliverables]]
and [[governance-and-sign-off]].

## Read next

- [[kinds-of-projects]]
- [[follow-the-adm-phases]]
- [[start-an-architecture-project]]
