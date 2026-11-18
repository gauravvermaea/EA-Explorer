---
title: MCP for developers
summary: The MCP server that lets AI agents work with the repository, and how to build on it.
group: Reading and reporting
roles: developer
---

## What it is

EA Explorer runs a Model Context Protocol (MCP) server beside its API, at `/mcp`. MCP is an open protocol that lets AI
assistants and agents call tools. Each tool is a thin wrapper over the same functions the REST API uses, with the same
permission checks, so an agent can do exactly what the person or account it acts for may do.

## Using it

Any MCP client connects with the address on **AI (MCP) › Connect your AI assistant** and a token. **AI (MCP) › What it
can do** lists every tool by area. Every call is recorded in the AI activity. See [[connect-your-ai-assistant]] and
[[ai-in-ea-explorer]].

## Building on it

- An agent of your own (in your organisation's agent platform) can use the same tools as a person's assistant: give it
  a service account with only the rights it needs.
- New tools are added in the code beside their REST call (`eax/mcp_server.py`), with a tile on What it can do and a
  How do I page; a test fails if a tool area has none. See [[make-a-change]].

## Read next

- [[discover-the-enterprise-with-ai]]
