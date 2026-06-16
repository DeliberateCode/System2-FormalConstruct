"""Composite domain scaffolding tests and multi-variable optimization."""

from __future__ import annotations

import pytest
from unittest.mock import patch

from formalconstruct.agents.lean_scaffolding import LeanScaffoldingAgent
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


class TestCompositeScaffolding:
    def test_composite_imports_merged(self, agent):
        spec = ProblemSpec(
            problem_domain=ProblemDomain.NON_COOPERATIVE_GAME,
            primary_domain=ProblemDomain.NON_COOPERATIVE_GAME,
            domain_components=[
                ProblemDomain.NON_COOPERATIVE_GAME,
                ProblemDomain.CONTINUOUS_OPTIMIZATION,
            ],
            spaces=[Space(name="S", base_type=BaseType.REAL)],
            variables=[
                Variable(
                    symbol="x",
                    classification=VariableClassification.STRATEGY_PROFILE,
                    space_reference="S",
                )
            ],
            functions=[
                Function(symbol="f", domain=["S"], codomain="Real", properties=[FunctionProperty.CONVEX])
            ],
            objective=Objective(
                direction=ObjectiveDirection.EQUILIBRIUM,
                expression_latex="f(x)",
            ),
        )
        result = agent.scaffold(spec)
        assert "Mathlib" in result.imports
        assert len(result.imports) == 1
        assert "sorry" in result.content


class TestPrimaryDomainRouting:

    def test_composite_uses_primary_domain_for_mapper_lookup(self, registry):
        spec = ProblemSpec(
            problem_domain=ProblemDomain.CONTINUOUS_OPTIMIZATION,
            primary_domain=ProblemDomain.NON_COOPERATIVE_GAME,
            domain_components=[
                ProblemDomain.NON_COOPERATIVE_GAME,
                ProblemDomain.CONTINUOUS_OPTIMIZATION,
            ],
            spaces=[Space(name="S", base_type=BaseType.REAL)],
            variables=[
                Variable(
                    symbol="x",
                    classification=VariableClassification.STRATEGY_PROFILE,
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
                direction=ObjectiveDirection.EQUILIBRIUM,
                expression_latex="f(x)",
            ),
        )
        agent = LeanScaffoldingAgent(registry)
        with patch.object(registry, "get_mapper", wraps=registry.get_mapper) as spy:
            agent.scaffold(spec)
            spy.assert_called_once_with(
                "non_cooperative_game",
                ["non_cooperative_game", "continuous_optimization"],
            )

    def test_non_composite_uses_problem_domain(self, registry):
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
        with patch.object(registry, "get_mapper", wraps=registry.get_mapper) as spy:
            agent.scaffold(spec)
            spy.assert_called_once_with("continuous_optimization", None)


# ---------------------------------------------------------------------------
# Primary_domain routing
# ---------------------------------------------------------------------------


class TestCR003PrimaryDomainRouting:

    def test_composite_uses_primary_domain(self, agent):
        spec = ProblemSpec(
            problem_domain=ProblemDomain.CONTINUOUS_OPTIMIZATION,
            primary_domain=ProblemDomain.NON_COOPERATIVE_GAME,
            domain_components=[
                ProblemDomain.NON_COOPERATIVE_GAME,
                ProblemDomain.CONTINUOUS_OPTIMIZATION,
            ],
            spaces=[Space(name="StrategySpace", base_type=BaseType.REAL)],
            variables=[
                Variable(
                    symbol="s",
                    classification=VariableClassification.STRATEGY_PROFILE,
                    space_reference="StrategySpace",
                )
            ],
            functions=[
                Function(
                    symbol="Payoff",
                    domain=["StrategySpace"],
                    codomain="Real",
                    properties=[FunctionProperty.CONTINUOUS],
                ),
            ],
            objective=Objective(
                direction=ObjectiveDirection.EQUILIBRIUM,
                expression_latex="Payoff(s)",
            ),
        )
        result = agent.scaffold(spec)
        assert "nash_equilibrium" in result.content

    def test_non_composite_ignores_primary_domain(self, agent):
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
                    properties=[FunctionProperty.CONVEX],
                ),
            ],
            objective=Objective(
                direction=ObjectiveDirection.MINIMIZE,
                expression_latex="f(x)",
            ),
        )
        result = agent.scaffold(spec)
        assert "ConvexOn" in result.content
        assert "nash_equilibrium" not in result.content


