"""Static checks on a compiled workflow, from the kit docs checklist. Returns a list of problems (empty = clean)."""
from __future__ import annotations

import json


def lint(workflow: dict) -> list[str]:
    errs: list[str] = []
    nodes = workflow.get("nodes", {})
    if "initial_node" not in workflow or workflow["initial_node"] not in nodes:
        errs.append("initial_node missing or unknown")
    if "agent_config" in workflow:
        errs.append("agent_config must be omitted")

    # no nulls anywhere
    def walk(x, path):
        if x is None:
            errs.append(f"null value at {path}")
        elif isinstance(x, dict):
            for k, v in x.items():
                walk(v, f"{path}.{k}")
        elif isinstance(x, list):
            for i, v in enumerate(x):
                walk(v, f"{path}[{i}]")
    walk(workflow, "workflow")

    end_nodes = {k for k, n in nodes.items() if n.get("node_type") == "end_call"}
    for k, n in nodes.items():
        nt = n.get("node_type")
        if n.get("name") != k:
            errs.append(f"{k}: name != key")
        if nt == "conversation" and n.get("pre_actions"):
            errs.append(f"{k}: conversation node has pre_actions (would be stripped)")
        if nt in ("code", "api_request") and n.get("tools"):
            errs.append(f"{k}: {nt} node has tools (would be stripped)")
        if n.get("passthrough"):
            trs = n.get("transitions") or []
            if not trs or trs[-1].get("condition", {}).get("operator") != "always":
                errs.append(f"{k}: passthrough node must end with an always transition")
        for t in n.get("transitions") or []:
            tgt = t.get("target_node")
            if tgt not in nodes and tgt != "__previous__":
                errs.append(f"{k}: transition to unknown node {tgt}")
        if n.get("max_turn_transition") and n["max_turn_transition"] not in nodes:
            errs.append(f"{k}: max_turn_transition unknown")
        for a in n.get("pre_actions") or []:
            code = a.get("function", {}).get("parameters", {}).get("properties", {}).get("code", {}).get("default", "")
            if "{{" in code or "}}" in code:
                errs.append(f"{k}: code contains double braces")
        for tool in n.get("tools") or []:
            _check_tool(tool, f"{k}.{tool.get('function', {}).get('name')}", errs)
        if nt == "end_call":
            if n.get("transitions"):
                errs.append(f"{k}: end_call node has transitions")
            if "terminal" not in n:
                errs.append(f"{k}: end_call node without terminal")
        if nt == "conversation" and "max_node_turns" in n and not n.get("max_turn_transition"):
            errs.append(f"{k}: max_node_turns without max_turn_transition")
    for tool in workflow.get("tools") or []:
        _check_tool(tool, f"workflow.{tool.get('function', {}).get('name')}", errs)
        if not tool.get("config", {}).get("alwaysRunsAt"):
            errs.append("workflow-level tool without alwaysRunsAt never runs")

    # every node reaches an end node
    reach = {k: set() for k in nodes}
    for k, n in nodes.items():
        for t in n.get("transitions") or []:
            reach[k].add(t.get("target_node"))
        if n.get("passthrough_default_transition"):
            reach[k].add(n["passthrough_default_transition"])
        if n.get("max_turn_transition"):
            reach[k].add(n["max_turn_transition"])
    for k in nodes:
        seen, stack = set(), [k]
        while stack:
            x = stack.pop()
            if x in seen or x not in nodes:
                continue
            seen.add(x)
            stack.extend(reach[x])
        if not seen & end_nodes:
            errs.append(f"{k}: cannot reach an end_call node")
    return errs


def _check_tool(tool: dict, where: str, errs: list[str]):
    fn = tool.get("function", {})
    params = fn.get("parameters", {}).get("properties", {})
    handler = fn.get("handler", "")
    if handler == "__function__:api_call":
        if "default" not in params.get("url", {}):
            errs.append(f"{where}: api_call without baked url")
        body = params.get("body", {})
        if body and "properties" not in body:
            errs.append(f"{where}: body without properties")
        for name, prop in (body.get("properties") or {}).items():
            if "const" in prop:
                errs.append(f"{where}.{name}: const is ignored, use default")
    for k in ("pre_process_code", "post_process_code"):
        c = tool.get(k, "")
        if "{{" in c or "}}" in c:
            errs.append(f"{where}: {k} contains double braces")
    for m in tool.get("response_mapping") or []:
        if not m.get("path", "").startswith("data."):
            errs.append(f"{where}: mapping path should start with data.")


def brief_leak_check(workflow: dict, forbidden: list[str]) -> list[str]:
    """Strings from a specific brief that must not appear in compiler templates (they may appear via the CallSpec)."""
    s = json.dumps(workflow)
    return [f for f in forbidden if f in s]
