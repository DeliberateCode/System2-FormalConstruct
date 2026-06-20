"""Shared fixtures and helpers for unit tests.

Provides common spec builders, stub mappers, and pytest fixtures used across
the split test modules.
"""

import pytest

from formalconstruct.agents.lean_scaffolding import LeanScaffoldingAgent
from formalconstruct.domains import create_default_registry
from formalconstruct.domains.registry import DomainMapper, DomainRegistry
from formalconstruct.schemas.problem_spec import (
    BaseType,
    Function,
    FunctionProperty,
    Objective,
    ObjectiveDirection,
    ProblemDomain,
    ProblemSpec,
    Space,
    TopologicalProperty,
    Variable,
    VariableBounds,
    VariableClassification,
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_continuous_opt_spec(**overrides) -> ProblemSpec:
    defaults = dict(
        problem_domain=ProblemDomain.CONTINUOUS_OPTIMIZATION,
        spaces=[Space(name="S", base_type=BaseType.REAL, topological_properties=[TopologicalProperty.CONVEX])],
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
                properties=[FunctionProperty.STRICT_CONVEX, FunctionProperty.CONTINUOUS],
            )
        ],
        objective=Objective(
            direction=ObjectiveDirection.MINIMIZE,
            expression_latex="f(x)",
        ),
    )
    defaults.update(overrides)
    return ProblemSpec(**defaults)


def _make_game_theory_spec(**overrides) -> ProblemSpec:
    defaults = dict(
        problem_domain=ProblemDomain.NON_COOPERATIVE_GAME,
        spaces=[Space(name="Strat", base_type=BaseType.REAL)],
        variables=[
            Variable(
                symbol="s",
                classification=VariableClassification.STRATEGY_PROFILE,
                space_reference="Strat",
            )
        ],
        functions=[
            Function(symbol="u", domain=["Strat"], codomain="Real", properties=[FunctionProperty.CONTINUOUS])
        ],
        objective=Objective(
            direction=ObjectiveDirection.EQUILIBRIUM,
            expression_latex="u(s)",
        ),
    )
    defaults.update(overrides)
    return ProblemSpec(**defaults)


class _StubMapper(DomainMapper):
    """Minimal concrete mapper for testing registry mechanics."""

    def __init__(self, name: str = "stub_domain") -> None:
        self._name = name

    @property
    def domain_name(self) -> str:
        return self._name

    def required_imports(self, spec):
        return ["import StubLib"]

    def map_space(self, space):
        return f"def {space.name} : stub"

    def map_variable(self, var, spaces):
        return f"variable ({var.symbol} : stub)"

    def map_function(self, func):
        return f"variable ({func.symbol} : stub)"

    def map_objective(self, objective, spec):
        return "theorem stub := sorry"

    def map_bounds(self, var):
        return "Set.univ"


# ---------------------------------------------------------------------------
# Lean scaffolding fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def registry() -> DomainRegistry:
    return create_default_registry()


@pytest.fixture()
def agent(registry: DomainRegistry) -> LeanScaffoldingAgent:
    return LeanScaffoldingAgent(registry)


@pytest.fixture()
def continuous_opt_spec() -> ProblemSpec:
    return ProblemSpec(
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


@pytest.fixture()
def game_theory_spec() -> ProblemSpec:
    return ProblemSpec(
        problem_domain=ProblemDomain.NON_COOPERATIVE_GAME,
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
            )
        ],
        objective=Objective(
            direction=ObjectiveDirection.EQUILIBRIUM,
            expression_latex="Payoff(s)",
        ),
    )
