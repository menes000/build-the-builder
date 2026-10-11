"""Run a Freya workflow JSON locally, with Gemini in place of Freya's models. No Freya request during the call.

Follows the engine as docs/build-the-builder/docs/workflow-format.md and tools-and-code.md describe it:
- after each user message: extraction, then routing, then dialogue (three separate model calls, all Gemini here);
- code nodes, code_exec and the pre/post hooks of api_call tools run in local Python (no snekbox);
- api_call tools send the same HTTP request Freya would, to the real bank mock, so the ledger is scored as usual;
- end_of_call lifecycle tools run when the call ends.

It is an approximation of Freya's runtime, not a copy: the dialogue model is Gemini, not experimental-5, and
undocumented details (prompt wrappers, extraction confidence) are guessed. Use it for cheap, unlimited runs and
confirm on Freya before trusting a result.

    agent = LocalAgent(workflow_json, call_variables)
    first_text = agent.start("Hello?")
    text, ended = agent.send("Yes, speaking.")
    agent.finish(); agent.transcript_text()
"""
import copy, datetime, json, os, re, urllib.error, urllib.parse, urllib.request

import gemini, llm

AGENT_MODEL = os.environ.get("EMU_AGENT_MODEL", gemini.MODEL)        # writes the agent's replies
ENGINE_MODEL = os.environ.get("EMU_ENGINE_MODEL", gemini.MODEL)      # extraction and routing
ENGINE_THINKING = os.environ.get("ENGINE_THINKING", "low")           # extraction/routing are classification: capped thinking saves money
AGENT_THINKING = os.environ.get("AGENT_THINKING") or None             # the dialogue model keeps the default (experimental-5 reasons too)
UA = {"user-agent": "freya-local-emulator/0.1"}
PH = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")
MAX_STEPS = 8                                                         # model/tool rounds in one agent turn


def load_workflow(given):
    """A path to a workflow JSON (plain or as written by freya.export_workflow), or a workflow id / agent id / slot on Freya."""
    if os.path.exists(given):
        w = json.load(open(given))
        return w.get("workflow", w)
    import freya
    listed = freya.api("GET", "/api/v2/workflow", workspaceId=freya.workspace_id())
    for x in listed.get("workflows", []) if isinstance(listed, dict) else listed:
        if given in (x.get("id"), x.get("name"), x.get("agentId")): given = x["id"]
    return freya.api("GET", f"/api/v2/workflow/{given}", workspaceId=freya.workspace_id())["workflow"]["workflow"]


def text_of(v):
    if isinstance(v, bool): return "true" if v else "false"
    if isinstance(v, (dict, list)): return json.dumps(v, default=str)
    return str(v)


def flatten(prefix, v, out):
    """The engine writes every result into the variable table, flattened with dots. Booleans become lower-case strings."""
    if isinstance(v, dict):
        for k, x in v.items(): flatten(f"{prefix}.{k}", x, out)
    else:
        out[prefix] = text_of(v) if isinstance(v, bool) else v


def endpoints_of(workflow):
    """Workflow tool name -> the bank API endpoint it calls (last URL path segment), for every api_call tool anywhere in the workflow.
    The judge reads endpoint names: Freya's judge accepted `transfer_support` for "transfer_to_agent called" and `api_call` for get_account,
    so a judge that fails on the workflow's own tool names would be stricter than the real one."""
    out = {}
    def scan(tools):
        for t in tools or []:
            f = t.get("function") or {}
            url = ((f.get("parameters") or {}).get("properties") or {}).get("url", {}).get("default")
            if f.get("handler") == "__function__:api_call" and isinstance(url, str) and f.get("name"):
                out[f["name"]] = url.rstrip("/").rsplit("/", 1)[-1] or f["name"]
    scan(workflow.get("tools"))
    for n in list((workflow.get("nodes") or {}).values()) + list((workflow.get("global_nodes") or {}).values()):
        scan(n.get("tools")); scan(n.get("pre_actions"))
    return out


SUPPORTED_OPS = {"equals", "not_equals", "greater_than", "less_than", "contains", "is_set", "is_not_set", "always", "matches_intent"}
SUPPORTED_NODE_TYPES = {"conversation", "api_request", "code", "end_call"}


