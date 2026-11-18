# The guides

Each guide is guided three ways: System Admin > Setup, `eax setup <guide>` and a Jenkins pipeline (R6.6, D750).
Windows: `.\eax`. macOS and Linux: `./eax.sh`.

| Guide | What it is for |
|---|---|
| [A laptop](laptop.md) | EA Explorer on your own computer, to try it or to work alone |
| [A server](server.md) | EA Explorer for a team, on a Linux server with Docker |
| [Any server over SSH](remote.md) | EA Explorer put on another machine from this one (no cloud-specific code, D746) |
| [A new machine](new-machine.md) | A machine made ready for EA Explorer: Docker, disk, folders, network |
| [Backups](backups.md) | What is backed up, when, where to keep it, and checking it works |
| [Restores](restores.md) | A model, a project, a part or everything put back |
| [A catastrophic failure](catastrophe.md) | The machine or its data is lost: what to do first, who to tell, what to check |
| [Building an environment from a backup](rebuild.md) | A new machine made from a backup or a DR pack, nothing lost |
| [A DR site](dr-site.md) | A second site kept up to date, ready to take over |
| [Switching to DR and back](switch-to-dr.md) | The DR site takes over; later the primary comes back |
| [Sync and DR pairings](pairings.md) | Content sync or DR sync between two sites |
| [Upgrades and rollbacks](upgrades.md) | A new release put in, and taken back out if needed |
| [Moving to a new machine](move.md) | A laptop to a server, or one server to another, nothing lost |
| [Security hardening](security.md) | A checklist for a security review |
| [A forgotten password or certificate](forgotten.md) | Getting back in |
| [Your own database server](external-db.md) | EA Explorer on a PostgreSQL server your DBA manages (R6.6.2) |
| [Real certificates](certificates.md) | The front door's certificate: your organisation's, uploaded |
| [Jenkins](jenkins.md) | A pipeline per eax command and DR tool, a click away (R6.6-J1) |
| [Database checks](db-checks.md) | Integrity and recent records, weekly and after restores (R6.6.1) |
