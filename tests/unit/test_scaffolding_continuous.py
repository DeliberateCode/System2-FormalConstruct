"""Continuous optimization scaffolding tests."""

from __future__ import annotations

import re

import pytest

from formalconstruct.agents.lean_scaffolding import LeanScaffoldingAgent, _find_theorem_name
from formalconstruct.core.exceptions import UnknownDomainError
from formalconstruct.schemas.problem_spec import (
    BaseType,
    Function,
    FunctionProperty,
    Objective,
    ObjectiveDirection,
    ProblemDomain,
    ProblemSpec,
    Space,
    Variable,
    VariableBounds,
    VariableClassification,
)


class TestContinuousOptScaffolding:
    def test_sorry_in_content(self, agent, continuous_opt_spec):
        result = agent.scaffold(continuous_opt_spec)
        assert "sorry" in result.content

    def test_imports_present(self, agent, continuous_opt_spec):
        result = agent.scaffold(continuous_opt_spec)
        assert "Mathlib" in result.imports

    def test_mathlib_modules(self, agent, continuous_opt_spec):
        result = agent.scaffold(continuous_opt_spec)
        assert all("Mathlib" in m for m in result.mathlib_modules)
        assert len(result.mathlib_modules) >= 1

    def test_goal_extraction(self, agent, continuous_opt_spec):
        result = agent.scaffold(continuous_opt_spec)
        assert len(result.goals) >= 1
        goal = result.goals[0]
        assert goal.goal_id == "goal_0"
        assert goal.theorem_name != "unknown"
        assert goal.line_number > 0
        assert goal.sorry_offset >= 0

    def test_theorem_signature(self, agent, continuous_opt_spec):
        result = agent.scaffold(continuous_opt_spec)
        assert "theorem" in result.content
        assert "StrictConvexOn" in result.content

    def test_space_definition(self, agent, continuous_opt_spec):
        result = agent.scaffold(continuous_opt_spec)
        assert "def OutputSpace" in result.content

    def test_variable_declaration(self, agent, continuous_opt_spec):
        result = agent.scaffold(continuous_opt_spec)
        assert "variable (CostCapital : ℝ → ℝ)" in result.content

    def test_bounds_as_domain_set(self, agent, continuous_opt_spec):
        result = agent.scaffold(continuous_opt_spec)
        assert "Set.Ici 0" in result.content

    def test_strict_bounds(self, agent):
        spec = ProblemSpec(
            problem_domain=ProblemDomain.CONTINUOUS_OPTIMIZATION,
            spaces=[Space(name="S", base_type=BaseType.REAL)],
            variables=[
                Variable(
                    symbol="y",
                    classification=VariableClassification.ENDOGENOUS,
                    space_reference="S",
                    bounds=VariableBounds(lower_bound="0", strict_inequality=True),
                )
            ],
            functions=[
                Function(symbol="f", domain=["S"], codomain="Real", properties=[FunctionProperty.CONVEX])
            ],
            objective=Objective(direction=ObjectiveDirection.MINIMIZE, expression_latex="f(y)"),
        )
        result = agent.scaffold(spec)
        assert "Set.Ioi 0" in result.content

    def test_function_hypotheses(self, agent, continuous_opt_spec):
        result = agent.scaffold(continuous_opt_spec)
        assert "StrictConvexOn" in result.content
        assert "ConvexOn" in result.content


class TestErrorCases:
    def test_unknown_domain_raises(self, registry):
        agent = LeanScaffoldingAgent(registry)
        spec = ProblemSpec(
            problem_domain=ProblemDomain.CONTINUOUS_OPTIMIZATION,
            spaces=[Space(name="S", base_type=BaseType.REAL)],
            variables=[
                Variable(
                    symbol="x",
                    classification=VariableClassification.ENDOGENOUS,
                    space_reference="S",
                )
            ],
            functions=[
                Function(
                    symbol="f",
                    domain=["S"],
                    codomain="Real",
                    properties=[FunctionProperty.CONTINUOUS],
                )
            ],
            objective=Objective(
                direction=ObjectiveDirection.MINIMIZE,
                expression_latex="f(x)",
            ),
        )
        spec.__dict__["problem_domain"] = type(
            "FakeDomain", (), {"value": "nonexistent"}
        )()
        with pytest.raises(UnknownDomainError):
            agent.scaffold(spec)


