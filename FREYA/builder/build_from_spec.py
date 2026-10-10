"""Compile a CallSpec JSON into a workflow, check it, write it. (Developer tool; the full builder adds extraction.)

    python3 -m builder.build_from_spec fixtures/callspec_brief_a.json kit/tools/openapi.json out/brief-a.workflow.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from .compile.compiler import compile_workflow
from .compile.lint import lint
from .compile.selfcheck import check_snippets
from .extract.callspec import CallSpec
from .extract.tools import parse_openapi


def build(spec_path: str, openapi_path: str) -> tuple[dict, list[str]]:
    spec = CallSpec.model_validate_json(Path(spec_path).read_text())
    spec.tools = parse_openapi(openapi_path)
    wf = compile_workflow(spec)
    problems = lint(wf) + check_snippets(wf)
    return wf, problems


def main(argv):
    spec_path, openapi_path, out_path = argv[1], argv[2], argv[3]
    wf, problems = build(spec_path, openapi_path)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps(wf, indent=1))
    print(f"wrote {out_path}: {len(wf['nodes'])} nodes, {len(json.dumps(wf))} bytes")
    for p in problems:
        print("PROBLEM:", p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
