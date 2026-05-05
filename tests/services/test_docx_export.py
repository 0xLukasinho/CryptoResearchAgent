import responses
from pathlib import Path

from crypto_research_agent.services.docx_export import DocxExporter


@responses.activate
def test_convert_markdown_to_docx_full_lifecycle(tmp_path):
    md = tmp_path / "article.md"
    md.write_text("# Test\nbody", encoding="utf-8")

    responses.add(
        responses.POST, "https://api.cloudconvert.com/v2/jobs", status=201,
        json={"data": {
            "id": "job-1",
            "tasks": [{
                "name": "import-my-file",
                "result": {"form": {"url": "https://upload.example.com",
                                     "parameters": {}}},
            }],
        }},
    )
    responses.add(
        responses.POST, "https://upload.example.com", status=201, body="",
    )
    responses.add(
        responses.GET, "https://api.cloudconvert.com/v2/jobs/job-1", status=200,
        json={"data": {
            "id": "job-1", "status": "finished",
            "tasks": [{
                "name": "export-my-file",
                "result": {"files": [{"url": "https://download.example.com/file.docx"}]},
            }],
        }},
    )
    responses.add(
        responses.GET, "https://download.example.com/file.docx", status=200,
        body=b"PK\x03\x04docx-bytes",
    )

    exp = DocxExporter(api_key="ck-test")
    out = exp.convert_markdown_to_docx(md)
    assert out == md.with_suffix(".docx")
    assert out.exists() and out.read_bytes().startswith(b"PK")
