"""Submission entry point: python3 builder/build.py <case folder, zip or brief file> <mock_url | tool openapi file> [extra builder options]

Final: build.py {case_folder} {mock_url}. Every tool of the agent calls the team's mock; the tool API is the OpenAPI file in the
case folder, or is written from the service contract when the case has none. Practice: build.py <brief> <openapi.json>.

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


def unzip_case(zip_path: Path) -> Path:
    """A case delivered as one zip: unpack it under out/cases/<name>/ and build from that folder."""
    import zipfile
    dest = ROOT / "out" / "cases" / zip_path.stem
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as z:
        for m in z.infolist():
            target = (dest / m.filename).resolve()
            if not str(target).startswith(str(dest.resolve())) or "__MACOSX" in m.filename:
                continue                                # no paths outside the folder, no macOS resource forks
            z.extract(m, dest)
    inner = [p for p in dest.iterdir() if not p.name.startswith(".") and p.name != "__MACOSX"]
    return inner[0] if len(inner) == 1 and inner[0].is_dir() else dest   # a zip with one top folder: that folder


def entry(argv: list[str]) -> int:
    if len(argv) < 2 or argv[0].startswith("-"):
        print(__doc__)
        return 2
    brief, second, extra = argv[0], argv[1], argv[2:]
    bp = Path(brief)
    if bp.is_file() and bp.suffix.lower() == ".zip":
        bp = unzip_case(bp)
        brief = str(bp)
    name = bp.name if bp.is_dir() else bp.stem
    if not bp.is_dir() and name.lower() in ("brief", "readme", "spec", "rules", "index"):   # hidden-1/brief.md -> hidden-1
        name = bp.parent.name
    name = name.removesuffix(".brief")
    # second argument: the team's mock (final: build.py {case_folder} {mock_url}) or a tool API file (practice briefs)
    mock = second.startswith(("http://", "https://"))
    api_args = ["--mock-url", second] if mock else ["--openapi", second]
    if "--no-local-test" in extra:          # the local coverage test (report only) is on by default
        extra = [x for x in extra if x != "--no-local-test"]
    elif "--local-test" not in extra and not mock:   # the local test's fake bank speaks the practice API, not the team's mock
        extra = ["--local-test", *extra]
    return main([brief, *api_args, "--slot", name, "--export", str(ROOT / "submission" / f"{name}.workflow.json"), *extra])


if __name__ == "__main__":
    sys.exit(entry(sys.argv[1:]))
