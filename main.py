"""The whole builder in one command: a brief + the bank's tool API -> a tested phone agent on Freya, exported, with a trace.

    source env.sh
    python3 main.py <brief file or folder> <tool openapi.json> [options]

Steps (every step is written to the trace; nothing is edited by hand):
  1. EXTRACT      Claude reads every brief file and fills the CallSpec form (FREYA/builder, unchanged).
  2. CROSS-CHECK  a second model reads the raw brief on its own; the fields where the two readings disagree go back to
                  Claude, which re-reads the brief for exactly those fields and corrects the CallSpec where the brief says so.
  3. COMPILE      deterministic CallSpec -> workflow (FREYA/builder), lint, local run of every code snippet.
  4. PUBLISH v1   dryRun, save + publish, export. From here on a valid submission file always exists.
  5. LOCAL TEST   customers generated from the CallSpec (fixed for the whole run), the workflow emulated locally
                  (Gemini plays agent and customer), a fake bank, a judge model. No Freya simulation.
  6. FIX          failed customers -> Claude revises the CallSpec texts (FREYA/builder/test/fixer.py: never values) ->
                  recompile -> the same customers again. Kept only when more customers pass and none that passed fails.
  7. PUBLISH      the best version, if it is not v1; export to submission/<name>.workflow.json.

Options:
    --budget-min N     hard time budget for the whole run (default 25; the rules allow 30)
    --fix-rounds N     fix rounds after the local test (default 1; 0 = test and report only)
    --reps N           runs per generated customer in the local test (default 2)
    --parallel N       customers tested at the same time (default 8)
    --no-cross-check   skip step 2
    --no-test          skip steps 5 and 6
    --no-publish       offline: compile and test, never call Freya (development)
    --spec PATH        skip extraction, start from this CallSpec (development)
    --name NAME        slot and output name (default: the brief's folder or file name)
    --model NAME       Claude model for extraction and fixes (default claude-opus-5-5)
    --only 20,24       test only these generated customers (number or full id); the full set is kept in cases.all.json
    --claude-test      run the local test on the Claude subscription (claude CLI, Haiku) instead of Gemini; without it: Gemini

Needs: FREYA_API_KEY (+ FREYA_WORKSPACE_ID), a Claude login or ANTHROPIC_API_KEY, GEMINI_API_KEY for the local test,
OPENAI_API_KEY optional (cross-check and judge; Gemini otherwise). Without GEMINI_API_KEY steps 5-6 are skipped and v1 is submitted.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FREYA_DIR = ROOT / "FREYA"
TESTER = ROOT / "tester"
sys.path.insert(0, str(FREYA_DIR))
sys.path.insert(0, str(FREYA_DIR / "kit"))

from builder.compile.compiler import compile_workflow  # noqa: E402
from builder.compile.lint import lint  # noqa: E402
from builder.compile.selfcheck import check_snippets  # noqa: E402
from builder.extract.callspec import CallSpec  # noqa: E402
from builder.extract.extractor import _ask_claude, _brief_text, _schema_text, extract_callspec  # noqa: E402
from builder.extract.tools import field_map, lint_spec, parse_openapi  # noqa: E402
from builder.main import expand_briefs, freya_retry  # noqa: E402
from builder.trace import Trace  # noqa: E402

STATE_FILE = str(FREYA_DIR / ".freya-agents.json")      # the same slot is updated in place (the workspace holds 200 workflows)


# ----------------------------------------------------------------------------- helpers

class Budget:
    def __init__(self, minutes: float):
        self.deadline = time.time() + minutes * 60

    def left(self) -> float:
        return self.deadline - time.time()

    def allows(self, seconds: float) -> bool:
        return self.left() > seconds


def name_of(brief: str) -> str:
    """Same rule as FREYA/builder/build.py: the folder name, or the file stem (brief.md inside a folder -> the folder)."""
    bp = Path(brief)
    name = bp.name if bp.is_dir() else bp.stem
    if not bp.is_dir() and name.lower() in ("brief", "readme", "spec", "rules", "index"):
        name = bp.parent.name
    return name.removesuffix(".brief")


def finish_spec(spec: CallSpec, openapi: str, trace: Trace) -> CallSpec:
    spec.tools = parse_openapi(openapi)
    spec.field_map = field_map(openapi)
    for w in spec.field_map.get("warnings", []):
        trace.note(f"field map: {w}")
    return spec


def flat(o, p=""):
    """{dotted.path: leaf} of a JSON value, for a readable field-by-field diff in the trace."""
    if isinstance(o, dict):
        out = {}
        for k, v in o.items():
            out.update(flat(v, f"{p}.{k}" if p else k))
        return out
    if isinstance(o, list) and o and isinstance(o[0], dict):
        out = {}
        for i, v in enumerate(o):
            out.update(flat(v, f"{p}[{i}]"))
        return out
    return {p: o}


def save(path: Path, data) -> Path:
    """Every hand-over in the loop is kept as a file in the run folder (what was sent, what came back, what was decided)."""
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False, default=str))
    return path


def new_notes(old: CallSpec, new: CallSpec) -> list[str]:
    """The source_notes the model added: its own account of what it changed or kept, and why."""
    return [n for n in new.source_notes if n not in set(old.source_notes)]


def spec_changes(old: CallSpec, new: CallSpec) -> list[str]:
    skip = ("tools", "field_map", "source_notes")
    a = flat(json.loads(old.model_dump_json(exclude=set(skip))))
    b = flat(json.loads(new.model_dump_json(exclude=set(skip))))
    return [f"{k}: {json.dumps(a.get(k), ensure_ascii=False)[:80]} -> {json.dumps(b.get(k), ensure_ascii=False)[:80]}"
            for k in sorted(set(a) | set(b)) if a.get(k) != b.get(k)]


# ----------------------------------------------------------------------------- 1. extract

def extract(briefs: list[str], openapi: str, out: Path, trace: Trace, model: str) -> CallSpec:
    """FREYA's extractor. If its retries end with API mismatches it raises; a schema-valid CallSpec on disk is still a
    better start than no agent at all, so continue with it and leave the mismatches in the trace."""
    try:
        return extract_callspec(briefs, str(out), trace, model=model, openapi_path=openapi)
    except RuntimeError as e:
        if not out.exists():
            raise
        try:
            spec = CallSpec.model_validate_json(out.read_text())
        except ValueError:
            raise e
        trace.note(f"extraction: continuing with the last schema-valid CallSpec despite: {str(e)[:300]}")
        return spec


# ----------------------------------------------------------------------------- 2. cross-check

def cross_check(spec: CallSpec, brief_args: list[str], openapi: str, trace: Trace) -> list[tuple]:
    """A second, independent reading of the raw brief (tester/rule_diff.py, another model and prompt), compared field by
    field with the CallSpec. Returns (path, callspec value, second reading, source named by the second reader)."""
    sys.path.insert(0, str(TESTER))
    import llm
    import rule_diff
    text, names = rule_diff.read_material(brief_args)
    text += "\n\n===== TOOL API (openapi.json) =====\n" + Path(openapi).read_text()[:12000]
    t0 = time.time()
    model = os.environ.get("CROSSCHECK_MODEL", "claude-sonnet-5-5")      # strong, and not the extractor's model (independence)
    try:
        import claude_cli
        second = claude_cli.ask_json(rule_diff.PROMPT, text, model=model)
    except Exception as e:                                               # no claude CLI login: the tester's judge model instead
        trace.note(f"cross-check: {model} unavailable ({str(e)[:120]}); using the judge model")
        model = llm.model_of(llm.provider("judge"))
        second = json.loads(llm.generate("judge", rule_diff.PROMPT, [("user", text)], json_mode=True))
    trace.model_call(model=model, purpose=f"cross-check: second, independent reading of {', '.join(names)}", seconds=time.time() - t0)
    mine = rule_diff.from_callspec(json.loads(spec.model_dump_json()))
    src = second.get("sources") or {}
    return [(p, x, y, src.get(p.split(".")[0].split("[")[0], "")) for p, x, y in rule_diff.diff(mine, {k: second.get(k) for k in mine})]


RECHECK = """# Task: re-read the brief for the fields a second reader disagrees on

