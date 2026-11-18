-- EA Explorer on your own PostgreSQL server (Release 6.6, R6.6.2, D750): what your DBA prepares, once.
--
-- Read it, change what your standards ask for, then run it as a superuser (or a login with CREATEROLE and CREATEDB):
--
--   psql -h <your server> -U <your admin> -d postgres -v ON_ERROR_STOP=1 \
--        -v admin_pw='...' -v app_pw='...' -v report_pw='...' -v migrator_pw='...' -v keycloak_pw='...' \
--        -v superset_pw='...' -v mayan_pw='...' -v library_pw='...' -v views_pw='...' \
--        -v console_it_pw='...' -v console_super_pw='...' -f prepare.sql
--
-- Use the passwords in EA Explorer's config file (work/eaexplorer.env: EAX_DB_PASSWORD, EAX_DB_REPORT_PASSWORD and the
-- rest; `eax setup external-db` prints which goes where), or set your own there with `eax secrets set`.
-- PostgreSQL 15 or later; the extensions pgcrypto, pg_trgm and amcheck must be installable (they ship with PostgreSQL).
--
-- eax_admin is the one login EA Explorer itself uses for its backups and restores, its database maintenance and its
-- integrity checks (EAX_DB_ADMIN_USER=eax_admin, its password in EAX_DB_SUPERUSER_PASSWORD). It is not a superuser:
-- it may create and drop EA Explorer's databases and is a member of each of their owners, nothing more. Your own
-- backups may run beside EA Explorer's (D750).

CREATE ROLE eax_admin          LOGIN CREATEDB PASSWORD :'admin_pw';
CREATE ROLE eax_app            LOGIN PASSWORD :'app_pw';
CREATE ROLE eax_report         LOGIN PASSWORD :'report_pw';
CREATE ROLE eax_migrator       LOGIN PASSWORD :'migrator_pw';
CREATE ROLE keycloak           LOGIN PASSWORD :'keycloak_pw';
CREATE ROLE superset           LOGIN PASSWORD :'superset_pw';
CREATE ROLE mayan              LOGIN PASSWORD :'mayan_pw';
CREATE ROLE eax_library        LOGIN PASSWORD :'library_pw';
CREATE ROLE eax_views          LOGIN PASSWORD :'views_pw';
CREATE ROLE eax_console_it     LOGIN PASSWORD :'console_it_pw';
CREATE ROLE eax_console_super  LOGIN PASSWORD :'console_super_pw';

-- the backup and restore login may act as each owner (to dump and restore what they own), and read everything
GRANT eax_app, eax_migrator, keycloak, superset, mayan, eax_library, eax_views TO eax_admin;
GRANT pg_read_all_data, pg_monitor TO eax_admin;
GRANT pg_read_all_data, pg_monitor TO eax_console_it;
GRANT pg_read_all_data, pg_write_all_data, pg_monitor TO eax_console_super;

CREATE DATABASE eaexplorer OWNER eax_app;
CREATE DATABASE keycloak   OWNER keycloak;
CREATE DATABASE superset   OWNER superset;
CREATE DATABASE mayan      OWNER mayan;
CREATE DATABASE eaxlibrary OWNER eax_library;
CREATE DATABASE eaxviews   OWNER eax_views;
REVOKE ALL ON DATABASE eaexplorer, keycloak, superset, mayan, eaxlibrary, eaxviews FROM PUBLIC;
GRANT CONNECT ON DATABASE eaexplorer TO eax_report, eax_migrator, eax_console_it, eax_console_super;

\connect eaexplorer
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS amcheck;