class TestSetContextCalled:

    def test_set_context_called_on_continuous_opt_mapper(self, registry):
        from unittest.mock import patch

        spec = ProblemSpec(
            problem_domain=ProblemDomain.CONTINUOUS_OPTIMIZATION,
            spaces=[Space(name="S", base_type=BaseType.REAL)],
            variables=[
                Variable(
                    symbol="x",
                    classification=VariableClassification.ENDOGENOUS,
                    space_reference="S",
                )
            ],
            functions=[
                Function(
                    symbol="f",
                    domain=["S"],
                    codomain="Real",
                    properties=[FunctionProperty.CONVEX],
                )
            ],
            objective=Objective(
                direction=ObjectiveDirection.MINIMIZE,
                expression_latex="f(x)",
            ),
        )
        agent = LeanScaffoldingAgent(registry)
        mapper = registry.get_mapper("continuous_optimization")
        with patch.object(mapper, "set_context", wraps=mapper.set_context) as spy:
            with patch.object(registry, "get_mapper", return_value=mapper):
                agent.scaffold(spec)
                spy.assert_called_once_with(spec)

    def test_set_context_not_called_when_absent(self, registry):
        from unittest.mock import MagicMock, patch

        spec = ProblemSpec(
            problem_domain=ProblemDomain.CONTINUOUS_OPTIMIZATION,
            spaces=[Space(name="S", base_type=BaseType.REAL)],
            variables=[
                Variable(
                    symbol="x",
                    classification=VariableClassification.ENDOGENOUS,
                    space_reference="S",
                )
            ],
            functions=[
                Function(
                    symbol="f",
                    domain=["S"],
                    codomain="Real",
                    properties=[FunctionProperty.CONVEX],
                )
            ],
            objective=Objective(
                direction=ObjectiveDirection.MINIMIZE,
                expression_latex="f(x)",
            ),
        )
        real_mapper = registry.get_mapper("continuous_optimization")
        mock_mapper = MagicMock(spec=["domain_name", "required_imports", "map_space",
                                      "map_variable", "map_function", "map_objective",
                                      "map_bounds"])
        mock_mapper.required_imports.return_value = real_mapper.required_imports(spec)
        mock_mapper.map_space.return_value = ""
        mock_mapper.map_variable.return_value = ""
        mock_mapper.map_function.return_value = ""
        mock_mapper.map_objective.return_value = "theorem t : True := by\n  sorry"

        agent = LeanScaffoldingAgent(registry)
        with patch.object(registry, "get_mapper", return_value=mock_mapper):
            result = agent.scaffold(spec)
            assert "sorry" in result.content


class TestFindTheoremName:
    def test_finds_theorem(self):
        content = "import X\n\ntheorem foo :\n  True := by\n  sorry\n"
        assert _find_theorem_name(content, 5) == "foo"

    def test_finds_lemma(self):
        content = "lemma bar :\n  True := by\n  sorry\n"
        assert _find_theorem_name(content, 3) == "bar"

    def test_returns_unknown_when_absent(self):
        content = "import X\n  sorry\n"
        assert _find_theorem_name(content, 2) == "unknown"


# ---------------------------------------------------------------------------
# REAL_N full scaffolding pipeline integration test
# ---------------------------------------------------------------------------


class TestRealNPipelineIntegration:

    def test_real_n_space_scaffolds_with_dimension_variable(self, agent):
        spec = ProblemSpec(
            problem_domain=ProblemDomain.CONTINUOUS_OPTIMIZATION,
            spaces=[Space(name="PortfolioSpace", base_type=BaseType.REAL_N)],
            variables=[
                Variable(
                    symbol="w",
                    classification=VariableClassification.ENDOGENOUS,
                    space_reference="PortfolioSpace",
                )
            ],
            functions=[
                Function(
                    symbol="RiskCost",
                    domain=["PortfolioSpace"],
                    codomain="Real",
                    properties=[FunctionProperty.CONVEX],
                )
            ],
            objective=Objective(
                direction=ObjectiveDirection.MINIMIZE,
                expression_latex="RiskCost(w)",
            ),
        )
        result = agent.scaffold(spec)
        assert "EuclideanSpace" in result.content
        assert "ℝ → ℝ" not in result.content
        assert "variable" in result.content and "n" in result.content
        has_dim_decl = bool(re.search(r"variable\s*\([^)]*\bn\b", result.content))
        assert has_dim_decl
        assert "sorry" in result.content


# ---------------------------------------------------------------------------
# REAL_N Full Scaffold Contract Tests
# ---------------------------------------------------------------------------


