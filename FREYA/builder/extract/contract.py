"""The bank's service contract as an OpenAPI file, for a case that describes its tools in prose (Markdown, Word, PDF)
instead of shipping an OpenAPI file. Claude reads the case material and writes the OpenAPI JSON the rest of the builder uses.
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

from .extractor import _ask_claude, _brief_text
from .tools import is_openapi

PROMPT = """You turn a bank's service contract into an OpenAPI 3 JSON file.

The files below are a bank's case material. One or more of them describe the bank's services (endpoints) that a phone
agent calls as tools. Write ONE OpenAPI 3.0 JSON document that describes exactly those endpoints:
- `paths`: one entry per endpoint, keyed by the FULL path after the host, including any base path the contract gives
  (base address https://host/api/v2/ + service `x` -> path `/api/v2/x`), with the HTTP method it gives (POST if it does not say).
  Only the services the agent calls; leave out token / auth endpoints.
- each operation: `summary` (one line, from the contract), `requestBody.content.application/json.schema` with every
  request field the contract names: exact field name, `type`, `enum` with the exact allowed values if the contract lists
  them, `description` (from the contract), and `required` as the contract says.
- `responses.200.content.application/json.schema`: the response fields the contract names, with types and enums.
- `servers`: [{"url": "https://mock.invalid"}] (host only, no path; the real address is set later).
Copy names and values exactly as the contract writes them; do not translate, rename or invent anything.
Write the JSON with the Write tool to exactly this path: {out}
"""


def contract_to_openapi(brief_paths: list[str], out_path: str, trace, model: str | None = None, tries: int = 2) -> Path:
    model = model or os.environ.get("BUILDER_MODEL", "claude-opus-5-5")
    out = Path(out_path).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    note = ""
    for attempt in range(1, tries + 1):
        if out.exists():
            out.unlink()
        from ..freeform import _case_text
        prompt = PROMPT.replace("{out}", str(out)) + note + "\n\n## The case files" + _case_text(brief_paths)
        asyncio.run(_ask_claude(prompt, out, Path.cwd(), model, trace, purpose=f"write the tool API (OpenAPI) from the service contract (attempt {attempt})"))
        if out.exists() and is_openapi(out):
            trace.note(f"tool API written from the service contract: {out}")
            return out
        note = "\n\nYour previous attempt did not produce a valid OpenAPI JSON file with `paths`. Write it again.\n"
        trace.note(f"tool API from the service contract, attempt {attempt}: no valid OpenAPI file")
    raise RuntimeError("could not write the tool API from the service contract")
