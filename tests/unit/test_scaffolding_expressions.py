"""Expression-related scaffolding tests: convexity, binder derivation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from formalconstruct.core.exceptions import ScaffoldingError
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


# ---------------------------------------------------------------------------
# Expression_latex consumption
# ---------------------------------------------------------------------------


class TestCR001ExpressionLatex:

    def test_expression_difference_not_sum(self, agent):
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
                ),
                Function(
                    symbol="CostLabor",
                    domain=["OutputSpace"],
                    codomain="Real",
                    properties=[FunctionProperty.CONVEX],
                ),
            ],
            objective=Objective(
                direction=ObjectiveDirection.MINIMIZE,
                expression_latex="CostCapital(x) - CostLabor(x)",
            ),
        )
        result = agent.scaffold(spec)
        assert "objective_statement" in result.content
        assert "theorem objective_statement" in result.content
        assert "minimize_x_convexon" not in result.content
        assert "minimize_x_strictconvexon" not in result.content

    def test_single_function_expression(self, agent):
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
                    symbol="CostCapital",
                    domain=["S"],
                    codomain="Real",
                    properties=[FunctionProperty.STRICT_CONVEX],
                ),
            ],
            objective=Objective(
                direction=ObjectiveDirection.MINIMIZE,
                expression_latex="CostCapital(x)",
            ),
        )
        result = agent.scaffold(spec)
        assert "CostCapital x" in result.content
        assert "CostLabor" not in result.content
        assert "StrictConvexOn" in result.content

    def test_golden_path_sum_unchanged(self, agent):
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
                ),
                Function(
                    symbol="CostLabor",
                    domain=["OutputSpace"],
                    codomain="Real",
                    properties=[FunctionProperty.LINEAR, FunctionProperty.CONVEX],
                ),
            ],
            objective=Objective(
                direction=ObjectiveDirection.MINIMIZE,
                expression_latex="CostCapital(x) + CostLabor(x)",
            ),
        )
        result = agent.scaffold(spec)
        assert "CostCapital x + CostLabor x" in result.content


# ---------------------------------------------------------------------------
# Property-driven theorem shapes
# ---------------------------------------------------------------------------


class TestCR002PropertyDrivenTheorem:

    def _make_spec(self, functions, direction):
        func_syms = [f.symbol for f in functions]
        parts = [f"{sym}(x)" for sym in func_syms]
        expr = " + ".join(parts)
        return ProblemSpec(
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
            functions=functions,
            objective=Objective(
                direction=direction,
                expression_latex=expr,
            ),
        )

    def test_convex_only_minimize_produces_convex_on(self, agent):
        spec = self._make_spec(
            [Function(symbol="f", domain=["S"], codomain="Real",
                      properties=[FunctionProperty.CONVEX])],
            ObjectiveDirection.MINIMIZE,
        )
        result = agent.scaffold(spec)
        assert "ConvexOn" in result.content
        assert "StrictConvexOn" not in result.content

    def test_strict_convex_minimize_produces_strict_convex_on(self, agent):
        spec = self._make_spec(
            [Function(symbol="f", domain=["S"], codomain="Real",
                      properties=[FunctionProperty.STRICT_CONVEX])],
            ObjectiveDirection.MINIMIZE,
        )
        result = agent.scaffold(spec)
        assert "StrictConvexOn" in result.content

    def test_continuous_only_minimize_raises(self, agent):
        spec = self._make_spec(
            [Function(symbol="f", domain=["S"], codomain="Real",
                      properties=[FunctionProperty.CONTINUOUS])],
            ObjectiveDirection.MINIMIZE,
        )
        with pytest.raises(ScaffoldingError):
            agent.scaffold(spec)

    def test_concave_maximize_produces_concave_on(self, agent):
        spec = self._make_spec(
            [Function(symbol="f", domain=["S"], codomain="Real",
                      properties=[FunctionProperty.CONCAVE])],
            ObjectiveDirection.MAXIMIZE,
        )
        result = agent.scaffold(spec)
        assert "ConcaveOn" in result.content
        assert "StrictConcaveOn" not in result.content

    def test_strict_concave_maximize_produces_strict_concave_on(self, agent):
        spec = self._make_spec(
            [Function(symbol="f", domain=["S"], codomain="Real",
                      properties=[FunctionProperty.STRICT_CONCAVE])],
            ObjectiveDirection.MAXIMIZE,
        )
        result = agent.scaffold(spec)
        assert "StrictConcaveOn" in result.content


# ---------------------------------------------------------------------------
# Expression Parser Integration Tests
# ---------------------------------------------------------------------------


class TestExpressionParserIntegration:

    def _make_opt_spec(
        self,
        expression_latex: str,
        functions: list[Function],
        *,
        direction: ObjectiveDirection = ObjectiveDirection.MINIMIZE,
    ) -> ProblemSpec:
        return ProblemSpec(
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
            functions=functions,
            objective=Objective(
                direction=direction,
                expression_latex=expression_latex,
            ),
        )

    def test_nested_function_in_scaffold(self, agent):
        spec = self._make_opt_spec(
            expression_latex="f(g(x))",
            functions=[
                Function(
                    symbol="f",
                    domain=["S"],
                    codomain="Real",
                    properties=[FunctionProperty.STRICT_CONVEX],
                ),
                Function(
                    symbol="g",
                    domain=["S"],
                    codomain="Real",
                    properties=[FunctionProperty.STRICT_CONVEX],
                ),
            ],
        )
        result = agent.scaffold(spec)
        assert "f (g x)" in result.content
        assert "sorry" in result.content

    def test_weighted_expression_in_scaffold(self, agent):
        spec = self._make_opt_spec(
            expression_latex="2 * f(x) + g(x)",
            functions=[
                Function(
                    symbol="f",
                    domain=["S"],
                    codomain="Real",
                    properties=[FunctionProperty.STRICT_CONVEX],
                ),
                Function(
                    symbol="g",
                    domain=["S"],
                    codomain="Real",
                    properties=[FunctionProperty.STRICT_CONVEX],
                ),
            ],
        )
        result = agent.scaffold(spec)
        assert "2 * f x + g x" in result.content
        assert "sorry" in result.content

    def test_division_expression_in_scaffold(self, agent):
        spec = self._make_opt_spec(
            expression_latex="f(x) / g(x)",
            functions=[
                Function(
                    symbol="f",
                    domain=["S"],
                    codomain="Real",
                    properties=[FunctionProperty.STRICT_CONVEX],
                ),
                Function(
                    symbol="g",
                    domain=["S"],
                    codomain="Real",
                    properties=[FunctionProperty.STRICT_CONVEX],
                ),
            ],
        )
        result = agent.scaffold(spec)
        assert "theorem objective_statement" in result.content
        assert "sorry" in result.content

    def test_unary_negation_in_scaffold(self, agent):
        spec = self._make_opt_spec(
            expression_latex="-f(x) + g(x)",
            functions=[
                Function(
                    symbol="f",
                    domain=["S"],
                    codomain="Real",
                    properties=[FunctionProperty.CONVEX],
                ),
                Function(
                    symbol="g",
                    domain=["S"],
                    codomain="Real",
                    properties=[FunctionProperty.CONVEX],
                ),
            ],
        )
        result = agent.scaffold(spec)
        assert "theorem objective_statement" in result.content
        assert "sorry" in result.content

    def test_parenthesized_expression_in_scaffold(self, agent):
        spec = self._make_opt_spec(
            expression_latex="(f(x) + g(x)) * h(x)",
            functions=[
                Function(
                    symbol="f",
                    domain=["S"],
                    codomain="Real",
                    properties=[FunctionProperty.STRICT_CONVEX],
                ),
                Function(
                    symbol="g",
                    domain=["S"],
                    codomain="Real",
                    properties=[FunctionProperty.STRICT_CONVEX],
                ),
                Function(
                    symbol="h",
                    domain=["S"],
                    codomain="Real",
                    properties=[FunctionProperty.STRICT_CONVEX],
                ),
            ],
        )
        result = agent.scaffold(spec)
        assert "theorem objective_statement" in result.content
        assert "sorry" in result.content

    def test_backward_compat_golden_path(self, agent):
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
                ),
                Function(
                    symbol="CostLabor",
                    domain=["OutputSpace"],
                    codomain="Real",
                    properties=[FunctionProperty.LINEAR, FunctionProperty.CONVEX],
                ),
            ],
            objective=Objective(
                direction=ObjectiveDirection.MINIMIZE,
                expression_latex="CostCapital(x) + CostLabor(x)",
            ),
        )
        result = agent.scaffold(spec)
        assert "CostCapital x + CostLabor x" in result.content
        assert "StrictConvexOn" in result.content
        assert "def OutputSpace" in result.content
        assert "sorry" in result.content

    def test_sqrt_latex_normalizes_in_scaffold(self, agent):
        spec = self._make_opt_spec(
            expression_latex=r"\sqrt{x}",
            functions=[
                Function(
                    symbol="sqrt",
                    domain=["S"],
                    codomain="Real",
                    properties=[FunctionProperty.CONCAVE],
                ),
            ],
            direction=ObjectiveDirection.MAXIMIZE,
        )
        result = agent.scaffold(spec)
        assert "sqrt x" in result.content
        assert "sorry" in result.content

    def test_empty_expression_raises_in_scaffold(self, agent):
        spec = self._make_opt_spec(
            expression_latex="",
            functions=[
                Function(
                    symbol="f",
                    domain=["S"],
                    codomain="Real",
                    properties=[FunctionProperty.CONVEX],
                ),
            ],
        )
        with pytest.raises(ScaffoldingError):
            agent.scaffold(spec)


# ---------------------------------------------------------------------------
# Binder Derivation Contract Tests
# ---------------------------------------------------------------------------


class TestBinderDerivation:

    def test_target_variable_used_as_binder(self, agent):
        spec = ProblemSpec(
            problem_domain=ProblemDomain.CONTINUOUS_OPTIMIZATION,
            spaces=[Space(name="S", base_type=BaseType.REAL)],
            variables=[
                Variable(
                    symbol="y",
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
                )
            ],
            objective=Objective(
                direction=ObjectiveDirection.MINIMIZE,
                expression_latex="f(y)",
                target_variable="y",
            ),
        )
        result = agent.scaffold(spec)
        assert "fun y =>" in result.content
        assert "fun x =>" not in result.content

    def test_default_binder_from_endogenous_variable(self, agent):
        spec = ProblemSpec(
            problem_domain=ProblemDomain.CONTINUOUS_OPTIMIZATION,
            spaces=[Space(name="S", base_type=BaseType.REAL)],
            variables=[
                Variable(
                    symbol="y",
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
                )
            ],
            objective=Objective(
                direction=ObjectiveDirection.MINIMIZE,
                expression_latex="f(y)",
            ),
        )
        result = agent.scaffold(spec)
        assert "fun y =>" in result.content

    def test_fallback_allows_declared_free_variable(self, agent):
        spec = ProblemSpec(
            problem_domain=ProblemDomain.CONTINUOUS_OPTIMIZATION,
            spaces=[Space(name="S", base_type=BaseType.REAL)],
            variables=[
                Variable(
                    symbol="x",
                    classification=VariableClassification.ENDOGENOUS,
                    space_reference="S",
                    bounds=VariableBounds(lower_bound="0", strict_inequality=False),
                ),
                Variable(
                    symbol="s",
                    classification=VariableClassification.EXOGENOUS,
                    space_reference="S",
                ),
            ],
            functions=[
                Function(
                    symbol="f",
                    domain=["S"],
                    codomain="Real",
                    properties=[FunctionProperty.STRICT_CONVEX],
                )
            ],
            objective=Objective(
                direction=ObjectiveDirection.MINIMIZE,
                expression_latex="f(x)",
                target_variable="x",
            ),
        )
        result = agent.scaffold(spec)
        assert "sorry" in result.content

    def test_invalid_target_variable_rejected_by_schema(self):
        with pytest.raises(ValidationError):
            ProblemSpec(
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
                    )
                ],
                objective=Objective(
                    direction=ObjectiveDirection.MINIMIZE,
                    expression_latex="f(x)",
                    target_variable="z",
                ),
            )

    def test_golden_path_binder_unchanged(self, agent):
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
                Function(
                    symbol="g",
                    domain=["S"],
                    codomain="Real",
                    properties=[FunctionProperty.CONVEX],
                ),
            ],
            objective=Objective(
                direction=ObjectiveDirection.MINIMIZE,
                expression_latex="f(x)+g(x)",
                target_variable="x",
            ),
        )
        result = agent.scaffold(spec)
        assert "fun x => f x + g x" in result.content


# ---------------------------------------------------------------------------
# Expression-Aware Convexity Contract Tests
# ---------------------------------------------------------------------------


class TestExpressionConvexitySafety:

    def _make_convex_spec(
        self,
        expression_latex: str,
        functions: list[Function],
        *,
        direction: ObjectiveDirection = ObjectiveDirection.MINIMIZE,
        target_variable: str = "x",
    ) -> ProblemSpec:
        return ProblemSpec(
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
            functions=functions,
            objective=Objective(
                direction=direction,
                expression_latex=expression_latex,
                target_variable=target_variable,
            ),
        )

    def test_sum_preserves_convexity(self, agent):
        spec = self._make_convex_spec(
            expression_latex="f(x) + g(x)",
            functions=[
                Function(symbol="f", domain=["S"], codomain="Real",
                         properties=[FunctionProperty.CONVEX]),
                Function(symbol="g", domain=["S"], codomain="Real",
                         properties=[FunctionProperty.CONVEX]),
            ],
        )
        result = agent.scaffold(spec)
        assert "ConvexOn" in result.content
        assert "objective_statement" not in result.content

    def test_subtraction_rejects_convexity(self, agent):
        spec = self._make_convex_spec(
            expression_latex="f(x) - g(x)",
            functions=[
                Function(symbol="f", domain=["S"], codomain="Real",
                         properties=[FunctionProperty.CONVEX]),
                Function(symbol="g", domain=["S"], codomain="Real",
                         properties=[FunctionProperty.CONVEX]),
            ],
        )
        result = agent.scaffold(spec)
        assert "theorem objective_statement" in result.content
        assert "minimize_x_convexon" not in result.content
        assert "minimize_x_strictconvexon" not in result.content

    def test_division_rejects_convexity(self, agent):
        spec = self._make_convex_spec(
            expression_latex="f(x) / g(x)",
            functions=[
                Function(symbol="f", domain=["S"], codomain="Real",
                         properties=[FunctionProperty.STRICT_CONVEX]),
                Function(symbol="g", domain=["S"], codomain="Real",
                         properties=[FunctionProperty.STRICT_CONVEX]),
            ],
        )
        result = agent.scaffold(spec)
        assert "theorem objective_statement" in result.content

    def test_function_multiplication_rejects_convexity(self, agent):
        spec = self._make_convex_spec(
            expression_latex="f(x) * g(x)",
            functions=[
                Function(symbol="f", domain=["S"], codomain="Real",
                         properties=[FunctionProperty.CONVEX]),
                Function(symbol="g", domain=["S"], codomain="Real",
                         properties=[FunctionProperty.CONVEX]),
            ],
        )
        result = agent.scaffold(spec)
        assert "theorem objective_statement" in result.content

    def test_scalar_multiplication_preserves_convexity(self, agent):
        spec = self._make_convex_spec(
            expression_latex="2 * f(x)",
            functions=[
                Function(symbol="f", domain=["S"], codomain="Real",
                         properties=[FunctionProperty.STRICT_CONVEX]),
            ],
        )
        result = agent.scaffold(spec)
        assert "StrictConvexOn" in result.content
        assert "objective_statement" not in result.content

    def test_scalar_multiply_plus_function_preserves(self, agent):
        spec = self._make_convex_spec(
            expression_latex="2 * f(x) + g(x)",
            functions=[
                Function(symbol="f", domain=["S"], codomain="Real",
                         properties=[FunctionProperty.STRICT_CONVEX]),
                Function(symbol="g", domain=["S"], codomain="Real",
                         properties=[FunctionProperty.STRICT_CONVEX]),
            ],
        )
        result = agent.scaffold(spec)
        assert "StrictConvexOn" in result.content
        assert "objective_statement" not in result.content

    def test_negation_rejects_convexity(self, agent):
        spec = self._make_convex_spec(
            expression_latex="-f(x)",
            functions=[
                Function(symbol="f", domain=["S"], codomain="Real",
                         properties=[FunctionProperty.CONVEX]),
            ],
        )
        result = agent.scaffold(spec)
        assert "theorem objective_statement" in result.content

    def test_golden_path_sum_still_strict_convex(self, agent):
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
                ),
                Function(
                    symbol="CostLabor",
                    domain=["OutputSpace"],
                    codomain="Real",
                    properties=[FunctionProperty.LINEAR, FunctionProperty.CONVEX],
                ),
            ],
            objective=Objective(
                direction=ObjectiveDirection.MINIMIZE,
                expression_latex="CostCapital(x) + CostLabor(x)",
                target_variable="x",
            ),
        )
        result = agent.scaffold(spec)
        assert "StrictConvexOn" in result.content
        assert "minimize_x_strictconvexon" in result.content
        assert "objective_statement" not in result.content


# ---------------------------------------------------------------------------
# Free variable rejection
# ---------------------------------------------------------------------------


class TestFreeVariableRejection:

    def test_expression_with_unbound_var_raises(self, agent):
        spec = ProblemSpec(
            problem_domain=ProblemDomain.CONTINUOUS_OPTIMIZATION,
            spaces=[Space(name="S", base_type=BaseType.REAL)],
            variables=[
                Variable(
                    symbol="x",
                    classification=VariableClassification.ENDOGENOUS,
                    space_reference="S",
                    bounds=VariableBounds(lower_bound="0", strict_inequality=False),
                ),
                Variable(
                    symbol="y",
                    classification=VariableClassification.ENDOGENOUS,
                    space_reference="S",
                ),
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
                expression_latex="f(x) + f(y)",
                target_variable="x",
            ),
        )
        result = agent.scaffold(spec)
        assert "fun p =>" in result.content
        assert "sorry" in result.content

    def test_expression_matching_target_passes(self, agent):
        spec = ProblemSpec(
            problem_domain=ProblemDomain.CONTINUOUS_OPTIMIZATION,
            spaces=[Space(name="S", base_type=BaseType.REAL)],
            variables=[
                Variable(
                    symbol="x",
                    classification=VariableClassification.ENDOGENOUS,
                    space_reference="S",
                    bounds=VariableBounds(lower_bound="0", strict_inequality=False),
                ),
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
                target_variable="x",
            ),
        )
        result = agent.scaffold(spec)
        assert "fun x => f x" in result.content
        assert "sorry" in result.content