class TestF19RealNFullScaffold:

    def test_real_n_full_scaffold_concrete_dimension(self, agent):
        spec = ProblemSpec(
            problem_domain=ProblemDomain.CONTINUOUS_OPTIMIZATION,
            spaces=[Space(name="PortfolioSpace", base_type=BaseType.REAL_N, dimension=3)],
            variables=[
                Variable(
                    symbol="w",
                    classification=VariableClassification.ENDOGENOUS,
                    space_reference="PortfolioSpace",
                )
            ],
            functions=[
                Function(
                    symbol="RiskCost",
                    domain=["PortfolioSpace"],
                    codomain="Real",
                    properties=[FunctionProperty.CONVEX],
                )
            ],
            objective=Objective(
                direction=ObjectiveDirection.MINIMIZE,
                expression_latex="RiskCost(w)",
            ),
        )
        result = agent.scaffold(spec)
        assert "Fin 3" in result.content
        assert "variable (n : ℕ)" not in result.content
        assert "EuclideanSpace" in result.content
        assert "sorry" in result.content

    def test_real_n_full_scaffold_generic_dimension(self, agent):
        spec = ProblemSpec(
            problem_domain=ProblemDomain.CONTINUOUS_OPTIMIZATION,
            spaces=[Space(name="PortfolioSpace", base_type=BaseType.REAL_N)],
            variables=[
                Variable(
                    symbol="w",
                    classification=VariableClassification.ENDOGENOUS,
                    space_reference="PortfolioSpace",
                )
            ],
            functions=[
                Function(
                    symbol="RiskCost",
                    domain=["PortfolioSpace"],
                    codomain="Real",
                    properties=[FunctionProperty.CONVEX],
                )
            ],
            objective=Objective(
                direction=ObjectiveDirection.MINIMIZE,
                expression_latex="RiskCost(w)",
            ),
        )
        result = agent.scaffold(spec)
        assert "variable (n : ℕ)" in result.content
        assert "EuclideanSpace" in result.content
        assert "Fin n" in result.content
        assert "sorry" in result.content

    def test_real_scaffold_no_dimension_variable(self, agent):
        spec = ProblemSpec(
            problem_domain=ProblemDomain.CONTINUOUS_OPTIMIZATION,
            spaces=[Space(name="OutputSpace", base_type=BaseType.REAL)],
            variables=[
                Variable(
                    symbol="x",
                    classification=VariableClassification.ENDOGENOUS,
                    space_reference="OutputSpace",
                    bounds=VariableBounds(lower_bound="0", strict_inequality=False),
                )
            ],
            functions=[
                Function(
                    symbol="CostCapital",
                    domain=["OutputSpace"],
                    codomain="Real",
                    properties=[FunctionProperty.STRICT_CONVEX],
                )
            ],
            objective=Objective(
                direction=ObjectiveDirection.MINIMIZE,
                expression_latex="CostCapital(x)",
            ),
        )
        result = agent.scaffold(spec)
        assert "variable (n : ℕ)" not in result.content
        assert "EuclideanSpace" not in result.content
        assert "sorry" in result.content


# ---------------------------------------------------------------------------
# NonnegReal/PosReal type consistency contract tests
# ---------------------------------------------------------------------------


class TestNonnegRealTypeConsistency:

    def test_nonneg_real_function_and_domain_share_type(self, agent):
        spec = ProblemSpec(
            problem_domain=ProblemDomain.CONTINUOUS_OPTIMIZATION,
            spaces=[Space(name="S", base_type=BaseType.NONNEG_REAL)],
            variables=[
                Variable(
                    symbol="x",
                    classification=VariableClassification.ENDOGENOUS,
                    space_reference="S",
                    bounds=VariableBounds(lower_bound="0", strict_inequality=False),
                )
            ],
            functions=[
                Function(
                    symbol="f",
                    domain=["S"],
                    codomain="Real",
                    properties=[FunctionProperty.STRICT_CONVEX],
                ),
            ],
            objective=Objective(
                direction=ObjectiveDirection.MINIMIZE,
                expression_latex="f(x)",
            ),
        )
        result = agent.scaffold(spec)
        content = result.content
        assert "ℝ → ℝ" in content
        assert "NNReal" not in content
        assert "Set ℝ" in content
        assert "StrictConvexOn ℝ" in content

    def test_pos_real_function_and_domain_share_type(self, agent):
        spec = ProblemSpec(
            problem_domain=ProblemDomain.CONTINUOUS_OPTIMIZATION,
            spaces=[Space(name="S", base_type=BaseType.POS_REAL)],
            variables=[
                Variable(
                    symbol="x",
                    classification=VariableClassification.ENDOGENOUS,
                    space_reference="S",
                    bounds=VariableBounds(lower_bound="0", strict_inequality=True),
                )
            ],
            functions=[
                Function(
                    symbol="f",
                    domain=["S"],
                    codomain="Real",
                    properties=[FunctionProperty.STRICT_CONVEX],
                ),
            ],
            objective=Objective(
                direction=ObjectiveDirection.MINIMIZE,
                expression_latex="f(x)",
            ),
        )
        result = agent.scaffold(spec)
        content = result.content
        assert "ℝ → ℝ" in content
        assert "NNReal" not in content
        assert "Set ℝ" in content
        assert "StrictConvexOn ℝ" in content

    def test_real_type_unchanged(self, agent):
        spec = ProblemSpec(
            problem_domain=ProblemDomain.CONTINUOUS_OPTIMIZATION,
            spaces=[Space(name="S", base_type=BaseType.REAL)],
            variables=[
                Variable(
                    symbol="x",
                    classification=VariableClassification.ENDOGENOUS,
                    space_reference="S",
                    bounds=VariableBounds(lower_bound="0", strict_inequality=False),
                )
            ],
            functions=[
                Function(
                    symbol="f",
                    domain=["S"],
                    codomain="Real",
                    properties=[FunctionProperty.STRICT_CONVEX],
                ),
            ],
            objective=Objective(
                direction=ObjectiveDirection.MINIMIZE,
                expression_latex="f(x)",
            ),
        )
        result = agent.scaffold(spec)
        content = result.content
        assert "ℝ → ℝ" in content
        assert "Set ℝ" in content
        assert "EuclideanSpace" not in content
        assert "NNReal" not in content
