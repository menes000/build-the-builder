# Pazar protokolü (11 Ekim 2026, 20:00–23:00 İstanbul)

Kurallar (kit README + organizatör maili): builder koşusu ≤30 dk, elle müdahale yok, ajan koşudan sonra düzenlenmez; **koşular arasında builder'daki GENEL bug düzeltilebilir, builder birden çok kez koşulabilir, bir koşunun ajanı + o koşunun trace'i teslim edilir**; gizli brief'ten koda/prompt'a değer yazılmaz (tatil, kuyruk, cümle, outcome adı). Eşitlikte: söz tutarı toplamı → kısa build süresi → erken teslim.

## 19:30 hazırlık
```
source env.sh && python3 tester/health.py        # key'ler, Freya API, kuyruk, bank mock, Gemini, OpenAI, sahte banka
```
Uyku kapalı (uzun koşuda DNS kopuyor), git temiz, `final/` boş, Dora'nın `build.py` sarmalayıcısı ve teslim formu şablonu hazır.

## 20:00 brief'ler gelir (mail/kanal → `final/hidden-1/`, `final/hidden-2/`; her biri md'ler + openapi.json)
İkimiz 5 dk okuruz (okumak serbest, değer yazmak yasak).

## Brief başına döngü (hedef ≤40 dk)
```
Dora:  python3 builder/build.py final/hidden-1 final/hidden-1/openapi.json 2>&1 | tee traces/hidden-1.log      (~5 dk)
       → FREYA/out/hidden-1.callspec.json, FREYA/out/hidden-1.export.workflow.json, agent id
Biz:   BRIEF=H1 TAG=H1 tester/final.sh hidden-1 2 8      (callspec/export'u FREYA/out, FREYA/submission, final/ altında kendisi bulur;
       OPENAPI=final/hidden-1/openapi.json ile sahte banka zorunlu alan/enum doğrular; STYLE=talkative ile stil)     (~5 dk)
       1 cases_from_callspec.py  CallSpec → ~30 vaka (+çok ürünlü), değerler CallSpec'ten, tarihler koddan, assert'li
       2 local_sim.py --agent local --bank local  Gemini ajan + sahte banka + gpt-5.4-mini judge, 2 tekrar
       3 results/hidden-1-report.md
Biz:   python3 tester/rule_diff.py FREYA/out/hidden-1.callspec.json final/hidden-1 --openapi final/hidden-1/openapi.json   (~30 sn)
       → extraction hatası adayları (ikinci model brief'i bağımsız okur, CallSpec ile alan alan diff)
```
Karar (2 dk, ikimiz):
- Rapor temiz + diff temiz → 3–5 riskli vakayı resmi yolda doğrula: `python3 tester/run_coverage.py <agent> --cases results/hidden-1-cases.json --only ...` (Pazar limiti; riskli = flags'li, after_promise/transfer yolları, intent routing, model-huyu sınıfları).
- FAIL, genel hata (routing intent, hook, prompt şablonu, parser) → Dora builder'ı düzeltir → yeniden build (yeni trace) → final.sh tekrar.
- FAIL, extraction kuralı kaçırmış (rule diff gösterir) → extraction prompt'unun GENEL zaafı düzeltilir ("memo ezer", "kod listesi outcome adlarını belirler"), değer yazılmaz → yeniden build.
- FAIL, judge kaprisi / vaka ifadesi → not, geç (check metnini düzeltmek serbest, test tarafı).
- FAIL, model farkı şüphesi (Gemini geçer, experimental-5 bilinmez) → resmi yola aday.
- `needs_local_bank` vakalar (sentetik hesap/alan) sadece lokalde; resmi yola gitmez.

## Sınıflama kılavuzu (dünkü dağılım: 28 vakada 26 lokal/Freya uyumu)
| Sınıf | Belirti | Yapılacak |
|---|---|---|
| platform | snekbox, 503, judge timeout | tekrar |
| judge | gerekçe transcript'le çelişiyor | check metni, geç |
| vaka | senaryo bölünmüş, beklenen yanlış | şablon düzelt (test tarafı) |
| ajan, genel | routing intent, hook, prompt | Dora → builder fix → rebuild |
| extraction | CallSpec brief'ten farklı | rule diff + brief; extraction prompt'u genel düzeltme |
| model farkı | lokal geçer, Freya düşer | resmi yolda 1–2 koşu |

## 21:20+ yedek
İkinci koşular, erken teslim. 22:30 teslim paketi (Dora): repo + commit, `submission/hidden-1.workflow.json`, `submission/hidden-2.workflow.json`, `traces/hidden-1.log`, `traces/hidden-2.log`, form JSON → kit mailindeki adres, 23:00 son.

## Ağır test (final'de, sınırsız)
Hızlı sinyal: `final.sh hidden-1 1 8` (~3 dk). Sonra arka planda jüri kriteriyle: `final.sh hidden-1 3 10` ve stiller
`STYLE=pieces|corrects|talkative|asks_back|in_words final.sh hidden-1 2 10`. Raporlarda 3/3 geçmeyenler ve stil bazlı düşenler.
Koşu başında iki denetim satırı okunur: `emulator audit` (desteklenmeyen Freya özelliği) ve `bank audit` (üretilemeyen cevap alanı).

## Kırmızı çizgiler
Freya'daki ajanı elle düzenleme ✗ · brief değerini koda/prompt'a yazma ✗ · tek build > 30 dk ✗ · kuyrukta çift simülasyon ✗ · `FREYA/` ve `kit/` bize kapalı ✗

## Bütçe
Lokal 30 vaka × 2 tekrar ≈ 60 arama ≈ 1.2M Gemini prompt token + 150 OpenAI çağrısı (dün: 30 arama 135 sn, 606k prompt, 20k düşünme). Pazar iki brief × 2 koşu ≈ 250 arama; kredi yeterli olmalı, `Gemini usage` satırını izle.
