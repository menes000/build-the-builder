"""CallSpec: the brief-independent, structured description of one collections call.

The extractor (LLM) fills this from the brief files. The compiler turns it into a Freya workflow.
Design rules:
  - Fields describe KINDS of rules a collections brief has. No value from any specific brief lives here.
  - Every section has `extra_rules`: free-text rules that do not fit the fields. The compiler appends
    them to the matching node prompt, so nothing the brief says is lost.
  - Anything the compiler computes in code (dates, floors, attempts) is parameterised here, never prompted.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator


# ----------------------------------------------------------------------------- shared

class Outcome(BaseModel):
    """One way a call can be closed, exactly as close_call expects it."""
    outcome: str = Field(description="close_call outcome value, e.g. not_reached")
    reason: str = Field("", description="close_call reason value, or empty when the brief lists none")


class Variable(BaseModel):
    name: str
    meaning: str


# ----------------------------------------------------------------------------- identity

class IdentityQuestion(BaseModel):
    field: str = Field(description="The `field` value sent to verify_identity, e.g. date_of_birth")
    ask: str = Field(description="How the agent asks it, one short sentence")
    answer_format: str = Field(description="How the answer must be sent, e.g. 'YYYY-MM-DD; numbers-only dates are day, month, year'")


class RetryHint(BaseModel):
    hint: str = Field(description="The `hint` value verify_identity may return, e.g. day_month_swapped")
    instruction: str = Field(description="What the agent must do when it sees this hint")
    counts_as_wrong: bool = False


class DeclinePolicy(BaseModel):
    explain_once_text: str = Field(description="The exact sentence the agent SAYS the first time the customer will not answer, in the agent's voice, e.g. 'These questions protect your account, so I have to ask them before I can continue.'")
    asking_purpose_counts_as_decline: bool = True
    explain_first: bool = Field(True, description="True: the first refusal gets the explanation once and the second refusal closes. False: the first refusal closes the call at once")
    close: Outcome


class Identity(BaseModel):
    questions: list[IdentityQuestion]
    intro_text: str = Field("", description="Exact sentence(s) spoken right after the name is confirmed and before the first security question, if the brief dictates them (e.g. a recording notice). Default: 'Thank you, <customer>. Before I continue, I need to ask you N security questions.'")
    ask_one_at_a_time: bool = True
    max_wrong_total: int = Field(description="Total wrong answers that end the check")
    retry_hints: list[RetryHint] = []
    wrong_answer_may_be_repeated: bool = True
    after_failed_text: str = Field(description="The exact sentence the agent SAYS to the customer after the check failed, in the agent's own voice, e.g. 'Please use the mobile app or visit a branch.' Not an instruction, not 'Say that...'")
    failed_close: Outcome
    decline: DeclinePolicy
    human_request: Optional["HumanRequest"] = None
    extra_rules: list[str] = []


# ----------------------------------------------------------------------------- opening

class Opening(BaseModel):
    first_sentence: str = Field(description="The exact required opening sentence (who is calling, recording notice)")
    ask_person_question: str = Field(description="The question that asks whether the customer is on the line, with {{title}} {{last_name}} placeholders")
    confirmation_examples: list[str] = Field(description="Answers that count as confirmation")
    non_confirmation_examples: list[str] = Field(description="Answers that do NOT count")
    max_asks: int = Field(2, description="How many times the question may be asked before closing as unclear")
    unclear_close: Outcome
    forbidden_words_before_verify: list[str] = Field(description="Words that must not be said before identity is verified")
    robot_answer: str = Field("", description="What to say if asked whether the agent is a robot/AI")
    scam_answer: str = Field("", description="What to say if asked whether this is a scam")
    extra_rules: list[str] = []


# ----------------------------------------------------------------------------- third party

class CallbackWindow(BaseModel):
    day_rule: str = Field(description="Which days are allowed, e.g. 'today or the next business day'")
    allow_today: bool = True
    allow_next_business_day: bool = True
    time_from: str = Field(description="HH:MM, inclusive")
    time_to: str = Field(description="HH:MM, inclusive")
    must_be_later_than_now: bool = True
    ask_again_once_if_outside: bool = True
    max_business_days_ahead: int = Field(1, description="How many days after today may be offered: 1 = only the next business day, 2 = the next business day or the one after it (business days unless calendar_days is true)")
    day_mode: Literal["computed", "text"] = Field("computed", description="computed: the allowed callback days come from the structured fields. text: the day rule fits no field; the code checks only the time window and 'later than now', the agent follows day_rule")
    calendar_days: bool = Field(False, description="True when the window counts CALENDAR days after today (not business days); holidays and Sundays are still excluded")
    saturday_allowed: bool = Field(False, description="True when a Saturday callback is allowed")


class ThirdParty(BaseModel):
    say_nothing_rule: str = Field(description="What may and may not be said to someone who is not the customer")
    ask_when_reachable: str = Field(description="How to ask when the customer can be reached")
    callback: CallbackWindow
    callback_close: Outcome
    no_callback_close: Outcome
    wrong_number_close: Outcome
    deceased_sentence: str = Field("", description="Exact sentence to say if the customer has died")
    deceased_close: Outcome
    relative_may_not_pay: bool = True
    extra_rules: list[str] = []


# ----------------------------------------------------------------------------- products, dates, amounts

class ProductType(BaseModel):
    type: str = Field(description="Value of `type` in get_account, e.g. credit_card")
    floor_field: str = Field(description="Field of the product that holds the floor amount, e.g. minimum_payment. When the floor is a percentage of the overdue amount, write past_due here and set floor_percent")
    floor_percent: Optional[float] = Field(None, description="If the floor is a percentage of past_due (e.g. 40 for 40 %), the percentage; the floor is then computed from past_due")
    floor_round_up_to_whole: bool = Field(False, description="True when a percentage floor is rounded UP to a whole currency unit")
    spoken_label: str = Field(description="How to name it in words; may use {card_last4}, e.g. 'credit card ending {card_last4}'")


class Band(BaseModel):
    name: str = Field(description="e.g. early, late")
    days_late_min: int
    days_late_max: int
    deadline_rule: str = Field(description="Human rule, e.g. 'the 12th business day after today'")
    deadline_business_days_after_today: Optional[int] = Field(None, description="If the rule is 'Nth business day after today', N")
    deadline_calendar_days_after_today: Optional[int] = Field(None, description="If the rule is 'N calendar days after today', N (a non-business day rolls forward to the next business day)")
    persuasion_attempts: int

    @model_validator(mode="after")
    def _one_deadline_number(self):
        if (self.deadline_business_days_after_today is None) == (self.deadline_calendar_days_after_today is None):
            raise ValueError(f"band {self.name}: exactly one of deadline_business_days_after_today / deadline_calendar_days_after_today must be set (rule: {self.deadline_rule!r})")
        return self


class Dates(BaseModel):
    business_days_text: str = Field(description="Which weekdays are business days, e.g. 'Monday to Friday'")
    weekend_days: list[int] = Field([5, 6], description="Python weekday numbers that are not business days (Mon=0)")
    holidays: list[str] = Field(description="ISO dates that are not business days")
    bands: list[Band]
    promise_date_rule: str = Field(description="e.g. 'today or later, a business day, not after the deadline'")
    weekend_or_holiday_rule: str = Field(description="What to offer when the customer names a non-business day, e.g. 'the next business day'")
    offer_next_business_day: bool = True
    weekend_named_offer: Literal["next_business_day", "previous_business_day", "both"] = Field("next_business_day", description="When the customer names a weekend day or holiday: offer the next business day after it, the last business day before it (if that is before today, the next business day), or both and let the customer choose")
    vague_period_fallback: Literal["deadline", "attempt1"] = Field("deadline", description="After one ask for the exact day with no answer: propose the deadline, or the attempt-1 date")
    vague_period_rule: str = Field(description="What to do with 'next week' etc.: ask once for the exact day, then propose the deadline")
    next_weekday_rule: str = Field(description="How 'next <weekday>' and 'this <weekday>' are read")
    after_deadline_rule: str = Field(description="What to do when the customer asks for a date after the deadline")
    extra_rules: list[str] = []


class Amounts(BaseModel):
    ask_full_first: bool = True
    never_ask_how_much: bool = True
    floor_rule: str = Field(description="What the floor is per product type, in words")
    floor_offer_once: bool = True
    floor_offer_text: str = Field(description="What must be said when offering the floor, e.g. 'the rest stays overdue'")
    floor_mode: Literal["computed", "text"] = Field("computed", description="computed: the floor comes from the structured fields (floor_field, floor_percent). text: the floor rule fits no field; the code does not compute or enforce a floor and the agent follows floor_rule")
    today_question: str = Field("", description="The exact first question about paying, if the brief dictates its wording (default: 'Can you make this payment today?'). Placeholders filled by the code: {amount} the past-due amount, {today}, {tomorrow} (first business day after today), {deadline}")
    customer_amount_rule: str = Field(description="Accept amounts from floor to full; below floor: say cannot record, offer floor once")
    extra_rules: list[str] = []


class Persuasion(BaseModel):
    flat_refusal_definition: str
    attempt_rules: list[str] = Field(description="Attempt 1, attempt 2... what to propose in each, in order")
    attempt1_date_rule: str = Field(description="e.g. 'last business day of this week; if today is that day, last business day of next week'")
    attempt1_date_kind: Literal["last_business_day_this_week", "next_business_day", "deadline", "today", "business_days_after_today", "other"] = Field(
        "other", description="Classification of attempt1_date_rule. last_business_day_this_week = Brief-A style (this week's last business day, next week's if today is it); business_days_after_today needs attempt1_business_days")
    attempt1_business_days: int = Field(0, description="Only for business_days_after_today: N")
    attempt1_mode: Literal["computed", "text"] = Field("computed", description="computed: the attempt-1 date comes from attempt1_date_kind. text: the rule fits no kind; the agent works the date out from attempt1_date_rule (also used automatically when attempt1_date_kind is other)")
    attempt1_uses_full_amount: bool = Field(True, description="Attempt 1 proposes the full amount (floor if the customer already said it is too much)")
    attempt2_uses_floor_on_deadline: bool = True
    stop_rule: str = Field(description="What to do when attempts are used up")
    refused_close: Outcome
    never_repeat_refused_offer: bool = True
    extra_rules: list[str] = []


# ----------------------------------------------------------------------------- special situations

class HumanRequest(BaseModel):
    ask_once_if_can_help: bool = True
    queue: str
    close: Outcome


class Hardship(BaseModel):
    triggers: list[str] = Field(description="e.g. illness, death in the family, job loss")
    sympathy_rule: str = Field(description="e.g. one short sentence of sympathy")
    no_persuasion: bool = True
    offer_queue: str = Field(description="Queue to offer, e.g. support")
    accept_close: Outcome
    decline_close: Outcome
    customer_may_still_promise: bool = True


class SimpleCase(BaseModel):
    triggers: list[str]
    say: str = Field("", description="The exact sentence the agent SAYS in this case, in the agent's own voice (e.g. 'Payments can take one business day to appear.'), or empty. Never an instruction such as 'Say that...'")
    take_promise: bool = False
    close: Outcome


class Transfer(BaseModel):
    triggers: list[str]
    queue: str
    close: Outcome
    do_not_describe_plan: bool = True


class Special(BaseModel):
    hardship: Hardship
    paid: SimpleCase
    dispute: SimpleCase
    restructuring: Transfer
    human: HumanRequest
    refuses_twice_verified_close: Outcome
    refuses_twice_unverified_close: Outcome
    unknown_answer_text: str = Field(description="What to say when a question cannot be answered from the tools")
    forbidden_offers: list[str] = Field(description="e.g. discount, waiver, instalment plan")
    extra_rules: list[str] = []


# ----------------------------------------------------------------------------- confirm & record

class Confirm(BaseModel):
    readback_fields: list[str] = Field(description="What is read back before recording, e.g. product, amount, date")
    confirm_question: str
    record_only_after_clear_yes: bool = True
    recheck_if_changed: bool = True
    one_promise_per_product: bool = True
    promise_immutable_text: str = Field("", description="What to say if the customer wants to change a recorded promise")
    say_recorded_only_after_ok: bool = True
    retry_once_on_failure: bool = True
    max_tries_on_failure: int = Field(2, description="How many create_promise calls in total before giving up on a technical failure (2 = one retry, 1 = no retry)")
    failed_twice_close: Outcome
    after_record_sentence: str = Field(description="Exact sentence after a recorded promise, e.g. the text-message sentence")
    extra_rules: list[str] = []


# ----------------------------------------------------------------------------- closing

class OutcomeRow(BaseModel):
    outcome: str
    reasons: list[str] = Field(description="Allowed reasons for this outcome; empty if none")
    when: str = Field(description="When this outcome applies, in words")


class Closing(BaseModel):
    outcomes: list[OutcomeRow]
    promise_outcome: str = Field(description="Outcome used when at least one promise was recorded")
    outcomes_without_reason: list[str] = Field(description="Outcomes that must be sent without a reason field")
    transfer_after_promise_rule: str = Field("", description="e.g. 'close as transferred with that transfer's reason'")
    thank_and_goodbye_before_close: bool = True
    extra_rules: list[str] = []


# ----------------------------------------------------------------------------- multi product (Brief B style)

class MultiProduct(BaseModel):
    enabled: bool = False
    state_all_products_first: bool = True
    per_product_bands: bool = True
    ask_today_for_all_once: bool = True
    today_question_all: str = Field("", description="Exact wording of the one question for all products, if dictated (default: 'Can you pay all of them today?'). Placeholders: {total}, {today}, {tomorrow}")
    closing_by_first_product: bool = Field(False, description="True when, with no promise, the closing follows the FIRST product's note only (paid -> paid outcome, else no_promise with that reason), ignoring the other notes")
    no_promise_reason_priority: list[str] = Field([], description="If the brief ranks note reasons for the closing reason (e.g. dispute before hardship before refused), the reasons in priority order")
    product_order_rule: str = Field("", description="e.g. 'in the order get_account returned them'")
    attempts_per_product: bool = True
    one_date_for_all_rule: str = Field("", description="What to do when one date is named for all and it passes one product's deadline")
    single_readback_single_confirmation: bool = True
    one_create_promise_per_product: bool = True
    note_reasons: list[str] = Field([], description="add_note reasons, e.g. refused, hardship, dispute, paid, service_error")
    note_for_each_product_without_promise: bool = True
    dispute_or_paid_does_not_end_call: bool = True
    transfer_rule: str = Field("", description="What happens to promises and notes on a transfer")
    failed_promise_note_reason: str = Field("", description="Note reason when create_promise fails twice for one product")
    closing_rule: str = Field("", description="How the final outcome is chosen with several products")
    extra_rules: list[str] = []


# ----------------------------------------------------------------------------- tools (parsed from openapi, not by the LLM)

class ToolField(BaseModel):
    name: str
    type: str = "string"
    enum: list[str] = []
    description: str = ""
    required: bool = False


class Tool(BaseModel):
    name: str
    url: str
    summary: str = ""
    fields: list[ToolField]


# ----------------------------------------------------------------------------- root

class CallSpec(BaseModel):
    bank_name: str
    language: str = "English"
    call_purpose: str = Field(description="One sentence: what the call is for")
    call_variables: list[Variable] = Field(description="Variables every call starts with, e.g. customer_id, first_name, title, now")
    address_customer_as: str = Field(description="e.g. '{{title}} {{last_name}}'")
    turn_style: str = Field("one or two short sentences per turn", description="Speaking style rule")

    opening: Opening
    third_party: ThirdParty
    identity: Identity
    debt_statement_rule: str = Field(description="What must be said after verification: team, product in words, amount, days late")
    debt_intro_sentence: str = Field("", description="The exact first sentence after verification, in the agent's voice, that names the team and the purpose, e.g. 'I am calling from the collections team about a late payment.' The product, amount and days late are added by the builder.")
    products: list[ProductType]
    dates: Dates
    amounts: Amounts
    persuasion: Persuasion
    special: Special
    confirm: Confirm
    closing: Closing
    multi_product: MultiProduct = MultiProduct()

    tools: list[Tool] = Field([], description="Filled by the builder from openapi.json, not by the extractor")
    field_map: dict = Field({}, description="Filled by the builder from openapi.json: canonical -> actual field names (req/resp/product)")
    global_extra_rules: list[str] = Field([], description="Rules that hold in every node and fit nowhere else")
    source_notes: list[str] = Field([], description="Extractor notes: conflicts resolved, assumptions made")


Identity.model_rebuild()
