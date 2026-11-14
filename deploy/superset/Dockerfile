# Apache Superset, used as is, plus the drivers it needs here:
#   psycopg2 (PostgreSQL) and Authlib (sign-in through Keycloak). Caches live in PostgreSQL.
# Recent Superset images ship without database drivers, so they are added on top.
# Superset 6.1.0 (R4.7; owner, 14 Nov 2026: "upgrade super set to latest version", "Straight to 6.1.0").
ARG SUPERSET_IMAGE=apache/superset:6.1.0
FROM ${SUPERSET_IMAGE}
USER root
# the Debian packages' own fixes (OpenSSL, GnuTLS, MariaDB client, perl…: R2.24)
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*
# Superset 5 and later keep their Python packages in /app/.venv, installed with uv (Superset's UPDATING.md for 5.0); the
# system's pip would put them where Superset never looks. An older image (EAX_IMAGE_SUPERSET set to a 4.x one) has no
# .venv: the system's pip, as before.
# Python packages inside Superset with critical vulnerabilities fixed in newer releases (R2.24, the full self-test 12 Nov 2026)
RUN set -e; \
    NEED='psycopg2-binary>=2.9,<3 Authlib>=1.3,<2'; \
    FIXED='Brotli>=1.2.1 PyJWT>=2.14.0,<3 certifi>=2026.10.18'; \
    if [ -x /app/.venv/bin/python ]; then \
        uv pip install --no-cache --python /app/.venv/bin/python $NEED; \
        uv pip install --no-cache --python /app/.venv/bin/python --upgrade $FIXED; \
    else \
        pip install --no-cache-dir $NEED; \
        pip install --no-cache-dir --upgrade $FIXED; \
    fi; \
    python_bin=$( [ -x /app/.venv/bin/python ] && echo /app/.venv/bin/python || echo python ); \
    $python_bin -c "import psycopg2, authlib; print('EA Explorer: Superset drivers', psycopg2.__version__, authlib.__version__)"
USER superset
