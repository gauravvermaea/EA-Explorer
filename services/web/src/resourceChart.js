// The resource history's charts (R3.5-M8; Footprint.jsx): plain functions, tested with node.

export const PERIODS = [["6h", "6 hours", 0.25], ["1d", "1 day", 1], ["7d", "7 days", 7], ["30d", "30 days", 30], ["90d", "90 days", 90]];
export const EVERY = [0, 1, 5, 10, 15, 30, 60];      // the choices offered; the API takes any 0 to 1440

// The charts drawn from the history's points: [key, title, fields [[field, label]], unit, fixed top (or null)]
export const CHARTS = [
  ["memory", "Memory, the whole installation", [["memory_peak_mb", "peak"], ["memory_mb", "average"]], "MB", null],
  ["cpu", "CPU, a share of the host", [["cpu_percent", "CPU"]], "%", 100],
  ["host", "Docker host: memory left and swap in use", [["available_mb", "left"], ["swap_used_mb", "swap"]], "MB", null],
  ["cache", "Database cache: blocks found in memory", [["cache_hit_percent", "hit rate"]], "%", 100],
  ["disk", "Disk: the fullest file system", [["disk_used_percent", "used"]], "%", 100],
];

// a nice top for the axis: 1, 2 or 5 times a power of ten at or above the largest value
export function niceTop(max) {
  if (!(max > 0)) return 1;
  const p = 10 ** Math.floor(Math.log10(max));
  for (const m of [1, 2, 5, 10]) if (m * p >= max) return m * p;
  return 10 * p;
}

// The lines of one chart: each field as an SVG path over [0, width] x [0, height], times placed by when they were
// taken (a gap in the history stays a gap: the line breaks where a sample is missing for more than three intervals).
export function lines(points, fields, { width = 720, height = 140, top = null } = {}) {
  const t = points.map((p) => Date.parse(p.at));
  const t0 = Math.min(...t), t1 = Math.max(...t);
  const values = points.flatMap((p) => fields.map(([f]) => p[f])).filter((v) => typeof v === "number");
  const yTop = top || niceTop(Math.max(0, ...values));
  const x = (i) => (t1 > t0 ? ((t[i] - t0) / (t1 - t0)) * width : width / 2);
  const y = (v) => height - (Math.max(0, Math.min(v, yTop)) / yTop) * height;
  const steps = t.slice(1).map((v, i) => v - t[i]).filter((d) => d > 0).sort((a, b) => a - b);
  const usual = steps.length ? steps[Math.floor(steps.length / 2)] : 0;
  const paths = fields.map(([f, label]) => {
    let d = "", up = false;
    points.forEach((p, i) => {
      const v = p[f];
      const gap = i > 0 && usual > 0 && t[i] - t[i - 1] > usual * 3;
      if (typeof v !== "number") { up = false; return; }
      d += `${up && !gap ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`;
      up = true;
    });
    return { field: f, label, d };
  });
  // the stretches during a self-test, a backup, a restore or a start-up, shaded behind the lines
  const bands = [];
  points.forEach((p, i) => {
    if (!(p.activity || []).length) return;
    const what = p.activity.join(", ");
    const last = bands[bands.length - 1];
    const half = usual ? (usual / 2 / Math.max(1, t1 - t0)) * width : 2;
    if (last && last.what === what && last.end === i - 1) { last.x1 = Math.min(width, x(i) + half); last.end = i; }
    else bands.push({ what, x0: Math.max(0, x(i) - half), x1: Math.min(width, x(i) + half), end: i });
  });
  return { paths, bands, top: yTop, from: points.length ? points[0].at : null, to: points.length ? points[points.length - 1].at : null };
}

// the containers by their highest memory, biggest first: [{name, average, peak, cpuPeak}]
export function containerTable(series) {
  return Object.entries(series || {}).map(([name, pts]) => {
    const mem = pts.map((p) => p.memory_mb).filter((v) => typeof v === "number");
    return { name, average: mem.length ? Math.round((mem.reduce((a, b) => a + b, 0) / mem.length) * 10) / 10 : null,
      peak: Math.max(0, ...pts.map((p) => p.memory_peak_mb || 0)), cpuPeak: Math.max(0, ...pts.map((p) => p.cpu_percent || 0)) };
  }).sort((a, b) => b.peak - a.peak);
}

// the query for a period: one of PERIODS, or from and to (datetime-local values, the browser's time, sent as UTC)
export function periodQuery(key, from = "", to = "") {
  if (key === "custom" && from && to) return `from=${encodeURIComponent(new Date(from).toISOString())}&to=${encodeURIComponent(new Date(to).toISOString())}`;
  const p = PERIODS.find(([k]) => k === key) || PERIODS[1];
  return `days=${p[2]}`;
}

// what a delete would remove, said before it is done: [query, sentence]
export function deleteChoice(kind, data, before = "") {
  if (kind === "period") return [`from=${encodeURIComponent(data.from)}&to=${encodeURIComponent(data.to)}`, "the samples of the period shown"];
  if (kind === "before" && before) return [`to=${encodeURIComponent(new Date(before).toISOString())}`, `every sample before ${before.replace("T", " ")}`];
  if (kind === "all") return ["", "the whole resource history"];
  return null;
}
