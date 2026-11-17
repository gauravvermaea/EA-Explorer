# EA Explorer's own estate (R2.33)

Made by `python tools/build_estate_diagrams.py` from docker-compose.yml: do not edit by hand. The pictures are
[estate/logical.drawio](estate/logical.drawio) and [estate/physical.drawio](estate/physical.drawio) (open them
in draw.io); System Admin › Estate draws them for the running installation.

## Logical: the components

| Component | What it does | Group |
|---|---|---|
| People (browser) | architects, admins and readers in a web browser | Users |
| AI assistant | a person's own language model, through MCP | Users |
| eax command | starts, stops, backs up, updates and tests the installation | Users |
| Front door (nginx) | https for everything; the only published ports | Edge |
| Screens (React) | the pages people use | Application |
| API and job runner | REST API, background jobs, the rules | Application |
| MCP server | the tools an assistant may use, with the person's own rights; running the installation (R4.22) | Application |
| Library service | reference and enterprise libraries, documentation | Application |
| Views service | drawn views and their versions | Application |
| draw.io | the diagram editor | Application |
| Keycloak | sign-in and the global roles | Platform |
| Reports (Superset) | dashboards and charts on the report views | Platform |
| Documents (Mayan) | project documents and files | Platform |
| Operations helper | backups, restores, updates, logs, the Command centre, the self-test | Operations |
| Backup service | dumps and restores every database and file set | Operations |
| Test runner | the self-test: API, browser, database, security, backups | Operations |
| Load test (k6) | the benchmark's people at once (R5.18), started by the helper | Operations |
| PostgreSQL | one database: the repository and its schemas (tests, operations, archive, personal, library_models, D630) | Data |
| Files and folders | documents, imports, exports, backups, logs, persist/ | Data |

## Logical: who calls whom

| From | To | What |
|---|---|---|
| People (browser) | Front door (nginx) | https |
| AI assistant | Front door (nginx) | MCP over https |
| eax command | Operations helper | commands |
| Front door (nginx) | Screens (React) | pages |
| Front door (nginx) | API and job runner | /api |
| Front door (nginx) | MCP server | /mcp |
| Front door (nginx) | Keycloak | /auth |
| Front door (nginx) | Reports (Superset) | /reports |
| Front door (nginx) | Documents (Mayan) | /documents |
| Front door (nginx) | draw.io | /drawio |
| Screens (React) | API and job runner | REST |
| API and job runner | PostgreSQL | SQL |
| API and job runner | Library service | REST |
| API and job runner | Views service | REST |
| API and job runner | Keycloak | tokens |
| API and job runner | Documents (Mayan) | REST |
| API and job runner | Operations helper | operations, updates |
| MCP server | PostgreSQL | SQL |
| Reports (Superset) | PostgreSQL | report views |
| Documents (Mayan) | PostgreSQL | SQL |
| Keycloak | PostgreSQL | SQL |
| Library service | PostgreSQL | SQL |
| Views service | PostgreSQL | SQL |
| Operations helper | Backup service | backups |
| Backup service | PostgreSQL | dump, restore |
| Backup service | Files and folders | archive |
| Operations helper | Test runner | runs |
| Test runner | Front door (nginx) | tests as people do |
| Operations helper | Load test (k6) | runs |
| Load test (k6) | Front door (nginx) | many people at once |
| Documents (Mayan) | Files and folders | documents |
| Front door (nginx) | Files and folders | web log (R5.6) |
| Operations helper | Files and folders | container logs |

## Physical: the containers

| Container | Image | Networks | Published | Mounted |
|---|---|---|---|---|
| setup (runs once at start) | `eaexplorer/api:dev` | none | - | eax-tls → /tls, eax-rendered → /rendered, eax-kc-import → /kc-import, ./deploy → /deploy, ./work/proxy → /eax-proxy, ./logs → /eax-logs |
| proxy | `nginx:1.30-alpine` | frontend, terminal | 443:443, 80:80, 9443:9443 | ./deploy/proxy/templates → /etc/nginx/templates, ./deploy/proxy/static → /etc/nginx/eax, ./work/proxy → /eax-proxy, ./logs/web → /var/log/eax-web, eax-tls → /etc/nginx/tls |
| web | `eaexplorer/web:dev` | frontend | - | - |
| api | `eaexplorer/api:dev` | frontend, backend | - | eax-imports → /data/imports, eax-exports → /data/exports, ./logs/web → /eax-web, ./work/backups → /data/backups, ./work → /eax-work, ./library → /data/library, ./library/templates/ea-explorer → /data/ea-explorer-templates, ./library/industry-packs → /data/industry-packs, ./work/packs → /data/packs-extra, ./docs → /data/docs/docs, ./README.md → /data/docs/README.md, ./eaxcli/help.txt → /data/docs/eaxcli/help.txt, ./releases → /data/docs/releases |
| backup | `eaexplorer/backup:dev` | backend | - | ./work/backups → /backups, eax-docs → /mayan, eax-tls → /tls, eax-superset-home → /superset-home, eax-imports → /imports, eax-exports → /exports, ./persist → /persist |
| library | `eaexplorer/library:dev` | frontend, backend | - | ./docs → /data/docs/docs, ./README.md → /data/docs/README.md, ./eaxcli/help.txt → /data/docs/eaxcli/help.txt, ./releases → /data/docs/releases, ./services/api/version.toml → /data/docs/version.toml |
| views | `eaexplorer/views:dev` | frontend, backend | - | - |
| testrunner (on demand) | `eaexplorer/testrunner:dev` | frontend, backend | - | ./work/tests → /results, ./testbench/data → /testdata, ./persist → /persist |
| k6 (on demand) | `grafana/k6:0.54.0` | frontend | - | - |
| testrunner-service (on demand) | `eaexplorer/testrunner:dev` | frontend, backend | - | - |
| ops | `eaexplorer/ops:dev` | backend, terminal | - | /var/run/docker.sock → /var/run/docker.sock, ./work → /eax-work, ./persist → /eax-persist, ./logs → /eax-logs, ./work/backups → /backups, ./docker-compose.yml → /eax-repo/docker-compose.yml, ./deploy → /eax-repo/deploy, ./eaxcli → /eax-repo/eaxcli, ./services/api/version.toml → /eax-repo/services/api/version.toml |
| db | `postgres:17-alpine` | backend | - | eax-pgdata → /var/lib/postgresql/data, ./deploy/postgres/initdb → /docker-entrypoint-initdb.d |
| dms-broker | `valkey/valkey:8-alpine` | backend | - | - |
| keycloak | `quay.io/keycloak/keycloak:26.0` | frontend, backend | - | eax-kc-import → /opt/keycloak/data/import, ./deploy/secrets → /eax-secrets |
| drawio | `eaexplorer/drawio:dev` | frontend | - | - |
| reports-init (runs once at start) | `eaexplorer/superset:dev` | backend | - | ./deploy/superset → /app/eax, eax-rendered → /rendered, eax-superset-home → /app/superset_home |
| reports | `eaexplorer/superset:dev` | frontend, backend | - | ./deploy/superset → /app/eax, eax-rendered → /rendered, eax-superset-home → /app/superset_home |
| dms | `mayanedms/mayanedms:s4` | frontend, backend | - | eax-docs → /var/lib/mayan, ./deploy/secrets → /eax-secrets |

The backend and terminal networks are internal: nothing on them is reachable from outside but through the
front door. Each database can live on a server of its own (docs/databases.md).
