# Freya Bank statement debt agent: design note

All prompts and fixed sentences are in Turkish. Call variables: `customerNumber`, `now` (test: 95004361, 2026-10-12T10:30:00+03:00).

## Flow (nodes)
1. `cards_list` (api_request, initial). Says "Bilgilerinizi kontrol ediyorum." and calls cards.list.
2. `prepare_cards` (code). Decides between no card (404 FB_IVR_CHANNEL_102), one card, several cards, or an error. It builds a numbered card list for the model: names that look like instructions or are empty are marked `[adı okunmaz]`, and `isMainCard=false` cards are marked `SEÇİLEMEZ`. It also builds the selection question with at most two example names. For a single card it sets `selectedCardNumber` directly.
3. `select_card` (conversation, several cards only). Handles Steps 2, 2a, 2b and 2c. The model calls `cards_balance` with a list index (`cardIndex`). A pre-hook turns that index into the masked `cardNumber` exactly as cards.list returned it, so the number is never rebuilt from the caller's digits.
4. `cards_balance` (api_request, single card). Calls cards.balance with the `cardNumber` baked in.
5. `build_reading` (code). Writes the whole reading as exact Turkish text: amounts in words, kuruş/sent/peni handling, the Turkish suffix on the last word ('dır / 'tir), dates, last four digits one by one, the "due date passed" and "statement cut today" cases, auto-payment, missing currency blocks, the no-debt sentence, and the Step 5 no-statement-debt text. Every "today" check uses `now`. It then picks the next step: ask about another card (several cards), go to the offer (single card with debt, or debt and e-mail asked together), or end with the no-debt text (single card).
6. `read_debt` (conversation, several cards). Speaks the reading and the other-card question as fixed TTS text. The extracted `next_step` routes to: another card, offer, e-mail, week change, or the main menu.
7. `contact_email_get` (api_request) runs once per call, before the offer. If `email_state` is already set, it is skipped. A failed lookup is not sent to an agent here.
8. `prepare_offer` (code). Works out `hasEmail` / `emailLookupFailed`, the spoken form of the address (read in full if short, otherwise "x ile başlayan <provider> adresinize"), and the offer sentence. It also routes requests made directly: e-mail goes to `email_send`, a failed lookup goes to an agent, no address gives the "no address" sentence plus the week offer, and a week request goes to the week flow.
9. `offer` (conversation). The extracted `offer_choice` routes to e-mail, week, main menu or another card.
10. `email_send` (conversation). Asks for confirmation. `statement_pdf_send` sends only to the registered address (every field is baked in). Success needs HTTP 200, returnCode "1" and exitState DONE. Other branches: refusal, "not my address", a different address, or an older month.
11. `statement_week_get` (api_request), then `prepare_week` (code: current state text, ordinal week names, the three other weeks as options, the M/C joint warning).
12. `week_choose` (conversation). The model calls `statement_week_decide` with the chosen week. The prompt forbids sending the current week.
13. `prepare_confirm` (code). Checks returnCode, `responseCode` 0 and the preview dates (`statementDueDate`). It writes the confirmation text (the joint warning comes just before "Onaylıyor musunuz?") and the final text.
14. `week_confirm` (conversation). `statement_week_change` runs once and only after an explicit yes. Success needs returnCode "1", exitState OK and responseCode 0. The dates told to the caller are the preview dates.
15. There are 16 `end_*` nodes, each with its own fixed sentence and its own endedReason. These cover main menu (normal, no debt, e-mail sent, address not the caller's, week changed, no card, tries used up, out of scope, other language), IVR login (third party), hang-up on silence, and agent (on request, payment, dispute, service failure, week failure).
16. Global nodes:
    - Routed by intent: agent request, payment, dispute, third party, non-Turkish speech.
    - Tool-call nodes the model triggers: 3 tries used up, 3rd silence, still angry after the 3rd calming reply, out-of-scope transfer accepted, caller finished or switching to another transaction.

## Technical choices
- Every tool declares flat body fields. A shared pre-hook wraps them into `{"data": …, "call": {"ani": "", "lang": "tr"}}` and converts the week and day to integers.
- Post-hooks remove headers and `messageText`, and compute `call_ok` for the write calls.
- Tool timeout is 25 s with no retries, because one test answer is slow but still succeeds.
- Failure counters (`<tool>_failure_count`) send every service error or timeout to an agent. Code nodes also check returnCode and HTTP status.
- Tool-result transitions use status variables that the code nodes reset after use. This stops a stale result from firing again on a second card or a second week choice.
- Amounts and dates are computed in code, not by the model.

## Conflicts resolved (latest decision wins, as in the design §7)
- **Silence:** the 3rd silence ends the call.
- **Out of scope:** ask before transferring to the main menu.
- **Angry caller:** three calming replies, then agent.
- **Tries used up:** "Size şu anda yardımcı olamıyorum. Sizi ana menüye aktarıyorum."
- **Duplicate cards:** ask for the last six, then the full number.
- **Card digits:** only the last four are ever spoken.
- **Currencies:** always said with their full names.
- **No-debt sentence:** follows the 8 Oct rule; missing currency blocks are left out.
- **Week change limit:** once a year, with no pre-check service. Any refusal from the change call goes to an agent with the week failure sentence.
- **Joint warning:** said before "Onaylıyor musunuz?".
- **E-mail lookup:** called before the offer.
- **E-mail address:** only the registered address is used.
- **Past statements:** only the last cut statement can be sent.
- **Second factor:** none.
- **Payment:** goes to an agent.
- **Service errors:** go to an agent, never to the main menu. The cards.list 404 is the "no card" case, not an error.
- **Third party:** IVR login step.
- **No-card sentence:** uses "aktarıyorum".
- **No-debt branch:** asks about another card, then the main menu.
- **E-mail lookup failure:** the offer leaves e-mail out; asking for e-mail anyway goes to an agent.
- **No transferAmount line**, and in the no-debt branch only the Türk Lirası future total is said.

## Known simplifications
- After a successful send the call goes straight to the main menu, so a resend or a week change after the e-mail is not offered.
- A request for "only one figure" still hears the full fixed reading, because the reading is spoken as fixed TTS to keep it exact.
- Because a successful week change ends the call, the "already changed in this call" branch cannot happen and is not built.