You extracted the CallSpec below from the brief. A second reader, with another model and another prompt, read the same
brief on its own and disagrees on the fields listed under "Disagreements". The second reader can be wrong too.

For EACH disagreement:
1. Re-read every brief document for that rule. Documents can contradict each other: a later-dated document (a memo, a
   later mail) replaces an earlier one (a policy) where they differ; a code list decides the exact outcome and reason codes.
2. Decide what the brief says. Change the CallSpec field only when the brief says something else than the CallSpec.
3. Add one `source_notes` entry per disagreement: "kept" or "changed", and the document and section that decide it.

Change nothing else. Keep the schema. Copy enum values exactly from the tool API.
Write the complete CallSpec JSON with the Write tool to the output path."""


def recheck(spec: CallSpec, rows: list[tuple], briefs: list[str], openapi: str, out: Path, trace: Trace, model: str) -> CallSpec | None:
    out = out.resolve()
    if out.exists():
        out.unlink()
    dis = "\n".join(f"- `{p}`: CallSpec has {json.dumps(x, ensure_ascii=False)}; second reader has {json.dumps(y, ensure_ascii=False)}"
                    + (f" (second reader's source: {s})" if s else "") for p, x, y, s in rows)
    prompt = (f"{RECHECK}\n\n## Output path\n{out}\n\n## Disagreements\n{dis}\n\n"
              f"## Current CallSpec\n```json\n{spec.model_dump_json(indent=1, exclude={'tools', 'field_map'})}\n```\n\n"
              f"## CallSpec JSON schema\n```json\n{_schema_text()}\n```\n\n## The brief files{_brief_text(briefs)}\n\n"
              f"## The bank's tool API\n```json\n{Path(openapi).read_text()}\n```\n")
    asyncio.run(_ask_claude(prompt, out, Path.cwd(), model, trace, purpose=f"re-read the brief for {len(rows)} field(s) the cross-check disputes"))
    if not out.exists():
        trace.note("cross-check: no revised CallSpec written; keeping v0")
        return None
    try:
        new = CallSpec.model_validate_json(out.read_text())
    except ValueError as e:
        trace.note(f"cross-check: revised CallSpec invalid ({str(e)[:200]}); keeping v0")
        return None
    new = finish_spec(new, openapi, trace)
    problems = lint_spec(new, new.tools, new.field_map)
    if problems:
        trace.note(f"cross-check: revised CallSpec has {len(problems)} API mismatch(es) ({problems[0][:150]}); keeping v0")
        return None
    return new


# ----------------------------------------------------------------------------- 3. compile, 4/7. publish

def compile_spec(spec: CallSpec, out: Path, trace: Trace, tag: str) -> dict:
    wf = compile_workflow(spec)
    problems = lint(wf) + check_snippets(wf)
    for p in problems:
        trace.note(f"lint {tag}: {p}")
    if any("syntax error" in p or "runtime error" in p for p in problems):
        raise SystemExit(f"generated code does not run ({tag}); aborting")    # a builder bug, not a brief problem
    out.write_text(json.dumps(wf, indent=1))
    trace.note(f"compiled {tag}: {len(wf['nodes'])} nodes -> {out}")
    return wf


def publish(wf: dict, slot: str, export: Path, trace: Trace, budget: Budget, tag: str) -> dict:
    import freya
    freya_retry(lambda: freya.validate_workflow(f"{slot} dryrun", wf), "dryRun", trace, budget.deadline)
    trace.note(f"dryRun valid ({tag})")
    ids = freya_retry(lambda: freya.save_workflow(slot, wf, state_file=STATE_FILE), "save", trace, budget.deadline)
    trace.created("workflow", wf, slot=slot, tag=tag, **ids)
    export.parent.mkdir(parents=True, exist_ok=True)
    freya_retry(lambda: freya.export_workflow(ids["workflow_id"], str(export)), "export", trace, budget.deadline)
    trace.note(f"exported {tag} -> {export}")
    return ids


# ----------------------------------------------------------------------------- 5. local test

def make_cases(spec_path: Path, openapi: str, out: Path, tag: str, trace: Trace) -> list[dict] | None:
    cmd = [sys.executable, str(TESTER / "cases_from_callspec.py"), str(spec_path), "--tag", tag, "--brief", tag,
           "--local-bank", "--openapi", openapi, "--out", str(out)]
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    if p.returncode != 0 or not out.exists():
        trace.note(f"case generation failed: {(p.stderr or p.stdout)[-400:]}")
        return None
    cases = json.loads(out.read_text())
    skipped = [line[9:].strip() for line in p.stdout.splitlines() if line.startswith("skipped:")]
    trace.note(f"test customers: {len(cases)} generated from the CallSpec (no model call; dates and amounts computed)"
               + (f"; {len(skipped)} template(s) skipped, rule not in this brief: {'; '.join(s[:60] for s in skipped)}" if skipped else ""))
    return cases


def local_run(wf_path: Path, cases_path: Path, openapi: str, reps: int, parallel: int, out: Path, trace: Trace, timeout_s: float, tag: str) -> dict | None:
    """tester/local_sim.py: emulated agent (Gemini) + generated customers (Gemini) + fake bank + judge. No Freya request."""
    cmd = [sys.executable, str(TESTER / "local_sim.py"), str(wf_path), "--agent", "local", "--bank", "local", "--cases", str(cases_path),
           "--openapi", openapi, "--reps", str(reps), "--parallel", str(parallel), "--out", str(out)]
    t0 = time.time()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT, timeout=max(60, timeout_s))
    except subprocess.TimeoutExpired:
        trace.note(f"local test {tag}: stopped after {int(timeout_s)} s (time budget); no result")
        return None
    usage = [line for line in p.stdout.splitlines() if line.startswith(("Gemini", "Claude", "OpenAI", "LLM cache")) or "audit:" in line]
    for line in usage:
        trace.note(f"local test {tag}: {line.strip()}")
    if not out.exists():
        trace.note(f"local test {tag}: no result (exit {p.returncode}): {(p.stderr or p.stdout)[-400:]}")
        return None
    r = json.loads(out.read_text())
    r["seconds"] = round(time.time() - t0)
    failed = [f"{f['id']} {f['passes']}/{f['runs']}" for f in r["final"] if not f["pass"]]
    trace.test(f"local test {tag} (generated customers, emulated agent, {reps} rep(s))", r["passed"], r["total"], r["seconds"], failed, simulation_id="local")
    return r


def passing(r: dict) -> set[str]:
    return {f["id"] for f in r["final"] if f["pass"]}


def failures_for_fixer(r: dict, cases: dict) -> list[dict]:
    """Local rows -> the failure records FREYA/builder/test/fixer.py expects (it was written for Freya's run_cases rows).
    Customers whose every run ended in an infrastructure error are left out: they say nothing about the agent."""
    out = []
    for f in r["final"]:
        if f["pass"]:
            continue
        rows = [x for x in r["rows"] if x["id"] == f["id"]]
        bad = [x for x in rows if x.get("status") == "FAIL"]
        if not bad:
            continue
        x, c = bad[0], cases.get(f["id"], {})
        out.append({"id": f["id"], "title": c.get("title", ""), "family": c.get("family", ""), "script": c.get("script", ""),
                    "checks": c.get("checks", []), "expected": c.get("expected", {}),
                    "failed": [f"(failed in {len(bad)} of {len(rows)} runs)"] + list(x.get("failed") or []),
                    "transcript": (x.get("transcript") or "")[-6000:]})
    return out


def with_agent_config(wf: dict, export: Path | None) -> dict:
    """The platform adds agent_config (model settings, the agent-level end_call tool) when it stores a workflow. The emulator
    reads it, so a candidate that is tested before it is published borrows it from the published export."""
    if export and export.exists():
        ac = json.loads(export.read_text()).get("workflow", {}).get("agent_config")
        if ac:
            return {**wf, "agent_config": ac}
    return wf


# ----------------------------------------------------------------------------- main

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("brief", help="brief file, or a folder of loose material (mails, memos, code lists)")
    ap.add_argument("openapi", help="the bank's tool API file")
    ap.add_argument("--name")
    ap.add_argument("--budget-min", type=float, default=25)
    ap.add_argument("--fix-rounds", type=int, default=1)
    ap.add_argument("--reps", type=int, default=2)
    ap.add_argument("--parallel", type=int, default=8)
    ap.add_argument("--no-cross-check", action="store_true")
    ap.add_argument("--no-test", action="store_true")
    ap.add_argument("--no-publish", action="store_true")
    ap.add_argument("--spec")
    ap.add_argument("--only", help="test only these generated customers: numbers (20,24) or full ids")
    ap.add_argument("--claude-test", action="store_true", help="local test on the Claude subscription (claude CLI) instead of Gemini")
    ap.add_argument("--model", default=os.environ.get("BUILDER_MODEL", "claude-opus-5-5"))
    a = ap.parse_args(argv)

    if a.claude_test:
        os.environ["LLM_BACKEND"] = "claude"             # read by tester/gemini.py and tester/llm.py in the test subprocesses
    else:
        os.environ.pop("LLM_BACKEND", None)              # default: Gemini, even if the shell has LLM_BACKEND set
    name = a.name or name_of(a.brief)
    briefs = expand_briefs([a.brief])
    openapi = str(Path(a.openapi).resolve())
    budget = Budget(a.budget_min)
    work = ROOT / "runs" / name / time.strftime("%Y%m%d-%H%M%S")
    work.mkdir(parents=True, exist_ok=True)
    export = ROOT / "submission" / f"{name}.workflow.json"
    trace = Trace(str(ROOT / "traces"), label=name)
    trace.note(f"main.py brief={a.brief} files={len(briefs)} openapi={a.openapi} name={name} model={a.model} budget_min={a.budget_min} "
               f"fix_rounds={a.fix_rounds} reps={a.reps} test_model={'claude subscription' if a.claude_test else 'gemini'} work={work}")

    # 1. extract
    if a.spec:
        spec = CallSpec.model_validate_json(Path(a.spec).read_text())
        trace.note(f"using CallSpec {a.spec} (no extraction)")
    else:
        spec = extract(briefs, openapi, work / "callspec.v0.json", trace, a.model)
    spec = finish_spec(spec, openapi, trace)
    (work / "callspec.v0.json").write_text(spec.model_dump_json(indent=1))

    # 2. cross-check
    if not a.no_cross_check and budget.allows(15 * 60):
        try:
            rows = cross_check(spec, [a.brief], openapi, trace)
            (work / "crosscheck.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False))
            trace.note(f"cross-check: {len(rows)} disagreement(s)" + "".join(f"\n    {p}: {json.dumps(x, ensure_ascii=False)[:70]} | {json.dumps(y, ensure_ascii=False)[:70]}" for p, x, y, _ in rows))
            if rows:
                save(work / "recheck.request.json", {"disagreements": [{"field": p, "callspec": x, "second_reader": y, "source": s} for p, x, y, s in rows]})
                new = recheck(spec, rows, briefs, openapi, work / "callspec.v1.json", trace, a.model)
                if new is not None:
                    changes = spec_changes(spec, new)
                    save(work / "recheck.result.json", {"accepted": True, "changes": changes, "notes": new_notes(spec, new)})
                    trace.note(f"cross-check: re-read changed {len(changes)} field(s)" + "".join(f"\n    {c}" for c in changes))
                    spec = new
                else:
                    save(work / "recheck.result.json", {"accepted": False, "changes": [], "notes": []})
        except Exception as e:                                   # the cross-check must never cost the run its agent
            trace.note(f"cross-check skipped: {type(e).__name__}: {str(e)[:200]}")
    spec_path = work / "callspec.json"
    spec_path.write_text(spec.model_dump_json(indent=1))

    # 3 + 4. compile and publish v1 (a valid submission exists from here on)
    wf = compile_spec(spec, work / "workflow.v1.json", trace, "v1")
    best = {"tag": "v1", "spec": spec, "wf": wf, "result": None}
    ids = None
    if not a.no_publish:
        ids = publish(wf, name, export, trace, budget, "v1")

    # 5. local test
    test_on = not a.no_test and bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("LLM_BACKEND") == "claude")
    if not a.no_test and not test_on:
        trace.note("local test skipped: neither GEMINI_API_KEY nor LLM_BACKEND=claude is set")
    cases = None
    if test_on and budget.allows(6 * 60):
        cases = make_cases(spec_path, openapi, work / "cases.json", re.sub(r"\W", "", name.upper())[:6] or "T", trace)
    if cases and a.only:
        want = [x.strip() for x in a.only.split(",") if x.strip()]
        pick = [c for c in cases if any(c["id"] == w or c["id"].endswith(f"-{w.zfill(2)}") for w in want)]
        save(work / "cases.all.json", cases)
        trace.note(f"--only {a.only}: testing {len(pick)} of {len(cases)} customers: " + "; ".join(f"{c['id']} {c['title']}" for c in pick))
        cases = pick
        save(work / "cases.json", cases)
    if cases:
        by_id = {c["id"]: c for c in cases}
        tpath = work / "workflow.v1.test.json"
        tpath.write_text(json.dumps(with_agent_config(wf, None if a.no_publish else export), indent=1))
        best["result"] = local_run(tpath, work / "cases.json", openapi, a.reps, a.parallel, work / "test.v1.json", trace, budget.left() - 90, "v1")

        # 6. fix rounds, on the same customers
        from builder.test.fixer import propose_fix
        for rnd in range(1, a.fix_rounds + 1):
            r = best["result"]
            if not r or r["passed"] == r["total"]:
                break
            fails = failures_for_fixer(r, by_id)
            if not fails:
                trace.note(f"fix {rnd}: every failure is an infrastructure error; nothing to fix")
                break
            last = r.get("seconds", 240)
            if not budget.allows(last + 3 * 60):
                trace.note(f"fix {rnd}: {int(budget.left())} s left, a fix and a retest need ~{last + 180} s; keeping {best['tag']}")
                break
            tag = f"fix{rnd}"
            save(work / f"{tag}.request.json", {"from": best["tag"], "failures": fails})
            trace.note(f"{tag}: sending {len(fails)} failed customer(s) to Claude ({', '.join(f['id'] for f in fails)})")
            new = propose_fix(best["spec"], fails, briefs, str(work / f"callspec.{tag}.json"), trace, model=a.model)
            if new is None:
                save(work / f"{tag}.result.json", {"changes": [], "notes": [], "verdict": "no revision (invalid, structural change, or platform noise only)"})
                break
            changes = spec_changes(best["spec"], new)
            save(work / f"{tag}.result.json", {"changes": changes, "notes": new_notes(best["spec"], new)})
            trace.note(f"{tag}: CallSpec changes ({len(changes)})" + "".join(f"\n    {c}" for c in changes[:25]))
            if not changes:
                break
            wf2 = compile_spec(new, work / f"workflow.{tag}.json", trace, tag)
            tpath = work / f"workflow.{tag}.test.json"
            tpath.write_text(json.dumps(with_agent_config(wf2, None if a.no_publish else export), indent=1))
            r2 = local_run(tpath, work / "cases.json", openapi, a.reps, a.parallel, work / f"test.{tag}.json", trace, budget.left() - 90, tag)
            if not r2:
                break
            old_p, new_p = passing(r), passing(r2)
            lost = sorted(old_p - new_p)
            save(work / f"{tag}.decision.json", {"before": f"{len(old_p)}/{r['total']}", "after": f"{len(new_p)}/{r2['total']}",
                                                 "gained": sorted(new_p - old_p), "lost": lost,
                                                 "accepted": len(new_p) > len(old_p) and not lost})
            if len(new_p) > len(old_p) and not lost:
                trace.note(f"{tag}: accepted, {len(old_p)}/{r['total']} -> {len(new_p)}/{r2['total']}")
                best = {"tag": tag, "spec": new, "wf": wf2, "result": r2}
            else:
                trace.note(f"{tag}: rejected, {len(old_p)}/{r['total']} -> {len(new_p)}/{r2['total']}" + (f", newly failing: {', '.join(lost)}" if lost else ", no gain") + f"; keeping {best['tag']}")
                break

    # 7. publish the best version if it is not v1
    if best["tag"] != "v1" and not a.no_publish:
        ids = publish(best["wf"], name, export, trace, budget, best["tag"])
    (work / "callspec.final.json").write_text(best["spec"].model_dump_json(indent=1))
    r = best["result"]
    summary = {"name": name, "version": best["tag"], "workflow_id": ids and ids["workflow_id"], "agent_id": ids and ids["agent_id"],
               "export": str(export) if ids else None, "local_test": f"{r['passed']}/{r['total']}" if r else "not run", "work": str(work)}
    trace.end(**summary)
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
