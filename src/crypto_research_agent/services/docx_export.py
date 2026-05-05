import time
from pathlib import Path

import requests

from ..config import CLOUDCONVERT_BASE_URL
from ..utils.logger import get_logger

logger = get_logger(__name__)


class DocxExporter:
    """Convert markdown to DOCX via CloudConvert."""

    def __init__(self, *, api_key: str, base_url: str = CLOUDCONVERT_BASE_URL):
        self._api_key = api_key
        self._base = base_url
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def convert_markdown_to_docx(self, input_path: Path | str) -> Path:
        in_path = Path(input_path)
        if not in_path.exists():
            raise FileNotFoundError(input_path)
        out_path = in_path.with_suffix(".docx")

        job = self._create_job()
        upload_task = next(t for t in job["tasks"] if t["name"] == "import-my-file")
        upload_url = upload_task["result"]["form"]["url"]
        upload_params = upload_task["result"]["form"]["parameters"]

        with in_path.open("rb") as fh:
            r = requests.post(upload_url, data=upload_params, files={"file": fh})
        if r.status_code not in (200, 201):
            raise RuntimeError(f"Upload failed: {r.text}")

        completed = self._wait_finished(job["id"])
        export_task = next(t for t in completed["tasks"] if t["name"] == "export-my-file")
        download_url = export_task["result"]["files"][0]["url"]
        self._download(download_url, out_path)
        logger.info("DOCX written to %s", out_path)
        return out_path

    def _create_job(self) -> dict:
        payload = {
            "tasks": {
                "import-my-file": {"operation": "import/upload"},
                "convert-my-file": {
                    "operation": "convert", "input": "import-my-file",
                    "output_format": "docx", "engine": "pandoc",
                },
                "export-my-file": {"operation": "export/url", "input": "convert-my-file"},
            }
        }
        r = requests.post(f"{self._base}/jobs", headers=self._headers, json=payload)
        r.raise_for_status()
        return r.json()["data"]

    def _wait_finished(self, job_id: str, *, timeout: int = 300) -> dict:
        deadline = time.time() + timeout
        while time.time() < deadline:
            r = requests.get(f"{self._base}/jobs/{job_id}", headers=self._headers)
            r.raise_for_status()
            data = r.json()["data"]
            if data["status"] == "finished":
                return data
            if data["status"] in ("error", "canceled"):
                raise RuntimeError(f"DOCX conversion {data['status']}")
            time.sleep(2)
        raise TimeoutError(f"DOCX conversion timed out after {timeout}s")

    def _download(self, url: str, out_path: Path) -> None:
        r = requests.get(url, stream=True)
        r.raise_for_status()
        with out_path.open("wb") as fh:
            for chunk in r.iter_content(chunk_size=8192):
                fh.write(chunk)
