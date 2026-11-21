// The {name} parts of an API path (the API harness, D804: no slow regular expression).

// every {name} of a path as [start, end, name], as /\{([^}]+)\}/g found them, without its slow cases (D804)
export function braces(path) {
  const out = [];
  let i = 0;
  while ((i = path.indexOf("{", i)) !== -1) {
    const j = path.indexOf("}", i + 1);
    if (j === -1) break;
    if (j > i + 1) { out.push([i, j + 1, path.slice(i + 1, j)]); i = j + 1; } else i += 1;
  }
  return out;
}

export function pathParams(path) {
  return braces(String(path || "")).map(([, , name]) => name.split(":").pop());
}

export function filledPath(path, values) {
  const p = String(path || "");
  let out = "", at = 0;
  for (const [a, b, name] of braces(p)) {
    const v = values[name.split(":").pop()];
    out += p.slice(at, a) + (v ? encodeURIComponent(v) : p.slice(a, b));
    at = b;
  }
  return out + p.slice(at);
}
