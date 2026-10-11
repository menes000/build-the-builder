"""Brief files -> CallSpec, using Claude through the Claude Agent SDK (same login as the kit's example builder).

Every model call is logged to the trace. Validation failures are fed back to the model, at most `max_retries` times.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path

from pydantic import ValidationError

from .callspec import CallSpec

PROMPT_DIR = Path(__file__).parent / "prompts"


def _schema_text() -> str:
    return json.dumps(CallSpec.model_json_schema(), indent=1)


def _office_text(path: Path) -> str:
    """Word / Excel / PowerPoint / ODF / RTF / HTML -> plain text: pandoc, then macOS textutil, then plain Python."""
    import subprocess
    suf = path.suffix.lower()
    if suf == ".xlsx":
        try:
            import openpyxl
            wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
            out = []
            for ws in wb.worksheets:
                out.append(f"--- sheet: {ws.title} ---")
                for row in ws.iter_rows(values_only=True):
                    if any(c is not None and str(c).strip() for c in row):
                        out.append(" | ".join("" if c is None else str(c) for c in row))
            return "\n".join(out)
        except Exception:
            pass
    for cmd in (["pandoc", str(path), "-t", "plain", "--wrap=none"], ["textutil", "-convert", "txt", "-stdout", str(path)]):
        try:
            text = subprocess.run(cmd, capture_output=True, text=True, timeout=60).stdout
            if text.strip():
                return text
        except Exception:
            pass
    if suf in (".docx", ".pptx", ".odt"):          # zipped XML: keep the text of each paragraph / slide line
        try:
            import re
            import zipfile
            with zipfile.ZipFile(path) as z:
                names = [n for n in z.namelist() if re.match(r"(word/document|word/(header|footer)\d*|ppt/slides/slide\d+|content)\.xml$", n)]
                out = []
                for n in sorted(names):
                    xml = z.read(n).decode("utf-8", errors="replace")
                    xml = re.sub(r"</(w:p|a:p|text:p|text:h)>", "\n", xml)
                    xml = re.sub(r"<(w:tab|text:tab)/>", "\t", xml)
                    out.append(re.sub(r"<[^>]+>", "", xml))
                import html
                return html.unescape("\n".join(out))
        except Exception:
            pass
    return ""


def _brief_text(brief_paths: list[str]) -> str:
    parts = []
    for p in brief_paths:
        path = Path(p)
        if path.suffix.lower() in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
            text = f"(image: {path.name}; look at it with the Read tool at {path.resolve()})"
        elif path.suffix.lower() in (".docx", ".doc", ".odt", ".rtf", ".xlsx", ".pptx", ".html", ".htm"):
            text = _office_text(path)
            if not text.strip():
                text = f"(file could not be converted to text: {path.name}; read it with the Read tool at {path.resolve()})"
        elif path.suffix.lower() == ".pdf":
            try:
                import subprocess
                text = subprocess.run(["pdftotext", "-layout", str(path), "-"], capture_output=True, text=True, timeout=60).stdout
            except Exception:
                text = ""
            if not text.strip():
                text = f"(PDF could not be converted to text: {path.name}; read it with the Read tool at {path.resolve()})"
        else:
            text = path.read_text(encoding="utf-8", errors="replace")
        parts.append(f"\n\n===== FILE: {p} =====\n{text}")
    return "".join(parts)


async def _ask_claude(prompt: str, out_path: Path, cwd: Path, model: str, trace, purpose: str) -> str:
    from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ResultMessage, TextBlock, query

    options = ClaudeAgentOptions(
        cwd=str(cwd), model=model,
        allowed_tools=["Read", "Write"], permission_mode="dontAsk", max_turns=12,
        setting_sources=[],
    )
    t0 = time.time()
    text = []
    cost = None
    async for m in query(prompt=prompt, options=options):
        if isinstance(m, AssistantMessage):
            for b in m.content:
                if isinstance(b, TextBlock):
                    text.append(b.text)
        elif isinstance(m, ResultMessage):
            cost = m.total_cost_usd
    trace.model_call(model=model, purpose=purpose, seconds=time.time() - t0, cost_usd=cost)
    return "\n".join(text)


def extract_callspec(brief_paths: list[str], out_path: str, trace, model: str | None = None, max_retries: int = 2, openapi_path: str | None = None) -> CallSpec:
    model = model or os.environ.get("BUILDER_MODEL", "claude-opus-5-5")
    out = Path(out_path).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    instructions = (PROMPT_DIR / "extract_callspec.md").read_text()
    base_prompt = (
        f"{instructions}\n\n## CallSpec JSON schema\n```json\n{_schema_text()}\n```\n\n"
        f"## Output path\nWrite the finished JSON with the Write tool to exactly this path: {out}\n\n"
        f"## The brief files{_brief_text(brief_paths)}\n"
        + (f"\n\n## The bank's tool API (use its exact field names and enum values for identity fields, queues, outcomes, reasons, product types)\n```json\n{Path(openapi_path).read_text()}\n```\n" if openapi_path else "")
    )
    cwd = Path.cwd()
    errors = ""
    best = None          # last schema-valid CallSpec: a lint problem must never cost the whole build
    for attempt in range(1 + max_retries):
        prompt = base_prompt if not errors else (
            base_prompt + f"\n\n## Your previous JSON was rejected by the schema validator\n{errors}\n"
            f"Fix every listed problem and write the complete corrected JSON again to {out}.")
        _ = asyncio.run(_ask_claude(prompt, out, cwd, model, trace, purpose=f"extract CallSpec from brief (attempt {attempt + 1})"))
        if not out.exists():
            errors = "No file was written to the output path."
            trace.note(f"extraction attempt {attempt + 1}: no file written")
            continue
        raw = out.read_text()
        try:
            spec = CallSpec.model_validate_json(raw)
        except (ValidationError, ValueError) as e:
            errors = str(e)[:6000]
            trace.note(f"extraction attempt {attempt + 1}: schema errors: {errors[:300]}")
            continue
        best = spec
        problems = []
        if openapi_path:
            from .tools import field_map, lint_spec, parse_openapi
            problems = lint_spec(spec, parse_openapi(openapi_path), field_map(openapi_path))
        if problems and attempt == max_retries:
            for pr in problems:
                trace.note(f"extraction attempt {attempt + 1}: WARNING kept as is (last attempt): {pr[:200]}")
            from .tools import apply_text_modes
            for fld in apply_text_modes(spec, problems):
                trace.note(f"extraction: left to the model: {fld} = text (the rule text and the structured field still disagree)")
            out.write_text(spec.model_dump_json(indent=1))
            return spec
        if problems:
            errors = "The values below do not match the tool API (copy enum values exactly from the API file):\n- " + "\n- ".join(problems)
            trace.note(f"extraction attempt {attempt + 1}: {len(problems)} API mismatch(es): {problems[0][:200]}")
            continue
        trace.note(f"extraction attempt {attempt + 1}: CallSpec valid ({len(raw)} bytes)")
        return spec
    if best is not None:
        trace.note(f"extraction: last attempt was not usable, using the last schema-valid CallSpec ({errors[:200]})")
        return best
    raise RuntimeError(f"CallSpec extraction failed after {1 + max_retries} attempts: {errors[:500]}")
