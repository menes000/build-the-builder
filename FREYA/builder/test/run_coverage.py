"""Run coverage cases (kit format + `session_case`) with the kit's own runner. The bank mock only knows PUB ids,
so each case borrows a PUB account via `session_case`; the case keeps its own id, script, checks and expected ledger.

    source env.sh && python3 builder/test/run_coverage.py <agent_id> --cases <file> [--only OUR-13,OUR-24] [--reps N] [--style S] [--out F]
"""
import pathlib, sys
KIT = pathlib.Path(__file__).resolve().parents[2] / "kit"
sys.path.insert(0, str(KIT)); sys.path.insert(0, str(KIT / "tools"))
src = (KIT / "tools" / "run_cases.py").read_text().replace(
    'http("/v1/practice/sessions", {"case": c["id"]})',
    'http("/v1/practice/sessions", {"case": c.get("session_case", c["id"])})')
assert 'session_case' in src, "runner patch did not apply"
sys.argv[0] = "run_cases.py"
import os; os.chdir(KIT)
exec(compile(src, "run_cases.py", "exec"), {"__name__": "__main__", "__file__": str(KIT / "tools" / "run_cases.py")})
