# İlerleme notları (10 Ekim 2026)

## Görev özeti
- Freya × YC "Build the Builder" hackathonu. **Builder** yazıyoruz: brief + `openapi.json` okuyup Freya'da telefon ajanı (workflow) üreten program. Puanlanan şey ajan.
- Senaryo: gecikmiş borç tahsilat araması. 7 tool: `verify_identity`, `get_account`, `create_promise`, `add_note`, `schedule_callback`, `transfer_to_agent`, `close_call`.
- **Final:** Pazar 17:00–20:00 UTC (20:00–23:00 İstanbul). 2 gizli brief (biri temiz spesifikasyon, biri dağınık materyal: mail + politika + memo + kod listesi), her birinin kendi `openapi.json`'u var. Tool isimleri aynı kalıyor, alanlar ve enum'lar değişebilir.
- Brief başına 30 müşteri, her vaka 3 kez koşuluyor, 3/3 geçmesi gerekiyor. Skor = geçen / 60.
- Builder bir brief için en fazla 30 dk sürebilir (testler dahil), tek komutla ve elle müdahale olmadan çalışmalı. Gizli brief'ten koda bilgi yazmak yasak.
- Teslim: repo + commit, `export_workflow` ile 2 workflow JSON, 2 trace (başlangıç/bitiş, model çağrıları, Freya'da oluşturulanlar, testler).
- Ajan modeli `experimental-5` sabit. Müşteri ve judge `gemini-3-flash-preview`.
- Pazar 17–20 arası platform testleri limitli olacak (kapsamı ve sayısı henüz açıklanmadı). Chat API de muhtemelen sayılıyor.

## Repo yapısı
- `docs/build-the-builder/`: Freya'nın kit'i (v3). `briefs/`, `tools/openapi.json`, `freya.py`, `tools/run_cases.py`, `tools/score.py`, `docs/*.md` (workflow formatı, tools/code, API).
- `docs/freya-platform/`: Freya'nın public OpenAPI'sinden ürettiğim dökümanlar (personas, simulations, chat, calls, unit-tests) + `README.md` (kit'te olmayan bilgiler: unit test API'si, `/chat/fork`, `rerun`, persona PUT/DELETE).
- `tester/`: bizim lokal test aracımız (aşağıda).
- `env.sh`: key'ler (gitignore'da). `FREYA_API_KEY`, `FREYA_API_URL`, `FREYA_BANK_TEAM_KEY`, `GEMINI_API_KEY`. Kullanım: `source env.sh`.
- `results/`: test çıktıları (gitignore'da).

## Lokal test aracı (`tester/`)
- `tester/local_sim.py <workflow_id | agent_id | slot adı> [--brief A|B] [--only PUB-01] [--reps 3] [--style in_words] [--parallel 3]`
  - Müşteriyi Gemini oynuyor (persona prompt'u `run_cases.persona_for`'dan), ajan Freya chat API'si üzerinden experimental-5 ile çalışıyor.
  - Puanlama: banka kaydı (`score.score_ledger`) + Gemini judge (vakanın `checks` listesi).
  - Sonuçlar PASS / FAIL / ERROR (Freya veya Gemini altyapı hatası) olarak ayrılıyor. Her turun Gemini ve Freya süresi ölçülüyor.
  - Görüşme kayıtları `results/local/<zaman>/<vaka>-<rep>.json` altına yazılıyor.
- `tester/dump_call.py <run.json>`: bir görüşmeyi tool çağrıları, banka kaydı ve judge kararıyla okunabilir markdown'a çeviriyor. Örnek: `results/ornek-konusma-PUB-01.md`.
- `tester/gemini.py`: stdlib Gemini istemcisi.

## Freya'ya yüklü workflow'umuz
- Slot `base` = kit'teki `examples/base-agent.json`. workflow `e1f0dca9-fb1c-45da-a5d3-5bd42d415a8e`, agent `5458b55d-a8f2-4002-acf6-d0a3b5aba805`. Kayıt: `docs/build-the-builder/.freya-agents.json`.
- Base agent PUB-01 sonucu: banka kaydı GEÇTİ, judge KALDI (SMS cümlesini söylemiyor). Ayrıca açılış cümlesi brief'e aykırı ve "bugün ödeyebilir misiniz" diye sormuyor.

## Öğrenilenler / tuzaklar
- **Chat API:** `workflowId` ile çağrılmalı. Aralıklı 503 ve 504 veriyor, araç mesajı iki kez göndermeden tekrar deniyor.
- **Snekbox:** Freya'nın Python sandbox'ı aralıklı olarak çöküyor (`Failed to reach snekbox: Cannot connect to host snekbox-svc.staging.local:8060`). Hook'lar ve code node'lar buna bağlı. Freya'ya bildirilmedi henüz.
- **Base agent'ta `close_call`:** `alwaysRunsAt: end_of_call` lifecycle tool'u. Görüşme bittikten ~15–20 sn sonra, Freya'nın analizi bitince çalışıyor ve outcome'u model transcript'ten tahmin ediyor. Yavaş ve kırılgan. **Bizim builder'da `close_call`'u ajan görüşme içinde, deterministik bir outcome ile çağıracak.**
- **Gemini:** key prepay faturalandırmada, kredi yüklendi. Kendisi hızlı (~1.5 sn/tur).
- **Workspace ("Dora Alkan's Workspace") paylaşımlı:** başka biri (muhtemelen takım arkadaşı) `run_cases.py` ile simülasyon koşuyor; `ours-a`, `ours-ab`, `ext-*`, `brief-a`, `probe-codetool` workflow'ları ona ait. Aynı anda 1 simülasyon ve Pazar limiti ortak olacak.
- Ajan modeli `agent_config.llmConfig` = experimental-5 (`freya.save_workflow` ayarlıyor). Doğrulandı.

## Strateji (kararlaştırılan)
1. Brief'ten kural JSON'u çıkar (LLM) → test edilmiş şablon + code node'lar ile workflow üret → doğrula → düzelt.
2. Hesaplar (iş günü, deadline, tatil, sayaçlar) code node'larda. Yasaklar node yapısıyla. Tool sonuçlarına post-hook ile `what_to_do_next`.
3. Pazar'dan önce şablonu kendi sahte brief'lerimizle (biri dağınık formatta) kanıtla. Pazar günü test bütçeli (`--test-budget N`), modelsiz kontroller (code node'ları lokalde çalıştırma, statik kontrol, dry-run) öncelikli.

## Sıradaki adımlar
- [ ] 13 vakanın hepsini base agent ile lokal koş (baseline), bir kez de `run_cases.py` ile karşılaştır.
- [ ] Chat API'nin ilk adım code node ise onu atlayıp atlamadığını test et (mini workflow).
- [ ] Organizatörlere sor: Pazar test limiti neyi kapsıyor; snekbox hatası.
- [ ] Builder'ın ilk versiyonu: Brief A için 10/10 hedefi, `--reps 3`.
