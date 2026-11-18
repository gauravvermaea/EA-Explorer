---
title: AI in EA Explorer
summary: How your own AI assistant works with the repository, what it may do, and the safeguards around it.
group: AI
roles: user, model-admin, system-admin, developer, executive
---

## Your assistant, your rules

EA Explorer does not ship an AI of its own. Instead it lets the AI assistant you already use connect to it, through
the Model Context Protocol (MCP), and work as you: it can read what you may read and change what you may change,
nothing more ([[connect-your-ai-assistant]]). Every call it makes is recorded ([[see-your-ai-activity]]).

## What it is good for

Exploring a model in plain language, analysing impact and gaps, drafting content for review, writing a report,
planning a project, looking after the installation, and discovering the enterprise from documents. See the How do I
pages in the AI group, starting with [[explore-a-model-with-ai]].

## The safeguards

- Changes it makes are your **uncommitted changes**, reviewed before they count ([[commit-your-changes]]).
- Documents marked **NOT FOR AI USE OR AUTOMATED PROCESSING** are never read; only their titles are noted.
- System Admins can switch the AI server off, and see everyone's AI activity.

## Read next

- [[discover-the-enterprise-with-ai]]
