"""Pre-flight for a test session: keys, Freya API, the bank mock, the simulation queue, Gemini and OpenAI. Exit code 1 when something is down.

    source env.sh && python3 tester/health.py [--no-llm]
"""
import json, os, pathlib, sys, time, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
KIT = next((pathlib.Path(p) for p in (os.environ.get("FREYA_KIT_DIR"), ROOT / "kit", ROOT / "docs" / "build-the-builder") if p and pathlib.Path(p).exists()), None)
sys.path.insert(0, str(KIT)); sys.path.insert(0, str(KIT / "tools")); sys.path.insert(0, str(ROOT / "tester"))
ok = True


def row(name, good, detail=""):
    global ok
    ok &= bool(good); print(f"{'OK  ' if good else 'FAIL'} {name:<28} {detail}")


def main():
    no_llm = "--no-llm" in sys.argv
    for k in ("FREYA_API_KEY", "FREYA_BANK_TEAM_KEY", "GEMINI_API_KEY"): row(f"env {k}", bool(os.environ.get(k)))
    row("env OPENAI_API_KEY", bool(os.environ.get("OPENAI_API_KEY")), "(optional: extraction + judge on OpenAI)")
    try:
        import freya; t = time.time(); ws = freya.workspace_id(); row("Freya API", True, f"workspace {ws} ({time.time()-t:.1f}s)")
        r = freya.api("GET", "/api/v2/simulations", workspaceId=ws); sims = r.get("simulations", r) if isinstance(r, dict) else r
        running = [s.get("name") for s in sims if s.get("status") not in ("completed", "failed", "cancelled")]
        row("simulation queue", not running, "free" if not running else f"busy: {running}")
    except Exception as e: row("Freya API", False, str(e)[:120])
    try:
        from score import http; t = time.time(); s = http("/v1/practice/sessions", {"case": "PUB-01"}); row("bank mock", s.get("ok"), f"session {s.get('variables', {}).get('customer_id', '?')} ({time.time()-t:.1f}s)")
    except Exception as e: row("bank mock", False, str(e)[:120])
    if not no_llm:
        try:
            import gemini; t = time.time(); gemini.generate("one word", [("user", "Say OK")], thinking="low"); row("Gemini", True, f"{gemini.MODEL} ({time.time()-t:.1f}s)")
        except Exception as e: row("Gemini", False, str(e)[:160].replace("\n", " "))
        if os.environ.get("OPENAI_API_KEY"):
            try:
                import openai_client; t = time.time(); openai_client.generate("one word", [("user", "Say OK")]); row("OpenAI", True, f"{openai_client.MODEL} ({time.time()-t:.1f}s)")
            except Exception as e: row("OpenAI", False, str(e)[:160].replace("\n", " "))
    try:
        import fakebank; base = fakebank.start([{"id": "H", "variables": {"first_name": "A", "last_name": "B", "title": "Mr", "now": "2026-01-01T10:00"}, "identity": {"x": "1"}, "products": []}])
        r = urllib.request.Request(base + "/v1/practice/sessions", data=b'{"case":"H"}', headers={"content-type": "application/json"}, method="POST")
        row("fake bank", json.load(urllib.request.urlopen(r)).get("ok"), base)
    except Exception as e: row("fake bank", False, str(e)[:120])
    print("\nall good" if ok else "\nsomething is down"); sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
