"""Prompt templates filled from a CallSpec. Brief-specific sentences come from the spec; structure is fixed."""
from __future__ import annotations

import re

from ..extract.callspec import CallSpec


def _speak_safe(text: str) -> str:
    """Brief wording that the agent would echo before a promise exists: avoid the word 'recorded' there."""
    text = re.sub(r"cannot be recorded", "cannot be accepted", text, flags=re.I)
    text = re.sub(r"can(not)? record\b", lambda m: "cannot accept" if m.group(1) else "can accept", text, flags=re.I)
    return text


def _rules(items: list[str]) -> str:
    return "".join(f"\n- {r}" for r in items) if items else ""


def system_prompt(spec: CallSpec) -> str:
    sp = spec.special
    lines = [
        f"You are {spec.bank_name}'s digital assistant on an outbound phone call. The customer is {spec.address_customer_as} (first name {{{{first_name}}}}). "
        f"Speak {spec.language}. Keep each turn to {spec.turn_style}. Address the customer as {spec.address_customer_as}.",
        "",
        "Rules that always hold:",
    ]
    if spec.opening.robot_answer:
        lines.append(f"- If asked whether you are a robot or an AI: {spec.opening.robot_answer}")
    if spec.opening.scam_answer:
        lines.append(f"- If asked whether this is a scam: {spec.opening.scam_answer}")
    lines.append(f"- If asked something you cannot answer from your instructions or a tool result: {sp.unknown_answer_text}")
    if sp.forbidden_offers:
        lines.append("- Never offer " + ", ".join(sp.forbidden_offers) + ".")
    lines += [
        "- If the answer itself is complete (a full date, all four digits, an amount, a day), use it at once even if the sentence around it was cut off or trailed into something else. Ask the customer to finish only when the answer itself is incomplete (a date without a year, two digits of four). If they stop mid-sentence about something unrelated, ignore it and repeat your own question briefly. Never ask the same thing more than twice in a row. An unfinished sentence is never a refusal, an agreement or an amount objection.",
        "- If the customer corrects themselves, the corrected value counts.",
        "- Say each required sentence, offer or explanation exactly once. If the customer talks about something else instead of answering an offer or a yes/no question, bring them back with exactly 'Is that a yes or a no?' and nothing else: do not restate the offer, the sympathy or the explanation. For an open question, repeat only the question itself.",
        "- Call at most one tool per message. After every tool result, speak to the customer or call the next tool. Never end a turn with nothing.",
        "- A tool result may contain what_to_do_next. Follow it.",
        "- If a tool fails with a technical error (connection error, service unavailable, timeout), call it once more with the same values. If it fails again, tell the customer once that there is a technical problem and call the transition_to_close_... tool that fits the situation. Never retry a third time and never repeat the same sentence.",
        "- Ask the same question at most twice. If the customer still has not answered after that, treat it as no answer and apply the rule for that case instead of asking again.",
        "- Never say that something is recorded, booked or transferred unless a tool result says so. Do not use the word 'recorded' at all before a tool result confirms a recording: for an amount or date that is not allowed say 'I can't take that amount' or 'I can't offer that date', never 'cannot be recorded'.",
        "- You never say goodbye in your own words and never end a turn with a farewell. When the call should end, call the matching transition_to_close_... tool: the closing words are spoken for you. If the customer says goodbye, call that tool at once.",
    ]
    lines += [f"- {r}" for r in spec.global_extra_rules]
    return "\n".join(lines)


def opening_line(spec: CallSpec) -> str:
    return f"{spec.opening.first_sentence} {spec.opening.ask_person_question}"


def opening_task(spec: CallSpec) -> str:
    o = spec.opening
    forb = ", ".join(o.forbidden_words_before_verify)
    return (f"You have just asked: \"{o.ask_person_question}\" "
            f"Do not say why you are calling and do not mention {forb}. No tool call is allowed in this turn." + _rules(o.extra_rules))


def retry_task(spec: CallSpec) -> str:
    o = spec.opening
    forb = ", ".join(o.forbidden_words_before_verify)
    answers = []
    if o.robot_answer:
        answers.append(f"robot or AI: {o.robot_answer}")
    if o.scam_answer:
        answers.append(f"scam: {o.scam_answer}")
    answers.append(f"who is calling: {spec.bank_name}'s digital assistant")
    return (f"You asked whether you are speaking with {spec.address_customer_as}, and the answer was not a clear yes. "
            f"If the person asked a question, answer it briefly first ({'; '.join(answers)}). "
            f"Never say why you are calling and never mention {forb}. "
            f"Then ask once more: \"{o.ask_person_question}\" No tool call is allowed in this turn." + _rules(o.extra_rules))


def line_status_description(spec: CallSpec) -> str:
    o = spec.opening
    return ("Who answered, from the person's LAST message, after the agent asked whether it is speaking with the customer. "
            f"confirmed: the person says {', '.join(o.confirmation_examples)}. "
            "someone_else: the person is not the customer but knows them (relative, partner, colleague), or says the customer is not available. "
            "wrong_number: the number does not belong to the customer or the person does not know them. "
            "deceased: the customer has died. "
            f"Leave empty for {', '.join(o.non_confirmation_examples)}, a question, or anything unclear.")


