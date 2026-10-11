"""Run the kit's tools/run_cases.py unchanged, but with every Freya API call retried on transient platform errors
(502/503/504, 'temporarily unavailable', timeouts) for up to --max-wait seconds. The kit stays untouched: only the
`freya.api` function is wrapped in memory before the kit script runs.

    python3 builder/test/run_cases_resilient.py <agent_id> --brief A [--style S] --out results/x.json [--max-wait 900]
"""
import runpy
import socket
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
KIT = ROOT / "kit"


def main() -> None:
    argv = sys.argv[1:]
    max_wait = 900
    if "--max-wait" in argv:
        i = argv.index("--max-wait")
        max_wait = int(argv[i + 1])
        argv = argv[:i] + argv[i + 2:]
    sys.path.insert(0, str(KIT))
    sys.path.insert(0, str(KIT / "tools"))
    socket.setdefaulttimeout(60)
    import freya  # the kit's client

    real_api = freya.api

    def api(method, path, body=None, **params):
        wait, spent = 15.0, 0.0
        while True:
            try:
                return real_api(method, path, body, **params)
            except Exception as e:
                msg = " ".join(str(e).split())
                transient = any(k in msg for k in ("502", "503", "504", "temporarily unavailable", "timed out", "Connection", "Remote end closed"))
                if not transient or spent >= max_wait:
                    raise
                print(f"[resilient] {method} {path.split('?')[0]}: {msg[:70]} -> retry in {wait:.0f} s", flush=True)
                time.sleep(wait)
                spent += wait
                wait = min(wait * 1.5, 90)

    freya.api = api
    import os
    os.chdir(KIT)
    sys.argv = ["run_cases.py", *argv]
    runpy.run_path(str(KIT / "tools" / "run_cases.py"), run_name="__main__")


if __name__ == "__main__":
    main()
