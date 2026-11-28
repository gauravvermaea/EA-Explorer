# Docker Compose, for advanced users

One folder for each way of running EA Explorer, each with the exact `docker compose` command. Most people use the deploy
page or `./install.sh`; these are for running and changing the stack yourself.

| Folder | For |
|---|---|
| [laptop](laptop/README.md) | One machine for one person or a demo: HTTP and HTTPS on localhost, the sample data. |
| [server](server/README.md) | A server for a team: HTTPS with your certificate, strong passwords, no sample data. |
| [server-external-db](server-external-db/README.md) | A server whose databases are on your own or a managed PostgreSQL (AWS RDS, Azure Database for PostgreSQL, DigitalOcean): the database container is not started, a small relay (socat) reaches your server. |
| [key-mode](key-mode/README.md) | The services sign in to each other with certificates (keys) instead of passwords. |
| [password-mode](password-mode/README.md) | The services sign in to each other with passwords (the default). |
| [scale](scale/README.md) | Spread over servers: a database standby, shared storage, the API or the library on other hosts. Pick the files you need from deploy/compose/scale/. |
| [jenkins](jenkins/README.md) | Jenkins beside EA Explorer, with a pipeline for every eax command (its own small stack). |
| [test-runner](test-runner/README.md) | The self-test's runner (about 1.5 GB), started for a test and removed after it. |

The compose files themselves are in the top folder (`docker-compose.yml`) and in `deploy/compose/`; they run the
published images (never built here).