def security_task(spec: CallSpec) -> str:
    idn = spec.identity
    forb = ", ".join(spec.opening.forbidden_words_before_verify)
    qs = "\n".join(f"  {i + 1}. {q.field}: ask \"{q.ask}\" Send the answer as: {q.answer_format}" for i, q in enumerate(idn.questions))
    parts = [
        f"The person confirmed they are {spec.address_customer_as}. Verify their identity before anything else. "
        f"Do not mention {forb}, any amount or any product until the check is complete. If asked why you are calling, say you can explain right after the security questions.",
        "",
        f"Ask {len(idn.questions)} security questions, {'one at a time' if idn.ask_one_at_a_time else 'together'}, in this order:",
        qs,
        "- Each time the customer gives a complete answer, call verify_identity with that field and the converted answer. Convert spoken dates and numbers yourself.",
        "- If the customer gives only part of an answer, ask for the rest before calling the tool.",
        "- If the customer corrects themselves, use the corrected value.",
        "- After each result, follow what_to_do_next.",
        f"- If the customer will not answer{', or asks what the call is about instead of answering' if idn.decline.asking_purpose_counts_as_decline else ''}: {idn.decline.explain_once_text} and ask again. "
        f"If they refuse a second time{', or ask a second time what the call is about' if idn.decline.asking_purpose_counts_as_decline else ''}, call transition_to_close_declined.",
        "- If the customer says twice that they do not want to talk, call transition_to_close_declined.",
    ]
    if idn.human_request:
        hr = idn.human_request
        parts.append(f"- If the customer asks for a human: {'ask once whether you can help first. If they insist, ' if hr.ask_once_if_can_help else ''}call transfer_to_agent with queue {hr.queue}.")
    parts.append(f"- After the check fails: {idn.after_failed_text}")
    return "\n".join(parts) + _rules(idn.extra_rules)


def third_party_task(spec: CallSpec) -> str:
    tp = spec.third_party
    return "\n".join([
        f"The person on the line is NOT {spec.address_customer_as}. {tp.say_nothing_rule}"
        + (f" A relative may not be told anything about the account, even if they offer to pay: say you can only speak with {spec.address_customer_as}." if tp.relative_may_not_pay else ""),
        "",
        f"Your task: find out when {spec.address_customer_as} can be reached, and book a callback.",
        "Now: {{today_text}}.",
        "Allowed callback times: {{callback_text}}.",
        f"- If the person has not said yet when the customer can be reached: {tp.ask_when_reachable}",
        "- When the person gives a day and a time inside the allowed times, call schedule_callback with date YYYY-MM-DD and time HH:MM (24-hour). If they give a day but no time, or a time but no day, ask for the missing part. If they correct themselves, use the corrected value.",
        f"- If what they offer is outside the allowed times: say we can only call back within the allowed times{' and ask once for another time. If the next answer is also outside them, or they cannot give a time' if tp.callback.ask_again_once_if_outside else ''}, call transition_to_close_no_callback. Do not book anything outside the allowed times.",
        f"- If the person says this number does not belong to {spec.address_customer_as}: call transition_to_close_wrong_number.",
        f"- If the person says {spec.address_customer_as} has died: call transition_to_close_deceased at once and say nothing else.",
        "- After schedule_callback, follow what_to_do_next.",
    ]) + _rules(tp.extra_rules)


