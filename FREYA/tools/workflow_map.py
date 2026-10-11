"""One HTML page that explains the whole system to someone who has never seen it: the big picture, what the builder does
step by step, how one phone call flows through the agent (with a worked example), how the engine runs one turn, and a
glossary. The real node graph (read from a compiled workflow JSON) sits at the bottom of the call tab as an advanced view.

    python3 tools/workflow_map.py [out/brief-a.workflow.json] [docs/workflow-map.html]
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WF = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "out" / "brief-a.workflow.json"
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "docs" / "workflow-map.html"


def cond_text(c):
    if not c:
        return "always"
    if "conditions" in c:
        return f" {c.get('logic', 'and').upper()} ".join(cond_text(x) for x in c["conditions"])
    if c.get("operator") == "matches_intent":
        return "niyet: " + str(c.get("intent") or c.get("operand") or c.get("description") or "")
    if c.get("operator") == "is_tool_call":
        return "tool: transition_to_" + str(c.get("tool_name") or c.get("operand") or "")
    return f"{c.get('variable')} {c.get('operator')} {c.get('operand')}"


def agent_graph(wf):
    nodes, edges = [], []
    for name, n in wf["nodes"].items():
        oe = n.get("on_enter") or {}
        nodes.append({
            "id": name, "type": n.get("node_type"),
            "on_enter": oe.get("text", "") if oe.get("type") == "tts" else "",
            "first_only": bool(n.get("on_enter_first_entry_only")),
            "task": (n.get("task_message") or "")[:3000],
            "tools": [{"name": t["function"]["name"], "desc": t["function"].get("description", "")[:260], "pre": bool(t.get("pre_process_code")),
                       "post": bool(t.get("post_process_code")), "mapping": [m.get("variable") for m in t.get("response_mapping", [])]} for t in n.get("tools", [])],
            "extraction": [{"name": e["name"], "enum": e.get("enum_values", []), "desc": e.get("description", "")[:300]} for e in n.get("extraction_schema", [])],
            "max_turns": n.get("max_node_turns"), "cap_to": n.get("max_turn_transition"),
            "code": (n.get("code") or "")[:4000] if n.get("node_type") == "code" else "",
            "transitions": [{"to": t.get("target_node"), "desc": t.get("description", ""), "cond": cond_text(t.get("condition"))} for t in n.get("transitions", [])],
        })
        seen = set()
        for t in n.get("transitions", []):
            key = (name, t.get("target_node"))
            edges.append({"from": name, "to": t.get("target_node"), "label": t.get("description", ""), "dup": key in seen})
            seen.add(key)
        if n.get("passthrough_default_transition") and (name, n["passthrough_default_transition"]) not in seen:
            edges.append({"from": name, "to": n["passthrough_default_transition"], "label": "always", "dup": False})
        if n.get("max_turn_transition"):
            edges.append({"from": name, "to": n["max_turn_transition"], "label": f"tur sınırı ({n.get('max_node_turns')})", "cap": True, "dup": False})
    return {"initial": wf.get("initial_node"), "nodes": nodes, "edges": edges, "lifecycle": [t["function"]["name"] for t in wf.get("tools", [])]}


PAGE = r"""<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Freya builder: nasıl çalışır</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/dagre/0.8.5/dagre.min.js"></script>
<style>
:root{--bg:#f6f7fb;--card:#ffffff;--ink:#1b1f2a;--muted:#5d6676;--line:#e3e6ee;--accent:#2f6fed;
 --claude:#7c5cff;--kod:#1f9d55;--freya:#2f6fed;--tester:#e8832a;--insan:#6b7280;--banka:#b4832b;--musteri:#d2466a;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 -apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
header{position:sticky;top:0;z-index:5;background:#fff;border-bottom:1px solid var(--line);padding:10px 20px;display:flex;gap:8px;align-items:center;flex-wrap:wrap}
header h1{font-size:17px;margin:0 14px 0 0;font-weight:700}
.tab{padding:7px 14px;border:1px solid var(--line);border-radius:999px;background:#fff;color:var(--ink);cursor:pointer;font-size:14px}
.tab.active{background:var(--accent);border-color:var(--accent);color:#fff}
main{max-width:1100px;margin:0 auto;padding:24px 20px 80px}
section.view{display:none}section.view.active{display:block}
h2{font-size:24px;margin:8px 0 6px}
h3{font-size:18px;margin:34px 0 10px}
p.lead{font-size:17px;color:var(--muted);margin:0 0 20px;max-width:820px}
.strip{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;align-items:stretch;margin:18px 0 8px}
.strip .box{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 16px;position:relative}
.strip .box:not(:last-child)::after{content:"→";position:absolute;right:-13px;top:40%;font-size:22px;color:var(--muted);background:var(--bg);padding:0 2px}
.box b{display:block;font-size:15px;margin-bottom:4px}
.box small{color:var(--muted)}
.who{display:inline-block;font-size:11px;font-weight:600;letter-spacing:.04em;text-transform:uppercase;color:#fff;border-radius:6px;padding:2px 7px;margin-bottom:8px}
.who.claude{background:var(--claude)}.who.kod{background:var(--kod)}.who.freya{background:var(--freya)}.who.tester{background:var(--tester)}.who.insan{background:var(--insan)}.who.banka{background:var(--banka)}.who.musteri{background:var(--musteri)}
.steps{display:flex;flex-direction:column;gap:0;margin-top:10px}
.step{display:grid;grid-template-columns:54px 1fr;gap:14px;position:relative;padding-bottom:18px}
.step .num{width:40px;height:40px;border-radius:50%;background:var(--accent);color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700;z-index:1}
.step:not(:last-child)::before{content:"";position:absolute;left:19px;top:40px;bottom:0;width:2px;background:var(--line)}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 18px;box-shadow:0 1px 2px rgba(0,0,0,.03)}
.card h4{margin:0 0 6px;font-size:16px}
.card .io{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:10px;font-size:13.5px}
.card .io div{background:#f3f5fa;border-radius:10px;padding:8px 10px}
.card .io b{display:block;color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.04em;margin-bottom:2px}
.card .ex{margin-top:10px;font-size:13.5px;color:var(--muted);border-left:3px solid var(--line);padding-left:10px}
.opt{border-style:dashed}
.timeline{display:grid;grid-template-columns:90px 1fr;gap:8px 14px;margin-top:10px}
.timeline .t{font-weight:700;color:var(--accent);text-align:right}
.timeline .d{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:8px 12px}
.phases{display:flex;flex-direction:column;gap:14px}
.phase{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 18px;border-left:6px solid var(--freya)}
.phase h4{margin:0 0 4px;font-size:17px}
.phase .nodes{display:flex;flex-wrap:wrap;gap:6px;margin:8px 0 10px}
.phase .nodes span{font-family:ui-monospace,Menlo,monospace;font-size:12px;background:#eef2ff;color:#2b3f8f;border-radius:6px;padding:2px 7px}
.phase ul{margin:6px 0 0 18px;padding:0}
.phase li{margin:3px 0}
.chat{display:flex;flex-direction:column;gap:8px;margin-top:12px}
.msg{max-width:70%;padding:10px 14px;border-radius:16px;line-height:1.4}
.msg.agent{align-self:flex-start;background:#e8efff;border-bottom-left-radius:4px}
.msg.cust{align-self:flex-end;background:#ffe6ed;border-bottom-right-radius:4px}
.msg .lbl{display:block;font-size:11px;color:var(--muted);margin-bottom:2px}
.engine{align-self:stretch;background:#f0f7f2;border:1px dashed #9ccfb0;border-radius:10px;padding:8px 12px;font-size:13px;color:#1f5c3a}
.engine b{color:#146c3b}
.loop{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:12px}
.loop .card{position:relative}
.loop .card .n{position:absolute;top:-10px;left:14px;background:var(--accent);color:#fff;border-radius:999px;padding:1px 9px;font-size:12px;font-weight:700}
.why{background:#fff8e6;border:1px solid #f1dfa6;border-radius:12px;padding:12px 16px;margin-top:16px}
dl{display:grid;grid-template-columns:200px 1fr;gap:8px 16px}
dt{font-weight:700}dd{margin:0;color:var(--ink)}
details{margin-top:28px;background:var(--card);border:1px solid var(--line);border-radius:14px;padding:10px 16px}
summary{cursor:pointer;font-weight:700;font-size:16px}
.graphwrap{display:grid;grid-template-columns:1fr 340px;gap:12px;height:620px;margin-top:12px}
#canvas{border:1px solid var(--line);border-radius:10px;overflow:hidden;background:#fbfbfd;cursor:grab}
svg{width:100%;height:100%}
.node rect{stroke:#fff;stroke-width:1.5;rx:8}.node text{fill:#fff;font-size:12px;pointer-events:none}.node.sel rect{stroke:#111;stroke-width:3}
.edge path{fill:none;stroke:#b6bdcb;stroke-width:1.4}.edge.cap path{stroke-dasharray:5 4;stroke:#e08b8b}.edge.hl path{stroke:var(--accent);stroke-width:2.5}
#panel{border:1px solid var(--line);border-radius:10px;padding:12px 14px;overflow:auto;font-size:13.5px}
#panel h5{margin:12px 0 4px;font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted)}
#panel pre{white-space:pre-wrap;font-size:11px;background:#f3f5fa;padding:8px;border-radius:8px;max-height:220px;overflow:auto}
.tag{display:inline-block;background:#eef2ff;color:#2b3f8f;border-radius:6px;padding:1px 6px;font-size:11px;margin-right:4px}
.legend{display:flex;gap:12px;flex-wrap:wrap;font-size:12.5px;color:var(--muted);margin-top:8px}
.legend i{display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:4px;vertical-align:-2px}
@media(max-width:860px){.strip{grid-template-columns:1fr 1fr}.strip .box::after{display:none}.loop{grid-template-columns:1fr}.graphwrap{grid-template-columns:1fr;height:auto}#canvas{height:420px}dl{grid-template-columns:1fr}.card .io{grid-template-columns:1fr}}
</style>
</head>
<body>
<header>
  <h1>Freya builder: nasıl çalışır</h1>
  <button class="tab active" data-tab="big">1 · Büyük resim</button>
  <button class="tab" data-tab="call">2 · Bir arama</button>
  <button class="tab" data-tab="engine">3 · Motor: bir tur</button>
  <button class="tab" data-tab="gloss">4 · Sözlük</button>
</header>
<main>

<!-- ================= 1 BÜYÜK RESİM ================= -->
<section class="view active" id="big">
<h2>Ne yapıyoruz?</h2>
<p class="lead">Banka bir <b>brief</b> verir: "gecikmiş borçlular için şu kurallarla arama yap". <b>Builder</b>, brief'i okuyan ve Freya platformunda bir <b>telefon ajanı</b> (konuşan robot) üreten programdır. Jüri, ajanı sahte müşterilerle arattırıp kurallara uyup uymadığını ölçer. Puanlanan şey ajan; ajanı üreten şey builder.</p>
<div class="strip">
  <div class="box"><span class="who banka">Banka</span><b>Brief + tool API</b><small>Kurallar (kimlik soruları, tatiller, tutarlar, ne zaman ne denecek) ve bankanın 7 servisinin tarifi (openapi.json).</small></div>
  <div class="box"><span class="who kod">Builder</span><b>Builder</b><small>Brief'i okur, bir form doldurur, formdan ajanı derler, Freya'ya yükler, dışa aktarır. 1-4 dakika.</small></div>
  <div class="box"><span class="who freya">Freya</span><b>Telefon ajanı</b><small>31 adımlık bir "akış": kim konuşuyor, kimlik, borç, söz alma, kapanış. Konuşan model: experimental-5.</small></div>
  <div class="box"><span class="who musteri">Jüri</span><b>Sahte müşteriler</b><small>Brief başına 30 müşteri, her biri 3 kez arar; 3/3 geçerse puan. Konuşma ve banka kayıtları kontrol edilir.</small></div>
</div>

<h3>Builder'ın içinde ne olur? (tek komut: <code>python3 builder/build.py &lt;brief&gt; &lt;openapi&gt;</code>)</h3>
<div class="steps">
  <div class="step"><div class="num">1</div><div class="card"><span class="who claude">Claude okur</span><h4>Brief'i anla → CallSpec formunu doldur</h4>
    Claude (claude-opus-5-5) brief'in tamamını okur ve sabit bir form olan <b>CallSpec</b>'i doldurur. Form brief'ten bağımsızdır: "kimlik soruları neler, kaç yanlış hakkı var, tatiller, bantlar ve son gün, en düşük tutar hangi alandan okunur, hangi cümle aynen söylenir, kuyruk adları, sonuç tablosu". Form bozuksa hata metni Claude'a geri verilir, 2 kez daha dener.
    <div class="io"><div><b>Girdi</b>brief dosyası ya da klasörü (mail + memo + kod listesi olabilir) + openapi.json</div><div><b>Çıktı</b>out/&lt;ad&gt;.callspec.json · ~60 saniye · ~0,4 $</div></div>
    <div class="ex">Örnek: "Ödeme 7 günden fazla gecikmişse son gün 7 iş günü sonrasıdır" → <code>bands[late].deadline_business_days_after_today = 7</code></div></div></div>
  <div class="step"><div class="num">2</div><div class="card"><span class="who kod">Kod (deterministik)</span><h4>CallSpec'ten ajanı derle</h4>
    Hiç model yok, saf Python. Form değerleri 31 düğümlük Freya akışına dönüşür: tarih ve tutar hesapları kod düğümlerine, cümleler prompt'lara, kontroller tool kancalarına. Aynı CallSpec her zaman aynı ajanı verir.
    <div class="io"><div><b>Girdi</b>CallSpec + openapi (alan adları, izinli değerler)</div><div><b>Çıktı</b>out/&lt;ad&gt;.workflow.json · 1 saniye</div></div>
    <div class="ex">Neden kod? Üç model çağrısı (anlama, yönlendirme, konuşma) aynı prompt'u görmez; model "bugün Cuma mı, 26 Ekim tatil mi" hesaplarken hata yapar. Hesap kodda, model sadece konuşur.</div></div></div>
  <div class="step"><div class="num">3</div><div class="card"><span class="who kod">Kod</span><h4>Kontrol et</h4>
    Kit'in kontrol listesi (lint), üretilen her Python parçasının bilgisayarda bir kez çalıştırılması (selfcheck), Freya'nın "kuru çalıştırma" doğrulaması (dryRun). Bir şey patlarsa builder durur: bu brief'in değil builder'ın hatasıdır.
    <div class="io"><div><b>Girdi</b>workflow.json</div><div><b>Çıktı</b>trace'e uyarılar · saniyeler</div></div></div></div>
  <div class="step"><div class="num">4</div><div class="card"><span class="who freya">Freya</span><h4>Yükle ve yayınla</h4>
    Akış Freya'ya gönderilir; aynı "slot" yerinde güncellenir ve yeni bir sürüm yayınlanır. Trace'e workflow id, ajan id, sürüm, adım ve tool sayısı yazılır.
    <div class="io"><div><b>Girdi</b>workflow.json</div><div><b>Çıktı</b>Freya'da canlı ajan (örn. hidden-1 v1) · 1 saniye</div></div></div></div>
  <div class="step"><div class="num">5</div><div class="card opt"><span class="who freya">Freya</span><h4>Test (isteğe bağlı, sadece A/B pratik brief'lerinde)</h4>
    Kit'in 10 hazır müşterisi Freya simülasyonunda ajanı arar (~3 dk). Gizli brief'lerde hazır müşteri olmadığı için bu adım yok; onun yerine 8. adım var.</div></div>
  <div class="step"><div class="num">6</div><div class="card opt"><span class="who claude">Claude</span><h4>Düzeltme turu (isteğe bağlı)</h4>
    Test kaybı varsa başarısız konuşmalar ve jüri gerekçeleri Claude'a gider; Claude CallSpec'teki <i>cümleleri</i> düzeltir (değerleri asla), ajan yeniden derlenir ve test edilir, kötüleştiyse geri alınır.</div></div>
  <div class="step"><div class="num">7</div><div class="card"><span class="who freya">Freya</span><h4>Dışa aktar</h4>
    Ajanın Freya'daki hâli dosyaya yazılır. <b>Teslim edilen dosya budur.</b> Jüri bunu kendi workspace'ine yükleyip test eder.
    <div class="io"><div><b>Çıktı</b>submission/&lt;ad&gt;.workflow.json</div><div><b>Ayrıca</b>traces/&lt;ad&gt;.log: başlangıç/bitiş saati, her model çağrısı, Freya'da oluşturulan, testler</div></div></div></div>
  <div class="step"><div class="num">8</div><div class="card"><span class="who tester">Lokal test aracı</span><h4>Kendi kendini test et (rapor)</h4>
    Export'tan sonra builder, takımın lokal test aracını (tester/) çalıştırır: CallSpec'ten ~30 sahte müşteri üretilir (LLM yok, tarihler koddan), sahte bir banka ayağa kalkar, ajan bilgisayarda taklit edilir (Gemini konuşur ve puanlar). Freya'ya hiç istek gitmez. Sonuç trace'e "local coverage 29/30" diye yazılır; <b>hiçbir şey otomatik değiştirilmez</b>.
    <div class="io"><div><b>Girdi</b>callspec.json + export</div><div><b>Çıktı</b>rapor (vaka başına geçti/kaldı, neden) · ~3 dk</div></div></div></div>
  <div class="step"><div class="num">9</div><div class="card"><span class="who insan">Operatör</span><h4>Karar</h4>
    Kural: ajana elle dokunmak yasak, brief'ten değer koda yazmak yasak. Ama builder'ın <i>genel</i> bir hatası düzeltilebilir ve builder yeniden koşulabilir; son koşunun export'u ve trace'i teslim edilir. Rapordaki her kayıp sınıflanır: jüri huyu mu, vaka metni mi, ajan davranışı mı (genel → düzelt), model farkı mı (Freya'da doğrula).</div></div>
</div>

<h3>Pazar günü (İstanbul saati)</h3>
<div class="timeline">
  <div class="t">19:30</div><div class="d">Hazırlık: platform ayakta mı, simülasyon kuyruğu boş mu, env.sh, login, 16 test geçiyor mu, final/ klasörü boş.</div>
  <div class="t">20:00</div><div class="d">İki gizli brief + openapi gelir. Dosyalar <code>final/hidden-1/</code> ve <code>final/hidden-2/</code> altına konur.</div>
  <div class="t">20:01</div><div class="d"><code>python3 builder/build.py final/hidden-1 final/hidden-1/openapi.json 2>&1 | tee traces/hidden-1.log</code> → ~2 dakikada ajan + export + trace; sonra ~3 dakika lokal test raporu.</div>
  <div class="t">20:06</div><div class="d">5 dakikalık insan kontrolü: CallSpec'i brief'le karşılaştır (tatiller, bantlar, kimlik, kuyruklar, sonuç tablosu, aynen söylenecek cümleler). Dağınık brief'te "memo eski kuralı eziyor" yerlerine dikkat.</div>
  <div class="t">20:10</div><div class="d">Lokal test raporu; riskli 3-5 vaka istenirse Freya'da resmi yolla koşulur (Pazar platform limiti var).</div>
  <div class="t">20:40</div><div class="d">Brief 2, aynı akış.</div>
  <div class="t">22:30</div><div class="d">Commit + push; teslim maili: team, repo, commit, run_command, workflows{hidden-1, hidden-2}, traces{...}. Kapanış 23:00.</div>
</div>
</section>

<!-- ================= 2 BİR ARAMA ================= -->
<section class="view" id="call">
<h2>Bir arama nasıl akar?</h2>
<p class="lead">Ajan bir "akış"tır: 31 düğüm. Konuşma düğümlerinde model konuşur, kod düğümlerinde Python sessizce hesap yapar. Müşteri her konuştuğunda motor önce "ne dedi?" diye bakar, sonra "hangi düğüme geçilecek?" diye karar verir, sonra düğümün modeli cevap verir. Aşağıda aşamalar, sonra satır satır örnek bir arama.</p>

<div class="phases">
  <div class="phase" style="border-left-color:#6b7280"><h4>0 · Hazırlık <span class="who kod">kod</span></h4>
    <div class="nodes"><span>setup</span></div>
    Arama başlar başlamaz Python çalışır: bugünün tarihi, yarın, tatil tablosu, geri arama penceresi, varsayılan sonuç ("söz yok / reddetti": müşteri aniden kapatsa bile bankaya anlamlı bir sonuç gitsin).</div>
  <div class="phase"><h4>1 · Açılış <span class="who freya">model konuşur</span></h4>
    <div class="nodes"><span>opening</span><span>opening_retry_1</span></div>
    "Freya Bank'tan dijital asistan, bu arama kaydediliyor. Bay Reyes ile mi görüşüyorum?" Henüz borç lafı yok (kimlik doğrulanmadan yasak).
    <ul><li>"Evet benim" → Kimlik</li><li>"Ben eşiyim" → Üçüncü kişi</li><li>"Yanlış numara" / "Vefat etti" → ilgili kapanış</li><li>Anlaşılmadı → bir kez daha sor, yine olmazsa kapat</li></ul></div>
  <div class="phase" style="border-left-color:#b4832b"><h4>1b · Üçüncü kişi <span class="who freya">model</span> + <span class="who banka">banka</span></h4>
    <div class="nodes"><span>third_party</span></div>
    Hiçbir şey açıklamadan ("sadece kendisiyle konuşabilirim") ne zaman ulaşılabileceğini sorar; pencere içindeyse <code>schedule_callback</code> ile geri arama planlar. Kancası (pre-hook) saati pencereye göre kontrol eder.</div>
  <div class="phase"><h4>2 · Kimlik <span class="who freya">model</span> + <span class="who banka">banka</span></h4>
    <div class="nodes"><span>security</span><span>security_explain</span></div>
    Soruları sırayla sorar (doğum tarihi, telefonun son 4 hanesi...). Her cevap <code>verify_identity</code> ile bankaya gider; kanca sonucu "doğru / yanlış, 2 hakkın kaldı / ipucu: gün-ay ters" gibi bir talimata çevirir.
    <ul><li>Hepsi doğru → Hesap</li><li>Yanlış hakkı bitti → "uygulama ya da şube" cümlesi, kapanış (failed)</li><li>Cevap vermeyi reddetti → <b>bir kez</b> açıklama düğümü ("bu sorular hesabınızı korur"), ikinci ret → kapanış (declined). Bu iki adım koddan: model ilk redde kapatamaz.</li><li>"Gerçek biriyle konuşmak istiyorum" → ret değil; bir kez "yardımcı olabilir miyim", ısrar → genel kuyruğa transfer</li></ul></div>
  <div class="phase" style="border-left-color:#1f9d55"><h4>3 · Hesap <span class="who banka">banka</span> + <span class="who kod">kod</span></h4>
    <div class="nodes"><span>load_account</span><span>account_facts</span></div>
    <code>get_account</code> bankadan ürünleri çeker (kredi kartı, taşıt kredisi; gecikme günü, tutar, en düşük ödeme). Kod her ürün için hesaplar: bant (erken/geç), son gün, ilk teklif günü (örn. bu haftanın son iş günü), izinli günler listesi, en düşük tutar. Bunlar prompt'a hazır metin olarak girer: model hesap yapmaz, okur.</div>
  <div class="phase"><h4>4 · Pazarlık <span class="who freya">model</span> + <span class="who banka">banka</span> + <span class="who kod">kod</span></h4>
    <div class="nodes"><span>negotiate</span><span>after_promise</span></div>
    Borcu söyler ("kredi kartınızda 510 gecikmiş, 14 gün geç"), "bugün ödeyebilir misiniz?" diye sorar.
    <ul><li>Evet / bir tarih verdi → <code>create_promise</code>. Kanca <b>bankaya gitmeden</b> kontrol eder: tutar en düşüğün altında mı, gün izinli mi, aynı ürüne ikinci söz mü. Geçerse kaydedilir, sonuç hemen "promise" olur, "Sözünüz kaydedildi, SMS alacaksınız. Başka bir şey var mı?"</li><li>Hayır → <code>note_refusal</code>: ret sayacı. Kaçıncı denemede olduğunu ve ne teklif edileceğini (tam tutar ilk teklif gününe / en düşük tutar son güne) kod söyler; hak bitince kapanış. Model saymaz.</li><li>Özel durumlar: iş kaybı/hastalık → bir kez destek teklifi; "zaten ödedim" → not; "bu borç benim değil" → itiraz; yeniden yapılandırma → transfer; insan → transfer.</li><li>Birden çok ürün: ürün ürün, her birine ayrı söz ya da not; hepsi bitince kapanış (tool sayaçlarından, deterministik).</li></ul></div>
  <div class="phase" style="border-left-color:#6b2f2f"><h4>5 · Kapanış <span class="who kod">kod</span> + <span class="who banka">banka</span></h4>
    <div class="nodes"><span>close_* (17 tane)</span><span>close_on_goodbye</span><span>close_on_transfer</span><span>decide_outcome</span><span>goodbye</span><span>close_call</span></div>
    Her yol küçük bir kod düğümüne gelir ("ipucu: sonuç=no_promise, sebep=hardship, veda cümlesi şu"). <code>decide_outcome</code> son kararı verir: transfer varsa transferred, söz varsa promise, not varsa ona göre, yoksa ipucu. Veda cümlesi söylenir, arama kapanır, <code>close_call</code> sonucu bankaya yazar. Müşteri aniden kapatırsa da <code>close_call</code> çalışır ve son bilinen durumu (zorluk / ödedim / itiraz) kullanır.</div>
</div>

<h3>Örnek arama: Daniel Reyes, taşıt kredisi, bugün ödeyecek</h3>
<div class="chat">
  <div class="engine"><b>setup</b> (kod): bugün = Çarşamba 14 Ekim 2026; tatiller yüklendi; varsayılan sonuç = no_promise / refused.</div>
  <div class="msg agent"><span class="lbl">Ajan (opening, girişte söylenen sabit cümle)</span>Hello, I am a digital assistant calling from Freya Bank, and we record this call. Am I speaking with Mr Reyes?</div>
  <div class="msg cust"><span class="lbl">Müşteri</span>Yes, this is Daniel Reyes.</div>
  <div class="engine"><b>extraction:</b> line_status = confirmed → <b>routing:</b> "müşteri kendisi" koşulu eşleşti → <b>security</b> düğümüne geç.</div>
  <div class="msg agent"><span class="lbl">Ajan (security, girişte söylenen)</span>Thank you, Mr Reyes. Before I continue, I need to ask you 2 security questions. What is your date of birth?</div>
  <div class="msg cust"><span class="lbl">Müşteri</span>14 March 1988.</div>
  <div class="engine"><b>tool verify_identity</b> → pre-hook "hangi soruda olduğumuzu" not eder → banka: doğru → post-hook: id_state = next, sıradaki soru = telefon.</div>
  <div class="msg agent"><span class="lbl">Ajan</span>What are the last four digits of the phone number on file?</div>
  <div class="msg cust"><span class="lbl">Müşteri</span>Four four seven one.</div>
  <div class="engine"><b>verify_identity</b> → banka: doğru, hepsi doğrulandı → id_state = verified → <b>routing:</b> "hepsi doğrulandı" koşulu → <b>load_account</b> (banka) → <b>account_facts</b> (kod): taşıt kredisi, 420 gecikmiş, 3 gün geç → bant erken, son gün 12 iş günü sonra = 2 Kasım, en düşük = 180, ilk teklif günü = Cuma 16 Ekim → <b>negotiate</b>.</div>
  <div class="msg agent"><span class="lbl">Ajan (negotiate, girişte söylenen borç cümlesi koddan)</span>Thank you, the security check is complete. I am calling from the collections team about a late payment. On your car loan the past-due amount is 420, and the payment is 3 days late. Can you make this payment today?</div>
  <div class="msg cust"><span class="lbl">Müşteri</span>Yes, I can pay the full amount today.</div>
  <div class="engine"><b>tool create_promise</b> (amount_kind = full, date = 2026-10-14) → pre-hook: tutar hesaptan 420, gün izinli, ilk söz → banka: kaydedildi → post-hook: promise_state = recorded, sonuç = promise. <b>routing:</b> promise_state == recorded → <b>after_promise</b>.</div>
  <div class="msg agent"><span class="lbl">Ajan (after_promise, girişte söylenen)</span>Your promise is recorded. You will receive a text message confirming this promise. Is there anything else?</div>
  <div class="msg cust"><span class="lbl">Müşteri</span>No, that's all. Thank you.</div>
  <div class="engine"><b>model</b> transition_to_close_promise tool'unu çağırır → <b>close_promise</b> (kod, ipucu) → <b>decide_outcome</b> (kod): söz var → promise, veda cümlesi → <b>goodbye</b> konuşur ve kapatır → <b>close_call</b> bankaya outcome = promise yazar.</div>
  <div class="msg agent"><span class="lbl">Ajan (goodbye)</span>Thank you for your time, Mr Reyes. Goodbye.</div>
</div>

<details><summary>İleri düzey: gerçek düğüm grafı (derlenmiş workflow'dan, __NNODES__ düğüm)</summary>
  <div class="legend"><span><i style="background:#2f6fed"></i>konuşma düğümü</span><span><i style="background:#1f9d55"></i>kod düğümü</span><span><i style="background:#b4832b"></i>banka isteği</span><span><i style="background:#6b2f2f"></i>aramayı bitir</span><span>— kesik kırmızı: tur sınırı</span><label style="margin-left:auto"><input type="checkbox" id="expand"> kapanış düğümlerini ayrı göster</label></div>
  <div class="graphwrap"><div id="canvas"><svg id="svg"><g id="view"></g></svg></div><aside id="panel"><b>Bir düğüme tıkla.</b><br>Sürükle: kaydır · tekerlek: yakınlaştır.</aside></div>
</details>
</section>

<!-- ================= 3 MOTOR ================= -->
<section class="view" id="engine">
<h2>Motor: müşteri bir cümle söyleyince ne olur?</h2>
<p class="lead">Freya her turda üç ayrı model çağrısı yapar ve bunlar birbirinin prompt'unu görmez. Tasarımın tamamı bu gerçeğe göre: karar mantığı prompt'ta değil, geçiş koşullarında ve kodda.</p>
<div class="loop">
  <div class="card"><span class="n">1</span><h4>Anlama (extraction)</h4>Düğümün "her turda çıkar" listesindeki alanlar son mesajdan çıkarılır: örn. <code>line_status</code> (benim / üçüncü kişi / yanlış numara), <code>declined_1</code> (açıkça reddetti mi), <code>situation</code> (zorluk / ödedim / itiraz...). Güven eşiğinin altı atılır.</div>
  <div class="card"><span class="n">2</span><h4>Yönlendirme (routing)</h4>Geçişler sırayla denenir: önce kesin koşullar (değişken == değer, tool sayacı &gt; 1), sonra "niyet eşleşmesi" (müşteri vedalaştı mı?). İlk eşleşen kazanır. Bu model görev prompt'unu görmez; o yüzden "ilk redde kapatma" gibi kurallar prompt'a değil, koşullara yazıldı.</div>
  <div class="card"><span class="n">3</span><h4>Konuşma (dialogue)</h4>Düğümün görev prompt'u + sistem kuralları + geçmişle experimental-5 cevap verir: ya konuşur ya bir tool çağırır. Geçişler ona <code>transition_to_close_refused</code> gibi tool'lar olarak görünür.</div>
  <div class="card"><span class="n">4</span><h4>Tool: kanca → banka → kanca</h4><b>pre-hook</b> argümanları doğrular (tutar en düşüğün altında mı, gün izinli mi, kuyruk adı geçerli mi) ve hatalıysa bankaya gitmeden REJECTED der. <b>post-hook</b> bankanın cevabını modelin anlayacağı talimata çevirir (<i>what_to_do_next</i>) ve değişkenlere yazar (promise_state, id_state, refusal_state).</div>
  <div class="card"><span class="n">5</span><h4>Düğüme giriş</h4>Kod düğümü: Python çalışır, değişken yazar, sessizce geçer. Konuşma düğümü: "girişte söylenen" sabit cümle varsa aynen okunur (sadece ilk girişte). Sabit cümleler modelin uydurma riskini sıfırlar.</div>
  <div class="card"><span class="n">6</span><h4>Arama biterken</h4><code>close_call</code> her aramanın sonunda çalışır, müşteri kapatsa bile. Kanca: bir kapanış düğümü karar vermediyse ve söz/transfer yoksa, son bilinen duruma (zorluk / ödedim / itiraz) göre sonucu seçer; sebep istemeyen sonuçlarda sebebi düşürür.</div>
</div>
<div class="why"><b>Neden karar ve hesap kodda?</b> Jüri kelimeleri harfiyen okur ("recorded" ancak kayıttan sonra, her cümle bir kez), tarihleri ve tutarları banka kaydından kontrol eder, aynı müşteriyi 3 kez arar ve 3/3 ister. Model her seferinde aynı kararı vermez; kod verir. Model sadece konuşmayı yürütür, karar ve hesap koddadır. Ölçüm: Brief A 10/10 temiz koşularda art arda, Brief B 3/3 üç tekrarda.</div>
</section>

<!-- ================= 4 SÖZLÜK ================= -->
<section class="view" id="gloss">
<h2>Sözlük</h2>
<dl>
  <dt>Brief</dt><dd>Bankanın arama kuralları metni. Finalde biri temiz spesifikasyon, biri dağınık materyal (mail + memo + kod listesi).</dd>
  <dt>openapi.json</dt><dd>Bankanın 7 servisinin tarifi: alan adları ve izinli değerler. Finalde adlar değişebilir; builder eşanlamlı eşlemeyle okur.</dd>
  <dt>Builder</dt><dd>Brief + openapi → ajan üreten program. Tek komut, elle müdahale yok, brief'ten koda değer yazılmaz.</dd>
  <dt>CallSpec</dt><dd>Builder'ın brief'ten doldurduğu sabit form (JSON). Lokal test aracının vaka üreticisi de bunu okur.</dd>
  <dt>Workflow / akış</dt><dd>Ajanın Freya'daki tanımı: düğümler, geçişler, tool'lar, prompt'lar. Teslim edilen dosya.</dd>
  <dt>Düğüm (node)</dt><dd>Akıştaki bir adım. Konuşma (model konuşur), kod (Python), banka isteği, aramayı bitir.</dd>
  <dt>Geçiş (transition)</dt><dd>Bir düğümden diğerine ne zaman gidileceği. Kesin koşul ya da niyet eşleşmesi; sırayla denenir.</dd>
  <dt>Extraction</dt><dd>Her turda müşterinin son mesajından çıkarılan küçük alanlar; geçiş koşullarını besler.</dd>
  <dt>Tool</dt><dd>Modelin çağırabildiği servis: banka servisleri (verify_identity, get_account, create_promise, add_note, schedule_callback, transfer_to_agent, close_call) ve geçiş tool'ları.</dd>
  <dt>Kanca (hook)</dt><dd>Tool'dan önce (pre) ve sonra (post) çalışan Python. Önce doğrular, sonra cevabı talimata çevirir.</dd>
  <dt>Slot</dt><dd>Freya'da aynı ajanın yerinde güncellenen adı (ours-a, hidden-1). Her koşu yeni sürüm.</dd>
  <dt>Export</dt><dd>Ajanın Freya'daki hâlinin dosyaya yazılması (submission/&lt;ad&gt;.workflow.json).</dd>
  <dt>Trace</dt><dd>Koşu günlüğü: saatler, her model çağrısı, Freya'da oluşturulan, testler. Teslimin parçası.</dd>
  <dt>Simülasyon</dt><dd>Freya'da sahte müşterinin (Gemini persona) ajanı araması; jüri de Gemini. Aynı workspace'te bir anda bir simülasyon.</dd>
  <dt>Ledger / banka kaydı</dt><dd>Bankanın tuttuğu sonuç: outcome, sebep, sözler, geri aramalar. Jürinin ikinci kontrol kaynağı.</dd>
  <dt>Bant / deadline / floor</dt><dd>Gecikme gününe göre sınıf; o sınıfın son ödeme günü; kabul edilen en düşük tutar.</dd>
  <dt>Ret sayacı</dt><dd>note_refusal: müşteri reddettikçe kodun saydığı deneme; kaçıncı teklif olduğunu ve ne teklif edileceğini kod söyler.</dd>
  <dt>Lokal test</dt><dd>tester/ aracı: CallSpec'ten vakalar, sahte banka, ajanın bilgisayarda taklidi; Freya'ya istek yok; sadece rapor.</dd>
</dl>
</section>
</main>

<script>
const AGENT = __AGENT__;
const COLORS = {conversation:"#2f6fed", code:"#1f9d55", api_request:"#b4832b", end_call:"#6b2f2f", closes:"#1f9d55"};
let selected = null;
function graphData() {
  const expand = document.getElementById("expand").checked;
  const isClose = id => id.startsWith("close_") && id !== "close_on_goodbye" && id !== "close_on_transfer";
  const closes = AGENT.nodes.filter(n => isClose(n.id));
  const nodes = AGENT.nodes.filter(n => expand || !isClose(n.id)).map(n => ({...n, label: n.id, kind: n.type}));
  if (!expand) nodes.push({id:"__closes", label:"close_* (" + closes.length + " kapanış)", kind:"closes", type:"code", text:"Her biri hint_outcome / hint_reason / hint_farewell yazan küçük kod düğümleri; hepsi decide_outcome'a geçer:\n" + closes.map(c => "• " + c.id).join("\n")});
  const edges = [], seen = new Map();
  for (const e of AGENT.edges) {
    let from = e.from, to = e.to;
    if (!expand) { if (isClose(from)) from = "__closes"; if (isClose(to)) to = "__closes"; }
    if (from === to) continue;
    const key = from + ">" + to;
    if (seen.has(key)) { seen.get(key).labels.push(e.label); continue; }
    const ed = {from, to, labels:[e.label], cap: !!e.cap}; seen.set(key, ed); edges.push(ed);
  }
  return {nodes, edges};
}
function render() {
  const {nodes, edges} = graphData();
  const g = new dagre.graphlib.Graph({multigraph:true}).setGraph({rankdir:"LR", nodesep:26, ranksep:80, marginx:24, marginy:24}).setDefaultEdgeLabel(() => ({}));
  nodes.forEach(n => g.setNode(n.id, {width: Math.max(110, n.label.length * 7 + 26), height: 38}));
  edges.forEach((e, i) => g.setEdge(e.from, e.to, {}, "e" + i));
  dagre.layout(g);
  const ns = "http://www.w3.org/2000/svg", view = document.getElementById("view"); view.innerHTML = "";
  const defs = document.createElementNS(ns, "defs");
  defs.innerHTML = '<marker id="arr" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#b6bdcb"/></marker>';
  view.appendChild(defs);
  edges.forEach((e, i) => {
    const ed = g.edge(e.from, e.to, "e" + i); if (!ed) return;
    const d = ed.points.map((p, k) => (k ? "L" : "M") + p.x + "," + p.y).join(" ");
    const grp = document.createElementNS(ns, "g"); grp.setAttribute("class", "edge" + (e.cap ? " cap" : "")); grp.dataset.from = e.from; grp.dataset.to = e.to;
    const path = document.createElementNS(ns, "path"); path.setAttribute("d", d); path.setAttribute("marker-end", "url(#arr)");
    const title = document.createElementNS(ns, "title"); title.textContent = e.labels.join(" | "); path.appendChild(title); grp.appendChild(path); view.appendChild(grp);
  });
  nodes.forEach(n => {
    const nd = g.node(n.id), grp = document.createElementNS(ns, "g");
    grp.setAttribute("class", "node" + (selected === n.id ? " sel" : "")); grp.setAttribute("transform", `translate(${nd.x - nd.width/2},${nd.y - nd.height/2})`);
    const r = document.createElementNS(ns, "rect"); r.setAttribute("width", nd.width); r.setAttribute("height", nd.height); r.setAttribute("fill", COLORS[n.kind] || "#555");
    const t = document.createElementNS(ns, "text"); t.setAttribute("x", nd.width/2); t.setAttribute("y", nd.height/2 + 4); t.setAttribute("text-anchor", "middle"); t.textContent = n.label;
    grp.appendChild(r); grp.appendChild(t); grp.style.cursor = "pointer";
    grp.addEventListener("click", ev => { ev.stopPropagation(); selected = n.id; show(n); render(); });
    view.appendChild(grp);
  });
  document.querySelectorAll(".edge").forEach(el => el.classList.toggle("hl", selected && (el.dataset.from === selected || el.dataset.to === selected)));
  if (!window.__fitted) { fit(g.graph()); window.__fitted = true; } else apply();
}
function esc(s) { return (s || "").replace(/[&<>]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;"}[c])); }
function show(n) {
  const p = document.getElementById("panel"); let h = `<b style="font-size:15px">${esc(n.label)}</b> <span class="tag">${n.type}</span>` + (n.max_turns ? `<span class="tag">en çok ${n.max_turns} tur → ${esc(n.cap_to)}</span>` : "");
  if (n.text) { p.innerHTML = h + `<p>${esc(n.text).replace(/\n/g, "<br>")}</p>`; return; }
  if (n.on_enter) h += `<h5>Girişte söylenen${n.first_only ? " (ilk giriş)" : ""}</h5><div>${esc(n.on_enter)}</div>`;
  if (n.tools.length) h += "<h5>Tool'lar</h5><ul style='padding-left:16px;margin:0'>" + n.tools.map(t => `<li><b>${esc(t.name)}</b>${t.pre ? ' <span class="tag">pre-hook</span>' : ""}${t.post ? ' <span class="tag">post-hook</span>' : ""}${t.mapping.length ? ' <span class="tag">→ ' + esc(t.mapping.join(", ")) + '</span>' : ""}<br><span style="color:#5d6676">${esc(t.desc)}</span></li>`).join("") + "</ul>";
  if (n.extraction.length) h += "<h5>Her turda çıkarılan</h5><ul style='padding-left:16px;margin:0'>" + n.extraction.map(e => `<li><b>${esc(e.name)}</b> ${e.enum.length ? '<span class="tag">' + esc(e.enum.join(" | ")) + '</span>' : ""}<br><span style="color:#5d6676">${esc(e.desc)}</span></li>`).join("") + "</ul>";
  if (n.transitions.length) h += "<h5>Geçişler (sırayla, ilk eşleşen kazanır)</h5><ol style='padding-left:18px;margin:0'>" + n.transitions.map(t => `<li>→ <b>${esc(t.to)}</b>: ${esc(t.desc)}<br><span style="color:#5d6676">${esc(t.cond)}</span></li>`).join("") + "</ol>";
  if (n.task) h += `<h5>Görev prompt'u</h5><pre>${esc(n.task)}</pre>`;
  if (n.code) h += `<h5>Kod</h5><pre>${esc(n.code)}</pre>`;
  p.innerHTML = h;
}
let tx = 0, ty = 0, scale = 1, drag = null;
const svg = document.getElementById("svg"), view = document.getElementById("view");
function apply() { view.setAttribute("transform", `translate(${tx},${ty}) scale(${scale})`); }
function fit(gr) { const W = svg.clientWidth || 700, H = svg.clientHeight || 600; scale = Math.min(1, W / (gr.width + 40), H / (gr.height + 40)); tx = (W - gr.width * scale) / 2; ty = (H - gr.height * scale) / 2; apply(); }
svg.addEventListener("mousedown", e => { drag = {x: e.clientX - tx, y: e.clientY - ty}; });
window.addEventListener("mousemove", e => { if (drag) { tx = e.clientX - drag.x; ty = e.clientY - drag.y; apply(); } });
window.addEventListener("mouseup", () => drag = null);
svg.addEventListener("wheel", e => { e.preventDefault(); const k = e.deltaY < 0 ? 1.1 : 0.9; const r = svg.getBoundingClientRect(); const mx = e.clientX - r.left, my = e.clientY - r.top; tx = mx - (mx - tx) * k; ty = my - (my - ty) * k; scale *= k; apply(); }, {passive:false});
document.getElementById("expand").addEventListener("change", () => { window.__fitted = false; render(); });
document.querySelector("details").addEventListener("toggle", ev => { if (ev.target.open) { window.__fitted = false; render(); } });
document.querySelectorAll(".tab").forEach(b => b.addEventListener("click", () => {
  document.querySelectorAll(".tab").forEach(x => x.classList.remove("active")); b.classList.add("active");
  document.querySelectorAll("section.view").forEach(s => s.classList.toggle("active", s.id === b.dataset.tab)); window.scrollTo(0, 0);
}));
</script>
</body>
</html>
"""

if __name__ == "__main__":
    wf = json.load(open(WF))
    agent = agent_graph(wf)
    page = PAGE.replace("__AGENT__", json.dumps(agent, ensure_ascii=False)).replace("__NNODES__", str(len(agent["nodes"])))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(page)
    print(f"wrote {OUT} ({len(page)//1024} KB): {len(agent['nodes'])} nodes, {len(agent['edges'])} edges from {WF}")
