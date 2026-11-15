#!/bin/sh
# EA Explorer api container.
#   EAX_ROLE=api (default): wait for the database, apply migrations, the job-queue schema and the core seed
#                           (what everyone needs to sign in; the rest loads after the API has started, D255),
#                           (one server at a time when there are several, D249), then run the web API (gunicorn),
#                           the job runner, the change log shipper (on one server only) and the MCP
#                           server (uvicorn, port 8001) side by side; the change log and the MCP server only when
#                           switched on (EAX_SERVICE_CHANGE_LOG, EAX_SERVICE_MCP; on by default, D191).
#   EAX_SERVE=operations|personal: the operations or the personal data service only (R2.27 part 2, R2.53)
#   any other command:      run it as given (the setup service uses: python -m eax.setup).
set -eu
cd /app

if [ "$#" -gt 0 ]; then
  exec "$@"
fi

# a service of its own (R2.27 part 2, R2.53): the operations or the personal data API, nothing else; the main API's
# container runs the migrations and the seed, so the service waits for them, then serves its prefix (eax/service_split.py)
case "${EAX_SERVE:-all}" in
  operations|personal)
    python -m eax.wait_for_db
    python -m eax.service_split ready
    PORT=$(python -c "from eax.service_split import SERVICES, serving; print(SERVICES[serving()]['port'])")
    echo "EA Explorer: starting the ${EAX_SERVE} service on port ${PORT}"
    exec gunicorn --bind 0.0.0.0:"${PORT}" --workers "${EAX_SERVICE_WORKERS:-2}" --timeout "${EAX_API_TIMEOUT:-120}" \
         --access-logfile - "eax.wsgi:app"
    ;;
esac

python -m eax.wait_for_db
# several API and job servers may start together (D249): the upgrade and the seed run on one at a time
echo "EA Explorer: applying database migrations"
python -m eax.startup serial -- sh -c "alembic upgrade head && python -m eax.databases ensure && python -m eax.jobs_schema && python -m eax.seed"

echo "EA Explorer: starting the API and the job runner"
# a request may take up to two minutes (gunicorn's own 30 seconds stopped a project's download and a busy page with a
# bare server error, R2.0.1, the laptop's full run); EAX_API_TIMEOUT changes it
gunicorn --bind 0.0.0.0:8000 --workers "${EAX_API_WORKERS:-2}" --timeout "${EAX_API_TIMEOUT:-120}" --access-logfile - "eax.wsgi:app" &
API_PID=$!
# four jobs at once (was two): long ones (a project repository, the industry packs) no longer hold up a delivery preview
# or a merge (R2.0.1, the laptop's full run)
# three queues, each with slots of its own (R5.30: the full test's backup waited an hour behind scheduled jobs): what
# people ask for (tasks), the scheduled housekeeping (default), and the alert checks (watch), so a stuck scheduled job
# never holds up a backup, and the alerts still run, and say so, when everything else is stuck (System Admin > Jobs)
# how many of each: System Admin > Scaling (the settings jobs_slots_tasks and jobs_slots_scheduled), read at each start
# (R5.33); else the config file's EAX_JOB_CONCURRENCY and EAX_SCHEDULED_CONCURRENCY; else 4 and 2
SLOTS=$(python -m eax.jobqueue slots 2>/dev/null || echo "${EAX_JOB_CONCURRENCY:-4} ${EAX_SCHEDULED_CONCURRENCY:-2}")
TASK_SLOTS=$(echo "$SLOTS" | awk '{print $1}')
SCHEDULED_SLOTS=$(echo "$SLOTS" | awk '{print $2}')
echo "EA Explorer: job slots: ${TASK_SLOTS:-4} for people's work, ${SCHEDULED_SLOTS:-2} for scheduled jobs, 1 for the alerts"
procrastinate --app=eax.jobs.app worker --concurrency "${TASK_SLOTS:-4}" --queues tasks --name tasks &
JOBS_PID=$!
procrastinate --app=eax.jobs.app worker --concurrency "${SCHEDULED_SLOTS:-2}" --queues default --name scheduled &
procrastinate --app=eax.jobs.app worker --concurrency 1 --queues watch --name watch &
# the change log (phase 9, D180): ships finished changes to its own database every few seconds; it logs and retries
# on errors and never stops the API. Switched off: no new entries (D191)
if python -m eax.services is-on change_log; then
  python -m eax.startup single change_log -- python -m eax.change_log &   # on one server only (D249)
else
  echo "EA Explorer: the change log is switched off (EAX_SERVICE_CHANGE_LOG=off): no new entries"
fi
# the second tier of the start-up (D255): the sample and laptop test models, the demo estate and the first data quality
# measurement, in the background, one step at a time, so the API is healthy at once and people can sign in; it logs each
# step, records how far it has got (operations.startup_parts, shown to everyone) and never stops the container
# (eax/seed/later.py). With several servers one runs it.
python -m eax.startup once later -- python -m eax.seed.later &
MCP_PID=""
if python -m eax.services is-on mcp; then
  echo "EA Explorer: starting the MCP server on port 8001 (/mcp)"
  uvicorn eax.mcp_server:app --host 0.0.0.0 --port 8001 --no-access-log &
  MCP_PID=$!
else
  echo "EA Explorer: the MCP server is switched off (EAX_SERVICE_MCP=off)"
fi

# If either process stops, stop the other and exit so Docker restarts the container.
trap 'kill $API_PID $JOBS_PID $MCP_PID 2>/dev/null' TERM INT
while kill -0 $API_PID 2>/dev/null && kill -0 $JOBS_PID 2>/dev/null \
      && { [ -z "$MCP_PID" ] || kill -0 $MCP_PID 2>/dev/null; }; do
  sleep 2
done
echo "EA Explorer: a process stopped; exiting"
kill $API_PID $JOBS_PID $MCP_PID 2>/dev/null || true
exit 1
