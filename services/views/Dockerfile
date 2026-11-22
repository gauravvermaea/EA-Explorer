# EA Explorer views service image (phases 28 and 29, D405): the models' drawn views (draw.io files and their versions) and
# their own generated-view definitions, a service of its own with its own database (eaxviews) and API (/api/views/v1)
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

# the Debian packages' own fixes, when there are any (R2.24)
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
# the user and its group both 10003: in certificate mode its key is root:10003 0640 (eax/certs.py CLIENTS), and
# useradd --system alone gives the group a system id (999), so the key could not be read (Release 11, D872)
RUN chmod +x /app/entrypoint.sh \
 && groupadd --system --gid 10003 eaxviews \
 && useradd --system --uid 10003 --gid 10003 --home /app eaxviews

USER eaxviews
EXPOSE 8110
ENTRYPOINT ["/app/entrypoint.sh"]
