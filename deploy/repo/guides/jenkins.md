# Jenkins

Most people run EA Explorer's commands from Jenkins: a pipeline for every eax command and DR tool, run with a click,
with its history.

```bash
./eax.sh jenkins up        # Jenkins and its agent started, the pipelines written; prints its address and sign-in
./eax.sh jenkins status
./eax.sh jenkins down
```

Jenkins runs beside EA Explorer, at http://127.0.0.1:8088 on the machine (reach it through an SSH tunnel or your proxy
from elsewhere). It runs nothing itself: a small agent on the machine (`eax jenkins agent`) runs each command exactly as
typed. A pipeline that changes everything (a restore, an update, a DR tool) asks for the installation's name first.
Its admin password: `./eax.sh logins --admins`. The image is ours (Jenkins with our plugins, settings and pipelines,
frozen at the release): guides/images.md.
