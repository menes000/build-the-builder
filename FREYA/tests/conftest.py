import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from builder.build_from_spec import build  # noqa: E402


def _run(code: str, env: dict) -> dict:
    g = {"__builtins__": __builtins__}
    g.update(env)
    exec(compile(code, "<snippet>", "exec"), g)
    return g


@pytest.fixture(scope="session")
def wf_a():
    wf, problems = build(str(ROOT / "fixtures/callspec_brief_a.json"), str(ROOT / "kit/tools/openapi.json"))
    assert not problems, problems
    return wf


@pytest.fixture(scope="session")
def wf_ab():
    wf, problems = build(str(ROOT / "fixtures/callspec_brief_ab.json"), str(ROOT / "kit/tools/openapi.json"))
    assert not problems, problems
    return wf


@pytest.fixture(scope="session")
def wf_c_renamed():
    wf, problems = build(str(ROOT / "fixtures/callspec_brief_c.claude.json"), str(ROOT / "briefs_extra/brief-c/openapi-renamed.json"))
    assert not problems, problems
    return wf


def tool(wf: dict, node: str, name: str) -> dict:
    return next(t for t in wf["nodes"][node]["tools"] if t["function"]["name"] == name)


def run_hook(code: str, vars_: dict, body: dict | None = None, result: dict | None = None) -> dict:
    env = {"vars": vars_}
    if body is not None:
        env["config"] = {"body": body}
    if result is not None:
        env["result"] = result
    _run(code, env)
    return env


FACTS_2 = [
    {"pid": "p1", "label": "credit card ending 9015", "past": 510, "floor": 153, "attempts": 2, "deadline": "2026-10-23", "att1": "2026-10-16", "valid": ["2026-10-14", "2026-10-15", "2026-10-16", "2026-10-19", "2026-10-20", "2026-10-21", "2026-10-22", "2026-10-23"]},
    {"pid": "p3", "label": "car loan", "past": 140, "floor": 46, "attempts": 1, "deadline": "2026-11-02", "att1": "2026-10-16", "valid": ["2026-10-14", "2026-10-15", "2026-10-16"]},
]
FACTS_1 = [FACTS_2[0]]
