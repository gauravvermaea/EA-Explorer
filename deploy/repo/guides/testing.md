# Testing a deployment

| Test | Command | Takes |
|---|---|---|
| Smoke | `./eax.sh test smoke` | minutes |
| Full: every screen, the API, security, reports, backups and restores, the DR drill | `./eax.sh test full` | hours |
| The backup and restore cases (models, projects, scheduled backups) | `./eax.sh test backup-cases` | 20 to 40 minutes |
| The whole-installation backup and restore | `./eax.sh test backup-restore` | about an hour; locks people out while each restore runs |
| Every eax command that is safe to run | `./eax.sh test commands` | minutes |

The test runner's image (about 1.5 GB) is pulled the first time a test runs. On an installation made from this
repository, the full test leaves out what needs the source code (the developer check, SonarQube) and says so. Each run's
report: Self-test in the screens, and `work/tests/`.

From Jenkins: the same tests are pipelines (guides/jenkins.md). From the deploy page: the "Test a deployment" tab writes
a script that runs them here or on a remote server over SSH, or starts the Jenkins pipeline.