# ---------------------------------------------------------------------------
# Multi-Variable Optimization Tests
# ---------------------------------------------------------------------------


class TestMultiVariableOptimization:

    def test_two_variable_product_type(self, agent):
        pytest.skip("multi-variable product-type support not yet implemented")

        spec = ProblemSpec(
            problem_domain=ProblemDomain.CONTINUOUS_OPTIMIZATION,
            spaces=[
                Space(name="SpaceX", base_type=BaseType.REAL),
                Space(name="SpaceY", base_type=BaseType.REAL),
            ],
            variables=[
                Variable(
                    symbol="x",
                    classification=VariableClassification.ENDOGENOUS,
                    space_reference="SpaceX",
                    bounds=VariableBounds(lower_bound="0", strict_inequality=False),
                ),
                Variable(
                    symbol="y",
                    classification=VariableClassification.ENDOGENOUS,
                    space_reference="SpaceY",
                ),
            ],
            functions=[
                Function(
                    symbol="f",
                    domain=["SpaceX"],
                    codomain="Real",
                    properties=[FunctionProperty.CONVEX],
                ),
                Function(
                    symbol="g",
                    domain=["SpaceY"],
                    codomain="Real",
                    properties=[FunctionProperty.CONVEX],
                ),
            ],
            objective=Objective(
                direction=ObjectiveDirection.MINIMIZE,
                expression_latex="f(x) + g(y)",
                target_variable="x",
            ),
        )
        result = agent.scaffold(spec)
        content = result.content
        has_tuple_proj = "p.1" in content or "p.2" in content
        has_multi_lambda = "fun p =>" in content or "fun (x, y) =>" in content
        assert has_tuple_proj or has_multi_lambda

    def test_single_variable_unchanged(self, agent):
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
                )
            ],
            objective=Objective(
                direction=ObjectiveDirection.MINIMIZE,
                expression_latex="f(x)",
                target_variable="x",
            ),
        )
        result = agent.scaffold(spec)
        assert "fun x =>" in result.content
        assert "sorry" in result.content

    def test_multi_variable_domain_product(self, agent):
        pytest.skip("multi-variable product-type support not yet implemented")

        spec = ProblemSpec(
            problem_domain=ProblemDomain.CONTINUOUS_OPTIMIZATION,
            spaces=[
                Space(name="SpaceX", base_type=BaseType.REAL),
                Space(name="SpaceY", base_type=BaseType.REAL),
            ],
            variables=[
                Variable(
                    symbol="x",
                    classification=VariableClassification.ENDOGENOUS,
                    space_reference="SpaceX",
                    bounds=VariableBounds(lower_bound="0", strict_inequality=False),
                ),
                Variable(
                    symbol="y",
                    classification=VariableClassification.ENDOGENOUS,
                    space_reference="SpaceY",
                ),
            ],
            functions=[
                Function(
                    symbol="f",
                    domain=["SpaceX"],
                    codomain="Real",
                    properties=[FunctionProperty.CONVEX],
                ),
                Function(
                    symbol="g",
                    domain=["SpaceY"],
                    codomain="Real",
                    properties=[FunctionProperty.CONVEX],
                ),
            ],
            objective=Objective(
                direction=ObjectiveDirection.MINIMIZE,
                expression_latex="f(x) + g(y)",
                target_variable="x",
            ),
        )
        result = agent.scaffold(spec)
        content = result.content
        assert "×ˢ" in content or "Set.prod" in content
