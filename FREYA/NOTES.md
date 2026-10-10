# NOTES — Build the Builder (Freya x YC), 10–11 Ekim 2026

## Kararlar
- Yaklaşım: **compiler-first hibrit**. LLM brief'i `CallSpec`'e çevirir (+ küçük kural fonksiyonları), elle yazılmış deterministik compiler workflow JSON üretir. Detay: `~/.claude/plans/twinkly-napping-lobster.md`.
- Kit `kit/` altında, **değiştirilmez**. `kit/freya.py` client olarak kullanılır (AGENT_LLM sabit: experimental-5).
- Builder LLM: Anthropic (claude-opus-5-5 / sonnet-5-5), temperature 0.
- Slot adları: `brief-a`, `brief-ab`, `brief-c`. Aynı slot = aynı workflow güncellenir (200 workflow limiti).

## Ortam
- `env.sh`: FREYA_API_KEY (fak_...), FREYA_API_URL=https://staging-app.freyavoice.ai, FREYA_BANK_TEAM_KEY (16+ karakter, hep aynı), FREYA_WORKSPACE_ID (açıkça!), ANTHROPIC_API_KEY.
- Yanlışlıkla açılan ekstra workspace: zararsız. `GET /api/v2/workspaces` ile doğru id'yi seç ve env'e yaz.
- Python 3.13, anthropic 0.88, pydantic 2.13, claude-agent-sdk kuruldu.

## Skor özeti
- Case = müşteri. Ledger (outcome/reason, promises, notes, callbacks, transfers, son tool close_call, verify öncesi tool yok) + judge (policy, honesty). Tam/boş.
- Final: görülmemiş brief'ler (biri ham materyal), görülmemiş müşteriler, 3 koşu × hepsi geçmeli. Eşitlik: promise tutarı → build süresi → erken teslim.
- 30 dk/brief builder limiti; trace zorunlu; final brief içeriği koda/prompt'a yazılamaz.

## Açık sorular (organizatöre)
- Final brief'lerde `run_cases.py` için case dosyası veriliyor mu? Mock'un `/v1/practice/sessions` final'de çalışıyor mu? (Self-test tasarımını belirler.)
- Judge model hangi "checks" listesini kullanıyor final'de (bize gösterilmeyen)?

## Baseline
- base-agent run_cases A (10 Eki 15:20): **0/10**, 216 s, medyan tur 3 s. Tüm FAIL nedenleri results/baseline-base-agent-A.log
- kit agent_builder A (10 Eki 15:21–15:33): 1. koşu **8/10**, düzeltme sonrası 2. koşu **10/10**. 715 s, $2.62, 24 tur. 26 node, Python üreteci yazdı (fixtures/example-builder-A/build_brief_a.py). workflow 8e2497f0, agent 143c5929

## Learnings (τ²τ-bench makalesi, arXiv 2609.04611)
- Materyali grep'leme, oku. Ham brief'te memo eski kuralı sessizce değiştirir → extraction iki aşamalı: tüm kuralları listele, çelişenleri tarihle çöz.
- "Niyete göre yönlendir + tool çağrılarını kontrol et" ipucu skoru 2x yapmış → extraction enum routing + pre-hook promise doğrulama (planımız).
- Deterministik policy guard'lar kazandırıyor; ham model çıktısı kaybettiriyor → outcome/reason kod yazar.
- Kendi testlerin kör noktalarını taşır (10/10 lokal, 59.7 gizli) → Brief C provası, test gevşetme yasak, --reps 3.
- Sessiz tool hataları (retry, uydurma id) → post-hook düz cümle, product_id koddan.
- İlk çalışan tasarımı gönderme → keşif hackathon sırasında, final günü sadece şablon uygulanır.
- Soru sormayanlar 3x düşük → organizatöre sor.
- kit agent_builder A ajanı, --reps 3 (10 Eki 15:40): **10/10, 10/10, 10/10** (3/3 ile 10/10). 228 s toplam. Yani Brief A'da örnek builder'ın ajanı kararlı. Rakiplerin tabanı bu.
- kit agent_builder A ajanının sınırları (10 Eki 15:50): Brief B **0/3** (tek ürün alıyor); A `--style corrects` **9/10** (PUB-02: "10, pardon 11" → 10 kaydetti); A `--style in_words` **9/10** (PUB-04: "bin iki yüz elli" → 1200 kaydetti; tam tutar kabulünde tutar koddan gelmeli, modelden değil).

