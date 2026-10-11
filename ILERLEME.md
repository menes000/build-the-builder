# İlerleme notları (10 Ekim 2026, akşam)

## Görev özeti
- Freya × YC "Build the Builder" hackathonu. **Builder**: brief + `openapi.json` okuyup Freya'da telefon ajanı (workflow) üreten program. Puanlanan şey ajan.
- Senaryo: gecikmiş borç tahsilat araması. 7 tool: `verify_identity`, `get_account`, `create_promise`, `add_note`, `schedule_callback`, `transfer_to_agent`, `close_call`.
- **Final:** Pazar 17:00–20:00 UTC (20:00–23:00 İstanbul). 2 gizli brief (biri temiz spesifikasyon, biri dağınık materyal: mail + politika + memo + kod listesi), her birinin kendi `openapi.json`'u var. Tool isimleri aynı kalıyor, alanlar ve enum'lar değişebilir.
- Brief başına 30 müşteri (1–3 ürün, farklı takvim günleri, insan gibi konuşan müşteriler), her vaka 3 kez koşuluyor, 3/3 geçmesi gerekiyor. Skor = geçen / 60. Eşitlikte: toplam söz tutarı, sonra build süresi.
- Builder bir brief için en fazla 30 dk (kendi koştuğu testler dahil), elle müdahale yok, ajan elle düzenlenmez. Gizli brief'ten koda bilgi yazmak yasak (kural, değer, isim).
- **Final sırasında builder'daki genel bir bug düzeltilebilir** (README: "After the final briefs open you may fix a bug in your builder... Fixing a crash on a table your parser did not expect is allowed"). **Builder birden çok kez koşulabilir, bir koşunun ajanı + o koşunun trace'i teslim edilir.** Eşitlikte kısa build süresi avantaj → builder'ın kendi içindeki test kısa olmalı; bizim lokal test builder dışında koşar, build süresine girmez.
- Teslim: repo + commit, `export_workflow` ile 2 workflow JSON, 2 trace.
- Ajan modeli `experimental-5` sabit. Müşteri ve judge `gemini-3-flash-preview`.
- **Pazar 17–20 platform test limiti:** docs'ta sayı/kapsam yok. Kickoff transcript'i (36:30–36:48): "limit on our platform, but no limit if you test yourself in your local… your system should simulate personas in itself". Chat API'nin sayılıp sayılmadığı bilinmiyor → lokal emülatör bu yüzden yazıldı.

## Durum: builder Dora'da, bizim görev test
- Builder'ı takım arkadaşı Dora yazdı. Kopyası bu repoda `FREYA/` altında (Dora düzenliyor, biz dokunmuyoruz; `FREYA/` dışı bizim): `cd FREYA && python3 -m builder.main <brief> --slot X`. Claude CallSpec çıkarır → deterministik compiler workflow üretir → publish + export + trace. Pratik sette A 10/10 (3 koşu), B 3/3.
- Bizim görev: `HANDOFF-coverage-tests.md`. PUB setinin test etmediği kurallar için kendi vakalarımız + lokal test altyapısı + sonuç tablosu. `kit/` ve Dora'nın `builder/compile/`'ına dokunma; check yumuşatma yok.
- Dora'nın ajanları (paylaşımlı workspace):
  - Brief A `ours-a`: workflow `76b6ef99-1679-4369-be3a-4580b853a8a8`, agent `a1230ea7-d704-4c24-8b07-d44e3f1d9b8a`
  - A+B `ours-ab`: workflow `e2378685-6142-444c-96c4-7f39d6aa0d1a`, agent `c95855d9-8457-4845-b92a-07d06797f1d1`
  - Export (lokal emülatör için): `results/workflows/ours-a.json`, `results/workflows/ours-ab.json`

## Repo yapısı
- `docs/build-the-builder/`: Freya'nın kit'i (v3). `briefs/`, `tools/openapi.json`, `freya.py`, `tools/run_cases.py`, `tools/score.py`, `docs/*.md`.
- `docs/freya-platform/`: Freya public OpenAPI'den üretilmiş dökümanlar (personas, simulations, chat, calls, unit-tests).
- `tester/`: bizim test aracımız (aşağıda).
- `env.sh`: key'ler (gitignore). `FREYA_API_KEY`, `FREYA_API_URL`, `FREYA_BANK_TEAM_KEY`, `GEMINI_API_KEY`. `source env.sh`.
- `results/`: test çıktıları (gitignore).
- **Commit edilmemiş değişiklikler var:** yeni `tester/emulator.py`, `tester/coverage_cases.py`, `tester/coverage-cases.json`, `HANDOFF-coverage-tests.md`; güncel `tester/local_sim.py`, `tester/gemini.py`, bu dosya.

