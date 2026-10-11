#!/usr/bin/env bash
# Sunday pipeline for ONE brief after Dora's builder has run: cases from the CallSpec -> local run -> report.
#   source env.sh && tester/final.sh <slot> [reps] [parallel]
# Expects (from the builder):  FREYA/out/<slot>.callspec.json  and  FREYA/out/<slot>.export.workflow.json
# (override with CALLSPEC=... EXPORT=...). Writes results/<slot>-cases.json, results/<slot>-local.json, results/<slot>-report.md.
set -u
cd "$(dirname "$0")/.."
SLOT=${1:?slot}; REPS=${2:-2}; PAR=${3:-6}
CALLSPEC=${CALLSPEC:-$(ls FREYA/out/$SLOT.callspec.json final/$SLOT.callspec.json out/$SLOT.callspec.json 2>/dev/null | head -1)}
EXPORT=${EXPORT:-$(ls FREYA/out/$SLOT.export.workflow.json FREYA/submission/$SLOT.workflow.json final/$SLOT.workflow.json submission/$SLOT.workflow.json 2>/dev/null | head -1)}
OPENAPI=${OPENAPI:-$(ls final/$SLOT/openapi.json final/$SLOT.openapi.json 2>/dev/null | head -1)}
BRIEF=${BRIEF:-$SLOT}; T0=$(date +%s)
[ -f "$CALLSPEC" ] || { echo "no callspec for $SLOT (set CALLSPEC=)"; exit 1; }; [ -f "$EXPORT" ] || { echo "no export for $SLOT (set EXPORT=)"; exit 1; }
echo "== 1/3 cases from $CALLSPEC ${OPENAPI:+(api rules: $OPENAPI)}"
python3 tester/cases_from_callspec.py "$CALLSPEC" --brief "$BRIEF" --tag "${TAG:-OUR}" --local-bank ${OPENAPI:+--openapi "$OPENAPI"} --out "results/$SLOT-cases.json" | tee "results/$SLOT-cases.log" | tail -n 12
echo "== 2/3 local run: $EXPORT, $REPS rep(s), $PAR parallel"
python3 tester/local_sim.py "$EXPORT" --agent local --bank local --cases "results/$SLOT-cases.json" --reps "$REPS" --parallel "$PAR" ${STYLE:+--style "$STYLE"} --out "results/$SLOT-local.json" | tee "results/$SLOT-local.log" | grep -E "^(PASS|FAIL|ERROR)|       - |       ! |passed|usage|cache|audit"
echo "== 3/3 report"
python3 - "$SLOT" "$T0" <<'PY'
import json, sys, time, pathlib
slot, t0 = sys.argv[1], int(sys.argv[2])
r = json.load(open(f"results/{slot}-local.json")); cases = {c["id"]: c for c in json.load(open(f"results/{slot}-cases.json"))}
rows = r["rows"]; final = {f["id"]: f for f in r["final"]}
L = [f"# {slot}: local coverage report ({time.strftime('%Y-%m-%d %H:%M')}, {int(time.time()-t0)} s)", "",
     f"**{r['passed']}/{r['total']} customers pass in every rep** (reps per customer: {rows and max(x['rep'] for x in rows)}).", "",
     "| case | family | title | reps | fails / flags |", "|---|---|---|---|---|"]
for cid, f in final.items():
    mine = [x for x in rows if x["id"] == cid]; c = cases[cid]
    notes = []
    for x in mine:
        for fl in x.get("failed", []): notes.append(f"rep{x['rep']}: {fl[:140]}")
        for fl in x.get("flags", []): notes.append(f"rep{x['rep']} ! {fl[:100]}")
    L.append(f"| {cid} | {c['family']} | {c['title']} | {f['passes']}/{f['runs']}{' ('+str(f['errors'])+' err)' if f['errors'] else ''} | {'<br>'.join(notes)} |")
skipped = [l for l in open(f"results/{slot}-cases.log") if l.startswith("skipped:")]
if skipped: L += ["", "Templates skipped (rule not in this brief): " + "; ".join(s.strip()[9:] for s in skipped)]
L += ["", "Classify every FAIL before acting: judge quirk / case wording / agent behaviour (generic -> builder fix allowed) / model difference (confirm on Freya).",
      "Candidates for the official run (limited): cases with flags, after_promise paths, intent routing, and every FAIL."]
pathlib.Path(f"results/{slot}-report.md").write_text("\n".join(L) + "\n"); print("\n".join(L[:4])); print(f"-> results/{slot}-report.md")
PY