def audit(workflow):
    """Features of a workflow this emulator does not reproduce (or only partly). Printed at run start so a silent mismatch is not mistaken for agent behaviour."""
    w = workflow.get("workflow", workflow); out = []
    nodes = dict(w.get("nodes") or {}); globals_ = dict(w.get("global_nodes") or {})
    if globals_: out.append(f"global_nodes {list(globals_)}: supported for intent/deterministic conditions; __previous__ and excluded_nodes partly")
    if w.get("context_variables"): out.append("context_variables: not rendered into the dialogue prompt (Freya drops them on save too)")
    def conds(c):
        if not c: return
        yield c
        for x in c.get("conditions") or []: yield from conds(x)
    for k, n in list(nodes.items()) + list(globals_.items()):
        if n.get("node_type") not in SUPPORTED_NODE_TYPES: out.append(f"{k}: node_type {n.get('node_type')} not supported")
        if n.get("loop_condition"): out.append(f"{k}: loop_condition (approximated: judged with the intents, loop_prompt used after a match)")
        if (n.get("truncation_strategy") or "keep_all") != "keep_all": out.append(f"{k}: truncation_strategy {n['truncation_strategy']} not applied (full history is sent)")
        if n.get("routing_prompt"): out.append(f"{k}: routing_prompt (appended to our routing prompt, wording differs from Freya's)")
        for t in n.get("transitions") or []:
            for c in conds(t.get("condition")):
                if c.get("operator") and c["operator"] not in SUPPORTED_OPS: out.append(f"{k}: condition operator {c['operator']} unsupported")
        for t in n.get("tools") or []:
            f = t.get("function") or {}; cfg = t.get("config") or {}
            if f.get("handler") == "__function__:code_exec": out.append(f"{k}: code_exec as a model tool (Freya returns no data to the model; emulated the same way)")
            if cfg.get("interruptible") is False: out.append(f"{k}/{f.get('name')}: background tool (result arrives next turn on Freya; here immediately)")
            if f.get("handler") not in ("__function__:api_call", "__function__:code_exec"): out.append(f"{k}/{f.get('name')}: handler {f.get('handler')} unsupported")
            if t.get("response_mapping") is None and n.get("response_mapping"): out.append(f"{k}: node-level response_mapping on a conversation node (Freya applies tool-level only)")
        for t in n.get("pre_actions") or []:
            if (t.get("function") or {}).get("handler") not in ("__function__:api_call", "__function__:code_exec"): out.append(f"{k}: pre_action handler {(t.get('function') or {}).get('handler')} unsupported")
            if t.get("response_mapping"): out.append(f"{k}: response_mapping inside a pre_action is ignored by Freya (must be node-level); emulator ignores it too")
        for f in n.get("extraction_schema") or []:
            if f.get("extraction_prompt"): out.append(f"{k}/{f.get('name')}: custom extraction_prompt not used (built-in prompt instead)")
            if f.get("type") in ("date", "datetime") : pass
        term = ((n.get("terminal") or {}).get("function") or {}).get("parameters", {}).get("properties", {})
        if (term.get("message_mode") or {}).get("default") == "llm" and n.get("node_type") == "end_call": out.append(f"{k}: end_call message_mode llm (farewell written by the dialogue model, approximated)")
        if term.get("interruptible"): out.append(f"{k}: terminal interruptible window not simulated")
    for t in w.get("tools") or []:
        at = (t.get("config") or {}).get("alwaysRunsAt") or []
        if "each_turn" in at: out.append(f"workflow tool {t['function']['name']}: alwaysRunsAt each_turn never fires on Freya; not emulated")
    return out


def dig(obj, path):
    for k in path.split("."):
        if isinstance(obj, dict) and k in obj: obj = obj[k]
        elif isinstance(obj, list) and k.isdigit() and int(k) < len(obj): obj = obj[int(k)]
        else: return None
    return obj


