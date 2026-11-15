"""eax estimate (R5.19): the server sizing estimate from the command line, the same as System Admin > Sizing. It needs
nothing running: it reads the sizing model (services/api/eax/sizing.py) straight from this folder.

  eax estimate --users N --models N [--size small|medium|large] --projects N [--documents N] [--no-reports]
               [--no-documents] [--backups N] [--headroom 0.3] [--node-gb 16 --node-cores 4] [--override FILE] [--json]

--override FILE writes the compose override (each service's limits and the API's copies) to paste beside
docker-compose.yml; --json prints the whole answer. Always a best estimate: it says so and lists its assumptions.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from .core import Failure

FLAGS = {"--users": "users", "--models": "models", "--size": "model_size", "--projects": "projects",
         "--documents": "documents_per_project", "--backups": "backups_kept", "--headroom": "headroom",
         "--node-gb": "node_gb", "--node-cores": "node_cores"}


def load():
    """The sizing model (services/api/eax/sizing.py), loaded from this folder."""
    path = Path(__file__).resolve().parents[1] / "services/api/eax/sizing.py"
    spec = importlib.util.spec_from_file_location("eax_sizing", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod                 # its dataclasses look themselves up there
    spec.loader.exec_module(mod)
    return mod


def parse(rest: list[str]) -> tuple[dict, str, bool]:
    """eax estimate's options as the estimate's inputs."""
    inputs, out, as_json, i = {}, "", False, 0
    while i < len(rest):
        a = rest[i]
        if a in FLAGS and i + 1 < len(rest):
            inputs[FLAGS[a]] = rest[i + 1]
            i += 2
            continue
        if a == "--override" and i + 1 < len(rest):
            out, i = rest[i + 1], i + 2
            continue
        if a in ("--no-reports", "--no-documents", "--no-mcp", "--no-discovery"):
            inputs[a.removeprefix("--no-")] = False
        elif a == "--json":
            as_json = True
        else:
            raise Failure(f"eax estimate: {a} is not known (eax help estimate)")
        i += 1
    return inputs, out, as_json


def main(rest: list[str]) -> int:
    """eax estimate: the server sizing estimate, printed (and the compose override written when asked)."""
    inputs, out, as_json = parse(rest)
    s = load()
    try:
        r = s.estimate(inputs)
    except ValueError as exc:
        raise Failure(f"eax estimate: {exc}") from exc
    print(json.dumps(r, indent=1) if as_json else s.text_report(r))
    if out:
        Path(out).write_text(r["override"], encoding="utf-8")
        print(f"The compose override: {out} (docker compose -f docker-compose.yml -f {out} ...)")
    return 0
