// EA Explorer's benchmark load test (R5.18, D695), run by the operations helper in k6's own container (grafana/k6) after
// the self-test's runner has filled the run's test model and timed each read alone. USERS people at once for MINUTES,
// each making the reads of the plan (bench-plan.json: the same paths the runner timed) in turn, as the run's own test
// users (TOKENS, one per person in turn). Reads only: nothing is changed. The summary is written to OUT as
// {users, minutes, requests, per_second, p50_ms, p95_ms, p99_ms, error_rate, by_path} for the run's judge.
import http from 'k6/http';
import { check, sleep } from 'k6';

const PLAN = JSON.parse(open(__ENV.PLAN || '/bench/bench-plan.json'));
const TARGET = (__ENV.TARGET || PLAN.target || 'https://proxy').replace(/\/$/, '');
const TOKENS = (__ENV.TOKENS || '').split(',').filter((t) => t);
const USERS = Number.parseInt(__ENV.USERS || PLAN.users || '20', 10);
const MINUTES = Number.parseFloat(__ENV.MINUTES || PLAN.minutes || '2');
const PATHS = PLAN.paths || ['/api/v1/me'];

export const options = {
  insecureSkipTLSVerify: true,              // the front door's own certificate on a laptop
  summaryTrendStats: ['avg', 'min', 'med', 'max', 'p(95)', 'p(99)'],
  scenarios: {
    people: {
      executor: 'ramping-vus',
      startVUs: 1,
      stages: [
        { duration: `${Math.max(1, Math.round(MINUTES * 60 * 0.2))}s`, target: USERS },
        { duration: `${Math.max(1, Math.round(MINUTES * 60 * 0.7))}s`, target: USERS },
        { duration: `${Math.max(1, Math.round(MINUTES * 60 * 0.1))}s`, target: 0 },
      ],
      gracefulRampDown: '20s',
    },
  },
};

export default function () {
  const token = TOKENS.length ? TOKENS[(__VU - 1) % TOKENS.length] : '';
  for (const p of PATHS) {
    const r = http.get(`${TARGET}${p}`, { headers: { Authorization: `Bearer ${token}`, Accept: 'application/json' },
      tags: { name: p.split('?')[0] } });
    check(r, { 'answered': (x) => x.status > 0 && x.status < 400 });
    // a person reads before the next click: 0.5 to 1.5 s, spread by the virtual user and its round, the same each run
    // (SonarQube S2245: a random number cannot be told from a security use)
    sleep(0.5 + ((__VU * 7919 + __ITER * 104729) % 1000) / 1000);
  }
}

export function handleSummary(data) {
  const d = data.metrics.http_req_duration ? data.metrics.http_req_duration.values : {};
  const f = data.metrics.http_req_failed ? data.metrics.http_req_failed.values : {};
  const n = data.metrics.http_reqs ? data.metrics.http_reqs.values : {};
  const round = (v) => Math.round((v || 0) * 10) / 10;
  const out = {
    users: USERS, minutes: MINUTES, requests: n.count || 0, per_second: round(n.rate),
    p50_ms: round(d.med), p95_ms: round(d['p(95)']), p99_ms: round(d['p(99)']), max_ms: round(d.max),
    error_rate: Math.round((f.rate || 0) * 10000) / 10000,
  };
  return { [__ENV.OUT || '/bench/bench-load.json']: JSON.stringify(out), stdout: JSON.stringify(out) + '\n' };
}
