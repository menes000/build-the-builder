"""The builder's own spoken sentences follow the call's language: CallSpec.phrases replaces every English default."""
import json
import sys

from conftest import ROOT

sys.path.insert(0, str(ROOT))
from builder.compile.compiler import compile_workflow  # noqa: E402
from builder.compile.selfcheck import facts_preview  # noqa: E402
from builder.extract.callspec import PHRASES_EN, CallSpec  # noqa: E402
from builder.extract.tools import field_map, parse_openapi  # noqa: E402

API = str(ROOT / "kit/tools/openapi.json")


def _wf(fixture: str, phrases: dict) -> dict:
    spec = CallSpec.model_validate_json((ROOT / "fixtures" / fixture).read_text())
    spec.tools, spec.field_map = parse_openapi(API), field_map(API)
    spec.phrases = phrases
    return compile_workflow(spec)


def _marked() -> dict:
    """Every phrase replaced by a marker that keeps the placeholders: 'XX<key> {name} {n}...'"""
    out = {}
    for k, v in PHRASES_EN.items():
        ph = " ".join(p for p in ("{name}", "{n}", "{team}", "{product}", "{amount}", "{days}") if p in v)
        out[k] = f"XX{k} {ph}".strip() + "."
    return out


def test_no_english_default_left_when_phrases_are_given():
    for fx in ("callspec_brief_a.json", "callspec_brief_ab.json"):
        text = json.dumps(_wf(fx, _marked()), ensure_ascii=False)
        for k, v in PHRASES_EN.items():
            if "{" not in v and k not in ("pay_today", "pay_all_today"):   # these two also appear in the fixtures' own rule text
                assert v not in text, (fx, k)


def test_spoken_lines_use_the_phrases():
    wf = _wf("callspec_brief_a.json", _marked())
    v = facts_preview(wf, "2026-10-14T11:00", [{"product_id": "p1", "type": "personal_loan", "past_due": 540.0, "days_late": 5, "instalment_amount": 180.0}])
    assert v["debt_statement"].startswith("XXsecurity_done.")
    assert "XXproduct_line " in v["debt_statement"] and " 540" in v["debt_statement"] and " 5." in v["debt_statement"]
    text = json.dumps(wf, ensure_ascii=False)
    assert "XXpay_today." in v["debt_statement"] or v["debt_statement"].endswith("?")
    assert "XXthanks_goodbye_name" in text and "XXdeclined." in text and "XXunclear." in text


def test_empty_phrases_keep_english():
    text = json.dumps(_wf("callspec_brief_a.json", {}), ensure_ascii=False)
    assert "Thank you, we will call back then. Thank you for your time. Goodbye." in text
    assert "XX" not in text
