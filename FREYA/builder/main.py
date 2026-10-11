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
from .extract.tools import field_map, find_openapi, is_openapi, parse_openapi  # noqa: E402
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


BRIEF_EXT = {".md", ".txt", ".pdf", ".docx", ".doc", ".odt", ".rtf", ".pptx", ".xlsx", ".html", ".htm", ".json", ".csv",
             ".yaml", ".yml", ".png", ".jpg", ".jpeg", ".gif", ".webp"}


def freya_retry(fn, what: str, trace: Trace, deadline: float, tries: int = 8, wait_s: float = 15):
    """Freya's API answers 502/503/504 or times out for a minute or two now and then. Retry instead of losing the run."""
    import urllib.error
    for i in range(1, tries + 1):
        try:
            return fn()
        except (RuntimeError, urllib.error.URLError, TimeoutError, OSError) as e:
            msg = str(e)
            transient = any(code in msg for code in ("502", "503", "504", "timed out", "Connection", "temporarily unavailable"))
            if not transient or i == tries or time.time() + wait_s > deadline:
                raise
            trace.note(f"{what}: Freya answered '{msg[:80]}', retry {i}/{tries - 1} in {wait_s:.0f} s")
            time.sleep(wait_s)
            wait_s = min(wait_s * 1.5, 60)


def expand_briefs(paths: list[str]) -> list[str]:
    """A brief may be a folder of loose material (emails, memos, code lists): take its files in name order, subfolders included."""
    out: list[str] = []
    for p in paths:
        pp = Path(p)
        if pp.is_dir():
            files = sorted(f for f in pp.rglob("*") if f.is_file() and f.suffix.lower() in BRIEF_EXT and not f.name.startswith("."))
            files = [f for f in files if "openapi" not in f.name.lower() and not is_openapi(f)]      # the tool API file is not brief text
            if not files:
                raise SystemExit(f"no brief files in folder {p}")
            out += [str(f) for f in files]
        else:
            out.append(p)
    return out


