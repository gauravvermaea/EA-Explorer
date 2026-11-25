# Release 14.5: the screens no journey uses yet

Made from the full test of 24 Nov 2026 (run 20261124T193750Z) (owner, 25 Nov 2026, 06:46: "Yes please add these missing journes to 14.5"; D914). The page sweep opened 207 kinds of page; the 21 journeys open 27 of them with an address. The other 180 are opened and checked (loads, no error, a heading, no server error) but no journey clicks, fills or chooses on them. Some are reached by a journey's clicks without their address being opened; each story below checks that first.

Each story adds a journey (or steps to one) that does the screen's real work as the role that does it, puts back what it changed, and runs the refused check for a role that may not. A page that only shows (a log, a list with nothing to do) needs no journey: the story says so for it instead.

## R14.5.7 System Admin: people and access (10)

- `#/admin/machine-access`
- `#/admin/machine-access/all`
- `#/admin/machine-access/mine`
- `#/admin/machine-access/service-accounts`
- `#/admin/secrets`
- `#/admin/security`
- `#/admin/users`
- `#/admin/users/mapping`
- `#/admin/users/people`
- `#/break-glass`

## R14.5.8 System Admin: running the installation (21)

- `#/admin/containers`
- `#/admin/containers/files`
- `#/admin/containers/logs`
- `#/admin/containers/properties`
- `#/admin/containers/terminal`
- `#/admin/databases`
- `#/admin/db-maintenance`
- `#/admin/estate`
- `#/admin/estate/logical`
- `#/admin/footprint`
- `#/admin/hosts`
- `#/admin/jobs`
- `#/admin/logs`
- `#/admin/mounts`
- `#/admin/operations`
- `#/admin/optimisation`
- `#/admin/persist`
- `#/admin/quality`
- `#/admin/scaling`
- `#/admin/sizing`
- `#/admin/sql`

## R14.5.9 System Admin: settings, updates and commands (13)

- `#/admin`
- `#/admin/alerts`
- `#/admin/application`
- `#/admin/branding`
- `#/admin/commands`
- `#/admin/commands/commands`
- `#/admin/commands/console`
- `#/admin/commands/history`
- `#/admin/licences`
- `#/admin/settings-transfer`
- `#/admin/setup`
- `#/admin/system`
- `#/admin/updates`

## R14.5.10 System Admin: disaster recovery, pairings and restores (3)

- `#/admin/disaster-recovery`
- `#/admin/pairings`
- `#/admin/restores`

## R14.5.11 System Admin: the self-test's own screens (7)

- `#/admin/self-test`
- `#/admin/self-test/fixtures`
- `#/admin/self-test/harness`
- `#/admin/self-test/history`
- `#/admin/self-test/performance`
- `#/admin/self-test/run`
- `#/admin/self-test/security`

## R14.5.12 Models: working in a model (31)

- `#/archive`
- `#/change-documents`
- `#/change-log`
- `#/compare`
- `#/compare/common`
- `#/compare/gaps`
- `#/merge-requests`
- `#/metamodel`
- `#/metamodel/drafts`
- `#/metamodel/hierarchy`
- `#/metamodel/{id}/backups`
- `#/metamodel/{id}/business`
- `#/metamodel/{id}/checks`
- `#/metamodel/{id}/designer`
- `#/metamodel/{id}/documents`
- `#/metamodel/{id}/grid`
- `#/metamodel/{id}/hierarchy`
- `#/metamodel/{id}/import`
- `#/metamodel/{id}/kpis`
- `#/metamodel/{id}/merge`
- `#/metamodel/{id}/merge-requests`
- `#/metamodel/{id}/metamodel`
- `#/metamodel/{id}/odata`
- `#/metamodel/{id}/people`
- `#/metamodel/{id}/pushdown`
- `#/metamodel/{id}/rels`
- `#/metamodel/{id}/reports`
- `#/metamodel/{id}/tags`
- `#/metamodel/{id}/types`
- `#/metamodel/{id}/views/custom`
- `#/metamodel/{id}/views/standard`

## R14.5.13 Model admin (16)

- `#/model-admin`
- `#/model-admin/drafts`
- `#/model-admin/hierarchy`
- `#/model-admin/list`
- `#/model-admin/wizards`
- `#/model-admin/{id}`
- `#/model-admin/{id}/backups`
- `#/model-admin/{id}/documents`
- `#/model-admin/{id}/family`
- `#/model-admin/{id}/merge`
- `#/model-admin/{id}/merge-requests`
- `#/model-admin/{id}/metamodel`
- `#/model-admin/{id}/people`
- `#/model-admin/{id}/pushdown`
- `#/model-admin/{id}/tags`
- `#/model-admin/{id}/wizards`

## R14.5.14 Projects: the new-project wizard and every project tab (28)

- `#/projects`
- `#/projects/new`
- `#/projects/{id}/analysis`
- `#/projects/{id}/archrepo`
- `#/projects/{id}/base`
- `#/projects/{id}/business`
- `#/projects/{id}/calendar`
- `#/projects/{id}/canvas`
- `#/projects/{id}/charter`
- `#/projects/{id}/content`
- `#/projects/{id}/home`
- `#/projects/{id}/journeys`
- `#/projects/{id}/library`
- `#/projects/{id}/library/reference`
- `#/projects/{id}/models`
- `#/projects/{id}/organisation`
- `#/projects/{id}/otherdocs`
- `#/projects/{id}/principles`
- `#/projects/{id}/quality`
- `#/projects/{id}/questions`
- `#/projects/{id}/report`
- `#/projects/{id}/reports`
- `#/projects/{id}/sheets`
- `#/projects/{id}/signoff`
- `#/projects/{id}/stakeholders`
- `#/projects/{id}/standards`
- `#/projects/{id}/tasks`
- `#/projects/{id}/views`

## R14.5.15 Project admin (8)

- `#/project-admin`
- `#/project-admin/bases`
- `#/project-admin/libprojects`
- `#/project-admin/library`
- `#/project-admin/list`
- `#/project-admin/principles`
- `#/project-admin/template-setup`
- `#/project-admin/templates`

## R14.5.16 The repository and the libraries (20)

- `#/discovery-projects`
- `#/enterprise-library`
- `#/governance`
- `#/library`
- `#/maturity`
- `#/principles`
- `#/project-library`
- `#/repository`
- `#/repository/board`
- `#/repository/calendar`
- `#/repository/capability`
- `#/repository/compliance`
- `#/repository/decisions`
- `#/repository/measures`
- `#/repository/people`
- `#/repository/reference/common`
- `#/repository/reference/foundation`
- `#/repository/reference/industry`
- `#/repository/reference/own`
- `#/repository/sheets`

## R14.5.17 Service desk and notifications (10)

- `#/notifications`
- `#/notifications/new`
- `#/notifications/received`
- `#/notifications/sent`
- `#/notifications/tasks`
- `#/service-desk/all`
- `#/service-desk/ask`
- `#/service-desk/catalogue`
- `#/service-desk/mine`
- `#/service-desk/queue`

## R14.5.18 The AI connection, the farm, search and the rest (13)

- `#/documentation/capabilities`
- `#/documentation/command-line-help`
- `#/documentation/readme`
- `#/farm`
- `#/farm/connect`
- `#/farm/deploy`
- `#/mcp`
- `#/mcp/activity`
- `#/mcp/connect`
- `#/mcp/tools`
- `#/more`
- `#/search`
- `#/work`
