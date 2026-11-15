"""eax jobs (R5.30 to R5.34): the background job queue from the command line, for admins, as on System Admin > Jobs.
It runs eax/jobqueue.py in the api container (as "eax", every action in the audit trail):

  eax jobs [list]                      what is being worked on and waiting, the stuck ones said, what to do
  eax jobs history [N]                 the newest N finished jobs
  eax jobs cancel|kill|up|down <id>    a waiting job off the queue | a job being worked on stopped | moved in the queue
  eax jobs clear-stuck [--restart]     every stuck job being worked on killed (then the job runner restarted)
  eax jobs restart                     the job runner (the API containers) restarted
  eax jobs delete-history [--older-than DAYS]   the finished jobs' history deleted
  eax jobs slots [<people's work> <scheduled>]  each API server's job slots shown, or set (taken at the next restart)

Nothing is killed, cancelled or restarted unless asked here (owner, 15 Nov 2026: "I dont want any job to be killed
without human approval").
"""

from __future__ import annotations

from .core import Failure, attached, compose_args

COMMANDS = ("list", "history", "cancel", "kill", "up", "down", "clear-stuck", "restart", "delete-history", "slots")


def main(rest: list[str]) -> int:
    """eax jobs: the job queue in the api container."""
    args = rest or ["list"]
    if args[0] not in COMMANDS:
        raise Failure("eax jobs list | history [N] | cancel|kill|up|down <id> | clear-stuck [--restart] | restart | "
                      "delete-history [--older-than DAYS] | slots [<people's work> <scheduled>]")
    if args[0] in ("cancel", "kill", "up", "down") and (len(args) < 2 or not args[1].isdigit()):
        raise Failure(f"eax jobs {args[0]} <job id> (the ids are in eax jobs list)")
    return attached(compose_args(["exec", "-T", "-e", "EAX_JOBS_CLI=1", "api", "python", "-m", "eax.jobqueue", *args]))
