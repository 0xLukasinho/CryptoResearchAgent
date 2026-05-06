import json
import re
from pathlib import Path

import docx as docx_lib

from .style_card import StyleCard
from ..utils.logger import get_logger
from ..utils.token_utils import truncate_to_token_limit

logger = get_logger(__name__)


JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


class StyleLearner:
    def __init__(self, backend, *, model: str,
                 samples_dir: Path, instructions_file: Path):
        self._backend = backend
        self._model = model
        self._samples_dir = Path(samples_dir)
        self._instructions_file = Path(instructions_file)

    def get_raw_materials(self) -> dict:
        samples = []
        if self._samples_dir.exists():
            for f in self._samples_dir.iterdir():
                if not f.is_file() or f.name == "README.txt":
                    continue
                if f.suffix.lower() == ".txt":
                    samples.append({"filename": f.name,
                                     "content": f.read_text(encoding="utf-8")})
                elif f.suffix.lower() == ".docx":
                    doc = docx_lib.Document(str(f))
                    samples.append({"filename": f.name,
                                     "content": "\n".join(p.text for p in doc.paragraphs)})
        instructions = (
            self._instructions_file.read_text(encoding="utf-8")
            if self._instructions_file.exists() else ""
        )
        return {"samples": samples, "instructions": instructions}

    def generate_style_card(self, materials: dict) -> StyleCard:
        samples = materials.get("samples", [])
        instructions = materials.get("instructions") or ""
        if not samples and not instructions.strip():
            logger.warning(
                "No writing samples or instructions found in %s; using fallback "
                "style card. Add .txt/.docx files to that directory to personalize "
                "the writing voice.", self._samples_dir,
            )
            return StyleCard.fallback()

        samples_text = ""
        for s in samples:
            content = truncate_to_token_limit(s.get("content", ""), self._model, 3000)
            samples_text += f"\n--- {s.get('filename', 'sample')} ---\n{content}\n"
        instr_block = f"\nExplicit writing instructions from author:\n{instructions}" if instructions else ""

        prompt = f"""Analyze these writing samples and produce a style card capturing the author's voice precisely.

{samples_text}{instr_block}

Return JSON with these keys:
- tone (string)
- sentence_patterns (string)
- vocabulary: {{ preferred: list, avoided: list }}
- paragraph_structure (string)
- section_openings (string)
- transitions (list of strings)
- example_excerpts (list of 3-5 verbatim excerpts)

Focus on what makes this voice distinctive and reproducible."""

        response = self._backend.complete(
            prompt=prompt, model=self._model,
            system_prompt="Extract precise, actionable style characteristics. Respond with valid JSON only.",
        )
        return self._parse(response.text)

    @staticmethod
    def _parse(text: str) -> StyleCard:
        try:
            return StyleCard.from_dict(json.loads(text))
        except json.JSONDecodeError:
            pass
        match = JSON_OBJECT_RE.search(text)
        if match:
            try:
                return StyleCard.from_dict(json.loads(match.group()))
            except json.JSONDecodeError:
                pass
        logger.warning("Failed to parse style card; using fallback")
        return StyleCard.fallback()
