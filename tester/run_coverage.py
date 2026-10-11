"""The organisers' runner (kit/tools/run_cases.py: Freya simulation + Freya judge) on our coverage cases, unchanged except that
a case may borrow a PUB bank account (`session_case`) and bring its own call variables (`variables.now`...).

    source env.sh
    python3 tester/run_coverage.py <agent_id> --cases tester/coverage-cases.json --out results/coverage-freya.json [--only OUR-01,OUR-02] [--reps 2]

Uses the shared workspace's simulation queue (one simulation at a time): check nobody else is running one.
"""
import pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent


def kit_dir(root):
    """The organisers' kit: FREYA_KIT_DIR, or <root>/kit (Dora's layout), or <root>/docs/build-the-builder (ours)."""
    import os
    for p in (os.environ.get("FREYA_KIT_DIR"), root / "kit", root / "docs" / "build-the-builder"):
        if p and pathlib.Path(p).exists(): return pathlib.Path(p)
    raise SystemExit("kit not found: set FREYA_KIT_DIR")

KIT = kit_dir(ROOT)
sys.path.insert(0, str(KIT)); sys.path.insert(0, str(KIT / "tools"))

HELPER = '''
def session_for(c):
    """A fresh bank session for the borrowed PUB account; the case's own call variables (e.g. now) win, customer_id never."""
    v = http("/v1/practice/sessions", {"case": c.get("session_case", c["id"])})["variables"]
    v.update({k: x for k, x in (c.get("variables") or {}).items() if k != "customer_id" and x not in (None, "")})
    return v

'''
OLD = 'http("/v1/practice/sessions", {"case": c["id"]})["variables"]'


def rewritten():
    src = (KIT / "tools" / "run_cases.py").read_text()
    assert src.count(OLD) == 1 and "\ndef run_once(" in src, "run_cases.py changed; update run_coverage.py"
    return src.replace(OLD, "session_for(c)").replace("\ndef run_once(", HELPER + "def run_once(", 1)


if __name__ == "__main__":
    sys.argv[0] = "run_cases.py"
    exec(compile(rewritten(), "run_cases.py", "exec"), {"__name__": "__main__", "__file__": str(KIT / "tools" / "run_cases.py")})
