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
from .extract.tools import field_map, parse_openapi  # noqa: E402
from .trace import Trace  # noqa: E402


def run_cases(agent_id: str, brief: str, cases: str, out_json: Path, trace: Trace, style: str | None = None, only: list[str] | None = None, timeout_s: float | None = None) -> dict | None:
    """Run the kit's practice customers against the agent. Returns the parsed result or None."""
    cmd = [sys.executable, str(KIT / "tools" / "run_cases.py"), agent_id, "--brief", brief, "--cases", cases, "--out", str(out_json)]
    if style:
        cmd += ["--style", style]
    if only:
        cmd += ["--only", ",".join(only)]
    t0 = time.time()
    try:
        p = subprocess.run(cmd, cwd=KIT, capture_output=True, text=True, timeout=timeout_s)
    except subprocess.TimeoutExpired:
        trace.note(f"run_cases {brief}: stopped after {int(timeout_s or 0)} s (time budget); result discarded")
        return None
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
    trace.test(name=f"practice brief {brief}" + (f" style={style}" if style else ""), passed=r["passed"], total=r["total"], seconds=time.time() - t0, failed=failed, simulation_id=r.get("simulation_id", ""))
    return r


BRIEF_EXT = {".md", ".txt", ".pdf", ".docx", ".odt", ".rtf", ".pptx", ".xlsx", ".html", ".htm", ".json", ".csv"}


def expand_briefs(paths: list[str]) -> list[str]:
    """A brief may be a folder of loose material (emails, memos, code lists): take its files in name order, subfolders included."""
    out: list[str] = []
    for p in paths:
        pp = Path(p)
        if pp.is_dir():
            files = sorted(f for f in pp.rglob("*") if f.is_file() and f.suffix.lower() in BRIEF_EXT and not f.name.startswith("."))
            files = [f for f in files if "openapi" not in f.name.lower()]      # the tool API file is not brief text
            if not files:
                raise SystemExit(f"no brief files in folder {p}")
            out += [str(f) for f in files]
        else:
            out.append(p)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("briefs", nargs="+")
    ap.add_argument("--openapi", default=str(KIT / "tools" / "openapi.json"))
    ap.add_argument("--slot")
    ap.add_argument("--spec")
    ap.add_argument("--test", action="append", default=[])
    ap.add_argument("--cases", default=str(KIT / "public-test-set.json"))
    ap.add_argument("--budget-min", type=float, default=25)
    ap.add_argument("--fix-rounds", type=int, default=1, help="how many times the builder may revise the CallSpec after failed tests")
    ap.add_argument("--style", default=None, help="customer speaking style for the tests (pieces, corrects, talkative, asks_back, in_words)")
    ap.add_argument("--model", default=os.environ.get("BUILDER_MODEL", "claude-opus-5-5"))
    ap.add_argument("--out-dir", default=str(ROOT / "out"))
    ap.add_argument("--export", default=None, help="where to write the exported workflow (default out/<slot>.export.workflow.json)")
    a = ap.parse_args(argv)

    slot = a.slot or Path(a.briefs[0]).stem
    a.briefs = expand_briefs(a.briefs)
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
    spec.field_map = field_map(a.openapi)
    for w in spec.field_map.get('warnings', []):
        trace.note(f'field map: {w}')
    (out_dir / f"{slot}.callspec.json").write_text(spec.model_dump_json(indent=1))

    def compile_and_save(spec_now: CallSpec, tag: str) -> tuple[dict, dict]:
        wf = compile_workflow(spec_now)
        problems = lint(wf) + check_snippets(wf)
        for p in problems:
            trace.note(f"lint{tag}: {p}")
        if any("syntax error" in p or "runtime error" in p for p in problems):
            raise SystemExit("generated code does not run; aborting")  # a real builder bug, not a brief problem
        wf_path = out_dir / f"{slot}{tag}.workflow.json"
        wf_path.write_text(json.dumps(wf, indent=1))
        trace.note(f"compiled{tag} {len(wf['nodes'])} nodes -> {wf_path}")
        freya.validate_workflow(f"{slot} dryrun", wf)
        trace.note(f"dryRun valid{tag}")
        ids = freya.save_workflow(slot, wf, state_file=str(ROOT / ".freya-agents.json"))
        trace.created("workflow", wf, slot=slot, tag=tag or "v1", **ids)
        return wf, ids

    # 2+3. compile, check, validate, save
    wf, ids = compile_and_save(spec, "")
    agent_id = ids["agent_id"]

    # 4. tests (budget permitting)
    def run_tests(tag: str) -> dict:
        res = {}
        for brief in a.test:
            if time.time() > deadline - 60:
                trace.note(f"budget exhausted, skipping test {brief}")
                break
            res[brief] = run_cases(agent_id, brief, a.cases, out_dir / f"{slot}{tag}.test-{brief}.json", trace, style=a.style, timeout_s=max(30, deadline - time.time() - 45))
        return res

    def score(res: dict) -> tuple[int, int]:
        return (sum(r["passed"] for r in res.values() if r), sum(r["total"] for r in res.values() if r))

    results = run_tests("")

    # 4b. the builder's own fix loop: failed customers -> revised CallSpec -> recompile -> retest; keep the better one
    cases_by_id = {c["id"]: c for c in json.loads(Path(a.cases).read_text())}
    for rnd in range(1, a.fix_rounds + 1):
        passed, total = score(results)
        failures = [f for r in results.values() if r for f in __import__("builder.test.fixer", fromlist=["collect_failures"]).collect_failures(r, cases_by_id)]
        if not failures or passed == total:
            break
        if time.time() > deadline - 8 * 60:
            trace.note(f"fix round {rnd}: not enough budget left ({int((deadline - time.time()) / 60)} min); keeping v{rnd}")
            break
        from .test.fixer import propose_fix
        new_spec = propose_fix(spec, failures, a.briefs, str(out_dir / f"{slot}.callspec.fix{rnd}.json"), trace, model=a.model)
        if new_spec is None:
            break
        prev_wf = wf
        wf, ids = compile_and_save(new_spec, f".fix{rnd}")
        new_results = run_tests(f".fix{rnd}")
        np, nt = score(new_results)
        trace.note(f"fix round {rnd}: {passed}/{total} -> {np}/{nt}")
        if np >= passed:
            spec, results = new_spec, new_results
            (out_dir / f"{slot}.callspec.json").write_text(spec.model_dump_json(indent=1))
        else:
            ids = freya.save_workflow(slot, prev_wf, state_file=str(ROOT / ".freya-agents.json"))
            wf = prev_wf
            trace.created("workflow", prev_wf, slot=slot, tag=f"rollback after fix{rnd}", **ids)
            break

    # 5. export
    export_path = Path(a.export) if a.export else out_dir / f"{slot}.export.workflow.json"
    export_path.parent.mkdir(parents=True, exist_ok=True)
    freya.export_workflow(ids["workflow_id"], str(export_path))
    trace.note(f"exported {export_path}")
    trace.end(workflow_id=ids["workflow_id"], agent_id=agent_id, export=str(export_path),
              tests={k: (f"{v['passed']}/{v['total']}" if v else "failed") for k, v in results.items()})
    print(json.dumps({"workflow_id": ids["workflow_id"], "agent_id": agent_id, "export": str(export_path)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
