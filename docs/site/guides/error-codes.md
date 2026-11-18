---
title: Error codes
summary: Every error code EA Explorer gives, what it means, its usual cause and what to do.
group: Running it
roles: system-admin
---

## Why do this

When something goes wrong, EA Explorer says so with a code of the form `EAX-AREA-NNN`, for example `EAX-AUTH-001`. The
area says which part it is about; the number tells problems in one area apart. A code never changes its meaning, so you
can look it up here, search the logs for it and quote it when you ask for help. See [[running-the-installation]].

**In TOGAF terms:** Outside the method: this keeps the tool that holds the Architecture Repository running. See [[ea-explorer-and-togaf]].

**The goal:** For any problem, you know what it means and what to do next.

> **Before you start** Anyone can read this guide; most of what it asks you to do needs the Super Admin or IT Admin role,
> or the machine EA Explorer runs on.

## Where you see the codes

- **`eax status`** on the machine: after the containers and the disks, every problem now with its code and what to do.
  `eax status problems` lists the problems only; `eax errors <code>` explains one code.
- **System Admin › Running › Health**: each part that is not up shows its code and what to do.
- **System Admin › Running › Alerts**: each open alert shows its code and what to do; its notification and email name
  the code too.
- **The screens**: an error message ends with its code in brackets.
- **The API**: every error answer has `error_code` and `to_do` beside `message`, and the header `X-EAX-Error-Code`.
- **The logs**: the API's log lines about a problem carry `error_code`, so `eax logs api` and System Admin › Running ›
  Logs can be searched by code.

When the code is `EAX-API-500`, the message also gives a request id: `eax logs api` shows what happened under that id;
give the id when you report the problem.

## Each task, one page

1. [Find what an error code means](../how-do-i/find-what-an-error-code-means.md)
2. [See every problem from the machine](../how-do-i/see-every-problem-from-the-machine.md)
3. [See the health of every part](../how-do-i/see-the-health-of-every-part.md)
4. [Read the logs](../how-do-i/read-the-logs.md)

## The codes

Each area below lists its codes in order. Do what a code says, in order; if the problem stays, `eax diag` saves a
report to send with the code.

### Docker and the containers (STACK)

**EAX-STACK-001: Container not running.** A container EA Explorer needs has stopped.

Usual cause: It failed, was stopped, or ran out of memory.

What to do: Run eax logs <container> to see why; then eax up.

**EAX-STACK-002: Container unhealthy.** A container is running but its own health check fails.

Usual cause: It is starting slowly or cannot reach what it needs.

What to do: Wait a minute; if it stays, run eax logs <container>.

**EAX-STACK-003: Docker not answering.** Docker's engine does not answer.

Usual cause: Docker Desktop is not running.

What to do: Start Docker Desktop, wait until it says it is running, then run eax up.

### The API's answers (API)

**EAX-API-001: API not answering.** The API container does not answer.

Usual cause: It stopped, is starting, or failed to start.

What to do: Run eax status, then eax logs api. Start it again with eax up.

**EAX-API-101: A value is not valid.** The database could not take a value as given.

Usual cause: Not an id, not a date, or the wrong kind of value.

What to do: Read the message: it names the value. Correct it and send again.

**EAX-API-102: Change refused.** The change cannot be made as asked.

Usual cause: It breaks a rule of the model, the metamodel or the request.

What to do: Read the message: it says which rule. Change the request to keep it.

**EAX-API-400: Request not valid.** The API could not take the request as sent.

Usual cause: A value is missing, of the wrong kind or not allowed.

What to do: Read the message: it names the value. Correct it and send again.

**EAX-API-401: Not signed in.** The request carried no valid sign-in.

Usual cause: The session ended, or the token or API key is wrong or expired.

What to do: Sign in again. For a machine, check its API key under System Admin > Machine access.

**EAX-API-403: Not allowed.** The person or machine is signed in but its roles do not allow this.

Usual cause: A role is missing, or the account is view only.

What to do: Ask a Super Admin to give the role needed (System Admin > Users and roles), or use an account that has it.

**EAX-API-404: Not found.** What was asked for is not there, or the person may not see it.

Usual cause: A wrong address or id, something deleted, or no right to read it.

What to do: Check the address and id. If it should be there, check the person's access to its model or project.

**EAX-API-405: Method not allowed.** The address does not take this kind of request.

Usual cause: A GET sent where a POST is needed, or the other way round.

What to do: Check the method in the API reference (Documentation > API (Swagger)).

**EAX-API-409: Conflict.** The change clashes with what is there now.

Usual cause: Someone changed it first, or the name is already taken.

What to do: Load it again, look at what changed and make the change again.

**EAX-API-413: Upload too large.** The upload is bigger than the largest allowed.

Usual cause: The file is over the limit set in System settings.

What to do: Make the file smaller, or raise the largest upload under System Admin > System settings.

**EAX-API-422: Values not valid.** The request's values did not pass the checks.

Usual cause: A field is missing or has a value it cannot take.

What to do: Read the message and the errors it lists; correct each field and send again.

**EAX-API-428: Needs your yes first.** This would put the maintenance page up, so it asks first.