def local_test(spec_path: Path, export_path: Path, out_path: Path, openapi: str, slot: str, trace: Trace, timeout_s: float) -> dict | None:
    """The team's own coverage test on the finished agent (report only). tester/ lives at the repo root, next to FREYA/."""
    runner = next((p for p in (ROOT / "tester" / "local_test.py", ROOT.parent / "tester" / "local_test.py") if p.exists()), None)
    if runner is None:
        trace.note("local test skipped: tester/local_test.py not found")
        return None
    if not os.environ.get("GEMINI_API_KEY"):
        trace.note("local test skipped: GEMINI_API_KEY not set")
        return None
    cmd = [sys.executable, str(runner), "--callspec", str(spec_path), "--export", str(export_path), "--out", str(out_path), "--openapi", openapi, "--tag", slot]
    t0 = time.time()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=max(60, timeout_s), cwd=str(runner.parent.parent))
    except subprocess.TimeoutExpired:
        trace.note(f"local test stopped: over the time budget after {round(time.time() - t0)} s")
        return None
    tail = (p.stdout.strip().splitlines() or [""])[-1][:200]
    try:
        res = json.loads(out_path.read_text())
    except Exception:
        trace.note(f"local test gave no result (exit {p.returncode}): {tail} {p.stderr.strip()[-300:]}")
        return None
    if "error" in res:
        trace.note(f"local test error: {str(res.get('error'))[:200]} {str(res.get('detail', ''))[-200:]}")
        return None
    failed = sorted({f"{r['id']}: {'; '.join(r.get('failed') or [])[:160]}" for r in res.get("rows", []) if r.get("status") != "PASS"})
    trace.test("local coverage (team tester, report only)", res.get("passed", 0), res.get("total", 0), res.get("seconds", time.time() - t0), failed, simulation_id="local")
    if res.get("skipped_templates"):
        trace.note(f"local test: {len(res['skipped_templates'])} case templates skipped (rule not in this brief)")
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("briefs", nargs="+")
    ap.add_argument("--openapi", default=None, help="the bank's tool API file (default: an OpenAPI file inside the case folder, else the kit's)")
    ap.add_argument("--mock-url", default=None, help="the team's own mock of the bank's services: every tool calls this address")
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
    ap.add_argument("--local-test", action="store_true", help="after the export, run the team's local coverage test (tester/local_test.py: cases generated from the CallSpec, local emulator, no Freya request) and record the result in the trace; report only, nothing is changed")
    a = ap.parse_args(argv)

    slot = a.slot or Path(a.briefs[0]).stem
    case_inputs = list(a.briefs)
    a.briefs = expand_briefs(a.briefs)
    out_dir = Path(a.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    trace = Trace(str(ROOT / "traces"), label=slot)
    deadline = time.time() + a.budget_min * 60
    if not a.openapi:
        # the tool API: an OpenAPI file in the case folder; else (mock mode) written from the service contract; else the kit's
        found = find_openapi(case_inputs)
        if found:
            a.openapi = str(found)
            trace.note(f"tool API found in the case material: {found}")
        elif a.mock_url and not a.spec:
            from .extract.contract import contract_to_openapi
            a.openapi = str(contract_to_openapi(a.briefs, str(out_dir / f"{slot}.openapi.json"), trace, model=a.model))
        else:
            a.openapi = str(KIT / "tools" / "openapi.json")
    trace.note(f"briefs={a.briefs} openapi={a.openapi} mock_url={a.mock_url} slot={slot} model={a.model} budget_min={a.budget_min}")

    import freya  # the kit's client

    # 1. extract
    if a.spec:
        spec = CallSpec.model_validate_json(Path(a.spec).read_text())
        trace.note(f"using CallSpec from {a.spec} (no extraction)")
    else:
        from .extract.extractor import extract_callspec
        spec = extract_callspec(a.briefs, str(out_dir / f"{slot}.callspec.json"), trace, model=a.model, openapi_path=a.openapi)
    spec.tools = parse_openapi(a.openapi, base_url=a.mock_url)
    if a.mock_url:
        trace.note(f"tools call the team's mock: {', '.join(t.name + ' ' + t.url for t in spec.tools)}")
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
        freya_retry(lambda: freya.validate_workflow(f"{slot} dryrun", wf), "dryRun", trace, deadline)
        trace.note(f"dryRun valid{tag}")
        ids = freya_retry(lambda: freya.save_workflow(slot, wf, state_file=str(ROOT / ".freya-agents.json")), "save", trace, deadline)
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
            ids = freya_retry(lambda: freya.save_workflow(slot, prev_wf, state_file=str(ROOT / ".freya-agents.json")), "save (rollback)", trace, deadline)
            wf = prev_wf
            trace.created("workflow", prev_wf, slot=slot, tag=f"rollback after fix{rnd}", **ids)
            break

    # 5. export
    export_path = Path(a.export) if a.export else out_dir / f"{slot}.export.workflow.json"
    export_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        # the export is the submission file: it gets its own retry window (up to 8 minutes), whatever the test budget left
        freya_retry(lambda: freya.export_workflow(ids["workflow_id"], str(export_path)), "export", trace, time.time() + 480, tries=12)
        trace.note(f"exported {export_path}")
        if a.mock_url and not a.local_test:
            trace.note("local test skipped: mock mode (the local fake bank speaks the practice API, not the team's mock)")
        if a.local_test:
            lt = local_test(out_dir / f"{slot}.callspec.json", export_path, out_dir / f"{slot}.localtest.json", a.openapi, slot, trace, deadline - time.time() - 30)
            if lt and "passed" in lt:
                results["local"] = {"passed": lt["passed"], "total": lt["total"]}
    finally:
        trace.end(workflow_id=ids["workflow_id"], agent_id=agent_id, export=str(export_path) if export_path.exists() else "NOT WRITTEN",
                  tests={k: (f"{v['passed']}/{v['total']}" if v else "failed") for k, v in results.items()})
    print(json.dumps({"workflow_id": ids["workflow_id"], "agent_id": agent_id, "export": str(export_path)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
