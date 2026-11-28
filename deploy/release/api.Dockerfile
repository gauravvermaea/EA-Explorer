# The published api image (D973): the image services/api/Dockerfile builds, plus what an installation would otherwise
# read from this repository's folders (docker-compose.yml mounts these on a developer's machine, over the same paths):
# the documentation the AI reads and the website shows, the help, the release notes, the printed guides, EA Explorer's
# own document templates, the industry packs, and the deploy folder the setup step reads. TOGAF's template files are The
# Open Group's and are never in an image (library/templates/togaf/.gitignore).
FROM base
USER root
COPY docs /data/docs/docs
COPY README.md /data/docs/README.md
COPY eaxcli/help.txt /data/docs/eaxcli/help.txt
COPY releases /data/docs/releases
COPY documents /data/docs/documents
COPY services/web/src/help/catalogue.json /data/docs/help/catalogue.json
COPY library/templates/ea-explorer /data/ea-explorer-templates
COPY library/industry-packs /data/industry-packs
COPY deploy /deploy
USER eax
