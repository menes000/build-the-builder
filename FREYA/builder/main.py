"""The builder. Brief file(s) + tool API -> a phone agent on Freya, exported to a file, with a trace.

    source env.sh
    python3 -m builder.main kit/briefs/brief-a.md --slot brief-a
    python3 -m builder.main kit/briefs/brief-a.md kit/briefs/brief-b.md --slot brief-ab --test B --test A

Options:
    --openapi PATH      the bank's tool API (default kit/tools/openapi.json)
    --slot NAME         Freya workflow slot; the same slot is updated in place (default: first brief's file name)
    --spec PATH         skip extraction, use this CallSpec JSON (development)
    --test A|B|...      run the kit's practice customers of that brief after building (repeatable)
    --cases PATH        case file for --test (default kit/public-test-set.json)
    --budget-min N      stop testing when this many minutes have passed (default 25)
    --model NAME        builder model for extraction (default claude-opus-5-5)
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KIT = ROOT / "kit"
sys.path.insert(0, str(KIT))

from .compile.compiler import compile_workflow  # noqa: E402
from .compile.lint import lint  # noqa: E402
from .compile.selfcheck import check_snippets  # noqa: E402
from .extract.callspec import CallSpec  # noqa: E402
from .extract.tools import parse_openapi  # noqa: E402
from .trace import Trace  # noqa: E402


def run_cases(agent_id: str, brief: str, cases: str, out_json: Path, trace: Trace) -> dict | None:
    """Run the kit's practice customers against the agent. Returns the parsed result or None."""
    cmd = [sys.executable, str(KIT / "tools" / "run_cases.py"), agent_id, "--brief", brief, "--cases", cases, "--out", str(out_json)]
    t0 = time.time()
    p = subprocess.run(cmd, cwd=KIT, capture_output=True, text=True)
    sys.stdout.write(p.stdout)
    if p.returncode != 0:
        trace.note(f"run_cases {brief} failed: {p.stderr[-500:]}")
        return None
    try:
        r = json.loads(out_json.read_text())
    except Exception as e:
        trace.note(f"run_cases {brief}: could not read results: {e}")
        return None
    failed = [f"{row['id']}: {'; '.join(row['failed'])[:200]}" for row in r.get("rows", []) if not row.get("pass")]
    trace.test(name=f"practice brief {brief}", passed=r["passed"], total=r["total"], seconds=time.time() - t0, failed=failed, simulation_id=r.get("simulation_id", ""))
    return r


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("briefs", nargs="+")
    ap.add_argument("--openapi", default=str(KIT / "tools" / "openapi.json"))
    ap.add_argument("--slot")
    ap.add_argument("--spec")
    ap.add_argument("--test", action="append", default=[])
    ap.add_argument("--cases", default=str(KIT / "public-test-set.json"))
    ap.add_argument("--budget-min", type=float, default=25)
    ap.add_argument("--model", default=os.environ.get("BUILDER_MODEL", "claude-opus-5-5"))
    ap.add_argument("--out-dir", default=str(ROOT / "out"))
    a = ap.parse_args(argv)

    slot = a.slot or Path(a.briefs[0]).stem
    out_dir = Path(a.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    trace = Trace(str(ROOT / "traces"), label=slot)
    trace.note(f"briefs={a.briefs} openapi={a.openapi} slot={slot} model={a.model} budget_min={a.budget_min}")
    deadline = time.time() + a.budget_min * 60

    import freya  # the kit's client

    # 1. extract
    if a.spec:
        spec = CallSpec.model_validate_json(Path(a.spec).read_text())
        trace.note(f"using CallSpec from {a.spec} (no extraction)")
    else:
        from .extract.extractor import extract_callspec
        spec = extract_callspec(a.briefs, str(out_dir / f"{slot}.callspec.json"), trace, model=a.model, openapi_path=a.openapi)
    spec.tools = parse_openapi(a.openapi)
    (out_dir / f"{slot}.callspec.json").write_text(spec.model_dump_json(indent=1))

    # 2. compile + check
    wf = compile_workflow(spec)
    problems = lint(wf) + check_snippets(wf)
    for p in problems:
        trace.note(f"lint: {p}")
    if any("syntax error" in p or "runtime error" in p for p in problems):
        raise SystemExit("generated code does not run; aborting")  # a real builder bug, not a brief problem
    wf_path = out_dir / f"{slot}.workflow.json"
    wf_path.write_text(json.dumps(wf, indent=1))
    trace.note(f"compiled {len(wf['nodes'])} nodes -> {wf_path}")

    # 3. validate + save on Freya
    freya.validate_workflow(f"{slot} dryrun", wf)
    trace.note("dryRun valid")
    ids = freya.save_workflow(slot, wf, state_file=str(ROOT / ".freya-agents.json"))
    trace.created("workflow", slot=slot, **ids)
    agent_id = ids["agent_id"]

    # 4. tests (budget permitting)
    results = {}
    for brief in a.test:
        if time.time() > deadline - 60:
            trace.note(f"budget exhausted, skipping test {brief}")
            break
        results[brief] = run_cases(agent_id, brief, a.cases, out_dir / f"{slot}.test-{brief}.json", trace)

    # 5. export
    export_path = out_dir / f"{slot}.export.workflow.json"
    freya.export_workflow(ids["workflow_id"], str(export_path))
    trace.note(f"exported {export_path}")
    trace.end(workflow_id=ids["workflow_id"], agent_id=agent_id, export=str(export_path),
              tests={k: (f"{v['passed']}/{v['total']}" if v else "failed") for k, v in results.items()})
    print(json.dumps({"workflow_id": ids["workflow_id"], "agent_id": agent_id, "export": str(export_path)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
