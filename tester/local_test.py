"""One call for a builder's self-test: CallSpec + exported workflow -> generated cases -> local run -> JSON summary.

    source env.sh
    python3 tester/local_test.py --callspec out/<slot>.callspec.json --export out/<slot>.export.workflow.json --out results/<slot>-localtest.json
                                 [--openapi final/x/openapi.json] [--reps 1] [--parallel 6] [--tag H1] [--only ID,ID]

Prints one line per case and a summary; exit code 0 when every case passes in every rep, 1 otherwise, 2 on an infrastructure error.
The --out JSON:
  {"passed": n, "total": m, "reps": r, "seconds": s, "cases_file": "...", "skipped_templates": [...],
   "rows": [{"id", "rep", "status": "PASS|FAIL|ERROR", "failed": [...], "flags": [...], "judge_reason", "transcript", "path", "record"}],
   "final": [{"id", "passes", "runs", "pass"}], "usage": {...}}
A builder can parse "rows" for its fix loop (id, failed, transcript) and write "passed/total" into its trace.
Needs GEMINI_API_KEY (customer + agent model) and, optionally, OPENAI_API_KEY (extraction + judge). No Freya request is made.
"""
import argparse, json, pathlib, subprocess, sys, time

ROOT = pathlib.Path(__file__).resolve().parent.parent
T = ROOT / "tester"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--callspec", required=True); ap.add_argument("--export", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--openapi"); ap.add_argument("--reps", type=int, default=1); ap.add_argument("--parallel", type=int, default=6)
    ap.add_argument("--tag", default="LT"); ap.add_argument("--only"); ap.add_argument("--accounts")
    a = ap.parse_args()
    t0 = time.time(); out = pathlib.Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    cases = out.with_name(out.stem + "-cases.json")
    cmd = [sys.executable, str(T / "cases_from_callspec.py"), a.callspec, "--tag", a.tag, "--brief", a.tag, "--local-bank", "--out", str(cases)]
    if a.accounts: cmd += ["--accounts", a.accounts]
    gen = subprocess.run(cmd, capture_output=True, text=True)
    if gen.returncode != 0:
        print(gen.stdout[-2000:], gen.stderr[-2000:]); json.dump({"error": "case generation failed", "detail": gen.stderr[-2000:]}, open(out, "w")); sys.exit(2)
    skipped = [l[9:].strip() for l in gen.stdout.splitlines() if l.startswith("skipped:")]
    print(f"cases: {len(json.load(open(cases)))} from {a.callspec}" + (f"; skipped templates: {len(skipped)}" if skipped else ""))
    run_out = out.with_name(out.stem + "-run.json")
    cmd = [sys.executable, str(T / "local_sim.py"), a.export, "--agent", "local", "--bank", "local", "--cases", str(cases), "--reps", str(a.reps), "--parallel", str(a.parallel), "--out", str(run_out)]
    if a.only: cmd += ["--only", a.only]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for line in p.stdout:
        if line.startswith(("PASS", "FAIL", "ERROR", "       -", "       !")) or "passed" in line or "usage" in line: print(line.rstrip())
    p.wait()
    if not run_out.exists(): json.dump({"error": "local run produced no output"}, open(out, "w")); sys.exit(2)
    r = json.load(open(run_out))
    rows = [{k: x.get(k) for k in ("id", "rep", "status", "failed", "flags", "judge_reason", "transcript", "path", "record", "tools")} for x in r["rows"]]
    summary = {"passed": r["passed"], "total": r["total"], "reps": a.reps, "seconds": round(time.time() - t0), "cases_file": str(cases),
               "skipped_templates": skipped, "rows": rows, "final": r["final"], "export": a.export, "callspec": a.callspec}
    json.dump(summary, open(out, "w"), indent=1)
    errors = sum(1 for x in rows if x["status"] == "ERROR")
    print(f"\nlocal test: {r['passed']}/{r['total']} pass in every rep, {errors} error(s), {summary['seconds']} s -> {out}")
    sys.exit(0 if r["passed"] == r["total"] else (2 if errors and r["passed"] + errors >= r["total"] else 1))


if __name__ == "__main__":
    main()