Usual cause: A restore, update or similar step.

What to do: Accept the warning on the screen, or send the request again with accept_maintenance set to true.

**EAX-API-429: Too many requests.** Too many requests came in a short time.

Usual cause: A script or tool calling in a tight loop.

What to do: Wait a minute and slow the caller down.

**EAX-API-500: Server error.** Something went wrong inside the API.

Usual cause: A fault in EA Explorer, or a service it needs is not answering.

What to do: Run eax status. Then eax logs api and look for the request id the message gives; report it with that id.

**EAX-API-502: Service behind the front door not answering.** The front door could not reach the service behind it.

Usual cause: That container stopped or is starting.

What to do: Run eax status. If a container is not running, run eax up.

**EAX-API-503: Not available right now.** The service cannot answer now.

Usual cause: It is starting, stopping or a part it needs is down.

What to do: Wait a minute and try again. If it stays, run eax status.

**EAX-API-504: The answer took too long.** The front door gave up waiting.

Usual cause: A slow query or a busy service.

What to do: Try again. If it keeps happening, see System Admin > Health and the tuning guide.

### Parts switched off (PART)

**EAX-PART-001: Part switched off.** This part of EA Explorer is switched off in this installation.

Usual cause: A Super Admin switched it off.

What to do: A Super Admin switches it on under System Admin > System settings. Its data is kept.

### Maintenance (MNT)

**EAX-MNT-001: Read only during maintenance.** Nothing can be changed while a restore or an update runs.

Usual cause: A restore or update was started.

What to do: Wait for it to finish (System Admin > Backups shows progress). Reading still works.

### Disaster recovery (DR)

**EAX-DR-001: Read only: DR copy.** This installation is the DR copy of another and takes no changes.

Usual cause: A DR pairing holds.

What to do: Make changes on the main site. To take over, a Super Admin stops the pairing (System Admin > Site pairings).

### The database (DB)

**EAX-DB-001: Database down.** The database does not answer.

Usual cause: The db container stopped, is full or is starting.

What to do: Run eax status. If db is not running, run eax up; then eax logs db. Check the disk is not full.

**EAX-DB-002: Database and API versions differ.** The database's version is not the API's.

Usual cause: An update did not finish, or a backup from another version was restored.

What to do: Run eax up again so the migrations run. See the upgrade guide if it stays.

**EAX-DB-003: Database connections nearly used up.** The database is near its connection limit.

Usual cause: Too many API servers, or connections left open.

What to do: See System Admin > Databases; lower EAX_API_SERVERS or raise the limit (tuning guide).

**EAX-DB-004: Long open transaction.** A transaction has been open a long time and can block others.

Usual cause: A stuck job or a session left open.

What to do: See System Admin > Databases; end the session or job holding it.

**EAX-DB-005: Database maintenance findings.** The last database check found things to fix.

Usual cause: Bloat, missing statistics or similar.

What to do: Open System Admin > Database maintenance and follow each finding.

**EAX-DB-006: Database integrity findings.** The integrity check found data that is not right.

Usual cause: An interrupted change or a restore.

What to do: Open System Admin > Database maintenance, its integrity check, and repair each finding.

### Background jobs (JOB)

**EAX-JOB-001: Job runner not working.** Background jobs cannot run.

Usual cause: The job tables are missing or the database is down.

What to do: Run eax status and eax logs api. Run eax up to start it again.

**EAX-JOB-002: Jobs waiting too long or failed.** Jobs wait too long, or some failed.

Usual cause: The job runner stopped, or a job hit an error.

What to do: Open System Admin > Jobs: look at the failed or waiting jobs, run again or cancel them.

**EAX-JOB-003: Jobs stuck.** Background jobs are waiting or running too long.

Usual cause: The job runner stopped or a job hangs.

What to do: Open System Admin > Jobs; cancel the stuck ones and check eax logs api.

**EAX-JOB-004: Discovery overdue.** Discovery projects whose run is overdue.

Usual cause: Their AI has not run them.

What to do: Open AI (MCP) > Enterprise discovery and run them, or change their schedule.

### Sign-in (AUTH)

**EAX-AUTH-001: Sign-in down.** Keycloak does not answer, so nobody can sign in.

Usual cause: The keycloak container stopped or is starting.

What to do: Run eax status and eax logs keycloak; run eax up. To get in meanwhile, use the break-glass account.

### The break-glass account (BRK)

**EAX-BRK-001: Break-glass account used.** The emergency account was used and is no longer sealed.

Usual cause: Someone signed in with it.

What to do: Check the audit log for what was done, change EAX_BREAK_GLASS_PASSWORD in the config file and run eax up.

**EAX-BRK-002: Break-glass state unreadable.** The break-glass account's state could not be read.

Usual cause: The database is down or not migrated.

What to do: Run eax status; fix the database first.

### The web screens (WEB)

**EAX-WEB-001: Web screens down.** The web container does not answer.

Usual cause: It stopped or is starting.

What to do: Run eax status and eax logs web; run eax up.

**EAX-WEB-002: Many server errors.** Many calls ended in a server error in the last hour.

