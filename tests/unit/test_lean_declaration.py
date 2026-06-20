"""Tests for LeanDeclaration model and parse_declarations utility."""

from __future__ import annotations

from formalconstruct.schemas.lean_source import LeanDeclaration, parse_declarations


class TestLeanDeclarationModel:
    def test_variable_declaration(self):
        decl = LeanDeclaration(
            kind="variable", name="x", content="variable (x : ℝ)",
        )
        assert decl.kind == "variable"
        assert decl.name == "x"
        assert decl.content == "variable (x : ℝ)"
        assert decl.schema_field == ""

    def test_schema_field_attribution(self):
        decl = LeanDeclaration(
            kind="def", name="S", content="def S : Set ℝ := Set.univ",
            schema_field="spaces[0]",
        )
        assert decl.schema_field == "spaces[0]"

    def test_dedup_key(self):
        a = LeanDeclaration(kind="variable", name="x", content="variable (x : ℝ)")
        b = LeanDeclaration(kind="variable", name="x", content="variable (x : ℤ)")
        assert (a.kind, a.name) == (b.kind, b.name)

    def test_different_names_not_equal(self):
        a = LeanDeclaration(kind="variable", name="x", content="variable (x : ℝ)")
        b = LeanDeclaration(kind="variable", name="y", content="variable (y : ℝ)")
        assert (a.kind, a.name) != (b.kind, b.name)


class TestParseDeclarations:
    def test_empty_input(self):
        assert parse_declarations("") == []

    def test_blank_lines_skipped(self):
        assert parse_declarations("\n\n") == []

    def test_variable_declaration(self):
        result = parse_declarations("variable (x : ℝ)")
        assert len(result) == 1
        assert result[0].kind == "variable"
        assert result[0].name == "x"
        assert result[0].content == "variable (x : ℝ)"

    def test_variable_with_hypothesis(self):
        text = (
            "variable (f : ℝ → ℝ)\n"
            "variable (h_f_convex : ConvexOn ℝ S f)"
        )
        result = parse_declarations(text, schema_field="functions[0]")
        assert len(result) == 2
        assert result[0].kind == "variable"
        assert result[0].name == "f"
        assert result[1].kind == "variable"
        assert result[1].name == "h_f_convex"
        assert all(d.schema_field == "functions[0]" for d in result)

    def test_def_declaration(self):
        result = parse_declarations("def OutputSpace : Set ℝ := Set.Ici 0")
        assert len(result) == 1
        assert result[0].kind == "def"
        assert result[0].name == "OutputSpace"

    def test_lemma_declaration(self):
        result = parse_declarations("lemma convex_s : Convex ℝ S :=")
        assert len(result) == 1
        assert result[0].kind == "lemma"
        assert result[0].name == "convex_s"

    def test_theorem_declaration(self):
        result = parse_declarations("theorem minimize_x_strictconvexon :")
        assert len(result) == 1
        assert result[0].kind == "theorem"
        assert result[0].name == "minimize_x_strictconvexon"

    def test_other_declaration(self):
        result = parse_declarations("  convex_Ici 0")
        assert len(result) == 1
        assert result[0].kind == "other"
        assert result[0].name == "convex_Ici 0"

    def test_multiline_mapper_output(self):
        text = (
            "variable (CostCapital : ℝ → ℝ)\n"
            "variable (h_CostCapital_strict_convex : StrictConvexOn ℝ OutputSpace CostCapital)"
        )
        result = parse_declarations(text)
        assert len(result) == 2
        assert result[0].name == "CostCapital"
        assert result[1].name == "h_CostCapital_strict_convex"

    def test_linear_property_multi_hypothesis(self):
        text = (
            "variable (f : ℝ → ℝ)\n"
            "variable (h_f_convex : ConvexOn ℝ S f)\n"
            "variable (h_f_concave : ConcaveOn ℝ S f)"
        )
        result = parse_declarations(text)
        assert len(result) == 3
        names = [d.name for d in result]
        assert names == ["f", "h_f_convex", "h_f_concave"]

    def test_dedup_by_kind_name(self):
        text = (
            "variable (f : ℝ → ℝ)\n"
            "variable (h_f_convex : ConvexOn ℝ S f)"
        )
        decls = parse_declarations(text)
        seen: set[tuple[str, str]] = set()
        deduped = []
        for decl in decls:
            key = (decl.kind, decl.name)
            if key not in seen:
                seen.add(key)
                deduped.append(decl)
        assert len(deduped) == 2

    def test_preserves_leading_whitespace_in_content(self):
        result = parse_declarations("  convex_Ici 0")
        assert result[0].content == "  convex_Ici 0"
