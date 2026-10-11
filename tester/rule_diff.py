"""Second, independent reading of the brief, compared field by field with the builder's CallSpec.

Why: on Sunday the agent and our generated cases both come from the CallSpec. If the extraction missed a rule (a memo that
changes the callback window, a holiday added in a later mail), both are wrong together and every local test passes. A second
model with a different prompt reads the raw brief files and fills only the checkable subset of the CallSpec; differences are
extraction-error candidates for a human to look at (2 minutes with the brief open). Values are never written into any code.

    source env.sh
    python3 tester/rule_diff.py <callspec.json> <brief file or folder> [more files...] [--out results/<slot>-rulediff.md]
"""
import argparse, json, pathlib, re, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import llm

PROMPT = """You are auditing a phone-agent specification for a bank's collections call. You get the raw brief material: one or
more documents (a specification, or mails, a policy extract, a memo, a code list). Read ALL of it. When documents disagree, the
LATER-DATED document wins; say which document each value comes from. Do not guess: if the material does not state a value, use null.
VOCABULARY (use these spellings, nothing else): identity question field names and product field names come from the tool API
listed after the material; outcome and reason values are the CODES of the brief's outcome table (e.g. "no_slot"), never their
descriptions; floor_fields maps each product type to the product field that holds its floor amount.
Answer with JSON only, exactly these keys:
{
 "holidays": ["YYYY-MM-DD", ...],
 "weekend_days": [5, 6],
 "bands": [{"name": "...", "days_late_min": int, "days_late_max": int, "deadline_business_days_after_today": int or null,
            "deadline_calendar_days_after_today": int or null, "persuasion_attempts": int}],
 "callback": {"allow_today": bool, "allow_next_business_day": bool, "time_from": "HH:MM", "time_to": "HH:MM"},
 "identity_questions": ["field_name_in_order", ...],
 "max_wrong_answers_total": int,
 "floor_fields": {"product_type": "field name of the floor amount"},
 "queues": {"human": "...", "hardship": "...", "restructuring": "..."},
 "outcomes": {"outcome": ["reason", ...]},
 "sentences": {"after_record": "exact sentence after a recorded promise", "deceased": "exact sentence when told the customer died",
               "opening": "the required first sentence"},
 "attempt1_date_rule": "one sentence", "attempt2_rule": "one sentence or null",
 "sources": {"<key>": "which document and line/section"}
}"""


def read_file(f):
    """md/txt/json as is; docx via its XML; pdf via pdftotext when installed (else a warning)."""
    suf = f.suffix.lower()
    if suf == ".docx":
        import re, zipfile
        xml = zipfile.ZipFile(f).read("word/document.xml").decode("utf8", "ignore")
        return re.sub(r"<[^>]+>", lambda m: "\n" if m.group(0).startswith(("</w:p", "<w:br", "<w:tab")) else "", xml)
    if suf == ".pdf":
        import shutil, subprocess
        if shutil.which("pdftotext"): return subprocess.run(["pdftotext", "-layout", str(f), "-"], capture_output=True, text=True).stdout
        return f"[pdf {f.name}: install pdftotext (poppler) to read it]"
    return f.read_text(errors="ignore")


def read_material(paths):
    files = []
    for p in paths:
        p = pathlib.Path(p)
        files += sorted(x for x in p.iterdir() if x.suffix.lower() in (".md", ".txt", ".json", ".docx", ".pdf") and "openapi" not in x.name.lower()) if p.is_dir() else [p]
    return "\n\n".join(f"===== DOCUMENT: {f.name} =====\n{read_file(f)}" for f in files), [f.name for f in files]


def field_map_vs_openapi(spec, openapi_path):
    """Deterministic: every actual field name in the CallSpec field_map must exist in the openapi request schema of that tool, and
    every required openapi field must be mapped. Returns problem lines."""
    o = json.load(open(openapi_path)); out = []
    req = (spec.get("field_map") or {}).get("req") or {}
    for path, methods in (o.get("paths") or {}).items():
        tool = path.rstrip("/").rsplit("/", 1)[-1]; op = methods.get("post") or methods.get("get") or {}
        schema = ((((op.get("requestBody") or {}).get("content") or {}).get("application/json") or {}).get("schema") or {})
        props = set((schema.get("properties") or {})); required = set(schema.get("required") or [])
        mapped = set((req.get(tool) or {}).values())
        if not props: continue
        for f in mapped - props: out.append(f"field_map.req.{tool}: '{f}' is not a request field of the API ({sorted(props)})")
        for f in required - mapped: out.append(f"field_map.req.{tool}: required API field '{f}' is not mapped (the builder will not send it)")
    return out


def outcome_reasons(rows):
    """The CallSpec has one row per outcome and reason (or several reasons per row): merge them per outcome."""
    out = {}
    for o in rows:
        out.setdefault(o["outcome"], set()).update(o.get("reasons") or [])
    return {k: sorted(v) for k, v in out.items()}


KEY_WORDS = re.compile(r"\d+|monday|tuesday|wednesday|thursday|friday|saturday|sunday|floor|full|deadline|latest|business|calendar|"
                       r"tomorrow|today|next|week|month|first|second|third|last|no attempt|none|same", re.I)


def same_rule(a, b):
    """Two paraphrases of one rule are the same when they name the same numbers, weekdays and amount/date words."""
    def keys(t):
        t = re.sub(r"\([^)]*\)", " ", t or "")                          # drop parenthesised sources and remarks
        t = re.sub(r"^\s*attempt\s*\d+\s*[:.-]?", " ", t, flags=re.I)    # drop a leading "Attempt 2:" label
        return {w.lower() for w in KEY_WORDS.findall(t)}
    ka, kb = keys(a), keys(b)
    return ka == kb


