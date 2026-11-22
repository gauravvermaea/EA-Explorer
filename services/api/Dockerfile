# EA Explorer API image (ours): Flask API + background job runner, one container
FROM python:3.12-slim

# PYTHONPATH: command-line tools (alembic, procrastinate) must find our eax package
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
# the user and its group both 10001: in certificate mode its key is root:10001 0640 (eax/certs.py CLIENTS), and
# useradd --system alone gives the group a system id (999), so the key could not be read (Release 11, D872)
RUN chmod +x /app/entrypoint.sh \
 && groupadd --system --gid 10001 eax \
 && useradd --system --uid 10001 --gid 10001 --home /app eax \
 && mkdir -p /data/imports /data/exports && chown -R eax /data

USER eax
EXPOSE 8000 8001
ENTRYPOINT ["/app/entrypoint.sh"]
