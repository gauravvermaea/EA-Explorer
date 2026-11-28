# eax in a container (Release 14.8.1, D976; owner, 28 Nov 2026, 10:22: "when we now deploy eax command will be also in
# a container so we need it and the mechanism to log into it. We should be able to test the command from there"): what
# the eax command needs to run (bash, Python 3.12, the Docker command with Compose, git, ssh, curl), so a machine needs
# only Docker. The eax it runs is the deploy folder's own (eax.sh, eaxcli/), mounted at the same path as on the machine,
# so the compose files' folders mean the same to Docker; the machine's Docker is reached through its socket.
#   ./eax <command>        the deploy folder's wrapper: one command in a container that goes when it ends
#   ./eax shell            a shell in it, with eax on the path: eax status, eax logins --admins, eax test full
ARG DOCKER_IMAGE=docker:29-cli
ARG PYTHON_IMAGE=python:3.12-slim
FROM ${DOCKER_IMAGE} AS docker

FROM ${PYTHON_IMAGE}
# the Debian packages' own fixes, then what eax.sh and its checks use
RUN apt-get update && apt-get upgrade -y \
 && apt-get install -y --no-install-recommends bash ca-certificates curl git openssh-client procps iproute2 less \
 && rm -rf /var/lib/apt/lists/*
COPY --from=docker /usr/local/bin/docker /usr/local/bin/docker
COPY --from=docker /usr/local/libexec/docker/cli-plugins /usr/local/libexec/docker/cli-plugins
COPY entrypoint.sh /usr/local/bin/eax-entrypoint
COPY eax /usr/local/bin/eax
RUN chmod 0755 /usr/local/bin/eax-entrypoint /usr/local/bin/eax \
 && docker --version && docker compose version
# eaxpy.sh runs eaxpy.py with this Python, fetching nothing (D976); HOME for a user the image does not know (the
# machine's own user runs it, so what it writes in the folder stays theirs)
ENV EAX_PYTHON=/usr/local/bin/python3 EAX_IN_CONTAINER=1 HOME=/tmp PYTHONDONTWRITEBYTECODE=1
ENTRYPOINT ["/usr/local/bin/eax-entrypoint"]
