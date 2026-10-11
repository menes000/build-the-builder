"""Final case input: a zip or folder of mixed documents, the tool API found in it, and every tool pointed at the team's mock."""
import json
import zipfile
from pathlib import Path

from builder.build import unzip_case
from builder.extract.extractor import _brief_text
from builder.extract.tools import find_openapi, is_openapi, parse_openapi
from builder.main import expand_briefs

KIT_API = Path(__file__).resolve().parent.parent / "kit" / "tools" / "openapi.json"


def _case(tmp_path: Path) -> Path:
    case = tmp_path / "Bank-Case"
    (case / "docs").mkdir(parents=True)
    (case / "BRIEF.md").write_text("# Brief\nrules")
    (case / "docs" / "service-contract.json").write_text(KIT_API.read_text())
    (case / "docs" / "customers.json").write_text(json.dumps([{"id": "c1"}]))
    return case


def test_openapi_is_found_by_content_not_name(tmp_path):
    case = _case(tmp_path)
    assert is_openapi(case / "docs" / "service-contract.json")
    assert not is_openapi(case / "docs" / "customers.json")
    assert find_openapi([case]) == case / "docs" / "service-contract.json"


def test_contract_is_not_brief_text_but_customers_are(tmp_path):
    files = [Path(f).name for f in expand_briefs([str(_case(tmp_path))])]
    assert "service-contract.json" not in files
    assert "BRIEF.md" in files and "customers.json" in files


def test_mock_url_replaces_the_servers_address():
    tools = parse_openapi(KIT_API, base_url="https://team-mock.example.workers.dev/")
    assert tools and all(t.url.startswith("https://team-mock.example.workers.dev/") for t in tools)
    default = parse_openapi(KIT_API)
    # same paths (server prefix included), only the host changes
    from urllib.parse import urlparse
    assert [urlparse(t.url).path for t in default] == [urlparse(t.url).path for t in tools]
    again = parse_openapi(KIT_API, base_url="https://team-mock.example.workers.dev" + urlparse(default[0].url).path.rsplit("/", 1)[0])
    assert [t.url for t in again] == [t.url for t in tools]      # a mock URL that already ends with the prefix is not doubled


def test_zip_with_one_top_folder_unpacks_to_that_folder(tmp_path, monkeypatch):
    import builder.build as b
    monkeypatch.setattr(b, "ROOT", tmp_path)
    case = _case(tmp_path / "src")
    zp = tmp_path / "Bank-Case.zip"
    with zipfile.ZipFile(zp, "w") as z:
        for f in case.rglob("*"):
            if f.is_file():
                z.write(f, f.relative_to(case.parent))
        z.writestr("__MACOSX/._BRIEF.md", "junk")
    folder = unzip_case(zp)
    assert folder.name == "Bank-Case" and (folder / "BRIEF.md").exists()
    assert find_openapi([folder]) is not None


def test_docx_and_xlsx_become_text_without_pandoc(tmp_path):
    docx = tmp_path / "memo.docx"
    with zipfile.ZipFile(docx, "w") as z:
        z.writestr("word/document.xml", '<w:document><w:body><w:p><w:r><w:t>Kural bir</w:t></w:r></w:p>'
                                        '<w:p><w:r><w:t>Rule &amp; two</w:t></w:r></w:p></w:body></w:document>')
    import openpyxl
    wb = openpyxl.Workbook()
    wb.active.title = "customers"
    wb.active.append(["id", "name"])
    wb.active.append(["c1", "Ayşe"])
    xlsx = tmp_path / "customers.xlsx"
    wb.save(xlsx)
    text = _brief_text([str(docx), str(xlsx)])
    assert "Kural bir" in text and "Rule & two" in text
    assert "sheet: customers" in text and "c1 | Ayşe" in text
