from __future__ import annotations

from pydantic import BaseModel, Field

_DECL_KEYWORDS = ("variable ", "def ", "lemma ", "theorem ")


class LeanDeclaration(BaseModel):
    """A single Lean 4 declaration produced by a mapper.

    Intermediate representation used inside the scaffolding agent for
    structured deduplication and categorized emission."""
    kind: str  # "import", "variable", "def", "lemma", "theorem", "hypothesis"
    name: str  # identifier name (for deduplication)
    content: str  # full Lean 4 text (may be multi-line)
    schema_field: str = ""  # source mapping attribution


def _extract_name(stripped: str) -> str:
    """Extract the identifier name from a declaration's first line."""
    parts = stripped.split()
    if len(parts) < 2:
        return "unknown"
    keyword = parts[0]
    if keyword == "variable":
        if "(" in stripped:
            after_paren = stripped.split("(")[1].split(":")[0].strip().rstrip(")")
            tokens = after_paren.split()
            return tokens[0] if tokens else "unknown"
        return "unknown"
    return parts[1].split("(")[0].split(":")[0] or "unknown"


def parse_declarations(text: str, schema_field: str = "") -> list[LeanDeclaration]:
    """Parse mapper output string into structured declarations.

    Groups multi-line declarations: a block starts at a declaration
    keyword (variable, def, lemma, theorem) and continues until the
    next declaration keyword or end of input."""
    blocks: list[tuple[str, list[str]]] = []
    current_keyword: str | None = None
    current_lines: list[str] = []

    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            if current_lines:
                current_lines.append(line)
            continue

        starts_new = any(stripped.startswith(kw) for kw in _DECL_KEYWORDS)

        if starts_new:
            if current_keyword is not None:
                blocks.append((current_keyword, current_lines))
            for kw in _DECL_KEYWORDS:
                if stripped.startswith(kw):
                    current_keyword = kw.strip()
                    break
            current_lines = [line]
        elif current_keyword is not None:
            current_lines.append(line)
        else:
            blocks.append(("other", [line]))

    if current_keyword is not None:
        blocks.append((current_keyword, current_lines))

    decls: list[LeanDeclaration] = []
    for keyword, lines in blocks:
        content = "\n".join(lines).rstrip()
        first_stripped = lines[0].strip()
        if keyword == "other":
            name = first_stripped[:20]
        else:
            name = _extract_name(first_stripped)
        decls.append(LeanDeclaration(
            kind=keyword, name=name, content=content, schema_field=schema_field,
        ))
    return decls


class LeanGoal(BaseModel):
    """Represents a single sorry-marked goal in the scaffolded Lean source."""
    goal_id: str
    theorem_name: str
    goal_state: str
    line_number: int
    sorry_offset: int


class SourceMappingEntry(BaseModel):
    """Records which schema field produced a given Lean line."""
    lean_line: int
    schema_field: str
    narrative_start: int = -1
    narrative_end: int = -1


class LeanSource(BaseModel):
    """Output of the Lean Scaffolding Agent."""
    content: str
    imports: list[str]
    goals: list[LeanGoal] = Field(default_factory=list)
    mathlib_modules: list[str] = Field(default_factory=list)
    source_mappings: list[SourceMappingEntry] = Field(default_factory=list)
