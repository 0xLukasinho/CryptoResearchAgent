from dataclasses import asdict, dataclass, field


@dataclass
class Vocabulary:
    preferred: list[str] = field(default_factory=list)
    avoided: list[str] = field(default_factory=list)


@dataclass
class StyleCard:
    tone: str
    sentence_patterns: str
    vocabulary: Vocabulary
    paragraph_structure: str
    section_openings: str
    transitions: list[str]
    example_excerpts: list[str]

    def format_for_prompt(self) -> str:
        excerpts = "".join(f"\n> {x}\n" for x in self.example_excerpts)
        preferred = ", ".join(self.vocabulary.preferred) or "none specified"
        avoided = ", ".join(self.vocabulary.avoided) or "none specified"
        transitions = ", ".join(f'"{t}"' for t in self.transitions) or "none specified"
        return f"""## Writing Style Guide

**Tone:** {self.tone}
**Sentence patterns:** {self.sentence_patterns}
**Paragraph structure:** {self.paragraph_structure}
**Section openings:** {self.section_openings}
**Preferred transitions:** {transitions}
**Vocabulary to use:** {preferred}
**Vocabulary to avoid:** {avoided}

## Example Excerpts from the Author's Writing
{excerpts}
Match this voice precisely. Every section you write — including rewrites — must sound like these excerpts."""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "StyleCard":
        v = d.get("vocabulary") or {}
        return cls(
            tone=d.get("tone", ""),
            sentence_patterns=d.get("sentence_patterns", ""),
            vocabulary=Vocabulary(
                preferred=v.get("preferred", []) if isinstance(v, dict) else [],
                avoided=v.get("avoided", []) if isinstance(v, dict) else [],
            ),
            paragraph_structure=d.get("paragraph_structure", ""),
            section_openings=d.get("section_openings", ""),
            transitions=d.get("transitions", []) or [],
            example_excerpts=d.get("example_excerpts", []) or [],
        )

    @classmethod
    def fallback(cls) -> "StyleCard":
        return cls(
            tone="analytical and informative",
            sentence_patterns="clear and direct",
            vocabulary=Vocabulary(),
            paragraph_structure="structured with clear points",
            section_openings="direct assertions",
            transitions=[],
            example_excerpts=[],
        )
