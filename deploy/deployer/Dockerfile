# EA Explorer's deployer (phase 36, D555): the tools eax deploy needs to set up another server from System admin >
# Deploy: ssh and scp, curl and git (no cloud tools: a server anywhere is reached over SSH, D746). Built by the operations
# helper the first time a deployment runs (eaexplorer/deployer:<version>); each deployment runs in a short-lived
# container of it with only its run folder and this release's eaxcli and templates mounted (services/ops/deploys.py).
FROM python:3.12-slim
RUN apt-get update \
 && apt-get install -y --no-install-recommends openssh-client curl git ca-certificates \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /eax
CMD ["python", "-m", "eaxcli.deploy_runner", "/run"]
