"""Write one local_sim run as a readable markdown page: the whole conversation with Freya's events and tool calls,
the bank's record, the ledger score and the judge's verdict.

    python3 tester/dump_call.py results/local/<time>/PUB-01-1.json [out.md]
"""
import json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
KIT = ROOT / "docs" / "build-the-builder"
sys.path[:0] = [str(KIT), str(KIT / "tools")]
import freya
from score import score_ledger


def events(call):
    lines = []
    for m in call.get("messages", []):
        role, text, t = m.get("role"), m.get("message") or "", m.get("secondsFromStart")
        ts = f"{t:6.1f}s " if isinstance(t, (int, float)) else "        "
        if role == "assistant": lines.append(f"{ts}AJAN:    {text}")
        elif role == "user": lines.append(f"{ts}MÜŞTERİ: {text}")
        elif role == "system":
            try: e = json.loads(text)
            except (ValueError, TypeError): continue
            ev = e.get("event")
            if ev == "node_enter": lines.append(f"{ts}  [node] {e.get('from_node')} → {e.get('node')}  ({e.get('reason')})")
            elif ev == "function_call_start":
                a = e.get("args") or {}; b = a.get("body", a) if isinstance(a, dict) else a
                lines.append(f"{ts}  [tool →] {e.get('function')} {json.dumps(b, ensure_ascii=False)}")
            elif ev == "function_call_complete":
                r = e.get("result"); d = r.get("data", r) if isinstance(r, dict) else r
                lines.append(f"{ts}  [tool ←] {e.get('function')} {json.dumps(d, ensure_ascii=False)}")
            elif ev == "error": lines.append(f"{ts}  [HATA] {json.dumps(e, ensure_ascii=False)[:300]}")
    return lines


def main(run_file, out=None):
    run = json.load(open(run_file)); row = run["row"]
    case = {c["id"]: c for c in json.load(open(KIT / "public-test-set.json"))}[row["id"]]
    call = freya.get_call(row["call_id"]); led = run.get("ledger") or {}
    s = score_ledger(case, led) if led else {"pass": False, "failed": ["no ledger in this run"]}
    j = run.get("judge") or {}
    L = [f"# Görüşme: {row['id']}", "",
         f"- Vaka: {case['title']} ({case['level']}, {case['family']})",
         f"- Müşteri senaryosu (Gemini'ye verilen): {case['script']}",
         f"- Sonuç: **{row['status']}**", f"- Freya call id: `{row['call_id']}`, banka customer_id: `{row.get('customer_id')}`",
         "- Ajan: experimental-5 (Freya). Müşteri ve judge: Gemini.", "",
         "## Görüşmenin tamamı", "",
         "**AJAN** / **MÜŞTERİ** konuşma, `[node]` adım değişimi, `[tool →]` bankaya çağrı, `[tool ←]` bankanın cevabı.", "", "```"]
    L += events(call)
    L += ["```", "", f"Bitiş nedeni: `{call.get('endedReason')}`", "",
          "## 1. Banka kaydı (outcome kontrolü)", "", "```json",
          json.dumps({k: led.get(k) for k in ("outcome", "reason", "promises", "notes", "callbacks", "transfers")}, indent=1, ensure_ascii=False), "```", "",
          f"Sonuç: **{'GEÇTİ' if s['pass'] else 'KALDI'}**"] + [f"- {f}" for f in s["failed"]]
    L += ["", "Beklenen:", "", "```json", json.dumps(case["expected"], indent=1), "```", "",
          "## 2. Judge (konuşma kontrolü)", "", "Kontrol listesi:", ""] + [f"- {c}" for c in case["checks"]]
    L += ["", f"Karar: **{'GEÇTİ' if j.get('pass') else 'KALDI'}**", "", f"Gerekçe: {j.get('reason', '(judge çalışmadı)')}"]
    out = pathlib.Path(out or ROOT / "results" / f"ornek-konusma-{row['id']}.md"); out.write_text("\n".join(L) + "\n")
    print(out)


if __name__ == "__main__":
    if len(sys.argv) < 2: sys.exit(__doc__)
    main(*sys.argv[1:3])
