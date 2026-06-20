"""Game theory scaffolding tests."""

from __future__ import annotations

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
    VariableClassification,
)


class TestGameTheoryScaffolding:
    def test_sorry_in_content(self, agent, game_theory_spec):
        result = agent.scaffold(game_theory_spec)
        assert "sorry" in result.content

    def test_equilibrium_theorem(self, agent, game_theory_spec):
        result = agent.scaffold(game_theory_spec)
        assert "nash_equilibrium" in result.content

    def test_goal_extraction(self, agent, game_theory_spec):
        result = agent.scaffold(game_theory_spec)
        assert len(result.goals) >= 1


# ---------------------------------------------------------------------------
# Game Theory Concrete Predicate Contract Tests
# ---------------------------------------------------------------------------


class TestGameTheoryConcretePredicates:

    def test_nash_equilibrium_has_function_update(self, agent):
        spec = ProblemSpec(
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
        result = agent.scaffold(spec)
        content = result.content
        assert "Function.update" in content
        assert "∀ i" in content or "\\forall i" in content

    def test_pareto_has_negation(self, agent):
        spec = ProblemSpec(
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
                direction=ObjectiveDirection.PARETO_OPTIMAL,
                expression_latex="Payoff(s)",
            ),
        )
        result = agent.scaffold(spec)
        content = result.content
        assert "¬∃" in content
        assert "profile'" in content

    def test_strategy_profile_type(self, agent):
        spec = ProblemSpec(
            problem_domain=ProblemDomain.NON_COOPERATIVE_GAME,
            spaces=[Space(name="StrategySpace", base_type=BaseType.REAL)],
            variables=[
                Variable(
                    symbol="profile",
                    classification=VariableClassification.STRATEGY_PROFILE,
                    space_reference="StrategySpace",
                )
            ],
            functions=[
                Function(
                    symbol="u",
                    domain=["StrategySpace"],
                    codomain="Real",
                    properties=[FunctionProperty.CONTINUOUS],
                )
            ],
            objective=Objective(
                direction=ObjectiveDirection.EQUILIBRIUM,
                expression_latex="u(profile)",
            ),
        )
        result = agent.scaffold(spec)
        content = result.content
        assert "Fin N →" in content or "Fin 2 →" in content

    def test_utility_function_type(self, agent):
        spec = ProblemSpec(
            problem_domain=ProblemDomain.NON_COOPERATIVE_GAME,
            player_count=2,
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
                    symbol="u",
                    domain=["StrategySpace"],
                    codomain="Real",
                    properties=[FunctionProperty.CONTINUOUS],
                )
            ],
            objective=Objective(
                direction=ObjectiveDirection.EQUILIBRIUM,
                expression_latex="u(s)",
            ),
        )
        result = agent.scaffold(spec)
        content = result.content
        assert "Fin 2 →" in content
        assert "(Fin 2 → ℝ) → ℝ" in content

    def test_player_count_concrete(self, agent):
        spec = ProblemSpec(
            problem_domain=ProblemDomain.NON_COOPERATIVE_GAME,
            player_count=3,
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
                    symbol="u",
                    domain=["StrategySpace"],
                    codomain="Real",
                    properties=[FunctionProperty.CONTINUOUS],
                )
            ],
            objective=Objective(
                direction=ObjectiveDirection.EQUILIBRIUM,
                expression_latex="u(s)",
            ),
        )
        result = agent.scaffold(spec)
        content = result.content
        assert "Fin 3" in content
        assert "Fin N" not in content

    def test_game_theory_sorry_present(self, agent):
        spec = ProblemSpec(
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
        result = agent.scaffold(spec)
        assert "sorry" in result.content
