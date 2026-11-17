# deploy/secrets

How the passwords and keys reach the containers that are not EA Explorer's own (R6-F1, D745). Every password and key
is a file of its own under `/run/secrets` in each container that needs it (Docker secrets, `docker-compose.yml`),
named as its setting, never an environment variable.

| Container | How it reads them |
|---|---|
| PostgreSQL (`db`) | its own `POSTGRES_PASSWORD_FILE`; the start-up script (`deploy/postgres/initdb`) reads the logins' files |
| Keycloak | `keycloak-start.sh`: its database and administrator passwords into its own process, then Keycloak |
| Documents (Mayan EDMS) | `mayan-start.sh`: `{{EAX_...}}` placeholders in its `MAYAN_*` settings filled, then Mayan |
| Documents' broker (Valkey) | its command reads the file itself |
| Reports (Superset) | `deploy/superset/*.sh` read them before starting |
| EA Explorer's own (api, setup, backup, library, views, the test runner, ops) | `eax/secretfiles.py` and each `entrypoint.sh` |

`docker inspect` therefore shows no password, and `tests/test_r6_secret_files.py` fails when one reaches a container
as an environment variable.
