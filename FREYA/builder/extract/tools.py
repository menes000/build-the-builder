"""Parse the bank's tool API (OpenAPI JSON) into CallSpec Tool objects. No LLM involved."""
from __future__ import annotations

import json
from pathlib import Path

from .callspec import Tool, ToolField


def parse_openapi(path: str | Path) -> list[Tool]:
    d = json.loads(Path(path).read_text())
    base = (d.get("servers") or [{}])[0].get("url", "").rstrip("/")
    tools: list[Tool] = []
    for p, ops in d.get("paths", {}).items():
        op = ops.get("post") or next(iter(ops.values()))
        schema = (op.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema", {}))
        req = set(schema.get("required", []))
        fields = []
        for name, prop in (schema.get("properties") or {}).items():
            fields.append(ToolField(
                name=name,
                type=prop.get("type", "string"),
                enum=list(prop.get("enum") or []),
                description=prop.get("description", "") or "",
                required=name in req,
            ))
        tools.append(Tool(name=p.strip("/"), url=f"{base}{p}", summary=op.get("summary", "") or "", fields=fields))
    return tools


def response_fields(path: str | Path) -> dict[str, set[str]]:
    """Tool name -> set of top-level response property names (for lint)."""
    d = json.loads(Path(path).read_text())
    out: dict[str, set[str]] = {}
    for p, ops in d.get("paths", {}).items():
        op = ops.get("post") or next(iter(ops.values()))
        ok = op.get("responses", {}).get("200", {}).get("content", {}).get("application/json", {}).get("schema", {})
        props = ok.get("properties") or {}
        names = set(props.keys())
        prods = props.get("products", {}).get("items", {}).get("properties") or {}
        names |= {f"products.{k}" for k in prods}
        out[p.strip("/")] = names
    return out
