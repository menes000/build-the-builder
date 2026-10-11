"""Submission entry point: python3 builder/build.py <brief file or folder> <tool openapi file> [extra builder options]

Builds one phone agent for one brief and writes:
  submission/<name>.workflow.json   the workflow as stored on Freya (freya.export_workflow)
  traces/<time>-<name>.txt/.jsonl   the run trace; the same lines go to stdout (tee them into traces/<name>.log)
<name> is the brief's file stem or folder name. The same brief can be built again; every run creates a new version
of the same agent slot. Extra options (for example `--test A`) are passed to builder.main unchanged.
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
    name = Path(brief).name if Path(brief).is_dir() else Path(brief).stem
    name = name.removesuffix(".brief")
    return main([brief, "--openapi", openapi, "--slot", name, "--export", str(ROOT / "submission" / f"{name}.workflow.json"), *extra])


if __name__ == "__main__":
    sys.exit(entry(sys.argv[1:]))