Usual cause: A fault or a service down.

What to do: Run eax status; then System Admin > Logs, web log filtered to 5xx, for the calls and their request ids.

### The front door (PROXY)

**EAX-PROXY-001: Front door down.** The proxy that every browser goes through does not answer.

Usual cause: The proxy container stopped, or its certificate or settings are wrong.

What to do: Run eax status and eax logs proxy; run eax up. Check the certificate files if it will not start.

### Reports (RPT)

**EAX-RPT-001: Reports down.** Apache Superset does not answer.

Usual cause: The reports container stopped or is starting.

What to do: Run eax status and eax logs reports; run eax up.

### Documents (DOC)

**EAX-DOC-001: Documents down.** Mayan EDMS does not answer.

Usual cause: The dms container stopped or is starting.

What to do: Run eax status and eax logs dms; run eax up.

**EAX-DOC-002: Document queue down.** Valkey, the documents' queue, does not answer or refuses the password.

Usual cause: The dms-broker container stopped, or its password changed.

What to do: Run eax status and eax logs dms-broker; run eax up.

### Diagrams (DRAW)

**EAX-DRAW-001: Diagrams down.** draw.io does not answer.

Usual cause: The drawio container stopped or is starting.

What to do: Run eax status and eax logs drawio; run eax up.

### The library (LIB)

**EAX-LIB-001: Library down.** The library service does not answer.

Usual cause: The library container stopped or is starting.

What to do: Run eax status and eax logs library; run eax up.

### Drawn views (VIEW)

**EAX-VIEW-001: Drawn views down.** The views service does not answer.

Usual cause: The views container stopped or is starting.

What to do: Run eax status and eax logs views; run eax up.

### Operations (OPS)

**EAX-OPS-001: Operations down.** The operations part does not answer or cannot reach its schema.

Usual cause: Its container or the database is down.

What to do: Run eax status and eax logs api; run eax up.

### Personal data (PDATA)

**EAX-PDATA-001: Personal data not available.** People's personal data (pins, settings) cannot be read now.

Usual cause: Its service or schema cannot be reached.

What to do: Run eax status and eax logs api; run eax up. The rest of EA Explorer still works.

### The MCP server (MCP)

**EAX-MCP-001: MCP server down.** AI tools cannot reach EA Explorer.

Usual cause: The MCP server inside the api container is not answering.

What to do: Run eax logs api; run eax up. Check EAX_MCP_ENABLED in the config file.

### Backups (BAK)

**EAX-BAK-001: Nightly backup switched off.** No backup is made each night.

Usual cause: Someone switched the schedule off.

What to do: Switch it on under System Admin > Backups.

**EAX-BAK-002: Backups folder not mounted.** The API cannot see the backups folder.

Usual cause: The folder in the config file is missing or not shared with Docker.

What to do: Check the backups folder setting in the config file exists, then run eax up.

**EAX-BAK-003: No backup yet.** There is no finished backup to restore from.

Usual cause: None has run yet, or every one failed.

What to do: Run eax backup now, then check eax backups lists it.

**EAX-BAK-004: Newest backup too old.** The newest backup is older than the limit.

Usual cause: The nightly backup failed or did not run.

What to do: Run eax backup now; then look at why the nightly one failed (System Admin > Backups shows each run and why it failed).

### Disk space (DISK)

**EAX-DISK-001: Disk filling up.** A disk the installation uses is nearly full.

Usual cause: Backups, logs or documents growing.

What to do: Run eax footprint; remove old backups (eax backups) and back up and clean the logs (eax logs backup).

### Memory (MEM)

**EAX-MEM-001: Container near its memory limit.** A container is near its memory limit and may be stopped.

Usual cause: Load, or a limit set too low.

What to do: See System Admin > Footprint; raise the container's limit (see the tuning guide) and run eax up.

### Certificates (CERT)

**EAX-CERT-001: Certificate ending.** The front door's certificate ends soon.

Usual cause: It was not renewed.

What to do: Renew it (System Admin > Secrets: passwords, keys and certificates) or replace the files, then run eax up.

### Secrets and security (SEC)

**EAX-SEC-001: Secret needs a person.** A password, key or certificate is due or overdue.

Usual cause: It does not rotate by itself, or its rotation failed.

What to do: Open System Admin > Secrets and rotate the ones listed.

**EAX-SEC-002: Security findings.** The last security gate found high or critical findings.

Usual cause: A dependency or setting with a known weakness.

What to do: Open the last security test run (System Admin > Self-test) and fix or accept each finding.

### Self-tests (TEST)

**EAX-TEST-001: Self-test failed.** The last self-test had failed checks.

Usual cause: Something is broken, or the test hit a change.

What to do: Open System Admin > Self-test, look at the failed checks and fix them.

### Alerts (ALRT)

**EAX-ALRT-001: A custom check is over its level.** A check an admin added is over its warning or critical level.

Usual cause: Whatever that check measures.

What to do: Open System Admin > Alerts to see the check and its message.

**EAX-ALRT-002: Health could not be checked.** The service health could not be read at all.

Usual cause: The API is failing.

What to do: Run eax status and eax logs api.