class LocalAgent:
    def __init__(self, workflow, variables, call_id="local"):
        self.w = workflow
        self.nodes = dict(workflow.get("nodes") or {})
        self.globals = dict(workflow.get("global_nodes") or {})
        self.vars = {**(workflow.get("test_variables") or {}), **variables}     # a value passed with the call wins
        self.vars.update({"call.direction": "web", "call.call_id": call_id})
        llm = (workflow.get("agent_config") or {}).get("llmConfig") or {}
        self.agent_tools = [t for t in llm.get("tools") or [] if (t.get("function") or {}).get("name")]   # offered in every node (end_call)
        self.temperature = float(llm.get("temperature") or 0.7)
        self.max_tokens = int(llm.get("maxTokens") or 1000)
        self.warnings = []        # agent behaviour worth a look (silent turn, parallel tool calls, model-filled lifecycle fields)
        self.endpoints = endpoints_of(workflow)
        self.bank_host = os.environ.get("LOCAL_BANK_HOST") or ""   # set by local_sim --bank local: every bank URL is redirected there
        self.path = []            # nodes entered, in order, like Freya's node_enter events
        self.routes = []          # routing decisions taken by the routing model (intent), like Freya's route_evaluated events
        self.started_at = datetime.datetime.now()
        self.events = []          # ("user"|"agent", text) | ("call", name, args, by_model, raw_part) | ("result", name, result)
        self.node = None
        self.prev = None
        self.turns = {}           # node -> {"current": n, "total": n}
        self.entered = set()
        self.loop_mode = False
        self.baked = {}           # tool name -> (baked fields, model fields) fixed at node entry
        self.ended = False
        self.infra = []

    # ---------- text ----------
    def sub(self, s, mode="prompt"):
        """{{var}} substitution. An unresolved placeholder stays literal (prompt, spoken line)."""
        if not isinstance(s, str): return s
        def one(m):
            name, as_json = m.group(1), False
            if name.endswith(":json"): name, as_json = name[:-5], True
            v = self.lookup(name)
            if v is None: return m.group(0)
            return json.dumps(v) if as_json else text_of(v)
        return PH.sub(one, s)

    def lookup(self, name):
        if name in self.vars and self.vars[name] not in (None,): return self.vars[name]
        if name == "system.conversation" or name.startswith("system.conversation.last-"):
            lines = [("AGENT: " if e[0] == "agent" else "USER: ") + e[1] for e in self.events if e[0] in ("user", "agent")]
            if "last-" in name: lines = lines[-2 * int(name.rsplit("-", 1)[1]):]
            return "\n".join(lines)
        if name.endswith(".current_turns") or name.endswith(".total_turns"):
            node, kind = name.rsplit(".", 1)
            return self.turns.get(node, {}).get(kind.split("_")[0], 0)
        if name == "system.iso_utc_now": return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        if name == "call.duration": return int((datetime.datetime.now() - self.started_at).total_seconds())
        return None

    def say(self, text, out):
        text = (text or "").strip()
        if text: self.events.append(("agent", text)); out.append(text)

    # ---------- conditions and routing ----------
    def check(self, c):
        """True / False for a deterministic condition, None when it needs the routing model."""
        if not c: return None
        if "conditions" in c:
            vals = [self.check(x) for x in c["conditions"]]
            if c.get("logic", "or") == "and":
                return False if False in vals else (None if None in vals else True)
            return True if True in vals else (None if None in vals else False)
        op, v = c.get("operator"), self.vars.get(c.get("variable"))
        if op == "always": return True
        if op == "matches_intent": return None
        if op == "is_set": return v not in (None, "")
        if op == "is_not_set": return v in (None, "")
        if v is None: return False
        o = c.get("operand")
        try:
            if op == "equals": return text_of(v) == text_of(o)
            if op == "not_equals": return text_of(v) != text_of(o)
            if op == "contains": return str(o).lower() in text_of(v).lower()
            if op == "greater_than": return float(v) > float(o)
            if op == "less_than": return float(v) < float(o)
        except (TypeError, ValueError):
            return False
        return False

    def intents(self, c, acc):
        if not c: return
        if c.get("operator") == "matches_intent": acc.append(c.get("description") or "")
        for x in c.get("conditions") or []: self.intents(x, acc)

    def judge_intents(self, descriptions, routing_prompt=""):
        """One routing-model call for all intent conditions of an evaluation. Returns the set of matched indices."""
        if not descriptions: return set()
        convo = self.lookup("system.conversation.last-5")
        prompt = ("You are the routing model of a phone agent. Read the end of the conversation and decide which of the numbered "
                  "conditions the USER's last message matches. " + (routing_prompt or "") +
                  '\nAnswer with JSON only: {"matches": [numbers]}. An empty list when none matches.\n\nConditions:\n' +
                  "\n".join(f"{i}. {self.sub(d)}" for i, d in enumerate(descriptions)))
        try:
            raw = llm.generate("route", prompt, [("user", convo or "(no conversation yet)")], json_mode=True, thinking=ENGINE_THINKING or None)
            return {int(i) for i in json.loads(raw).get("matches", [])}
        except Exception as e:
            self.infra.append(f"routing model: {e}"[:200]); return set()

    def route(self, node_key, deterministic_only=False, user_turn=False):
        """Return the target node or None. Order: loop_condition, the node's transitions in list order, global nodes."""
        n = self.nodes.get(node_key) or self.globals.get(node_key) or {}
        trans = [t for t in n.get("transitions") or [] if not t.get("is_tool_call")]
        cands = []                                             # (kind, transition or global key, condition)
        if user_turn and n.get("loop_condition"):
            cands.append(("loop", None, {"operator": "matches_intent", "description": n["loop_condition"]}))
        cands += [("t", t, t.get("condition")) for t in trans]
        cands += [("g", k, g.get("condition")) for k, g in self.globals.items()
                  if not g.get("is_tool_call") and node_key not in (g.get("excluded_nodes") or []) and k != node_key]
        if deterministic_only:
            for kind, t, c in cands:
                if kind == "t" and c and c.get("operator") != "always" and self.check(c) is True: return t["target_node"]
            return None
        verdicts, descs = [], []
        for kind, t, c in cands:
            v = self.check(c)
            if v is None:
                acc = []; self.intents(c, acc); idx = list(range(len(descs), len(descs) + len(acc))); descs += acc
                verdicts.append((kind, t, idx))
            else:
                verdicts.append((kind, t, v))
        hit = None
        for i, (kind, t, v) in enumerate(verdicts):         # deterministic matches before the intents need no model call
            if v is True and not any(isinstance(x[2], list) for x in verdicts[:i]): hit = (kind, t); break
        if hit is None and descs:
            matched = self.judge_intents(descs, n.get("routing_prompt", ""))
            for kind, t, v in verdicts:
                if v is True or (isinstance(v, list) and matched & set(v)): hit = (kind, t); break
        if hit is None: return None
        kind, t = hit
        if isinstance(hit_v := next((v for k, tt, v in verdicts if (k, tt) == hit), None), list):
            desc = next((c.get("description") for c in [(t.get("condition") if kind == "t" else (self.globals.get(t) or {}).get("condition")) or {}] if c), "")
            self.routes.append(f"{node_key} -> {t['target_node'] if kind == 't' else t}: intent '{(desc or '')[:90]}'")
        if kind == "loop": self.loop_mode = True; return None
        return t if kind == "g" else t["target_node"]

    # ---------- extraction ----------
    def extract(self, node_key):
        schema = (self.nodes.get(node_key) or self.globals.get(node_key) or {}).get("extraction_schema") or []
        if not schema: return
        lines = []
        for f in schema:
            extra = f" One of: {', '.join(map(str, f['enum_values']))}." if f.get("enum_values") else ""
            lines.append(f"- {f['name']} ({f.get('type', 'string')}): {f.get('description', '')}{extra}")
        today = str(self.vars.get("now") or datetime.date.today().isoformat())
        prompt = ("Extract variables from the conversation of a phone call. Use the latest user message and its context. "
                  f"Now is {today}. Dates as YYYY-MM-DD, datetimes as YYYY-MM-DDTHH:MM. Leave a variable null when it was not given.\n"
                  "Variables:\n" + "\n".join(lines) +
                  '\nAnswer with JSON only: {"values": {"name": value or null, ...}, "confidence": {"name": 0.0 to 1.0, ...}}. '
                  "Confidence is how sure you are of each value; 1.0 only when the user said it plainly.")
        try:
            got = json.loads(llm.generate("extract", prompt, [("user", self.lookup("system.conversation.last-10"))], json_mode=True, thinking=ENGINE_THINKING or None))
        except Exception as e:
            self.infra.append(f"extraction model: {e}"[:200]); return
        if not isinstance(got, dict): return
        values, conf = (got.get("values") if isinstance(got.get("values"), dict) else got), (got.get("confidence") if isinstance(got.get("confidence"), dict) else {})
        for f in schema:
            v = values.get(f["name"])
            if v in (None, ""): continue
            if f.get("enum_values") and text_of(v) not in map(text_of, f["enum_values"]): continue
            if f.get("validation_pattern") and not re.search(f["validation_pattern"], text_of(v)): continue
            c = conf.get(f["name"])
            try: c = float(c) if c is not None else 1.0
            except (TypeError, ValueError): c = 1.0
            if c < float(f.get("min_confidence") or 0.95):     # Freya discards low-confidence values without a trace
                self.warnings.append(f"extraction: {f['name']}={v!r} dropped, confidence {c:.2f} < {f.get('min_confidence') or 0.95}"); continue
            self.vars[f["name"]] = v
            self.events.append(("extracted", f["name"], v))

    # ---------- tools ----------
    def bake(self, tool):
        """At node entry: fields whose default resolves are baked; the others are for the model, named after their variable."""
        props = ((tool.get("function") or {}).get("parameters") or {}).get("properties") or {}
        baked, model = {}, {}
        def leaf(spec, path):
            d = spec.get("default")
            names = PH.findall(d) if isinstance(d, str) else []
            if d is not None and not (names and len(names) == 1 and d.strip() == "{{" + names[0] + "}}" and self.lookup(names[0]) is None):
                baked[".".join(path)] = self.sub(d) if isinstance(d, str) else d
            else:
                name = names[0] if names else path[-1]
                model[name] = (".".join(path), {k: v for k, v in spec.items() if k in ("type", "description", "enum")})
        for k, s in props.items():
            if k in ("headers", "body") and isinstance(s.get("properties"), dict):
                for kk, ss in s["properties"].items(): leaf(ss, [k, kk])
            else:
                leaf(s, [k])
        return baked, model

    def declaration(self, tool):
        f = tool["function"]
        _, model = self.baked[f["name"]]
        if f.get("handler") == "__function__:code_exec":
            props = {k: {kk: vv for kk, vv in s.items() if kk in ("type", "description", "enum")} for k, s in (f.get("parameters") or {}).get("properties", {}).items() if "default" not in s}
        else:
            props = {name: spec for name, (_, spec) in model.items()}
        for s in props.values():
            if s.get("type") not in ("string", "number", "integer", "boolean", "object", "array"): s["type"] = "string"
        decl = {"name": f["name"], "description": f.get("description") or ""}
        if props: decl["parameters"] = {"type": "object", "properties": props}
        return decl

    def run_python(self, code, scope):
        try:
            exec(compile(code, "<workflow code>", "exec"), {"__builtins__": __builtins__, **scope})
            return True
        except Exception as e:
            self.infra.append(f"python: {type(e).__name__}: {e}"[:200]); return False

    def http_call(self, tool, args, counter_name, by_model, raw=None):
        """One api_call or code_exec as the engine runs it. Returns the result envelope the model sees."""
        f = tool["function"]; name = f["name"]; cfg = tool.get("config") or {}
        timeout = max(1.0, float(cfg.get("timeoutMs") or 20000) / 1000)
        if f.get("handler") == "__function__:code_exec":
            code = self.sub(dig({"p": (f.get("parameters") or {}).get("properties", {})}, "p.code.default") or args.get("code") or "")
            self.events.append(("call", name, {"code": code[:300]}, by_model, raw))
            ok = self.run_python(code, {"vars": self.vars})
            res = {"status": "success" if ok else "error", "data": None, "message": "Code executed successfully" if ok else "Code failed", "status_code": 200 if ok else 500}
        else:
            baked, model = self.baked.get(name) or self.bake(tool)
            req = {"url": "", "method": "POST", "headers": {}, "body": {}}
            for path, v in baked.items():
                parts = path.split(".")
                if parts[0] in ("headers", "body") and len(parts) > 1: req[parts[0]][".".join(parts[1:])] = v
                else: req[parts[0]] = v
            for var, (path, _) in model.items():
                if var in args:
                    parts = path.split(".")
                    if parts[0] == "body": req["body"][".".join(parts[1:])] = args[var]
                    self.vars[f"{name}_args.{parts[-1]}"] = args[var]
            if tool.get("pre_process_code", "").strip(): self.run_python(tool["pre_process_code"], {"vars": self.vars, "config": req})
            self.events.append(("call", name, req.get("body"), by_model, raw))
            res = None
            for attempt in range(1 + int(cfg.get("maxRetries") or 0)):
                res = self.send_http(req, timeout)
                if res["status"] == "success": break
            if tool.get("post_process_code", "").strip(): self.run_python(tool["post_process_code"], {"vars": self.vars, "result": res})
        good = res.get("status") == "success"
        data = res.get("data") if isinstance(res, dict) else None
        if by_model and (not good or (isinstance(data, dict) and data.get("ok") is False)):
            self.rejected = getattr(self, "rejected", {}); self.rejected[name] = self.rejected.get(name, 0) + 1
            if self.rejected[name] == 2: self.warnings.append(f"{name} rejected/failed {self.rejected[name]}x in one call: the model keeps retrying (seen on Freya: create_promise after a recorded promise)")
        key = counter_name
        self.vars[f"{key}_success_count"] = int(self.vars.get(f"{key}_success_count") or 0) + good
        self.vars[f"{key}_failure_count"] = int(self.vars.get(f"{key}_failure_count") or 0) + (not good)
        self.vars[f"{key}_status_code"] = res.get("status_code")
        flat = {}; flatten(f"{key}_response", res, flat); self.vars.update(flat)
        self.events.append(("result", name, res))
        return res

    def send_http(self, req, timeout=20):
        body = req.get("body")
        data = body.encode() if isinstance(body, str) else json.dumps(body).encode()
        headers = {**UA, "content-type": "application/json", **{k: str(v) for k, v in (req.get("headers") or {}).items()}}
        url = self.sub(req.get("url"))
        if self.bank_host:                                  # keep the path (/v1/create_promise), swap scheme and host for the local fake bank
            u = urllib.parse.urlsplit(url); b = urllib.parse.urlsplit(self.bank_host)
            url = urllib.parse.urlunsplit((b.scheme, b.netloc, u.path, u.query, ""))
        r = urllib.request.Request(url, data=data if req.get("method", "POST") != "GET" else None, headers=headers, method=req.get("method", "POST"))
        try:
            with urllib.request.urlopen(r, timeout=timeout) as resp:
                raw, code = resp.read().decode(), resp.status
        except urllib.error.HTTPError as e:
            raw, code = e.read().decode(), e.code
        except Exception as e:
            self.infra.append(f"http {req.get('url')}: {e}"[:200])
            return {"status": "error", "data": None, "message": str(e), "status_code": 0}
        try: payload = json.loads(raw)
        except ValueError: payload = raw
        return {"status": "success" if 200 <= code < 300 else "error", "data": payload, "message": f"Executed {req.get('method', 'POST')} request", "status_code": code, "header": {}}

    def apply_mapping(self, mapping, res):
        for m in mapping or []:
            v = dig(res, m["path"])
            if v is not None: self.vars[m["variable"]] = text_of(v) if isinstance(v, bool) else v

    # ---------- nodes ----------
    def spec(self, key): return self.nodes.get(key) or self.globals.get(key) or {}

    def enter(self, key, out, hops=0):
        """Enter a node: entry actions, entry line, passthrough routing, end of call."""
        if hops > 25: self.infra.append("routing loop: more than 25 nodes in one turn"); return
        if key == "__previous__": key = self.prev or self.w.get("initial_node")
        if key not in self.nodes and key not in self.globals: self.infra.append(f"unknown node {key}"); return
        self.prev, self.node, self.loop_mode = self.node, key, False
        self.path.append(key)
        n = self.spec(key)
        self.turns.setdefault(key, {"current": 0, "total": 0})["current"] = 0
        first = key not in self.entered; self.entered.add(key)
        for t in n.get("tools") or []: self.baked[t["function"]["name"]] = self.bake(t)
        for t in n.get("pre_actions") or []:
            self.baked[t["function"]["name"]] = self.bake(t)
            res = self.http_call(t, {}, key, by_model=False)
            self.apply_mapping(n.get("response_mapping"), res)
        if n.get("node_type") == "end_call":
            p = ((n.get("terminal") or {}).get("function") or {}).get("parameters", {}).get("properties", {})
            mode = (p.get("message_mode") or {}).get("default", "custom")
            farewell = self.sub((p.get("spoken_message") or {}).get("default", ""))
            self.events.append(("call", "end_call", {"message_mode": mode, "spoken_message": farewell} if mode == "custom" else {"message_mode": mode}, False, None))
            if mode == "custom": self.say(farewell, out)
            elif mode == "llm": self.dialogue(key, out, entry_prompt=(p.get("llm_prompt") or {}).get("default", "Say goodbye."), allow_tools=False)
            self.events.append(("result", "end_call", {"status": "success", "message": "Call ended"}))
            self.ended = True
            return
        oe = n.get("on_enter") or {"type": "llm"}
        if first or not n.get("on_enter_first_entry_only"):
            if oe.get("type") == "tts": self.say(self.sub(oe.get("text", "")), out)
            elif oe.get("type") == "llm" and not n.get("passthrough"): self.dialogue(key, out, entry_prompt=oe.get("prompt"))
            if self.ended or self.node != key: return
        elif n.get("node_type") == "conversation" and self.events and self.events[-1][0] == "user":
            self.dialogue(key, out)                                  # re-entry without an entry line: answer the user
            if self.ended or self.node != key: return
        if n.get("passthrough"):
            target = self.route(key) or n.get("passthrough_default_transition")
            if target and target != key: self.enter(target, out, hops + 1)

    def system_for(self, key, entry_prompt=None):
        n = self.spec(key)
        task = n.get("loop_prompt") if self.loop_mode and n.get("loop_prompt") else n.get("task_message", "")
        if entry_prompt: task = (task + "\n\n" + entry_prompt).strip()
        parts = [self.w.get("system_prompt", ""), n.get("role_message", ""), "## Current Task\n" + (task or "")]
        return self.sub("\n\n".join(p for p in parts if p))

    def contents(self):
        """Conversation for the dialogue model. Calls the model made keep their raw parts; engine-run calls are told as text."""
        out = []
        def push(role, part):
            if out and out[-1]["role"] == role: out[-1]["parts"].append(part)
            else: out.append({"role": role, "parts": [part]})
        pending = {}
        for e in self.events:
            if e[0] == "user": push("user", {"text": e[1]})
            elif e[0] == "agent": push("model", {"text": e[1]})
            elif e[0] == "call" and e[3] and e[4]: push("model", e[4]); pending[e[1]] = True
            elif e[0] == "result" and pending.pop(e[1], None): push("user", {"functionResponse": {"name": e[1], "response": {"result": e[2]}}})
            elif e[0] == "result" and e[1] != "engine": push("user", {"text": f"[engine ran {e[1]}, result: {json.dumps(e[2], default=str)[:600]}]"})
        if not out or out[0]["role"] != "user": out.insert(0, {"role": "user", "parts": [{"text": "(call connected)"}]})
        return out

    def dialogue(self, key, out, entry_prompt=None, allow_tools=True):
        """The dialogue model's turn in a node: speak, or call tools until it speaks, routing after each tool result."""
        n = self.spec(key)
        tools = {t["function"]["name"]: t for t in (n.get("tools") or [])} if allow_tools else {}
        moves = {}
        if allow_tools:
            for t in n.get("transitions") or []:
                if t.get("is_tool_call"): moves["transition_to_" + t["target_node"]] = t
            for gk, g in self.globals.items():
                if g.get("is_tool_call") and key not in (g.get("excluded_nodes") or []): moves["transition_to_" + gk] = {"target_node": gk, "description": g.get("description", "")}
        decls = [self.declaration(t) for t in tools.values()]
        decls += [{"name": k, "description": self.sub(t.get("description") or (t.get("condition") or {}).get("description", ""))} for k, t in moves.items()]
        agent_level = {}
        if allow_tools:
            for t in self.agent_tools:                      # agent_config.llmConfig.tools: offered in every conversation node
                f = t["function"]
                if f["name"] in tools or f["name"] in moves: continue
                agent_level[f["name"]] = t
                decls.append({"name": f["name"], "description": f.get("description") or ""})
        for _ in range(MAX_STEPS):
            try:
                parts = gemini.call(self.system_for(key, entry_prompt), self.contents(), decls or None, model=AGENT_MODEL, temperature=self.temperature, max_tokens=self.max_tokens, thinking=AGENT_THINKING)
            except Exception as e:
                self.infra.append(f"dialogue model: {e}"[:300]); return
            entry_prompt = None
            text = "".join(p.get("text", "") for p in parts if "text" in p).strip()
            self.say(text, out)
            calls = [p for p in parts if "functionCall" in p]
            if not calls and not text:
                self.warnings.append(f"node {key}: the model returned no speakable content (no text, no tool call)")
                self.events.append(("result", "engine", {"error": "The model returned no speakable content"}))
            if not calls: return
            if len(calls) > 1: self.warnings.append(f"node {key}: {len(calls)} tool calls in one message ({', '.join(p['functionCall'].get('name', '?') for p in calls)})")
            for p in calls:
                fc = p["functionCall"]; name, args = fc.get("name"), fc.get("args") or {}
                if name in agent_level and (agent_level[name]["function"].get("handler") == "__function__:end_call"):
                    self.events.append(("call", name, args, True, p)); self.events.append(("result", name, {"status": "success", "message": "Call ended"}))
                    self.warnings.append(f"node {key}: the model hung up with the agent-level end_call tool")
                    self.ended = True; return
                if name in moves:
                    self.events.append(("call", name, args, True, p)); self.events.append(("result", name, {"status": "success"}))
                    self.enter(moves[name]["target_node"], out); return
                if name not in tools:
                    self.events.append(("call", name, args, True, p))
                    self.events.append(("result", name, {"error": f"The function `{name}` is not currently available."})); continue
                res = self.http_call(tools[name], args, name, by_model=True, raw=p)
                self.apply_mapping(tools[name].get("response_mapping"), res)
                if n.get("suppress_tool_results"):
                    self.events[-1] = ("result", name, {"status": res.get("status")})
                target = self.route(key, deterministic_only=True)
                if target and target != key: self.enter(target, out); return
                if self.ended: return
        self.infra.append(f"node {key}: no reply after {MAX_STEPS} model/tool rounds")

    # ---------- the call ----------
    def lifecycle(self, when):
        for t in self.w.get("tools") or []:
            if when not in ((t.get("config") or {}).get("alwaysRunsAt") or []): continue
            name = t["function"]["name"]
            self.baked[name] = baked, model = self.bake(t)
            args = {}
            if model:                                         # docs: an unresolved {{var}} parameter is filled by one model call
                self.warnings.append(f"lifecycle {name}: {', '.join(model)} unresolved at {when}, filled by the model")
                try:
                    parts = gemini.call(self.w.get("system_prompt", "") + f"\n\nThe call has ended. Call the tool {name} with the values that fit this call.",
                                        self.contents(), [self.declaration(t)], model=AGENT_MODEL, temperature=self.temperature)
                    for p in parts:
                        if "functionCall" in p and p["functionCall"].get("name") == name: args = p["functionCall"].get("args") or {}
                except Exception as e:
                    self.infra.append(f"lifecycle model: {e}"[:200])
            res = self.http_call(t, args, name, by_model=False)
            if when == "start_of_call": self.apply_mapping(t.get("response_mapping"), res)

    def start(self, first_user_message="Hello?"):
        out = []
        self.lifecycle("start_of_call")
        if first_user_message: self.events.append(("user", first_user_message))
        self.enter(self.w["initial_node"], out)
        if self.ended: self.finish()
        return " ".join(out)

    def send(self, message):
        """One customer message. Returns (agent text, call ended)."""
        if self.ended: return "", True
        out = []
        self.events.append(("user", message))
        key = self.node; n = self.spec(key)
        tc = self.turns.setdefault(key, {"current": 0, "total": 0}); tc["current"] += 1; tc["total"] += 1
        self.extract(key)
        if n.get("max_node_turns") and n.get("max_turn_transition") and tc["current"] > int(n["max_node_turns"]):
            self.enter(n["max_turn_transition"], out)
        else:
            target = self.route(key, user_turn=True)
            if target and target != key: self.enter(target, out)
            else: self.dialogue(key, out)
        if self.ended: self.finish()
        return " ".join(out), self.ended

    def finish(self):
        """The call is over (agent hung up, or the customer did): end_of_call tools run once."""
        if getattr(self, "_finished", False): return
        self._finished = True; self.ended = True
        self.lifecycle("end_of_call")

    def transcript_text(self):
        out, ep = [], self.endpoints
        for e in self.events:
            if e[0] == "user": out.append("CUSTOMER: " + e[1])
            elif e[0] == "agent": out.append("AGENT: " + e[1])
            elif e[0] == "call" and not e[1].startswith("transition_to_"): out.append(f"TOOL CALL {ep.get(e[1], e[1])}: {json.dumps(e[2], default=str)[:400]}")
            elif e[0] == "result" and e[1] == "engine": out.append(f"ENGINE: {json.dumps(e[2])[:200]}")
            elif e[0] == "result" and e[1] != "code_exec" and not e[1].startswith("transition_to_"):
                r = e[2].get("data", e[2]) if isinstance(e[2], dict) else e[2]
                out.append(f"TOOL RESULT {ep.get(e[1], e[1])}: {json.dumps(r, default=str)[:400]}")
        return "\n".join(out)
