# İlerleme notları (10 Ekim 2026, akşam)

## Görev özeti
- Freya × YC "Build the Builder" hackathonu. **Builder**: brief + `openapi.json` okuyup Freya'da telefon ajanı (workflow) üreten program. Puanlanan şey ajan.
- Senaryo: gecikmiş borç tahsilat araması. 7 tool: `verify_identity`, `get_account`, `create_promise`, `add_note`, `schedule_callback`, `transfer_to_agent`, `close_call`.
- **Final:** Pazar 17:00–20:00 UTC (20:00–23:00 İstanbul). 2 gizli brief (biri temiz spesifikasyon, biri dağınık materyal: mail + politika + memo + kod listesi), her birinin kendi `openapi.json`'u var. Tool isimleri aynı kalıyor, alanlar ve enum'lar değişebilir.
- Brief başına 30 müşteri (1–3 ürün, farklı takvim günleri, insan gibi konuşan müşteriler), her vaka 3 kez koşuluyor, 3/3 geçmesi gerekiyor. Skor = geçen / 60. Eşitlikte: toplam söz tutarı, sonra build süresi.
- Builder bir brief için en fazla 30 dk (testler dahil), tek komut, elle müdahale yok. Gizli brief'ten koda bilgi yazmak yasak.
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

**Dora'ya iletilecek (öncelik sırası):** (1) söz sonrası anında kapanış: OUR-13 + OUR-24; Brief A metni "transfer follows a recorded promise" ve kural 36'yı açıkça anıyor, gizli sette olması muhtemel. (2) `test_variables.customer_id` (chat API). (3) tool adları API adlarıyla aynı olsun (OUR-10/11 judge). (4) OUR-25: "I don't want to talk" ilk seferde kapanış.

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

## Öğrenilenler / tuzaklar
- **Chat API + `test_variables.customer_id` (ÖNEMLİ):** Dora'nın workflow'unda `test_variables` içinde `"customer_id": "c_test"` var. Chat API'de tool'lar (`verify_identity`) gönderdiğimiz `customerVariables.customer_id` yerine `c_test`'i kullanıyor → mock reddediyor → ajan "technical problem" deyip kapatıyor. `close_call` (end_of_call) gerçek id'yi alıyor. Base agent'ın `test_variables`'ında `customer_id` yok, orada sorun yok. Simülasyon (`run_cases`) etkilenmiyor (Dora 10/10 oradan). Docs "call değeri kazanır" diyor, chat API'de öyle değil.
  - Önceki "OUR-06 snekbox yüzünden düştü" teşhisi YANLIŞTI; sebep bu. `code_exec` sonucunun `null` görünmesi normal (docs: `data: null`).
  - Çözüm seçenekleri: (1) Dora'nın workflow'unun `test_variables.customer_id` silinmiş kopyasını kendi slotumuza (`ours-a-chattest`) yükleyip Freya modunda onu koş — kullanıcı onayı bekleniyor. (2) Dora compiler'da `test_variables`'a `customer_id` koymasın.
- **Chat API:** `workflowId` ister (agent id ile 500). Aralıklı 500/503/504. `api.md`: ilk adım code node ise chat route atlayabilir.
- **Snekbox:** Freya'nın Python sandbox'ı aralıklı çöküyordu (`Failed to reach snekbox…`). Şu an çalışıyor.
- **Gemini judge** bazen çok uzun düşünüyor (215 sn); 90 sn timeout × 3 retry ile ERROR'a düşebiliyor.
- **Workspace paylaşımlı** (Dora ile): aynı anda 1 simülasyon. Chat API simülasyon kuyruğunu kullanmıyor.
- Ajan modeli `agent_config.llmConfig` = experimental-5 (`freya.save_workflow` ayarlıyor).

## Sıradaki adımlar
- [ ] (onay bekliyor) `ours-a-chattest` kopyasını oluştur, 18 vakayı Freya modunda koş, lokal ile karşılaştır → emülatör kalibrasyonu (`path` alanı bunun için).
- [ ] Lokal 18 vaka --reps 2 koşusu: `results/coverage-local-v2.json` (10 Eki 20:40 başladı). Yeni 10 vaka: `results/coverage-local-new.json`.
- [ ] (Dora'yla koordine) `python3 tester/run_coverage.py a1230ea7-d704-4c24-8b07-d44e3f1d9b8a --cases tester/coverage-cases.json --out results/coverage-freya.json` → Freya judge ile lokal judge karşılaştır, `--judge-view` seç.
- [ ] Coverage tablosu `--reps 2`, sonuç Dora'nın `NOTES.md`'sine "Coverage set" başlığıyla (vaka, rep başına pass/fail, sınıf, tek satır kanıt).
- [ ] Dora'ya bulgular: `c_test` / test_variables, tool adları (OUR-10/11), OUR-13.
- [ ] Brief B (`ours-ab`) için çok ürünlü coverage vakaları.
- [ ] Organizatörlere sor: Pazar limiti hangi endpoint'leri kapsıyor (chat/message, simulations, unit-tests), kaç tane.
- [ ] Pazar için runner'a bütçe sayacı + koşu öncesi sağlık kontrolü.