## Bizim compiler
- v1, Brief A, elle yazılmış CallSpec (10 Eki 16:20): **10/10** ilk koşuda, 73 s. workflow 76b6ef99, agent a1230ea7 (slot ours-a).
- Brief B ilk koşu **0/3**: facts kodu `product_id` değişkeni yazıyordu → tool alanı baked oldu, model p1 dışını seçemedi. Düzeltildi (model-filled alan adlarıyla çakışan var yasak).
- Extraction (Claude Opus, 10 Eki 16:35): Brief A → geçerli CallSpec ilk denemede, 58 s, $0.49; elle yazılanla 17 kritik alan birebir. Kopya: fixtures/callspec_brief_a.claude.json
- v1.1 (hook args via vars + farewell fix), A+B ajanı (10 Eki 17:05): Brief B **3/3**, Brief A 9/10 (PUB-08: ajan add_note(paid) yazdı; B kuralı A beklentisiyle çakışıyor, gerçek hata değil).
- Extraction A+B (10 Eki 17:15): geçerli CallSpec ilk denemede, 64 s, $0.47; multi_product ve tüm kritik alanlar fixture ile aynı; A/B add_note çelişkisini source_notes'ta çözmüş. Kopya: fixtures/callspec_brief_ab.claude.json. Slot ext-ab (agent 4d26dcd8).
- A ajanı --reps 3 (10 Eki 17:45): 10/10, 9/10, 10/10 → 3/3 ile 9/10. Tek düşüş PUB-10: judge açılıştaki "this call is recorded" kelimesini "recorded before success" ihlali saydı (davranış doğruydu). Önlem: açılışta "we record this call" (fixture + extractor talimatı).
- Stiller, A ajanı v1.1 (10 Eki 18:10): corrects **10/10**, in_words **10/10**, pieces 8/10 (PUB-07: yarım cümle "I can't do that, I" → model taban teklif etti; PUB-10: judge "recorded" kaprisi). Prompt'a "yarım cümlede tamamlamasını iste" + "bugün ödeyemem ≠ tutar itirazı" eklendi.
- AB ajanı v2 B --reps 3: 2/3, 3/3, 3/3. Düşüş PUB-12: tek turda iki add_note, sonra model sustu, müşteri kapattı; close_call outcome'u model uydurdu. Düzeltme v3: all_products_done response_mapping ile, outcome varsayılanı baked.
- Stil talkative, A v1.1: 8/10 (PUB-05: sempati+teklif tekrarı; PUB-10: judge "recorded"). Prompt: "her teklif/açıklama tam bir kez, dağılırsa kısa soruyla geri getir".
- AB v4 B --reps 3 (10 Eki 19:00): 2/3, 2/3, 2/3 → 0/3. PUB-11: model 3 create_promise'ı paralel çağırdı, hook'lar birbirini görmedi, "bitti" yolu tetiklenmedi, model sustu, müşteri kapattı. PUB-13: model izinli tarihi deadline'a kaydırdı. PUB-12: judge "today?" sorusunu deneme saydı (tartışmalı).
- v5: "bitti" geçişi platform sayaçlarından (create_promise_success_count + add_note_success_count ≥ n_products, k=1..5 numaralandırılmış AND grupları); decide_outcome promise sayısını sayaçtan da alıyor; prompt: izinli tarihi taşıma, tool'ları tek tek çağır.
- A v2 talkative: 8/10. PUB-04: "cümlenizi tamamlayın" döngüsü (yeni kuralın yan etkisi) → kural yumuşatıldı (sadece cevap yarımsa iste, en fazla 2 kez). PUB-06: müşteri doğru tekliften 3 sn sonra kapattı (rastgele).
- A v2 pieces: 9/10 (PUB-07 geçti; PUB-10 judge "300 cannot be recorded"). Sistem kuralı: başarıdan önce "recorded" kelimesi yasak.
- **DİKKAT**: A v2 asks_back koşusu 0/10 çıktı; sebep koşu sırasında aynı slotu yayınlamam (16:42:32), canlı aramalar dondu. Kural: simülasyon koşan ajanı yayınlama; önce kuyruk bitsin.
- **Platform arızası (10 Eki ~16:40–?)**: /chat/message ikinci turda 503 (hem bizim hem örnek ajan). Bu aralıktaki tüm simülasyon sonuçları (A v2 asks_back 0/10, A v4 reps run1 0/10) geçersiz. Kuyruk durduruldu; platform dönünce A v4 reps3 + stiller, AB v7 B reps3 yeniden koşulacak.
- Platform 16:57'de döndü. **A v4 --reps 3 (10 Eki 20:05): 10/10, 10/10, 10/10 → 3/3 ile 10/10.**
- AB v7 B --reps 3 (20:10): 3/3, 0/3 (banka mock verify_identity connection error ×3, platform), 2/3 (PUB-12: model geç banttaki loan'a 1 deneme yaptı, 2 olmalıydı; judge "bugün?" sorusunu da deneme saydı). Karar: deneme sayacı koda alınacak (note_refusal code_exec tool) — önce platformda code_exec-as-tool doğrulanacak.
- Probe (20:20): code_exec tool konuşma node'unda model tarafından çağrılıyor, argüman `params` sözlüğünde geliyor, ama sonucu modele dönmüyor (data null). Sayaç tool'u bu yolla olmaz. Alternatif (yarın, gerekirse): get_account api_call'ı taşıyıcı olarak kullanıp pre/post hook'ta sayma.
- v8: offers_text'e ürün başına açık "refusal script" (deneme 1: X tarih D1; deneme 2: taban D2; sonra add_note/close).
- A v4 asks_back (17:10–17:20): **10/10**. A v4 talkative (17:20): 5/10, 5 düşüşün 5'i snekbox arızası (judge gerekçelerinde "snekbox connection failure") → geçersiz, sabah tekrar.
- builder/test/scan.py: her koşunun tüm aramalarını (geçen dahil) kötü kalıplar için tarar (loop, sessizlik, snekbox, uydurma close_call, 'recorded', hang-up). İlk tarama: PUB-07 geçerken bile "cannot be recorded" diyordu → kaynak calendar_text metni, "not allowed" yapıldı. "Could you answer my question?" 4x tekrar (talkative, geçti) izlenecek.
- AB v8 B --reps 3 rerun (17:30–17:40): 3/3, 0/3 (snekbox), 1/3 (snekbox + PUB-11: sayaç geçişi doğru çalıştı [route matched after 3rd promise], ama decide_outcome code node'u snekbox yüzünden çalışmadı → varsayılan outcome gitti). Sayaç tabanlı "bitti" geçişi doğrulandı.
- 20:50: veda düzeltmesi + kelime temizliği yayınlandı: ours-a v5, ours-ab v9. Gece ölçüm yok; sabah: A geveze/parça, B 3 tekrar, scan.py ile her koşu.
- 19:45 tarama (arıza dışı koşular): yeni sınıf yok; kimlik aşamasında aynı soru 3-6x (geçiyor, döngü riski). Kural: tool teknik hatada 1 tekrar sonra kapanışa geç; aynı soru en fazla 2 kez. Yayın: A v6, AB v10.
- A v6 --reps 3 (19:50–19:56): 10/10, 9/10, 10/10. Düşüş PUB-08 rep2: ilk get_account isteği 12 s timeout sonrası tekrarlandı, gecikmiş ilk istek bankaya close_call'dan SONRA ulaştı ("close_call son tool değil"). Ağ gecikmesi, önlenemez; 60+ aramada 1 kez.
- AB v10 B rep2 PUB-12: müşterinin "yarın" (15 Ekim, izinli) teklifi reddedildi → v8'deki refusal script modeli katılaştırdı (regresyon). Ayrıca ürün başına "bugün?" tekrar soruldu (B kural 4 ihlali). Düzeltme v11: script "sadece düz ret sonrası", "müşterinin izinli tarihi her zaman kabul", "Yarın: ..." satırı, çok üründe "bugün'ü tekrar sorma". Zincir bitince yayınlanacak.
- A v6 talkative (20:05): 8/10. PUB-03: tam söylenmiş DOB'u "tamamlayın" diye reddetti (kural fazla geniş) → "cevap tamsa kullan". PUB-05: simülatör bozuk mesaj üretti, ajan teklifi tekrarladı + vedada "I understand/take care" ikinci sempati sayıldı → geri getirme sadece "Is that a yes or a no?", hardship vedası sade.
- A v6 pieces (20:10): 9/10. PUB-09: müşteri "bu tutarı ödeyemem" / "düşük taksit istiyorum" cümlesini iki parçada söyledi; ajan ilk parçaya teklif yaptı, judge "transferden önce plan anlattı" saydı. Parça stilinin kaçınılmaz yan etkisi, düzeltme yok.
- Gece zinciri özeti (v6/v10, snekbox temiz): A 10-9-10 (gecikme), B 3-2-2 (PUB-12, v11 düzeltmesi bekliyor), talkative 8/10 (v7 düzeltmesi bekliyor), pieces 9/10.
- AB v12 B --reps 3 (20:25): 2/3, 3/3, 3/3. PUB-12: "yarın" artık kabul; kalan sorun ürün başına "bugün?" sorusu (judge deneme sayıyor). v13: çok üründe ürün açılış cümlesi doğrudan 1. deneme ("Can you pay X on <att1>?").
- **A v7 talkative (20:35): 10/10** (önce 8/10). Tam-cevap kuralı ve "yes or no" geri getirme işledi.
- AB v13 B --reps 3 (20:15–20:22): **3/3, 3/3, 2/3**. PUB-12 rep3: bu kez loan'a 1 deneme yaptı (2 olmalı). Deneme sayısı tek kararsız sınıf; prompt ile %70-80 bandında. Yarın: deterministik sayaç (get_account taşıyıcı hook) denemesi.
## Gün sonu (10 Eki 20:25), temiz koşular, son sürümler (A v7, AB v13)
- A: 3 tekrar 10-9-10 (gecikme); stiller corrects 10, in_words 10, asks_back 10, talkative 10, pieces 9.
- B: 3 tekrar 3-3-2 (PUB-12 deneme sayısı).
- Extraction: A, A+B, C ilk denemede doğru. Builder tek komut, ~1 dk, trace+export.
- Yarın: API key testi; deneme sayacı; builder'ın kendi düzeltme döngüsü; kapsama seti (Mehmet); tool API cevap alanlarını openapi'den okuma; öğlen dondurma.
- 21:00 **Tool API alan eşlemesi**: `tools.field_map()` canonical→gerçek ad (exact → eşanlamlı → gevşek eşleme → uyarı). codegen/compiler tüm banka alanlarını eşlemeden okuyor. Test: briefs_extra/brief-c/openapi-renamed.json (12 alan yeniden adlandırılmış) → derleme, selfcheck, dryRun OK.
- 21:35 **Fix loop uçtan uca** (ext-a, Brief A, --style pieces, --fix-rounds 1): extraction 59 s → test 8/10 → Claude revizyonu 69 s ($0.42; hardship teklifi bir kez, belirsiz dönemde tek soru) → yeniden derle (v3) → test **10/10**. Toplam 351 s. Trace: traces/20261010-203007-ext-a.txt. Yapısal koruma (tatil/bant/outcome/kimlik soruları değişmez) geçti.
- 21:50 Fallback senaryoları: (1) test dosyasız koşu (Brief C) 61 s, export+trace OK; (2) dar bütçe (4 dk): test koştu 9/10, fix turu "bütçe yetersiz" diye atlandı, export OK.
- PUB-05 corrects: müşteri "hoşça kalın" deyince veda geçişi sabit `refused`'a gitti (bağlam hardship'ti) + sempati tekrarı. v9/v15: negotiate'e `situation` extraction (hardship/paid/dispute/plan/human/refusal/negotiating) + `close_on_goodbye` kod node'u bağlama göre kapanış seçiyor; "müşteri tekrar anlatsa da sempati bir kez".
- A v9 (22:05): corrects **10/10**, plain **10/10**. Bağlama göre veda kapanışı ve sempati kuralı doğrulandı.
## Gün sonu 2 (22:05): son sürümler A v9, AB v14. Yarın: API key testi, deneme sayacı (B PUB-12), Mehmet kapsama seti, öğlen dondurma, akşam final.
## Mehmet'in inceleme bulguları (10 Eki 22:30) — uygulananlar
- #1 debt intro cümlesi koddan çıktı → CallSpec.debt_intro_sentence (extractor doldurur). #2 "Say that…" metinleri: şema "aynen söylenen cümle", _sentence sertleştirildi, fixture'lar düzeltildi. #3 pre-hook precheck bayrağı (promise/note/callback), post-hook mock hata metnine bağımlı değil. #4 parser: path son segmenti, YAML, PDF/encoding toleransı. #5 run_cases timeout = kalan bütçe. #6 lint_spec: outcome/queue/field/note enum'ları openapi ile karşılaştırılır, extractor'a retry. #7 product_id create_promise'da her zaman (final müşterileri 3 ürüne kadar). #8 test_variables.customer_id kaldırıldı. #11 human_request boşsa special.human. #12 close_done metni sadece çok üründe; floor fallback.
- Yeni bilgi: final Pazar 20:00–23:00 İstanbul, brief başına 30 müşteri, puan = geçen/60; Pazar platform test limiti var (sayı belirsiz).
- 22:55 #9/#10 yayınlandı (A v11, AB v16): tek transfer_to_agent tool'u (queue enum model-doldurmalı, pre-hook doğrular, close_on_transfer kuyruktan kapanış seçer); tek üründe promise sonrası bir tur açık (transition_to_close_promise model çağırır; veda/transfer yolları var). Ölçüm: **A 10/10, B 3/3**. Not: B koşusu 415 s sürdü (platform yavaştı).
## Gün sonu 3 (23:00): son sürümler A v11, AB v16. Yarın: API key testi; deneme sayacı; Mehmet'in Freya-moda kapsama koşusu (çakışmayalım: simülasyon kuyruğu tek); 3 tekrar ölçümleri; öğlen dondurma; 20:00 final.
