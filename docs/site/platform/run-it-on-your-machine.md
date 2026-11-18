---
title: Run it on your machine
summary: A full EA Explorer on your laptop with Docker: set up, start, sign in, start clean.
group: Running locally
roles: platform-developer
---

## Why a full local installation

EA Explorer is several services working together (screens, API, database, sign-in, reports, documents). Running the
real stack locally means what you test is what ships, with the demo data and test accounts to work with.

## What you need

Docker (Docker Desktop on Windows or macOS, Docker Engine on Linux), git, and enough memory (`eax estimate` says how
much for a size). Python is fetched by the `eaxpy` launcher into `work/tools` the first time; nothing else is installed
on your machine.

## The commands

| Command | What it does |
| --- | --- |
| `.\eax init laptop` (`./eax.sh init laptop`) | Makes `work/eaexplorer.env`, the config, with generated passwords |
| `.\eax up` | Builds what changed and starts everything; keeps data |
| `.\eax clean-run` | Removes everything and starts fresh; use after migration, realm or config changes |
| `.\eax status` | Every container and its state |
| `.\eax url` | The addresses and the sign-ins (the laptop's test accounts too) |
| `.\eax stop` | Stops everything; keeps data |

On a laptop the installation has a test account for each role and the demo estate, so you can try any screen as any
role. See [[follow-a-setup-guide]] for the same steps with your own values.

## Read next

- [[debug-it]]
