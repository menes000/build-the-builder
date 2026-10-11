"""Live view of a main.py run in the browser. Reads files only (the trace and the local test's per-customer records); no model
call, no Freya request, safe to keep open during the final.

    python3 watch.py            # then open http://localhost:8765
    python3 watch.py --port 9000

It follows the newest traces/*.jsonl (main.py's trace) and, while a local test runs, the newest results/local/<time>/ folder,
where tester/local_sim.py writes one record per finished customer.
"""
from __future__ import annotations

import argparse
import json
import re
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
TRACES = ROOT / "traces"
LOCAL = ROOT / "results" / "local"


def read_jsonl(path: Path) -> list[dict]:
    out = []
    for line in path.read_text(errors="replace").splitlines():
        try:
            out.append(json.loads(line))
        except ValueError:
            pass                                    # the last line can be half written
    return out


def traces() -> list[Path]:
    return sorted(TRACES.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True) if TRACES.exists() else []


def local_progress(started: float, events: list[dict]) -> dict | None:
    """Customers finished so far in the newest local test folder created after the run started."""
    if not LOCAL.exists():
        return None
    dirs = [d for d in LOCAL.iterdir() if d.is_dir() and d.stat().st_mtime >= started - 5]
    if not dirs:
        return None
    d = max(dirs, key=lambda p: p.stat().st_mtime)
    rows = []
    for f in sorted(d.glob("*.json"), key=lambda p: p.stat().st_mtime):
        try:
            rec = json.loads(f.read_text())
        except ValueError:
            continue
        row = rec.get("row") or {}
        rows.append({"id": row.get("id") or rec.get("case"), "rep": row.get("rep"), "status": row.get("status", "?"),
                     "family": row.get("family", ""), "failed": (row.get("failed") or [])[:3], "error": row.get("error", ""),
                     "turns": row.get("turns"), "at": f.stat().st_mtime})
    total = None
    work = next((m.group(1) for e in events if e.get("kind") == "note" for m in [re.search(r"work=(\S+)", e.get("text", ""))] if m), None)
    reps = next((int(m.group(1)) for e in events if e.get("kind") == "note" for m in [re.search(r"reps=(\d+)", e.get("text", ""))] if m), 1)
    if work and (Path(work) / "cases.json").exists():
        try:
            total = len(json.loads((Path(work) / "cases.json").read_text())) * reps
        except ValueError:
            pass
    return {"dir": d.name, "rows": rows, "total": total}


def load(p: Path):
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return None


def work_files(events: list[dict]) -> dict | None:
    """The run folder main.py writes every hand-over into: cross-check, what was sent to Claude, what changed, test results."""
    work = next((m.group(1) for e in events if e.get("kind") == "note" for m in [re.search(r"work=(\S+)", e.get("text", ""))] if m), None)
    if not work or not Path(work).exists():
        return None
    w = Path(work)
    cases = {c["id"]: {"title": c.get("title", ""), "family": c.get("family", ""), "script": c.get("script", ""), "checks": c.get("checks", [])}
             for c in (load(w / "cases.json") or [])}
    tests = {}
    for f in sorted(w.glob("test.*.json")):
        r = load(f)
        if not r:
            continue
        rows = [{k: x.get(k) for k in ("id", "rep", "status", "failed", "judge_reason", "transcript", "path", "flags", "error")} for x in r.get("rows", [])]
        tests[f.stem.split(".", 1)[1]] = {"passed": r.get("passed"), "total": r.get("total"), "seconds": r.get("seconds"), "final": r.get("final", []), "rows": rows}
    rounds = {}
    for f in sorted(w.glob("fix*.json")):
        tag, part = f.stem.split(".", 1)
        rounds.setdefault(tag, {})[part] = load(f)
    return {"dir": str(w), "cases": cases, "tests": tests, "rounds": rounds,
            "crosscheck": load(w / "crosscheck.json"), "recheck": {"request": load(w / "recheck.request.json"), "result": load(w / "recheck.result.json")}}