## Test aracı (`tester/`)
- `local_sim.py <workflow_id | agent_id | slot | workflow.json> --agent freya|local [--cases F] [--only X,Y] [--reps N] [--style S] [--parallel N] [--out F]`
  - Müşteri ve hakem her iki modda Gemini (persona prompt'u `run_cases.persona_for`). Skor: banka ledger'ı (`score.score_ledger`) + Gemini judge (vakanın `checks`'i). PASS / FAIL / ERROR (altyapı) ayrı.
  - `--agent freya` (varsayılan): ajan Freya'da, chat API ile tur tur. Agent id verilirse workflow id Freya listesinden bulunur.
  - `--agent local`: `tester/emulator.py` workflow JSON'unu kendisi yürütür. Her tur extraction → routing → dialogue (Gemini); code node + pre/post hook lokal Python (snekbox yok); api_call tool'ları gerçek bank mock'a gider (ledger aynı); `end_of_call` lifecycle tool'ları çağrı bitince. Dosya verilirse Freya'ya hiç istek yok. Freya'nın yaklaşığı: docs'ta olmayan detaylar tahmin (prompt sarmalayıcısı, extraction güven eşiği, deterministik/intent routing sırası).
  - Kayıtlar `results/local/<zaman>/<vaka>-<rep>.json` (transcript judge'dan önce kaydediliyor). Özet satırı `results/local-log.jsonl`.
- `coverage_cases.py` → `coverage-cases.json`: 18 vaka OUR-01..18 (wrong number, deceased, unclear, no_callback, declined, gün/ay ters, floor altı, kendi tutarı, dispute, human, support, refused x2, söz+human, iki ikna denemesi, belirsiz tarih, cumartesi, "next Friday", scam). Her biri `session_case` ile bir PUB hesabını ödünç alır (mock sadece PUB id'lerini tanıyor). Tarihler kodla hesaplanır, assert edilir.
- `dump_call.py`, `gemini.py` (`call()` = function calling, `generate()` = düz metin/JSON).
- **Emülatör sadakat güncellemesi (10 Eki 20:40, docs ile satır satır karşılaştırıldı):**
  - `agent_config.llmConfig.tools` içindeki ajan seviyesi `end_call` tool'u artık her konuşma node'unda modele sunuluyor (Freya'da model bununla sessizce kapatabiliyor). Çağrılırsa `flags`'e yazılır.
  - Diyalog modeli sıcaklığı ve maxTokens `llmConfig`'ten (0.7 / 1000), sabit 0.3 değil.
  - Extraction: model her değer için güven veriyor, `min_confidence` altı atılıyor (Freya token olasılığından hesaplıyor; bizimki yaklaşık). Atılan değer `flags`'e yazılır.
  - Lifecycle tool (`close_call`) çözülmemiş `{{var}}` alanı varsa docs'taki gibi tek model çağrısıyla dolduruluyor (eskiden alan düşüyordu) + flag.
  - Tool `timeoutMs` kullanılıyor; `call.duration` var; terminal `end_call` çağrısı transcript'te görünüyor (Freya ile aynı).
  - "Model sessiz kaldı" (metin yok, tool yok) ve "tek mesajda N tool çağrısı" `flags`'e yazılıyor; Freya'da ilki "no speakable content" hatası, ikincisi paralel hook sorunu (NOTES PUB-11).
  - Satırda `path` (girilen node'lar sırayla) var; Freya modunda `node_enter` olaylarından, lokalde emülatörden → ikisi birebir karşılaştırılabilir.
  - **Freya modu düzeltmesi:** chat API `endedByAgent`'ı `end_call` sonrası da false dönüyordu, runner fazladan tur yolluyor, ajan ikinci `close_call` atıyordu (mock "already closed" diyordu). Şimdi ajan vedalaşınca bir kez `get_call` ile `endedReason` kontrol ediliyor. Doğrulandı: OUR-01 tek `close_call`.
  - Routing sırası doğrulandı (Freya `route_evaluated` olayı): `opening`'de intent transition listede `always`'ten önceyse önce o değerlendiriliyor; emülatör de öyle.

## Sonuçlar (ours-a, 1'er rep)
| Vaka | Lokal (emülatör) | Freya (chat API) |
|---|---|---|
| OUR-01..05 (doğrulama öncesi biten) | 5/5 PASS | 5/5 PASS (birebir aynı) |
| OUR-06, 07, 08 | PASS | FAIL — geçersiz, `c_test` sorunu (aşağıda) |
| OUR-09, 12, 14–18 | PASS | koşulmadı (koşu durduruldu) |
| OUR-10 human | FAIL judge | FAIL geçersiz (`c_test`) |
| OUR-11 support | FAIL judge | koşulmadı |
| OUR-13 söz+human | FAIL | koşulmadı |
- Lokal toplam: 15/18 ilk koşu (OUR-10 tekrarında da judge FAIL).
- **OUR-10 / OUR-11 (judge, tool adı):** ledger doğru. Ama transcript'te tool adı `transfer_general` / `transfer_support`, check "`transfer_to_agent` called" diyor; judge kaldırıyor (OUR-10'da 215 sn düşündü). Organizatör check'leri de API tool adlarını kullanıyor (PUB-09) → **Dora'ya: workflow'daki tool adları API'deki adlarla aynı olsun.**
- **OUR-13 (ajan tasarımı):** söz kaydedilince ajan hemen vedalaşıp kapatıyor; müşteri sonra insan isteyemiyor. Brief A'da "transfer follows a recorded promise → transferred" kuralı var. Dora'ya sor.

## Sonuçlar v2 (10 Eki 20:40–21:00, lokal emülatör güncel sürüm, judge tool görünümü)
| Vaka | Lokal 2 rep | Sınıf | Kanıt |
|---|---|---|---|
| OUR-01..09, 12, 14..18 | 15/15 vaka 2/2 PASS | — | path'ler beklenen node sırasında |
| OUR-10 human | 1/2 → tekrar 2/2 | judge / tool adı (judge bazen affediyor) | transcript'te `transfer_general`, check `transfer_to_agent` ister; ledger doğru |
| OUR-11 hardship | 0/2 ERROR → judge `thinking=low` ile tekrar: 0/2 FAIL | altyapı → judge / tool adı | eski ayarda judge 90 sn timeout ×3; yeni ayarda 8 koşu 56 sn, timeout yok. FAIL sebebi OUR-10 ile aynı: `transfer_support` ≠ `transfer_to_agent`; ledger doğru |
| OUR-13 söz+human | 0/2 FAIL | ajan tasarımı | `create_promise` sonrası ajan hemen vedalaşıp `end_call`; müşteri insan isteyemiyor |
| OUR-19..22, 26..28 (yeni) | 7/7 PASS (1 rep) | — | kural 15, 23, 26, 30-early, 42-kimlik, Cuma takvimi (deneme 1 = 23 Eki, deadline 28 Eki), 18:30 callback doğru |
| OUR-23 read-back'te tutar | FAIL (1 rep) → check netleştirildi → 2/2 PASS | judge hatası | ajan 1500 ile tekrar okudu ve onay istedi; judge "ikinci kez okumadı" dedi |
| OUR-24 kayıtlı sözü değiştir | FAIL (1 rep) | ajan tasarımı (= OUR-13) | söz kaydedilince hemen kapanış; müşteri "Cuma'ya alalım" diyemiyor, kural 36 cümlesi hiç söylenemiyor |
| OUR-25 doğrulama öncesi "konuşmak istemiyorum" | FAIL 3/3 koşu | ajan (model kararı, kararlı) | ilk redde `transition_to_close_declined` çağrıldı; kural 15 "önce bir kez açıkla" atlandı. OUR-05 (açık "vermem") 2/2 geçiyor. Freya'da doğrulanmalı |

## Resmi yol vs lokal (10 Eki 21:05, `run_coverage.py`, Freya simülasyon + Freya judge, 28 vaka, 1 koşu, 178 sn, sim `4e297550`)
| Vaka | Freya resmi | Lokal (Gemini) | Yorum |
|---|---|---|---|
| 24 vaka | PASS | PASS | birebir aynı |
| OUR-13, OUR-24 | FAIL | FAIL | **doğrulandı**: söz sonrası anında kapanış (ajan tasarımı) |
| OUR-25 | FAIL | FAIL 3/3 | **doğrulandı**, experimental-5'te de aynı transcript: ilk "I don't want to talk"ta `close_declined`, kural 15 açıklaması yok |
| OUR-15 | FAIL | PASS 2/2 | Freya ajanı belirsiz tarih + "bilmiyorum" sonrası deadline (23 Eki) yerine Cuma 16'yı önerdi (kural 21 → deadline; kural 30 "non-answer → deneme 1 = Cuma" ile çakışıyor, Dora'nın prompt'u 30'u seçmiş). Gemini ajan doğru yaptı → emülatör bu tür prompt-yorum farklarını yakalayamaz |
| OUR-10, OUR-11 | PASS | 10: 1/2→2/2, 11: 0/2 | Freya judge `transfer_support` ve `api_call` (get_account) adlarını affetti; lokal judge affetmiyordu → judge'a artık URL'deki API uç adı gösteriliyor (`endpoints_of`). Tool adı bulgusu Dora için düşük öncelik oldu |

Sonuç: emülatör 28 vakanın 26'sında Freya ile aynı karar (2 farkın biri judge katılığı, düzeltildi; biri model farkı). Pazar için lokal test güvenilir; model-yorum farkları için az sayıda resmi koşu ayrılmalı.

**Dora'ya iletilecek (öncelik sırası):** (0) OUR-15: belirsiz tarih sonrası "bilmiyorum" → kural 21 deadline önerisi; şu an deneme-1 Cuma'ya gidiyor (Freya'da düştü). (0b) OUR-25: "konuşmak istemiyorum" ilk seferde kapanış; kural 15 "önce bir kez açıkla" + kural 45 "iki kez" (Freya'da düştü). Eski liste: (1) söz sonrası anında kapanış: OUR-13 + OUR-24; Brief A metni "transfer follows a recorded promise" ve kural 36'yı açıkça anıyor, gizli sette olması muhtemel. (2) `test_variables.customer_id` (chat API). (3) tool adları API adlarıyla aynı olsun (OUR-10/11 judge). (4) OUR-25: "I don't want to talk" ilk seferde kapanış.

## Dora'ya builder bulguları (FREYA/ kod incelemesi, 10 Eki 21:30; biz dokunmuyoruz, Dora'ya iletilecek)
Önem sırasıyla. Hepsi hedeflenen davranışa değil, final brief'inde (başka kelimeler/alanlar) kırılmaya dair.
| # | Bulgu | Yer | Öneri |
|---|---|---|---|
| 1 | Debt statement'ta `'collections team about a late payment'` sabit; `DEBT_RULE` parametresi kullanılmıyor. Brief C "arrears team / overdue payment" der → yanlış cümle + "brief değeri kodda" kural ihlali | `builder/compile/codegen.py:248` | CallSpec'e `debt_intro_sentence` alanı, codegen onu kullansın |
| 2 | Sözlü söylenen alanlar talimat gelince aynen okunuyor: `after_failed_text` string replace ile cümleye çevriliyor; Brief C extraction "Say they should use the app or a branch; say nothing about the balance." üretti → ajan bunu söyler. `paid.say` benzer (`_sentence` sadece "Say that" soyuyor) | `compiler.py:221`, `compiler.py:67` | Şemada "exact spoken sentence, first person"; compiler'da "Say/Tell" ile başlıyorsa reddet/retry |
| 3 | Hook'lar mock'un hata metnine bağımlı: pre-hook reddi (`date='REJECTED'`) post-hook'ta `'must be'/'invalid'/'REJECTED'/'already'` string'lerinden anlaşılıyor. Final mock başka metin dönerse ret → "servis hatası" → 2. seferde `no_promise/service_error`. `callback_post`, `note_post` aynı | `codegen.py:398, 564` | pre-hook `vars['promise_precheck']='rejected'` yazsın, post-hook önce onu okusun |
| 4 | Parser kırılgan: tool adı `path.strip('/')` (prefix'li path → KeyError), `servers` yoksa URL boş, openapi YAML → crash, brief PDF/docx → `read_text` crash | `builder/extract/tools.py:27`, `extractor.py:27` | Son path segmenti; `servers` yoksa hata ver; yaml fallback; binary brief'te pdftotext/pandoc veya net hata |
| 5 | 30 dk bütçe aşılabilir: deadline sadece test başlamadan önce kontrol ediliyor; 24. dk'da başlayan `run_cases` 11 dk sürebilir | `builder/main.py:110` | `subprocess.run(..., timeout=kalan)` |
| 6 | CallSpec ↔ openapi anlamsal doğrulama yok (outcome/reason, queue, identity field, note reason enum'ları). Bir yazım farkı = 0 puan | `extractor.py` / yeni `lint_spec` | enum'ları openapi ile karşılaştır, hatayı extractor'a retry olarak geri ver (altyapı var) |
| 7 | Tek-ürünlü spec + 2 ürünlü müşteri = her promise REJECTED (`product_id` alanı yok → `pid=''`). README: "Final customers can have up to three products" | `codegen.py:321`, `compiler.py:165` | `product_id` alanı her zaman; çok-ürün mantığı runtime `n_products`'a göre |
| 8 | `test_variables.customer_id='c_test'` chat API'de gerçek id'yi eziyor (simülasyonda sorun yok) | `compiler.py:378` | Sil, maliyeti sıfır |
| 9 | Söz sonrası transfer imkânsız (Brief A kural 46 son satır, Brief B kural 10): tek üründe `promise_state==recorded` tool sonucunda anında kapanıyor → OUR-13/24 | `compiler.py:318` | Kapanışı tool transition / bye intent yap; post-hook'lar `vars['outcome']/['reason']`'ı anında yazsın (müşteri kapatırsa `close_call` doğru gitsin). Aynı önlem platformun `agent_config`'e eklediği `end_call` tool'u için de gerekli |
| 10 | Tool adları `transfer_general/support/restructuring` ≠ API `transfer_to_agent`; bizim judge OUR-10/11'i düşürüyor, Freya judge PUB-09'u geçiriyor (tool adını görmüyor olabilir) | `compiler.py:181` | Belirsiz; alternatif tek `transfer_to_agent`, `queue` enum model-filled + pre-hook doğrulama |
| 11 | `human_request` Brief C extraction'da null → security node'da transfer tool yok. Brief A kural 45 "doğrulama öncesi de geçerli" | `fixtures/callspec_brief_c.claude.json`, `compiler.py:264` | Extractor varsayılanı `special.human` olsun |
| 12 | Küçük: `promise_post` tek üründe de "call transition_to_close_done" diyor (tool yok); bilinmeyen product type → floor 0 → her tutar kabul; `scan.py` CLOSE_INVALID Brief A outcome listesine sabit; `verify_post` "Both security answers" (3 soruda yanlış, dahili) | `codegen.py:428, 163`, `test/scan.py:58` | fallback `minimum_payment`/`instalment_amount`; listeyi spec'ten al |

**Not:** OUR-25 (ilk redde kapanış) sonucu Gemini ajanla alındı; Dora'ya iletmeden önce Freya'da (`run_coverage`) doğrula. OUR-21 check'i kural 26+30 okuması; kural 31 "reddedilen teklifi tekrarlama" ile çelişebilir, FAIL gelirse sınıf "kural belirsizliği".

## v12 doğrulaması (10 Eki 21:30, Dora: ours-a v12, tool adı tek `transfer_to_agent`, c_test kaldırıldı)
| Vaka | Lokal v12 (2 rep) | Resmi v12 | Not |
|---|---|---|---|
| OUR-13 | 2/2 PASS | 1/2 | run 2: söz sonrası "Is there anything else I can help you with?" + insan isteyince "Can I help you with anything first?" → Freya judge "yardım sorusu iki kez" saydı. Judge'a duyarlı; söz sonrası soru "help" kelimesiz olmalı ya da insan isteği gelince ikinci soru sorulmamalı |
| OUR-24 | 2/2 PASS | 0/2 | **experimental-5 model davranışı, Gemini'de yok.** Söz sonrası "Cuma'ya alalım" → ajan read-back + `create_promise` tekrar; pre-hook "one promise per product" reddediyor (`date: REJECTED`), ama what_to_do_next genel sebep listesi veriyor, ajan tarih sorunu sanıp bugünü ve 2 Kasım'ı yeniden öneriyor, 3–4 `create_promise`. Kural 36 cümlesi ya hiç yok ya 3. redden sonra. Ledger temiz (mock reddetti). Çözüm: hook ve prompt "bu ürün için söz zaten kayıtlı → değiştirilemez, mobil uygulama" demeli; kayıtlı ürün için `create_promise` bir daha çağrılmamalı |
| OUR-15 | 2/2 PASS | 2/2 PASS | belirsiz tarih → deadline, düzeldi |
| OUR-25 | 0/2 FAIL | 0/2 FAIL | **kök neden routing, prompt değil.** Freya v6 kaydı `route_evaluated`: security node'unda t4 intent "The customer says goodbye, says they are hanging up, or clearly ends the conversation" → "I don't want to talk about anything right now" ile eşleşti → `close_declined`; diyalog modeline sıra gelmedi. v12 prompt'u düzeltti ama t4 açıklaması aynı. Çözüm: t4 intent'ini daraltmak ("explicitly says goodbye / hanging up now. NOT: refusing to answer, not wanting to talk, asking what the call is about") ya da kapanış kararını tamamen diyalog modelinin tool transition'ına bırakmak. Emülatör aynı kararı verdi (routing Gemini). |
- Resmi v12 koşusu: sim `f8322ed1`, 474 sn, 2 tekrar. Sonuç JSON `results/coverage-freya-v12.json`, log `.log`.
- **Emülatör sınırı (kesinleşti):** model-yorum farkları (experimental-5'in reddedilen tool'u tekrar tekrar çağırması, judge'ın "help" sayması) lokalde görünmüyor. Eklenen bayrak: aynı tool bir aramada 2+ kez reddedilince `flags`'e yazılır (her iki mod). Pazar: lokal = kural/akış/takvim hataları; resmi = model davranışı için az sayıda koşu.
- Emülatöre `routes` eklendi: intent ile alınan her routing kararı `flags`'te "routed by intent: ..." olarak görünüyor; bu sınıf hata artık doğrudan okunuyor.
- Lokal 4 vaka × 2 rep 550 sn sürdü (judge/müşteri yavaşlamış olabilir; Gemini yoğunluğu). İzlenecek.

## İkinci ajanın incelemesi (10 Eki 21:00) ve yapılanlar
| # | Bulgu | Karar / yapılan |
|---|---|---|
| 1 | Resmi yol (Freya simülasyon + Freya judge) hiç koşulmadı | `tester/run_coverage.py` yazıldı: kit'in `run_cases.py`'ını `session_case` + vaka `variables` (now) desteğiyle exec eder. **Koşulmadı**: paylaşımlı workspace'te aynı anda tek simülasyon, Dora'yla koordinasyon gerek. |
| 2 | Judge'a tool satırları + code_exec gidiyor; Freya judge belki sadece konuşmayı görüyor | `--judge-view tools\|spoken` eklendi (varsayılan `tools`; `code_exec`, `end_call`, ENGINE satırları her zaman atılıyor). Hangisinin Freya'ya yakın olduğu ancak #1 koşulunca anlaşılır. |
| 3 | Vakanın `variables.now`'u yok sayılıyordu | `run_case` ve `run_coverage` vaka değişkenlerini session üstüne yazıyor (`customer_id` hariç). OUR-27 (Cuma), OUR-28 (18:30) bununla çalışıyor. |
| 4 | Kapsanmayan kurallar | OUR-19..28 eklendi: 15 (iki kez "ne için arıyorsunuz"), 23 (deadline reddi), 26 (floor reddi), 30 early tek deneme, 35 (read-back'te tutar değişimi), 36 (kayıtlı sözü değiştirme), 45 doğrulama öncesi, 42 kimlik sırasında, Cuma takvimi (deneme 1 → 23 Eki, deadline 28 Eki, 26 tatil), 18:30 callback. Brief B hâlâ yok. |
| 5 | OUR-07 check "300 cannot be recorded" Dora'nın "recorded" yasağıyla çelişiyor | Check davranışa çevrildi: "300'ü kabul etmez, 300 için create_promise çağırmaz". **Anlaşmazlık notu:** Brief A kural 27 "say it cannot be recorded" diyor; Dora judge kaprisi yüzünden "I can't take that amount" dedirtiyor. Organizatör judge'ı kelimeye bakarsa risk; Dora'nın NOTES'undaki ölçümler (PUB-07 geçti) Dora'nın lehine. |
| 6 | Judge 215 sn | `gemini.generate(thinking=...)` eklendi; judge `thinkingLevel: low` (`JUDGE_THINKING` env ile değişir; `minimal` düşünmeyi tamamen kapatır). |
| 7 | BYE listesi "Bye!" kaçırıyor | Regex oldu. |
| 8 | Emülatör route() deterministiği her zaman önce almıyor | **Reddedildi.** Freya `route_evaluated` kaydı (OUR-01, 20:30): `opening`'de listede önce gelen intent (t4 → close_unclear) sonraki `always`'ten (t5 → opening_retry_1) önce eşleşti. Emülatör liste sırasını uyguluyor, Freya ile aynı. |

## OUR-24 yan yana: lokal (Gemini ajan) vs Freya (experimental-5), v15 (11 Eki 00:20–00:40)
| | Lokal 2 rep | Freya 2 rep (sim `b9951724`) |
|---|---|---|
| Sonuç | PASS, PASS | PASS, PASS |
| Node yolu | setup > opening > security > load_account > account_facts > negotiate > **after_promise** > close_promise > decide_outcome > goodbye | birebir aynı |
| Söz sonrası | "Your promise is recorded. You will receive a text message... Is there anything else?" | aynı cümle (TTS, hook'tan) |
| "Cuma'ya alalım" | "A recorded promise cannot be changed or cancelled in the same call; they can change it in the mobile app. Is there anything else?" | kelimesi kelimesine aynı |
| `create_promise` | 1 | 1 (v12'de 3–4'tü, düzeldi) |
| Fark | Gemini doğum tarihinden sonra "That's correct" ekliyor; read-back cümle kalıbı az farklı | Freya run 1 929 sn sürdü (platform yavaş), run 2 80 sn |
Sonuç: v15 `after_promise` node'u model farkını kapattı; experimental-5 artık kayıtlı ürün için tool'u tekrar çağırmıyor. Lokal ile Freya aynı kararları verdi. Judge artık `gpt-5.4-mini` (lokal) vs Freya judge: ikisi de PASS.
- Not: ilk deneme 00:15'te ağ hatasıyla (DNS) başlamadan düştü; bilgisayar uyumuş olabilir. Uzun koşularda uyku kapalı olmalı.

## v15 lokal regresyon (10 Eki 23:10, kredi yüklendi, thinking low)
| Vaka | Lokal v15 2 rep | Not |
|---|---|---|
| OUR-13, 24, 25 | 2/2 PASS | v14/v15 düzeltmeleri lokalde tutuyor: `security_explain` (bir kez açıkla, ikincide kapat), `after_promise` (söz sonrası açık tur, insan → transfer, değiştirme → uygulama cümlesi) |
| OUR-05, 12, 19 | 2/2 PASS | regresyon yok |
| OUR-03 | 0/2 → check netleştirildi | judge hatası: NO_DISCLOSURE'ı "banka adını söylemiş" diye okudu; banka adı kural 1 gereği. Check'e "Freya Bank'tan aradığını söylemek zorunlu" eklendi |
- OUR-12: `get_account` iki kez görünüyor → Dora'nın v14 ret sayacı (`get_account` endpoint'i taşıyıcı, hook'ta sayım). Tasarım gereği; judge "iki kez" derse risk, Dora'ya bilgi.
- Maliyet ölçümü: 14 arama = 202 Gemini çağrısı, 176k prompt, 4.8k çıktı, 5.8k düşünme → düşünme artık ihmal edilebilir, fatura prompt token'ından. 70 sn.
- Resmi v15 koşusu henüz yok (kuyruk Dora'da).

## Gemini maliyeti (10 Eki 22:50)
- Bugün ~130 lokal arama = 121 TRY (~3 $), arama başına ~1 TRY. Sebep: her tur 4–6 çağrı, diyalog çağrısı tüm geçmiş + ~5k token system prompt, ve `gemini-3-flash-preview` varsayılan olarak her çağrıda düşünüyor (thinking token'ları çıktı fiyatından).
- Yapılan: müşteri `thinking=low` (`CUSTOMER_THINKING`; `minimal` istenmedi, senaryoya uyum için), extraction/routing `low` (`ENGINE_THINKING`), judge `low`; diyalog modeli varsayılan (`AGENT_THINKING` boş). Koşu sonunda "Gemini usage: N calls, X M prompt, Y k output, Z k thinking" satırı; `results/local-log.jsonl`'a da yazılıyor. **Kredi gelince ilk koşuda arama başına token/maliyet ölç, Pazar bütçesini ona göre ayır.**
- Kredi: 402 "prepayment credits are depleted" 21:33'te. Yükleme https://ai.studio/projects.

## Öğrenilenler / tuzaklar
- **Chat API + `test_variables.customer_id` (ÖNEMLİ):** Dora'nın workflow'unda `test_variables` içinde `"customer_id": "c_test"` var. Chat API'de tool'lar (`verify_identity`) gönderdiğimiz `customerVariables.customer_id` yerine `c_test`'i kullanıyor → mock reddediyor → ajan "technical problem" deyip kapatıyor. `close_call` (end_of_call) gerçek id'yi alıyor. Base agent'ın `test_variables`'ında `customer_id` yok, orada sorun yok. Simülasyon (`run_cases`) etkilenmiyor (Dora 10/10 oradan). Docs "call değeri kazanır" diyor, chat API'de öyle değil.
  - Önceki "OUR-06 snekbox yüzünden düştü" teşhisi YANLIŞTI; sebep bu. `code_exec` sonucunun `null` görünmesi normal (docs: `data: null`).
  - Çözüm seçenekleri: (1) Dora'nın workflow'unun `test_variables.customer_id` silinmiş kopyasını kendi slotumuza (`ours-a-chattest`) yükleyip Freya modunda onu koş — kullanıcı onayı bekleniyor. (2) Dora compiler'da `test_variables`'a `customer_id` koymasın.
- **Chat API:** `workflowId` ister (agent id ile 500). Aralıklı 500/503/504. `api.md`: ilk adım code node ise chat route atlayabilir.
- **Snekbox:** Freya'nın Python sandbox'ı aralıklı çöküyordu (`Failed to reach snekbox…`). Şu an çalışıyor.
- **Gemini judge** bazen çok uzun düşünüyor (215 sn); 90 sn timeout × 3 retry ile ERROR'a düşebiliyor.
- **Workspace paylaşımlı** (Dora ile): aynı anda 1 simülasyon. Chat API simülasyon kuyruğunu kullanmıyor.
- Ajan modeli `agent_config.llmConfig` = experimental-5 (`freya.save_workflow` ayarlıyor).

## Pazar düzeneği: ne yapıldı (11 Eki 01:30–11:30)
Problem tanımındaki 5 maddenin çözümü. Protokol: `docs/PAZAR-PROTOKOLU.md`.

| Parça | Dosya | Ne yapar | Doğrulama |
|---|---|---|---|
| Sahte banka | `tester/fakebank.py` | Organizatör mock'unun lokal kopyası: her kimlik alanı, her hesap (vaka dosyasından), aynı ledger şekli, `faults` (fail_first_n), "already has a promise", "identity not verified", day_month_swapped ipucu. `score.py` değişmeden puanlar | gerçek mock probe'larıyla self-test; PUB-10 arıza yolu PASS |
| `--bank local` | `local_sim.py`, `emulator.py` | tool URL'leri sahte bankaya yönlenir, oturum/ledger oradan | OUR-05/06/28 + PUB-10 PASS |
| Vaka üretici | `tester/cases_from_callspec.py` | CallSpec → ~30 tek ürün + 6 çok ürün şablonu; tarih/tutar koddan (`Rules`: bant, deadline iş/takvim günü, floor alanı, callback penceresi, deneme-1 kuralı); hesap havuzu + sentez (eksik kimlik alanı, boş bant); `check()` her beklentiyi kurallara göre doğrular; kuralı olmayan şablon atlanır ve listelenir | Brief A: 30 vaka, elle yazılan 28'in tüm imzaları üretildi; Brief C: 30 (postcode, no_slot/not_confirmed/refused_check/plans/hardship_desk, "serious" bandı sentetik, 09:00–17:30); Brief B: 36 |
| Kural diff'i | `tester/rule_diff.py` | gpt-5.4-mini ham brief'i (klasör: mail+memo+kod listesi) bağımsız okur, CallSpec'in sayısal/enum alt kümesiyle alan alan diff; kaynak belge belirtir | Brief C: 0 gerçek fark (memo'nun 5 değişikliği CallSpec'te var); format farkları prompt'a kelime dağarcığı verilerek giderildi |
| Tek komut | `tester/final.sh <slot> [reps] [parallel]` | CallSpec → vakalar → lokal koşu → `results/<slot>-report.md` | Brief C 122 sn, Brief A (v15) 135 sn |
| Sağlık | `tester/health.py` | key'ler, Freya API, kuyruk, mock, Gemini, OpenAI, sahte banka | hepsi OK |

**Prova sonuçları (11 Eki sabah):**
- Brief C (`ext-c` ajanı, 10 Eki 21:05 derlemesi, v11 öncesi): 24/30. Düşenler: söz sonrası kapanış ×2 ve floor iki kez (eski derleme, A'da v11–v15 ile düzelen sınıf), belirsiz tarih → floor önerdi (OURC-21, A'da v12 ile düzelen sınıf). Check ifadesi kaynaklı 3 FAIL düzeltildi (judge "bugün?" sorusunu ikna, Cuma teklifini plan, 1. denemeyi "deneme sonrası teklif" saydı).
- Brief A üretilmiş set, v15 ajanı: **29/30**. Tek FAIL **OUR-09 kimlik sırasında insan isteği: v14 regresyonu.** `security` node'unun `declined_1` extraction tanımı "refuses to answer… says no" diyor; "I want to speak to a real person" ret sayılıyor → `security_explain` → `declined_2` → `close_declined`. Diyalog modeline (transfer tool'u orada) hiç sıra gelmiyor. v12'de geçiyordu (OUR-26). Dora'ya: extraction tanımına "insan/temsilci isteğinde boş bırak" ya da `human` enum değeri + transfer yolu.
- Brief B çok ürün (`ext-ab`, 20:22 derlemesi): 5/6. OURB-35 "söz üzerinde anlaşıldı ama okunmadı, plan istendi" → tek okuma kuralında söz kaydedilmez (önce şablon yanlıştı, düzeltildi). OURB-36 arıza ×2: not doğru, sözler korunuyor.
- Maliyet: 30 arama ≈ 600k Gemini prompt token + 20k düşünme + 150 OpenAI çağrısı; ~2.5 dk.

**Sınırlar:** (1) şablonlar bilinen kural ailelerini test eder; şemada olmayan kural tipi için LLM senaryo önerisi yazılmadı (zaman). (2) Sahte banka brief'i uygulamaz (mock gibi). (3) `needs_local_bank` vakalar resmi yola gidemez. (4) Judge ve extraction gpt-5.4-mini, Freya'nınkiler farklı; kalibrasyon Gemini judge ile yapıldı (26/28).

### Dora'nın builder self-test isteği (11 Eki 11:16) → cevap
- `tester/local_test.py`: tek çağrı, CallSpec + export → vakalar → lokal koşu → JSON (`rows`: id, status, failed, flags, judge_reason, transcript, path). exit 0/1/2. Dora'nın `--local-test` bayrağı bunu subprocess ile çağırır, `passed/total`'ı trace'e yazar.
- Tester kit yolunu otomatik bulur (`kit/` veya `docs/build-the-builder`); Dora düzeninde prova edildi. Paket: `results/handoff-dora-tester-20261011.zip` (tester/ + README + protokol).
- Öneri: kademe 1 (sadece rapor, trace'e test satırı) bugün; kademe 2 (fix loop) yalnız A'da resmi sonuçla uyum görülürse ve düzeltmeler genel kalıyorsa.

## Pazar için problem tanımı (11 Eki 01:30)
Pazar 20:00'de iki görülmemiş brief gelecek; Dora'nın builder'ı ~5 dk'da ajan üretecek; 3 saat içinde o ajanın gizli jüri müşterilerinde nerede düşeceğini bulup Dora'ya genel düzeltme fırsatı vermemiz gerekiyor. Bugünkü düzenek bunu yapamıyor:
1. **Vakalar elle ve tek brief'e özgü.** 28 vaka Brief A değerleriyle elle yazıldı. Yeni brief için elle yazmaya zaman yok, gizli değerleri elle yazmak gri alan. Brief → vaka dönüşümü otomatik değil.
2. **Çok ürün kapsanmıyor.** Final müşterileri 3 ürüne kadar (README). Brief B tipi vaka yok; emülatör `ours-ab` ile hiç koşulmadı (paralel `create_promise`, `add_note` sayaçları, "bitti" geçişi Dora'nın en kırılgan alanı).
3. **Extraction kör noktası.** Ajan da vakalar da aynı CallSpec'ten beslenirse extraction'ın kaçırdığı kural test edilmez. Dağınık brief'te (memo eski kuralı eziyor) en olası hata bu.
4. **Model farkı.** Lokal ajan Gemini, gerçek experimental-5; 28'de 26 uyum ama farklar "model huyu" sınıfında. Pazar resmi koşu limitli; hangi vakaların resmi yola ayrılacağı kuralı yok.
5. **Operasyon.** Tek komut zinciri (export → vaka üret → koş → rapor) yok; bank mock final hesaplarıyla çalışır mı bilinmiyor; teslim formatı (`builder/build.py {brief} {openapi}`, `submission/`, `traces/<ad>.log`) Dora tarafında henüz yok.

Çözüm planı (sıra):
- (1)+(3) `tester/cases_from_callspec.py`: 28 şablon, değerler CallSpec'ten, tarihler koddan, assert'li; + LLM ile ham brief'ten bağımsız kural listesi → CallSpec diff (extraction hatası adayları); + şablon dışı kurallar için LLM senaryo önerisi, beklenen ledger kodla doğrulanır. Check yazım kuralları sabit: davranış + somut sayı/tarih, brief kelimeleri, "X zorunludur, ihlal değildir" netleştirmeleri, API tool adı.
- (2) 8–10 çok ürünlü şablon (kısmi söz + kısmi red, tek tarih bir ürünün deadline'ını aşıyor, bir ürün "ödedim" diğeri söz, restructuring sonrası not yok, bir üründe `create_promise` hatası, hepsi "ödedim" → paid, iki farklı bant); PUB-11..13 hesapları; `ours-ab` lokal + 1 resmi.
- (5) `tester/final.sh` + `health.py`; Brief C ile baştan sona prova, süre ölçümü. Dora'ya teslim formatı iletildi (01:00 mesajı).
- (4) riskli vaka kuralı: tool tekrar bayrağı, `after_promise`, intent routing geçen vakalar, ret sayacı → resmi yolda öncelik.

## Sıradaki adımlar (11 Eki, finale kadar)
- [ ] Dora: OUR-09 regresyonu (declined extraction vs insan isteği), `build.py` sarmalayıcı + `submission/` + trace'e node/tool sayısı ve mutlak saat; `ext-c`/`ext-ab`'yi güncel compiler ile yeniden derleyip bize export.
- [ ] Biz: Dora'nın yeni derlemeleriyle `final.sh` provası (C ve AB), OUR-09'u resmi yolda 1 koşu.
- [ ] 19:30 `health.py`, kuyruk koordinasyonu, protokol okuması.
- [x] Pazar düzeneği (sahte banka, vaka üretici, kural diff'i, final.sh, health.py) — yukarıda.

## Sıradaki adımlar (eski)
- [ ] (onay bekliyor) `ours-a-chattest` kopyasını oluştur, 18 vakayı Freya modunda koş, lokal ile karşılaştır → emülatör kalibrasyonu (`path` alanı bunun için).
- [ ] Lokal 18 vaka --reps 2 koşusu: `results/coverage-local-v2.json` (10 Eki 20:40 başladı). Yeni 10 vaka: `results/coverage-local-new.json`.
- [x] Resmi koşu yapıldı (21:05): 24/28, `results/coverage-freya.json`. `--judge-view tools` Freya'ya yakın (tool adları artık API adı).
- [x] v12 lokal: 13/15/24 düzeldi, 25 routing yüzünden hâlâ düşüyor. Resmi v12 koşusu kuyruk boşalınca otomatik (`results/coverage-freya-v12.log`).
- [ ] Dora t4 intent'ini daraltınca OUR-25 (+ OUR-05, 12, 19 regresyon) tekrar.
- [ ] Coverage tablosu `--reps 2`, sonuç Dora'nın `NOTES.md`'sine "Coverage set" başlığıyla (vaka, rep başına pass/fail, sınıf, tek satır kanıt).
- [ ] Dora'ya bulgular: `c_test` / test_variables, tool adları (OUR-10/11), OUR-13.
- [ ] Brief B (`ours-ab`) için çok ürünlü coverage vakaları.
- [ ] Organizatörlere sor: Pazar limiti hangi endpoint'leri kapsıyor (chat/message, simulations, unit-tests), kaç tane.
- [ ] Pazar için runner'a bütçe sayacı + koşu öncesi sağlık kontrolü.
