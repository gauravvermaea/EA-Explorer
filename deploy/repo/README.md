# EA Explorer: deploy it

**EA Explorer {{VERSION}}** is an open-source enterprise architecture repository: models, projects, documents,
reports and an AI assistant (MCP), in Docker. This repository holds **only how to run it**: no source code. Everything
here is made from the code repository's release, and the images are published from there.

| | |
|---|---|
| **Run it** (you are here) | {{DEPLOY_REPO}} |
| **The deploy page**: answer a few questions, get your own script (this repository's website, [index.html](index.html)) | https://gauravvermaea.github.io/EA-Explorer-Deploy/ |
| **The code**: source, issues, contributing, the full documentation | {{CODE_REPO}} |
| **The website**: how to use it, the books, every guide | https://gauravvermaea.github.io/EA-Explorer/ |
| **The images** | GitHub's registry: `{{REGISTRY}}<image>:{{VERSION}}` ([which images, and what we changed](guides/images.md)) |

**Just trying it on this computer?** Download the basic install and run it, no questions:
[for Windows](https://gauravvermaea.github.io/EA-Explorer-Deploy/downloads/ea-explorer-basic.cmd) (double-click it) or
[for Linux or macOS](https://gauravvermaea.github.io/EA-Explorer-Deploy/downloads/ea-explorer-basic.sh) (`bash ea-explorer-basic.sh`).
It installs Docker if it is missing, starts EA Explorer at https://localhost, shows the passwords and opens your browser.

## Three ways to deploy

1. **The deploy page** (most people): it asks where (this machine, a remote server, AWS, Azure, DigitalOcean), from
   where, the operating system, mount points, the database (in the containers, or an existing or managed PostgreSQL)
   and what to switch on, then writes a script for your case. Tabs for testing, backups, DR and restoring do the same.
2. **This machine, straight away** (Linux or macOS):

   ```bash
   git clone {{DEPLOY_REPO}}.git ea-explorer && cd ea-explorer
   ./install.sh laptop          # or: ./install.sh server
   ```
   Windows (Docker Desktop, PowerShell): `.\eax.cmd init laptop`, then `.\eax.cmd images pull`, then
   `.\eax.cmd up --wait-all` ([guides/deploy.md](guides/deploy.md)).
3. **Plain Docker Compose**, for advanced users: the folders in [compose/](compose/), one for each way of running it.

## After it is up

| | |
|---|---|
| The admin passwords | `./eax.sh logins --admins` (Super Admin, Keycloak, break-glass, Jenkins); every login: `./eax.sh logins` |
| Test it | `./eax.sh test smoke` (minutes), `./eax.sh test full` (everything, with backups and DR; hours) |
| Jenkins (to run everything from a browser) | `./eax.sh jenkins up` ([guides/jenkins.md](guides/jenkins.md)) |
| Backups, DR, restores | [guides/backups-and-dr.md](guides/backups-and-dr.md) |
| Update to a newer release | `git pull`, `./eax.sh backup before-update`, `./eax.sh images pull`, `./eax.sh up --wait-all` ([guides/deploy.md](guides/deploy.md#updating-to-a-newer-release)) |
| Every command | `./eax.sh help` |
| How to use EA Explorer, the books and every guide | the website: https://gauravvermaea.github.io/EA-Explorer/ |
| eax in a container (this machine needs only Docker; a last resort) | `./eax <command>`, `./eax shell` |

**The TOGAF templates** are loaded by each organisation from its own copy: download them from
<https://publications.opengroup.org/i094>, then **Administration > Project library > Upload the TOGAF zip**
([guides/deploy.md](guides/deploy.md#the-togaf-templates-optional-once)).

## The latest release

[releases/LATEST.md](releases/LATEST.md). Every release: {{CODE_REPO}}/tree/main/releases

## Licence

AGPL-3.0, as the code. Problems and ideas: {{CODE_REPO}}/issues
