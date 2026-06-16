"""Source mapping attribution tests for Lean scaffolding."""

import pytest


class TestPreambleSourceMappingAttribution:

    def test_def_line_attributed_to_space(self, agent, continuous_opt_spec):
        result = agent.scaffold(continuous_opt_spec)
        content_lines = result.content.split("\n")
        for mapping in result.source_mappings:
            line_idx = mapping.lean_line - 1
            if line_idx < len(content_lines) and "def OutputSpace" in content_lines[line_idx]:
                assert mapping.schema_field == "spaces[0]"
                return
        pytest.fail("No source mapping found for 'def OutputSpace' line")

    def test_no_generic_objective_preamble_for_def_lines(self, agent, continuous_opt_spec):
        result = agent.scaffold(continuous_opt_spec)
        content_lines = result.content.split("\n")
        for mapping in result.source_mappings:
            line_idx = mapping.lean_line - 1
            if line_idx < len(content_lines):
                line = content_lines[line_idx].strip()
                if line.startswith("def ") and mapping.schema_field == "objective.preamble":
                    pytest.fail(
                        f"def line attributed to 'objective.preamble': {line}"
                    )


# ---------------------------------------------------------------------------
# Source mapping attribution
# ---------------------------------------------------------------------------


class TestCR006SourceMappings:

    def test_domain_def_attributed_to_space(self, agent, continuous_opt_spec):
        result = agent.scaffold(continuous_opt_spec)
        content_lines = result.content.split("\n")
        found = False
        for mapping in result.source_mappings:
            line_idx = mapping.lean_line - 1
            if line_idx < len(content_lines) and "def " in content_lines[line_idx]:
                assert mapping.schema_field.startswith("spaces[")
                found = True
        assert found, "No source mapping found for any 'def ' line"

    def test_theorem_still_attributed_to_objective(self, agent, continuous_opt_spec):
        result = agent.scaffold(continuous_opt_spec)
        content_lines = result.content.split("\n")
        found = False
        for mapping in result.source_mappings:
            line_idx = mapping.lean_line - 1
            if line_idx < len(content_lines) and "theorem " in content_lines[line_idx]:
                assert mapping.schema_field == "objective"
                found = True
        assert found, "No source mapping found for 'theorem' line"

    def test_no_objective_preamble_for_def_or_lemma(self, agent, continuous_opt_spec):
        result = agent.scaffold(continuous_opt_spec)
        content_lines = result.content.split("\n")
        for mapping in result.source_mappings:
            line_idx = mapping.lean_line - 1
            if line_idx < len(content_lines):
                line = content_lines[line_idx].strip()
                if line.startswith("def ") or line.startswith("lemma "):
                    assert mapping.schema_field != "objective.preamble"


# ---------------------------------------------------------------------------
# Convexity lemma stays in preamble
# ---------------------------------------------------------------------------


class TestConvexityLemmaInPreamble:

    def test_convexity_lemma_in_preamble_not_theorem_block(self, agent, continuous_opt_spec):
        result = agent.scaffold(continuous_opt_spec)
        content_lines = result.content.split("\n")
        found_lemma = False
        for mapping in result.source_mappings:
            line_idx = mapping.lean_line - 1
            if line_idx < len(content_lines):
                line = content_lines[line_idx].strip()
                if line.startswith("lemma "):
                    found_lemma = True
                    assert mapping.schema_field != "objective"
                    assert "variables" in mapping.schema_field or "bounds" in mapping.schema_field or "preamble" in mapping.schema_field
        assert found_lemma
