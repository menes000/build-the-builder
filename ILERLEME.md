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
- Builder'ı takım arkadaşı Dora yazdı (ayrı repo, bu makinede yok): `python3 -m builder.main <brief> --slot X`. Claude CallSpec çıkarır → deterministik compiler workflow üretir → publish + export + trace. Pratik sette A 10/10 (3 koşu), B 3/3.
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
- [ ] (onay bekliyor) `ours-a-chattest` kopyasını oluştur, 18 vakayı Freya modunda koş, lokal ile karşılaştır → emülatör kalibrasyonu.
- [ ] Coverage tablosu `--reps 2`, sonuç Dora'nın `NOTES.md`'sine "Coverage set" başlığıyla (vaka, rep başına pass/fail, sınıf, tek satır kanıt).
- [ ] Dora'ya bulgular: `c_test` / test_variables, tool adları (OUR-10/11), OUR-13.
- [ ] Brief B (`ours-ab`) için çok ürünlü coverage vakaları.
- [ ] Organizatörlere sor: Pazar limiti hangi endpoint'leri kapsıyor (chat/message, simulations, unit-tests), kaç tane.
- [ ] Pazar için runner'a bütçe sayacı + koşu öncesi sağlık kontrolü.
