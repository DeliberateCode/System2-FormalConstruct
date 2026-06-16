"""Unit tests for formalconstruct.prompts -- template rendering."""

import pytest

from formalconstruct.prompts.loader import (
    render_error_feedback,
    render_tactic_generation,
)


class TestRenderErrorFeedback:
    def test_error_feedback_basic(self):
        result = render_error_feedback(
            goal_state="x : Real\n⊢ x > 0",
            error_message="type mismatch\n  expected: x > 0",
        )
        assert "x : Real" in result
        assert "⊢ x > 0" in result
        assert "type mismatch" in result
        assert "expected: x > 0" in result
        assert "previous tactic failed" in result.lower()

    def test_error_feedback_with_type_mismatch(self):
        result = render_error_feedback(
            goal_state="⊢ 1 + 1 = 2",
            error_message="type mismatch",
            type_mismatch_details="expected Nat, got Int",
        )
        assert "Type mismatch details:" in result
        assert "expected Nat, got Int" in result

    def test_error_feedback_without_type_mismatch(self):
        result = render_error_feedback(
            goal_state="⊢ True",
            error_message="unknown identifier 'foo'",
            type_mismatch_details=None,
        )
        assert "Type mismatch details:" not in result
        assert "unknown identifier 'foo'" in result

    def test_error_feedback_special_chars(self):
        result = render_error_feedback(
            goal_state="f : ℝ → ℝ\nh_convex : ConvexOn ℝ (Set.Ici 0) f\n⊢ ∃ x, IsMinOn f (Set.Ici 0) x",
            error_message="unknown identifier '⊢'",
        )
        assert "ℝ" in result
        assert "ConvexOn" in result
        assert "∃ x" in result
        assert "Set.Ici" in result

    def test_error_feedback_ends_with_instruction(self):
        result = render_error_feedback(
            goal_state="⊢ True",
            error_message="error",
        )
        assert "next tactic" in result.lower()


class TestRenderTacticGeneration:
    def test_tactic_generation_basic(self):
        result = render_tactic_generation(
            theorem_signature="theorem foo (x : ℝ) : x = x",
            goal_state="⊢ x = x",
            hypotheses=["x : ℝ"],
        )
        assert "theorem foo" in result
        assert "⊢ x = x" in result
        assert "x : ℝ" in result
        assert "tactic" in result.lower()

    def test_tactic_generation_with_domain_hints(self):
        result = render_tactic_generation(
            theorem_signature="theorem opt_exists : ...",
            goal_state="⊢ ∃ x, IsMinOn f S x",
            hypotheses=["h_convex : StrictConvexOn ℝ S f", "h_compact : IsCompact S"],
            domain_hints=["Use IsCompact.exists_isMinOn", "Apply StrictConvexOn.unique"],
        )
        assert "Domain hints:" in result
        assert "IsCompact.exists_isMinOn" in result
        assert "StrictConvexOn.unique" in result

    def test_tactic_generation_without_domain_hints(self):
        result = render_tactic_generation(
            theorem_signature="theorem bar : True",
            goal_state="⊢ True",
            hypotheses=[],
            domain_hints=None,
        )
        assert "Domain hints:" not in result

    def test_tactic_generation_empty_hypotheses(self):
        result = render_tactic_generation(
            theorem_signature="theorem trivial_thm : True",
            goal_state="⊢ True",
            hypotheses=[],
        )
        assert "Available hypotheses:" in result
        assert "trivial_thm" in result

    def test_tactic_generation_multiple_hypotheses(self):
        hypotheses = [
            "h1 : x > 0",
            "h2 : y > 0",
            "h3 : x + y > 0",
        ]
        result = render_tactic_generation(
            theorem_signature="theorem sum_pos : ...",
            goal_state="⊢ x + y > 0",
            hypotheses=hypotheses,
        )
        for h in hypotheses:
            assert h in result

    def test_tactic_generation_empty_domain_hints_list(self):
        result = render_tactic_generation(
            theorem_signature="theorem t : True",
            goal_state="⊢ True",
            hypotheses=[],
            domain_hints=[],
        )
        # An empty list is falsy, so domain hints section should be omitted
        assert "Domain hints:" not in result

    def test_error_feedback_strict_undefined(self):
        """StrictUndefined is configured; passing unexpected variables should work
        only if they are defined in the template context."""
        # This just verifies that missing required args raise TypeError
        # (from the Python function signature, not Jinja2)
        with pytest.raises(TypeError):
            render_error_feedback(goal_state="x")  # missing error_message