def negotiate_task(spec: CallSpec) -> str:
    a, p, sp, cf, mp = spec.amounts, spec.persuasion, spec.special, spec.confirm, spec.multi_product
    hs = sp.hardship
    parts = [
        "The customer is verified. You have just told them about the late payment and asked whether they can pay today.",
        "",
        "TOOL RULES",
        f"- create_promise: only after the customer says a clear yes to your read-back. date as YYYY-MM-DD. amount_kind: 'full' when the agreed amount is the full past-due amount, 'floor' when it is the floor, otherwise 'custom' with the amount as a number."
        + (" Always give the product_id of the product this promise is for." if mp.enabled else ""),
        "- If create_promise fails, follow what_to_do_next: call it once more with the same values. If it says the date or amount is not allowed, tell the customer it cannot be recorded and offer a valid option.",
        "- When a rule below says to call a tool or a transition, call it. Saying it is not enough.",
        "",
        "ACCOUNT",
        "{{offers_text}}",
        "- Today: {{today_text}}. Tomorrow: {{tomorrow_text}}.",
        "- A date the customer names that the DATES list marks as allowed for that product is accepted as it is, even if it is not in the refusal script. The script is only for what YOU propose after a flat refusal.",
        "",
        "SPECIAL SITUATIONS (these come first)",
        f"- {', '.join(hs.triggers)}: {hs.sympathy_rule} Say it once and never repeat it, even if the customer mentions the hardship again.{' Make no persuasion attempt.' if hs.no_persuasion else ''} Offer once to connect them with the {hs.offer_queue} team. If they accept, call transfer_to_agent with queue {hs.offer_queue}. If they decline, call transition_to_close_hardship. If they neither accept nor decline, ask only whether that is a yes or a no."
        + (" Only if they themselves name a date or an amount, record the promise with the steps below." if hs.customer_may_still_promise else ""),
        f"- {', '.join(sp.paid.triggers)} (this past-due amount): {sp.paid.say} Take no promise{'; call add_note for that product with reason paid and continue with the other products' if mp.enabled else ', call transition_to_close_paid'}.",
        f"- {', '.join(sp.dispute.triggers)}: {sp.dispute.say} Take no promise{'; call add_note for that product with reason dispute and continue with the other products' if mp.enabled else ', call transition_to_close_dispute'}.",
        f"- {', '.join(sp.restructuring.triggers)}: {'do not describe any plan. ' if sp.restructuring.do_not_describe_plan else ''}Call transfer_to_agent with queue {sp.restructuring.queue}.",
        f"- A request for a human: {'ask once whether you can help first. If they insist, ' if sp.human.ask_once_if_can_help else ''}call transfer_to_agent with queue {sp.human.queue}.",
        "- If they say a second time that they do not want to talk: call transition_to_close_refused.",
        "",
        "HOW TO GET THE PROMISE",
        f"1. {'Ask for the full past-due amount first. ' if a.ask_full_first else ''}{'Never ask how much they can pay; you propose every amount.' if a.never_ask_how_much else ''}",
        f"2. Only if they say the AMOUNT is too much (too high, cannot afford that much): offer the floor{' once' if a.floor_offer_once else ''}, {a.floor_offer_text} Ask when they can pay it. Do not attach a date to this offer. From then on never propose the full amount again. If they refuse the floor amount, that is a flat refusal (step 6). 'I cannot pay today', 'no', or a no to a date is NOT an amount objection: it is a flat refusal (step 6) or a date question (step 4), and the amount stays the full amount.",
        f"3. {a.customer_amount_rule}",
        f"4. Dates: look up every date the customer names in the DATES list and do what it says. {spec.dates.after_deadline_rule}",
        f"5. {spec.dates.vague_period_rule}",
        f"6. A flat refusal ({p.flat_refusal_definition}) uses one persuasion attempt. The number of attempts allowed and the attempt-1 date are in ACCOUNT{' per product' if mp.enabled else ''}:",
    ]
    for r in p.attempt_rules:
        parts.append(f"   - {r}")
    parts += [
        f"   - {p.stop_rule} When the allowed attempts are used up and they still refuse, {'call add_note for that product with reason refused and continue with the next product' if mp.enabled else 'call transition_to_close_refused'}.",
        f"   Whenever you propose the floor, {a.floor_offer_text}",
        "   A date or an amount the customer proposes is never a refusal: handle it with steps 2 to 5.",
        f"7. When the amount and the date are agreed: read back {', '.join(cf.readback_fields)} (date with weekday, day and month), then ask \"{cf.confirm_question}\". Call create_promise only after a clear yes. If they change the date or the amount, check it again and read it back again.",
    ]
    if cf.promise_immutable_text:
        parts.append(f"8. {cf.promise_immutable_text}")
    if mp.enabled:
        parts += [
            "",
            "SEVERAL PRODUCTS",
            f"- {'State every late product, one sentence each, before asking for anything (already done in your first line).' if mp.state_all_products_first else ''}",
            f"- {'First ask whether they can pay all of them today. If not, go through the products one by one' if mp.ask_today_for_all_once else 'Go through the products one by one'}{', ' + mp.product_order_rule if mp.product_order_rule else ''}. Do not ask about today again for each product. Start each product at attempt 1.",
            f"- {mp.one_date_for_all_rule}" if mp.one_date_for_all_rule else "",
            "- Never move a date the customer named if the DATES list says it is allowed for that product. Only a product whose own deadline is earlier gets its deadline instead.",
            "- Call the tools one at a time: one create_promise or add_note per message, then speak, then the next.",
            f"- {'Read all agreed promises back together and ask for one confirmation. Then call create_promise once per product, one call per message.' if mp.single_readback_single_confirmation else ''}",
            f"- For each product without a promise call add_note with that product_id and a reason: {', '.join(mp.note_reasons)}. This also applies when no product gets a promise.",
            f"- {'A dispute or an already-paid claim on one product does not end the call: note it and continue with the others.' if mp.dispute_or_paid_does_not_end_call else ''}",
            f"- {mp.transfer_rule}" if mp.transfer_rule else "",
            "- When every product has a promise or a note, call transition_to_close_done.",
        ]
    parts += ["", "DATES (every date the customer may name, and what to do)", "{{calendar_text}}", "",
              f"{spec.dates.next_weekday_rule}", "{{weekday_text}}"]
    extra = a.extra_rules + p.extra_rules + sp.extra_rules + cf.extra_rules + spec.dates.extra_rules + (mp.extra_rules if mp.enabled else [])
    return _speak_safe("\n".join(x for x in parts if x is not None) + ("\n\nOTHER RULES" + _rules(extra) if extra else ""))
