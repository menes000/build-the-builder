"""Submission entry point: python3 builder/build.py <brief file or folder> <tool openapi file> [extra builder options]

Builds one phone agent for one brief and writes:
  submission/<name>.workflow.json   the workflow as stored on Freya (freya.export_workflow)
  traces/<time>-<name>.txt/.jsonl   the run trace; the same lines go to stdout (tee them into traces/<name>.log)
<name> is the brief's file stem or folder name. The same brief can be built again; every run creates a new version
of the same agent slot. After the export the team's local coverage test runs (tester/local_test.py, report only, needs GEMINI_API_KEY);
`--no-local-test` skips it. Other options (for example `--test A`) are passed to builder.main unchanged.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from builder.main import main  # noqa: E402


def entry(argv: list[str]) -> int:
    if len(argv) < 2 or argv[0].startswith("-"):
        print(__doc__)
        return 2
    brief, openapi, extra = argv[0], argv[1], argv[2:]
    bp = Path(brief)
    name = bp.name if bp.is_dir() else bp.stem
    if not bp.is_dir() and name.lower() in ("brief", "readme", "spec", "rules", "index"):   # hidden-1/brief.md -> hidden-1
        name = bp.parent.name
    name = name.removesuffix(".brief")
    if "--no-local-test" in extra:          # the local coverage test (report only) is on by default
        extra = [x for x in extra if x != "--no-local-test"]
    elif "--local-test" not in extra:
        extra = ["--local-test", *extra]
    return main([brief, "--openapi", openapi, "--slot", name, "--export", str(ROOT / "submission" / f"{name}.workflow.json"), *extra])


if __name__ == "__main__":
    sys.exit(entry(sys.argv[1:]))