def from_callspec(c):
    d, tp, ident, sp = c["dates"], c["third_party"], c["identity"], c["special"]
    return {
        "holidays": sorted(d.get("holidays") or []), "weekend_days": d.get("weekend_days") or [5, 6],
        "bands": [{k: b.get(k) for k in ("name", "days_late_min", "days_late_max", "deadline_business_days_after_today", "deadline_calendar_days_after_today", "persuasion_attempts")} for b in d["bands"]],
        "callback": {k: tp["callback"].get(k) for k in ("allow_today", "allow_next_business_day", "time_from", "time_to")},
        "identity_questions": [q["field"] for q in ident["questions"]], "max_wrong_answers_total": ident.get("max_wrong_total"),
        "floor_fields": {p["type"]: p["floor_field"] for p in c.get("products") or []},
        "queues": {"human": (sp.get("human") or {}).get("queue"), "hardship": (sp.get("hardship") or {}).get("offer_queue"), "restructuring": (sp.get("restructuring") or {}).get("queue")},
        "outcomes": outcome_reasons(c["closing"]["outcomes"]),
        "sentences": {"after_record": c["confirm"].get("after_record_sentence"), "deceased": tp.get("deceased_sentence"), "opening": c["opening"].get("first_sentence")},
        "attempt1_date_rule": c["persuasion"].get("attempt1_date_rule"),
        "attempt2_rule": next((r for r in c["persuasion"].get("attempt_rules") or [] if "attempt 2" in r.lower() or "second" in r.lower()), None),
    }


def norm(v):
    if isinstance(v, str): return " ".join(v.lower().replace("’", "'").split()).strip(" .")
    if isinstance(v, list): return [norm(x) for x in v]
    if isinstance(v, dict): return {k: norm(x) for k, x in v.items()}
    return v


def diff(a, b, path=""):
    """(path, callspec value, second reading) for every leaf that differs. Sentences compare loosely (word overlap)."""
    out = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)): out += diff(a.get(k), b.get(k), f"{path}.{k}" if path else k)
    elif isinstance(a, list) and isinstance(b, list) and a and isinstance(a[0], dict):
        for i in range(max(len(a), len(b))): out += diff(a[i] if i < len(a) else None, b[i] if i < len(b) else None, f"{path}[{i}]")
    elif (path.startswith("sentences") or path.startswith("attempt")) and isinstance(a, str) and isinstance(b, str):
        wa, wb = set(norm(a).split()), set(norm(b).split())
        if path.startswith("attempt"):                                      # rules are paraphrased: compare what they name
            if not same_rule(a, b): out.append((path, a, b))
        elif len(wa & wb) < 0.7 * min(len(wa), len(wb), 1e9): out.append((path, a, b))   # sentences must be near-exact
    elif path.startswith("outcomes") and isinstance(a or [], list) and isinstance(b or [], list):
        if sorted(norm(a or [])) != sorted(norm(b or [])): out.append((path, a, b))    # no reasons = [] = left out
    elif norm(a) != norm(b): out.append((path, a, b))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("callspec"); ap.add_argument("material", nargs="+"); ap.add_argument("--out"); ap.add_argument("--openapi")
    a = ap.parse_args()
    spec = json.load(open(a.callspec)); text, names = read_material(a.material)
    tools = spec.get("tools") or []
    if a.openapi: text += "\n\n===== TOOL API (openapi.json) =====\n" + pathlib.Path(a.openapi).read_text()[:12000]
    elif tools: text += "\n\n===== TOOL API (field names) =====\n" + json.dumps({t["name"]: [f["name"] + (f" one of {f['enum']}" if f.get("enum") else "") for f in t["fields"]] for t in tools})
    raw = llm.generate("judge", PROMPT, [("user", text)], json_mode=True)       # the judge provider (OpenAI when set), not the builder's model
    second = json.loads(raw)
    mine = from_callspec(spec)
    rows = diff(mine, {k: second.get(k) for k in mine})
    fm_problems = field_map_vs_openapi(spec, a.openapi) if a.openapi else []
    lines = [f"# Rule diff: {pathlib.Path(a.callspec).name} vs a second reading of {', '.join(names)}", "",
             f"Second reader: {llm.model_of(llm.provider('judge'))}. {len(rows)} difference(s). A difference is a candidate extraction error, not a verdict: open the brief and decide.", "",
             "| field | CallSpec (builder) | second reading | source named by the second reader |", "|---|---|---|---|"]
    src = second.get("sources") or {}
    for p, x, y in rows:
        key = p.split(".")[0].split("[")[0]
        lines.append(f"| `{p}` | {json.dumps(x, ensure_ascii=False)} | {json.dumps(y, ensure_ascii=False)} | {src.get(key, src.get(p, ''))} |")
    if not rows: lines.append("| (none) | | | |")
    if a.openapi: lines += ["", f"field_map vs openapi (deterministic): {len(fm_problems)} problem(s)"] + [f"- {x}" for x in fm_problems]
    lines += ["", "Fields compared: " + ", ".join(mine)]
    out = pathlib.Path(a.out or (pathlib.Path("results") / (pathlib.Path(a.callspec).stem.replace(".callspec", "") + "-rulediff.md")))
    out.parent.mkdir(parents=True, exist_ok=True); out.write_text("\n".join(lines) + "\n")
    print("\n".join(lines)); print(f"\n-> {out}")


if __name__ == "__main__":
    main()
