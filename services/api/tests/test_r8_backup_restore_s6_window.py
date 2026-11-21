"""D808: the backup and restore test's S6 reads only the jobs from the test's start on, and S1 says why a call had no
answer (the owner's run, 20 Nov 2026: S6 failed on five recurring jobs deferred twice during the night's full test, all
hours before the test began at 03:39; S1's Architect showed only "599").

The job queue is stood in by rows the fake database groups as the real query does (task, time; the time from `since`
on), so the same rows show the failure before the change and none after it, and a job deferred twice inside the test's
window still fails."""

from __future__ import annotations

from collections import Counter

from eax.testing import backup_restore as br

TEST_START = 1795146000                                   # 20 Nov 2026 03:40Z
NIGHT = [("eax.sync_tick", 1795129560), ("eax.backup_scheduler", 1795130100), ("eax.backup_scheduler", 1795120260),
         ("eax.project_repositories", 1795135560), ("eax.backup_scheduler", 1795143000)]


class _Result:
    def __init__(self, rows):
        self.rows = rows

    def scalar(self):
        return self.rows[0][0] if self.rows else None

    def all(self):
        return self.rows


class _Conn:
    """The jobs table as (task, timestamp) rows; answers the three queries S6 makes."""

    def __init__(self, jobs):
        self.jobs, self.asked = jobs, []

    def execute(self, sql, params=None):
        sql = str(sql)
        self.asked.append((sql, params))
        if "to_regclass" in sql:
            return _Result([("jobs.procrastinate_jobs",)])
        if "HAVING count(*) > 1" in sql:
            since = int((params or {}).get("since", 0)) if ":since" in sql else 0
            seen = Counter((t, str(ts)) for t, ts in self.jobs if ts >= since)
            return _Result([k for k, n in seen.items() if n > 1][:5])
        return _Result([])                    # SET search_path; nothing running for over half an hour


class _Engine:
    def __init__(self, conn):
        self.conn = conn

    def begin(self):
        engine = self

        class _Ctx:
            def __enter__(self):
                return engine.conn

            def __exit__(self, *_):
                return False
        return _Ctx()


def _s6(monkeypatch, jobs, since):
    conn = _Conn(jobs)
    monkeypatch.setattr(br, "text", lambda s: s)
    import eax.db
    monkeypatch.setattr(eax.db, "get_engine", lambda: _Engine(conn))
    return br._jobs(since), conn


def _twice_each(rows):
    return [j for r in rows for j in (r, r)]


def test_the_nights_duplicates_failed_s6_before_and_pass_now(monkeypatch):
    jobs = _twice_each(NIGHT) + [("eax.sync_tick", TEST_START + 60)]
    before, _ = _s6(monkeypatch, jobs, None)          # as before D808: the whole history
    assert before[2] is False and "eax.sync_tick" in before[3]
    after, conn = _s6(monkeypatch, jobs, TEST_START)
    assert after[2] is True and after[3] == "none"
    assert any(p == {"since": TEST_START} for _q, p in conn.asked)


def test_a_job_deferred_twice_during_the_test_still_fails(monkeypatch):
    jobs = _twice_each(NIGHT) + _twice_each([("eax.backup_scheduler", TEST_START + 1200)])
    out, _ = _s6(monkeypatch, jobs, TEST_START)
    assert out[2] is False
    assert str(TEST_START + 1200) in out[3] and "1795129560" not in out[3]



def test_the_start_step_records_when_it_began():
    import inspect
    src = inspect.getsource(br.start)
    assert "began = int(time.time())" in src and '"began": began' in src
    assert 'br._jobs(state.get("began"))' not in src                # read in after(), from the state
    assert '_jobs(state.get("began"))' in inspect.getsource(br.after)


def test_s1_says_why_a_call_had_no_answer():
    assert br.signed_in(200, {"results": []}) == "200"
    assert br.signed_in(599, {"text": "no answer: timed out"}) == "599: no answer: timed out"
    assert br.signed_in(401, {"message": "Sign in again."}) == "401: Sign in again."
    assert br.signed_in(503, {}) == "503"
    assert br.signed_in(599, "no answer: [Errno 111] Connection refused") == "599: no answer: [Errno 111] Connection refused"
