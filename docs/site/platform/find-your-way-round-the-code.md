---
title: Find your way round the code
summary: Where each kind of change goes: API reads and writes, permissions, MCP tools, screens, help, the command line.
group: The code
roles: platform-developer
---

## The API (`services/api/eax`)

Flask with flask-smorest; gunicorn serves it, Procrastinate runs background jobs, uvicorn serves MCP. The main files:

| File | What it is for |
| --- | --- |
| `app.py` | The app: blueprints, request ids, logging |
| `config.py` | Settings from the environment; secrets read from `/run/secrets` |
| `auth.py`, `permissions.py` | Sign-in tokens and the one permission check, shared by REST and MCP |
| `repository.py` | All reads of models and content: one function per question |
| `metamodel_edit.py` and similar | Writes, each in one transaction, audited |
| `api/` | REST blueprints with marshmallow schemas (they appear at `/api/docs`) |
| `mcp_server.py` | MCP tools: thin wrappers over the same functions |
| `jobs.py` | Background jobs |
| `migrations/` | Alembic versions; big SQL in `migrations/sql` |
| `testing/` | The self-test |

## The screens (`services/web/src`)

React 18 and Vite, no router library: the hash is the route (`#/metamodel/<model>/<tab>`), parsed in `App.jsx`.
`auth.js` signs in with keycloak-js; `apiFetch` adds the token. `menu.js` is the menu; `help/catalogue.json` is the
F1 help for every page, tab, pop-up and button; one `styles.css`.

## The command line (`eaxcli`)

`main.py` dispatches every `eax` command; `help.txt` is the one source of the help (eax.ps1, eax.sh and eaxpy print
it). New commands go in all three launchers' lists.

## Read next

- [[make-a-change]]
