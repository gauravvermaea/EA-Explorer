# The published library image (D973): services/library/Dockerfile's image, plus the documentation it serves as the
# Enterprise library's EA Explorer folder (mounted from this repository on a developer's machine, over the same paths).
FROM base
USER root
COPY docs /data/docs/docs
COPY README.md /data/docs/README.md
COPY eaxcli/help.txt /data/docs/eaxcli/help.txt
COPY releases /data/docs/releases
COPY services/api/version.toml /data/docs/version.toml
USER eaxlib