def state(name: str | None) -> dict:
    files = traces()
    if not files:
        return {"files": [], "events": []}
    path = next((f for f in files if f.name == name), files[0])
    events = read_jsonl(path)
    started = path.stat().st_ctime
    if events and events[0].get("kind") == "start":
        started = path.stat().st_mtime - (events[-1].get("t") or 0)
    running = not any(e.get("kind") == "end" for e in events)
    return {"files": [f.name for f in files[:30]], "file": path.name, "events": events, "running": running,
            "idle_s": round(time.time() - path.stat().st_mtime), "local": local_progress(started, events), "work": work_files(events)}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/api/state":
            body = json.dumps(state((parse_qs(u.query).get("file") or [None])[0]), default=str).encode()
            ctype = "application/json"
        elif u.path == "/":
            body, ctype = PAGE.encode(), "text/html; charset=utf-8"
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


PAGE = r"""<!doctype html>
<html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>main.py Canlı</title>
<style>
:root{--bg:#f7f6f2;--card:#fff;--ink:#1d1b16;--mute:#6b6658;--line:#dcd8cb;--run:#c98a1b;--ok:#2f8a5b;--bad:#b5462f;--idle:#b9b4a6;--acc:#3a6ea5}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#16150f;--card:#211f18;--ink:#ece8dc;--mute:#a39d8c;--line:#3a372d;--run:#e0a84a;--ok:#6cc493;--bad:#e2785f;--idle:#5a564a;--acc:#7aa6d6}}
:root[data-theme="dark"]{--bg:#16150f;--card:#211f18;--ink:#ece8dc;--mute:#a39d8c;--line:#3a372d;--run:#e0a84a;--ok:#6cc493;--bad:#e2785f;--idle:#5a564a;--acc:#7aa6d6}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
main{max-width:1100px;margin:0 auto;padding:20px 16px 40px}
header{display:flex;flex-wrap:wrap;gap:10px 18px;align-items:center;justify-content:space-between;margin-bottom:14px}
h1{font-size:20px;margin:0}select{background:var(--card);color:var(--ink);border:1px solid var(--line);border-radius:6px;padding:4px 6px;max-width:100%}
.pill{display:inline-block;padding:2px 9px;border-radius:99px;font-size:12px;font-weight:600;color:#fff;background:var(--idle)}
.pill.run{background:var(--run)}.pill.ok{background:var(--ok)}.pill.bad{background:var(--bad)}
.grid{display:grid;grid-template-columns:300px 1fr;gap:14px}@media(max-width:800px){.grid{grid-template-columns:1fr}}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px;min-width:0}
.card h2{font-size:13px;color:var(--mute);margin:0 0 8px;font-weight:600;text-transform:uppercase;letter-spacing:.04em}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:14px}@media(max-width:600px){.stats{grid-template-columns:repeat(2,1fr)}}
.stat b{display:block;font-size:22px}.stat span{font-size:12px;color:var(--mute)}
.bar{height:6px;background:var(--line);border-radius:3px;overflow:hidden;margin-top:6px}.bar i{display:block;height:100%;background:var(--acc)}
.bar.warn i{background:var(--bad)}
ol.steps{list-style:none;margin:0;padding:0}ol.steps li{display:flex;gap:10px;padding:7px 0;border-bottom:1px solid var(--line)}ol.steps li:last-child{border:none}
.dot{flex:none;width:12px;height:12px;border-radius:50%;margin-top:4px;background:var(--idle)}
.dot.run{background:var(--run);animation:p 1s infinite alternate}.dot.ok{background:var(--ok)}.dot.bad{background:var(--bad)}.dot.skip{background:transparent;border:2px solid var(--idle)}
@keyframes p{to{opacity:.35}}
.steps small{display:block;color:var(--mute);font-size:12px;word-break:break-word}
.chips{display:flex;flex-wrap:wrap;gap:4px;margin:6px 0 4px}.chip{font:11px ui-monospace,Menlo,monospace;padding:2px 6px;border-radius:5px;background:var(--line)}
.chip.PASS{background:color-mix(in srgb,var(--ok) 25%,transparent)}.chip.FAIL{background:color-mix(in srgb,var(--bad) 30%,transparent)}.chip.ERROR{background:color-mix(in srgb,var(--run) 30%,transparent)}
.log{font:12px/1.5 ui-monospace,Menlo,monospace;max-height:520px;overflow:auto;white-space:pre-wrap;word-break:break-word}
.log div{padding:3px 0;border-bottom:1px dashed var(--line)}.log .t{color:var(--mute)}.log .k{font-weight:700}
.k.model_call{color:var(--acc)}.k.test{color:var(--ok)}.k.created_on_freya{color:#8a5cc7}.k.end{color:var(--ok)}
.fails div{font-size:12px;padding:4px 0;border-bottom:1px solid var(--line)}.muted{color:var(--mute)}
#loop h3{font-size:15px;margin:18px 0 6px}#loop h3:first-child{margin-top:0}#loop h4{font-size:13px;margin:12px 0 4px;color:var(--mute)}
#loop table{width:100%;border-collapse:collapse;font-size:12px;display:block;overflow-x:auto}#loop th,#loop td{text-align:left;padding:5px 7px;border-bottom:1px solid var(--line);vertical-align:top}
#loop th{color:var(--mute);font-weight:600}
details{border:1px solid var(--line);border-radius:8px;padding:6px 10px;margin:6px 0}summary{cursor:pointer;font-size:13px}
details pre{font:12px/1.45 ui-monospace,Menlo,monospace;white-space:pre-wrap;word-break:break-word;max-height:380px;overflow:auto;margin:6px 0 0;background:color-mix(in srgb,var(--line) 35%,transparent);padding:8px;border-radius:6px}
.diff{font:12px/1.5 ui-monospace,Menlo,monospace;white-space:pre-wrap;word-break:break-word}.diff div{padding:2px 0;border-bottom:1px dashed var(--line)}
.verdict{display:inline-block;padding:3px 10px;border-radius:6px;font-weight:600;font-size:13px}.verdict.ok{background:color-mix(in srgb,var(--ok) 25%,transparent)}.verdict.bad{background:color-mix(in srgb,var(--bad) 25%,transparent)}
.flowline{font-size:12px;color:var(--mute);margin:2px 0 8px}
</style></head><body><main>
<header><h1>main.py <span id="status" class="pill">…</span></h1><div><select id="file"></select></div></header>
<div class="stats">
 <div class="card stat"><b id="elapsed">–</b><span>geçen süre</span><div class="bar" id="bb"><i id="budget"></i></div></div>
 <div class="card stat"><b id="calls">–</b><span>Claude/model çağrısı · <span id="cost">0 $</span></span></div>
 <div class="card stat"><b id="test">–</b><span>lokal test (son)</span></div>
 <div class="card stat"><b id="version">–</b><span>en iyi sürüm</span></div>
</div>
<div class="grid">
 <div class="card"><h2>Adımlar</h2><ol class="steps" id="steps"></ol></div>
 <div style="display:flex;flex-direction:column;gap:14px;min-width:0">
  <div class="card" id="localcard"><h2>Lokal test, canlı</h2><div id="local" class="muted">henüz yok</div></div>
  <div class="card"><h2>Olaylar</h2><div class="log" id="log"></div></div>
 </div>
</div>
<div class="card" style="margin-top:14px"><h2>Döngü detayı: ne gönderildi, ne geri geldi, ne karar verildi</h2><div id="loop" class="muted">henüz yok</div></div>
</main>
<script>
const STEPS=[
 ["start","Başlangıç"],["extract","1 · Extract (Claude)"],["cross","2 · Çapraz kontrol"],["compile","3 · Derle"],
 ["publish1","4 · Yayınla v1 + export"],["cases","5a · Vakaları üret"],["test1","5b · Lokal test v1"],
 ["fix","6 · Düzelt + tekrar test"],["final","7 · En iyiyi yayınla"],["end","Bitti"]];
const $=id=>document.getElementById(id);let chosen=null,lastLen=-1;
function txt(e){return e.text||e.purpose||e.name||e.what||""}
function analyse(ev){
 const s={};STEPS.forEach(([k])=>s[k]={st:"",info:""});const set=(k,st,info)=>{s[k].st=st;if(info!==undefined)s[k].info=info};
 let budget=25,calls=0,cost=0,lastTest=null,version="–",failed=false;
 for(const e of ev){const t=txt(e);
  if(e.kind==="start")set("start","ok",e.at);
  if(e.kind==="note"){const m=t.match(/budget_min=([\d.]+)/);if(m)budget=+m[1];
   if(/^main\.py/.test(t)){set("extract","run")}
   if(/using CallSpec/.test(t))set("extract","ok","verilen CallSpec");
   if(/^extraction attempt .*valid/.test(t))set("extract","ok",t);
   if(/^extraction attempt .*(mismatch|schema)/.test(t))set("extract","run",t);
   if(/^extraction: continuing/.test(t))set("extract","bad",t);
   if(/^cross-check: \d+ disagreement/.test(t))set("cross",/^cross-check: 0 /.test(t)?"ok":"run",t.split("\n")[0]);
   if(/^cross-check: re-read changed/.test(t))set("cross","ok",t.split("\n")[0]);
   if(/^cross-check: (no revised|revised CallSpec)/.test(t))set("cross","ok",t);
   if(/^cross-check skipped/.test(t))set("cross","skip",t);
   if(/^compiled v1/.test(t)){set("compile","ok",t.replace(/ -> .*/,""));if(s.cross.st==="")set("cross","skip","kapalı");if(s.extract.st!=="bad")set("extract","ok")}
   if(/^dryRun valid \(v1\)/.test(t))set("publish1","run");
   if(/^exported v1/.test(t))set("publish1","ok","teslim dosyası hazır");
   if(/^test customers/.test(t)){set("cases","ok",t);set("test1","run")}
   if(/^local test skipped|case generation failed/.test(t)){set("cases","skip",t);set("test1","skip");set("fix","skip")}
   if(/^fix\d/.test(t)){set("fix",/rejected/.test(t)?"bad":/accepted/.test(t)?"ok":"run",t.split("\n")[0]);if(/accepted/.test(t))version=t.match(/^(fix\d)/)[1]}
   if(/^fix \d+:/.test(t))set("fix","skip",t);
   if(/^exported fix/.test(t))set("final","ok",t);
  }
  if(e.kind==="model_call"){calls++;cost+=+(e.cost_usd||0);
   if(/extract CallSpec/.test(t))set("extract","run",t+` · ${e.seconds}s`);
   if(/cross-check|re-read/.test(t))set("cross","run",t+` · ${e.seconds}s`);
   if(/revise CallSpec/.test(t))set("fix","run",t+` · ${e.seconds}s`)}
  if(e.kind==="test"){lastTest=e;const v=(e.name.match(/local test (\S+)/)||[])[1];
   if(v==="v1")set("test1",e.passed===e.total?"ok":"bad",`${e.passed}/${e.total} · ${e.seconds}s`);
   else if(v)set("fix","run",`${v}: ${e.passed}/${e.total}`)}
  if(e.kind==="end"){set("end","ok",`${e.total_seconds}s · ${e.version||""}`);version=e.version||version;
   if(!s.final.st)set("final",version==="v1"?"skip":"ok",version==="v1"?"v1 teslim":"");
   for(const k of ["cases","test1","fix"])if(!s[k].st)set(k,"skip")}
 }
 return {s,budget,calls,cost,lastTest,version}}
function fmt(sec){sec=Math.max(0,Math.round(sec));return `${Math.floor(sec/60)}:${String(sec%60).padStart(2,"0")}`}
function esc(x){return String(x).replace(/[&<>]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]))}
async function tick(){
 let d;try{d=await (await fetch("/api/state"+(chosen?"?file="+encodeURIComponent(chosen):""))).json()}catch(e){$("status").textContent="sunucu yok";return}
 const sel=$("file");if(sel.options.length!==d.files.length){sel.innerHTML=d.files.map(f=>`<option>${f}</option>`).join("")}sel.value=d.file||"";
 const ev=d.events||[];if(!ev.length){$("log").textContent="trace yok: python3 main.py ... ile bir koşu başlat";return}
 const a=analyse(ev),last=ev[ev.length-1],el=last.t+(d.running?d.idle_s:0);
 $("status").className="pill "+(d.running?"run":"ok");$("status").textContent=d.running?`çalışıyor · ${d.idle_s}s önce yazdı`:"bitti";
 $("elapsed").textContent=fmt(el)+" / "+a.budget+" dk";const pct=Math.min(100,el/(a.budget*60)*100);$("budget").style.width=pct+"%";$("bb").className="bar"+(pct>85?" warn":"");
 $("calls").textContent=a.calls;$("cost").textContent=a.cost.toFixed(2)+" $";
 $("test").textContent=a.lastTest?`${a.lastTest.passed}/${a.lastTest.total}`:"–";$("version").textContent=a.version;
 let cur=STEPS.findIndex(([k])=>a.s[k].st==="run");
 if(d.running&&cur<0){const lastDone=Math.max(...STEPS.map(([k],i)=>a.s[k].st?i:-1));cur=lastDone+1<STEPS.length?lastDone+1:-1}
 $("steps").innerHTML=STEPS.map(([k,l],i)=>{let st=a.s[k].st;if(d.running&&i===cur&&!st)st="run";return `<li><span class="dot ${st}"></span><div><b>${l}</b><small>${esc(a.s[k].info||"")}</small></div></li>`}).join("");
 const lp=d.local;
 if(lp&&lp.rows.length){const n=lp.rows.length,p=lp.rows.filter(r=>r.status==="PASS").length,f=lp.rows.filter(r=>r.status==="FAIL").length,er=n-p-f;
  const fails=lp.rows.filter(r=>r.status!=="PASS");
  $("local").innerHTML=`<div><b>${n}${lp.total?" / "+lp.total:""}</b> görüşme bitti · <span style="color:var(--ok)">${p} geçti</span> · <span style="color:var(--bad)">${f} kaldı</span>${er?` · ${er} hata`:""} <span class="muted">(${lp.dir})</span></div>
  ${lp.total?`<div class="bar"><i style="width:${Math.min(100,n/lp.total*100)}%"></i></div>`:""}
  <div class="chips">${lp.rows.map(r=>`<span class="chip ${r.status}" title="${esc(r.family)}">${esc(r.id)}·${r.rep}</span>`).join("")}</div>
  <div class="fails">${fails.slice(-8).reverse().map(r=>`<div><b>${esc(r.id)}·${r.rep}</b> ${r.status}: ${esc((r.failed[0]||r.error||"").slice(0,220))}</div>`).join("")}</div>`}
 if(ev.length!==lastLen){lastLen=ev.length;const box=$("log"),stick=box.scrollTop+box.clientHeight>=box.scrollHeight-20;
  box.innerHTML=ev.map(e=>{const x={...e};delete x.t;delete x.kind;const body=e.kind==="note"?e.text:Object.entries(x).map(([k,v])=>`${k}=${typeof v==="object"?JSON.stringify(v):v}`).join("  ");
   return `<div><span class="t">[${String(e.t).padStart(6)}s]</span> <span class="k ${e.kind}">${e.kind}</span> ${esc(body)}</div>`}).join("");
  if(stick)box.scrollTop=box.scrollHeight}
}
let lastWork="";
const J=v=>esc(typeof v==="string"?v:JSON.stringify(v));
function caseDetails(w,id,extra){const c=w.cases[id]||{};return `<details><summary><b>${esc(id)}</b> ${esc(c.title||"")} <span class="muted">${esc(c.family||"")}</span>${extra||""}</summary>
 ${c.script?`<h4>Müşteri senaryosu</h4><div>${esc(c.script)}</div>`:""}${c.checks&&c.checks.length?`<h4>Judge check'leri</h4><ul>${c.checks.map(x=>`<li>${esc(x)}</li>`).join("")}</ul>`:""}`}
function renderTest(w,tag,t){
 const bad=(t.final||[]).filter(f=>!f.pass);
 let h=`<h3>Lokal test ${esc(tag)}: ${t.passed}/${t.total} <span class="muted">(${t.seconds||"?"} s)</span></h3>`;
 if(!bad.length)return h+`<div class="muted">düşen yok</div>`;
 return h+bad.map(f=>{const rows=t.rows.filter(r=>r.id===f.id);
  return caseDetails(w,f.id,` · <span style="color:var(--bad)">${f.passes}/${f.runs}</span>`)+rows.map(r=>`<h4>Koşu ${r.rep}: ${esc(r.status)}</h4>
   ${(r.failed||[]).length?`<ul>${r.failed.map(x=>`<li>${esc(x)}</li>`).join("")}</ul>`:""}${r.error?`<div>${esc(r.error)}</div>`:""}
   ${r.path?`<div class="flowline">yol: ${esc(r.path.join(" › "))}</div>`:""}${(r.flags||[]).length?`<div class="flowline">bayraklar: ${esc(r.flags.join(" · "))}</div>`:""}
   ${r.transcript?`<details><summary>transcript</summary><pre>${esc(r.transcript)}</pre></details>`:""}`).join("")+`</details>`}).join("")}
function renderLoop(w){
 if(!w)return `<span class="muted">bu koşunun çalışma klasörü yok</span>`;
 let h="";
 const cc=w.crosscheck;
 h+=`<h3>2 · Çapraz kontrol</h3>`;
 if(cc===null||cc===undefined)h+=`<div class="muted">çalışmadı / henüz yok</div>`;
 else if(!cc.length)h+=`<div>İkinci okuyucu ile CallSpec aynı fikirde, fark yok.</div>`;
 else{h+=`<div class="flowline">${cc.length} alanda farklı okuma → bu alanlar Claude'a "brief'i tekrar oku" diye gönderildi</div>
  <table><tr><th>alan</th><th>CallSpec (Claude)</th><th>ikinci okuyucu</th><th>ikinci okuyucunun kaynağı</th></tr>${cc.map(([p,x,y,s])=>`<tr><td><code>${esc(p)}</code></td><td>${J(x)}</td><td>${J(y)}</td><td>${esc(s||"")}</td></tr>`).join("")}</table>`;
  const rr=w.recheck&&w.recheck.result;
  if(rr){h+=`<h4>Claude'un yeniden okumasının sonucu ${rr.accepted?`<span class="verdict ok">uygulandı</span>`:`<span class="verdict bad">geçersiz, v0 kaldı</span>`}</h4>
   <div class="diff">${(rr.changes||[]).map(c=>`<div>${esc(c)}</div>`).join("")||"<div>hiçbir alan değişmedi</div>"}</div>
   ${(rr.notes||[]).length?`<h4>Claude'un notları (alan başına korundu/değişti + kaynak)</h4><ul>${rr.notes.map(n=>`<li>${esc(n)}</li>`).join("")}</ul>`:""}`}
  else h+=`<div class="muted">Claude yeniden okuyor…</div>`}
 const order=Object.keys(w.tests).sort((a,b)=>a==="v1"?-1:b==="v1"?1:a.localeCompare(b));
 if(w.tests.v1)h+=renderTest(w,"v1",w.tests.v1);
 for(const tag of Object.keys(w.rounds).sort()){const R=w.rounds[tag];
  h+=`<h3>6 · Düzeltme turu ${esc(tag)}</h3>`;
  if(R.request){const fs=R.request.failures||[];
   h+=`<h4>→ Claude'a gönderilen (${fs.length} düşen müşteri; ${esc(R.request.from)} sürümünün CallSpec'i ve brief'in tamamıyla birlikte)</h4>
   <div class="flowline">Talimat: sadece metinleri değiştir (kurallar, cümleler, extra_rules). Tatil, bant, outcome, kuyruk, kimlik soruları, tutarlar yasak. Müşteriye özel değer yazma, kuralı gevşetme.</div>`+
   fs.map(f=>`<details><summary><b>${esc(f.id)}</b> ${esc(f.title)} <span class="muted">${esc(f.family)}</span></summary>
    <h4>Ne düştü</h4><ul>${(f.failed||[]).map(x=>`<li>${esc(x)}</li>`).join("")}</ul>
    <h4>Senaryo</h4><div>${esc(f.script)}</div><h4>Judge check'leri</h4><ul>${(f.checks||[]).map(x=>`<li>${esc(x)}</li>`).join("")}</ul>
    <h4>Beklenen banka kaydı</h4><pre>${esc(JSON.stringify(f.expected,null,1))}</pre>
    <details><summary>gönderilen transcript</summary><pre>${esc(f.transcript)}</pre></details></details>`).join("")}
  if(R.result){h+=`<h4>← Claude'un geri gönderdiği değişiklikler (${(R.result.changes||[]).length})</h4>
   ${R.result.verdict?`<div><span class="verdict bad">${esc(R.result.verdict)}</span></div>`:""}
   <div class="diff">${(R.result.changes||[]).map(c=>`<div>${esc(c)}</div>`).join("")||"<div class='muted'>değişiklik yok</div>"}</div>
   ${(R.result.notes||[]).length?`<h4>Claude'un gerekçeleri (vaka başına ne değiştirdi / neden değiştirmedi)</h4><ul>${R.result.notes.map(n=>`<li>${esc(n)}</li>`).join("")}</ul>`:""}`}
  else if(R.request)h+=`<div class="muted">Claude düzeltme yazıyor…</div>`;
  if(w.tests[tag])h+=renderTest(w,tag,w.tests[tag]);
  else if(R.result&&(R.result.changes||[]).length)h+=`<div class="muted">aynı müşterilerle tekrar test ediliyor…</div>`;
  const D=R.decision;
  if(D)h+=`<h4>Karar</h4><div><span class="verdict ${D.accepted?"ok":"bad"}">${D.accepted?"KABUL":"RED, eski sürüm kalır"}</span> ${esc(D.before)} → ${esc(D.after)}
   ${D.gained.length?` · <span style="color:var(--ok)">yeni geçen: ${esc(D.gained.join(", "))}</span>`:""}${D.lost.length?` · <span style="color:var(--bad)">yeni düşen: ${esc(D.lost.join(", "))}</span>`:""}</div>
   <div class="flowline">Kural: daha çok müşteri geçmeli VE önceden geçen hiçbiri düşmemeli.</div>`}
 for(const tag of order)if(tag!=="v1"&&!w.rounds[tag])h+=renderTest(w,tag,w.tests[tag]);
 return h||`<span class="muted">henüz yok</span>`}
const _tick=tick;tick=async function(){await _tick();
 try{const d=await (await fetch("/api/state"+(chosen?"?file="+encodeURIComponent(chosen):""))).json();
  const key=JSON.stringify(d.work||null);if(key!==lastWork){lastWork=key;$("loop").innerHTML=renderLoop(d.work)}}catch(e){}};
$("file").onchange=e=>{chosen=e.target.value;lastLen=-1;lastWork="";tick()};tick();setInterval(tick,2000);
</script></body></html>"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8765)
    a = ap.parse_args()
    print(f"main.py live view: http://localhost:{a.port}  (Ctrl+C to stop)")
    ThreadingHTTPServer(("127.0.0.1", a.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
