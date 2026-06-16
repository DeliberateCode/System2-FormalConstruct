"""Unit tests for GameTheoryMapper and heterogeneous strategy spaces."""

from formalconstruct.domains import create_default_registry
from formalconstruct.domains.game_theory_mapper import GameTheoryMapper
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

from tests.unit.conftest import _make_game_theory_spec


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_heterogeneous_game_spec(**overrides) -> ProblemSpec:
    """Build a 2-player game spec with per-player strategy spaces."""
    defaults = dict(
        problem_domain=ProblemDomain.NON_COOPERATIVE_GAME,
        spaces=[
            Space(name="PriceSpace", base_type=BaseType.REAL),
            Space(name="QuantitySpace", base_type=BaseType.REAL),
        ],
        variables=[
            Variable(
                symbol="profile",
                classification=VariableClassification.STRATEGY_PROFILE,
                space_reference="PriceSpace",
            ),
        ],
        functions=[
            Function(symbol="u_0", domain=["PriceSpace"], codomain="Real",
                     properties=[FunctionProperty.CONTINUOUS]),
            Function(symbol="u_1", domain=["QuantitySpace"], codomain="Real",
                     properties=[FunctionProperty.CONTINUOUS]),
        ],
        objective=Objective(
            direction=ObjectiveDirection.EQUILIBRIUM,
            expression_latex="u_0(profile)",
        ),
        player_count=2,
        strategy_spaces={"0": "PriceSpace", "1": "QuantitySpace"},
    )
    defaults.update(overrides)
    return ProblemSpec(**defaults)


# ---------------------------------------------------------------------------
# GameTheoryMapper tests
# ---------------------------------------------------------------------------


class TestGameTheoryMapper:

    def test_domain_name_non_cooperative(self):
        assert GameTheoryMapper(domain="non_cooperative_game").domain_name == "non_cooperative_game"

    def test_domain_name_cooperative(self):
        assert GameTheoryMapper(domain="cooperative_game").domain_name == "cooperative_game"

    def test_required_imports(self):
        spec = _make_game_theory_spec()
        imports = GameTheoryMapper().required_imports(spec)
        assert "import Mathlib" in imports

    def test_map_objective_equilibrium(self):
        spec = _make_game_theory_spec()
        result = GameTheoryMapper().map_objective(spec.objective, spec)
        assert "nash_equilibrium" in result
        assert "sorry" in result

    def test_map_objective_pareto_optimal(self):
        spec = _make_game_theory_spec(
            objective=Objective(direction=ObjectiveDirection.PARETO_OPTIMAL, expression_latex="u(s)")
        )
        result = GameTheoryMapper().map_objective(spec.objective, spec)
        assert "pareto_optimal" in result
        assert "sorry" in result

    def test_map_variable_strategy_profile(self):
        spaces = {"Strat": Space(name="Strat", base_type=BaseType.REAL)}
        var = Variable(
            symbol="s",
            classification=VariableClassification.STRATEGY_PROFILE,
            space_reference="Strat",
        )
        result = GameTheoryMapper().map_variable(var, spaces)
        assert "s" in result
        assert "variable" in result


# ---------------------------------------------------------------------------
# Heterogeneous strategy spaces
# ---------------------------------------------------------------------------


class TestHeterogeneousStrategySpaces:

    def test_heterogeneous_nash_contains_per_player_deviations(self):
        mapper = GameTheoryMapper()
        spec = _make_heterogeneous_game_spec()
        mapper.set_context(spec)
        result = mapper.map_objective(spec.objective, spec)
        assert "nash_equilibrium" in result
        assert "sorry" in result
        assert "s_0'" in result
        assert "s_1'" in result
        assert "PriceSpace" in result
        assert "QuantitySpace" in result

    def test_heterogeneous_nash_uses_product_type_deviations(self):
        mapper = GameTheoryMapper()
        spec = _make_heterogeneous_game_spec()
        mapper.set_context(spec)
        result = mapper.map_objective(spec.objective, spec)
        assert "Function.update" not in result
        assert "s_0', profile.2" in result or "(s_0'" in result
        assert "profile.1, s_1'" in result or "s_1')" in result

    def test_heterogeneous_nash_utility_per_player(self):
        mapper = GameTheoryMapper()
        spec = _make_heterogeneous_game_spec()
        mapper.set_context(spec)
        result = mapper.map_objective(spec.objective, spec)
        assert "u_0" in result
        assert "u_1" in result

    def test_homogeneous_backward_compat_when_no_strategy_spaces(self):
        mapper = GameTheoryMapper()
        spec = _make_game_theory_spec(player_count=2)
        mapper.set_context(spec)
        result = mapper.map_objective(spec.objective, spec)
        assert "Function.update" in result
        assert "s_0'" not in result

    def test_heterogeneous_nash_feasibility_hypotheses(self):
        mapper = GameTheoryMapper()
        spec = _make_heterogeneous_game_spec()
        mapper.set_context(spec)
        result = mapper.map_objective(spec.objective, spec)
        assert "profile.1 ∈ PriceSpace" in result
        assert "profile.2 ∈ QuantitySpace" in result


# ---------------------------------------------------------------------------
# Single `import Mathlib` in GameTheoryMapper
# ---------------------------------------------------------------------------


class TestCR007SingleMathlib:

    def test_required_imports_single_mathlib_only(self):
        spec = _make_game_theory_spec()
        imports = GameTheoryMapper().required_imports(spec)
        assert imports == ["import Mathlib"]
        for imp in imports:
            assert "Mathlib." not in imp

    def test_composite_single_import_mathlib_line(self):
        reg = create_default_registry()
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
                Function(
                    symbol="f",
                    domain=["S"],
                    codomain="Real",
                    properties=[FunctionProperty.CONTINUOUS],
                )
            ],
            objective=Objective(
                direction=ObjectiveDirection.EQUILIBRIUM,
                expression_latex="f(x)",
            ),
        )
        composite = reg.get_mapper(
            "non_cooperative_game",
            domain_components=["non_cooperative_game", "continuous_optimization"],
        )
        imports = composite.required_imports(spec)
        assert imports == ["import Mathlib"]


# ---------------------------------------------------------------------------
# GameTheoryMapper set_context and _lean_type_for_space usage
# ---------------------------------------------------------------------------


class TestGameTheoryMapperSetContext:

    def test_set_context_caches_spaces(self):
        mapper = GameTheoryMapper()
        spec = _make_game_theory_spec()
        mapper.set_context(spec)
        assert "Strat" in mapper._spaces

    def test_clear_context_resets_spaces(self):
        mapper = GameTheoryMapper()
        spec = _make_game_theory_spec()
        mapper.set_context(spec)
        mapper.clear_context()
        assert len(mapper._spaces) == 0

    def test_map_variable_real_n_with_dimension(self):
        mapper = GameTheoryMapper()
        spec = _make_game_theory_spec(
            spaces=[Space(name="Strat", base_type=BaseType.REAL_N, dimension=3)],
        )
        mapper.set_context(spec)
        spaces = {s.name: s for s in spec.spaces}
        var = spec.variables[0]
        result = mapper.map_variable(var, spaces)
        assert "EuclideanSpace ℝ (Fin 3)" in result

    def test_map_variable_real_n_no_dimension(self):
        mapper = GameTheoryMapper()
        spec = _make_game_theory_spec(
            spaces=[Space(name="Strat", base_type=BaseType.REAL_N)],
        )
        mapper.set_context(spec)
        spaces = {s.name: s for s in spec.spaces}
        var = spec.variables[0]
        result = mapper.map_variable(var, spaces)
        assert "EuclideanSpace ℝ (Fin n)" in result

    def test_map_variable_real_fallback_no_context(self):
        mapper = GameTheoryMapper()
        spaces = {"Strat": Space(name="Strat", base_type=BaseType.REAL)}
        var = Variable(
            symbol="s",
            classification=VariableClassification.STRATEGY_PROFILE,
            space_reference="Strat",
        )
        result = mapper.map_variable(var, spaces)
        assert "ℝ" in result

    def test_map_space_real_n_with_dimension(self):
        mapper = GameTheoryMapper()
        space = Space(name="Strat", base_type=BaseType.REAL_N, dimension=5)
        result = mapper.map_space(space)
        assert "EuclideanSpace ℝ (Fin 5)" in result

    def test_map_space_real_n_no_dimension(self):
        mapper = GameTheoryMapper()
        space = Space(name="Strat", base_type=BaseType.REAL_N)
        result = mapper.map_space(space)
        assert "EuclideanSpace ℝ (Fin n)" in result

    def test_map_function_uses_resolved_type(self):
        mapper = GameTheoryMapper()
        spec = _make_game_theory_spec(
            spaces=[Space(name="Strat", base_type=BaseType.REAL_N, dimension=4)],
        )
        mapper.set_context(spec)
        func = spec.functions[0]
        result = mapper.map_function(func)
        assert "EuclideanSpace ℝ (Fin 4)" in result


# ---------------------------------------------------------------------------
# GameTheory REAL_N dimension contract tests
# ---------------------------------------------------------------------------


class TestGameTheoryRealNDimension:

    def test_game_theory_real_n_dimension_3(self):
        mapper = GameTheoryMapper()
        spec = _make_game_theory_spec(
            spaces=[Space(name="Strat", base_type=BaseType.REAL_N, dimension=3)],
        )
        mapper.set_context(spec)

        space_result = mapper.map_space(spec.spaces[0])
        assert "EuclideanSpace ℝ (Fin 3)" in space_result

        spaces = {s.name: s for s in spec.spaces}
        var_result = mapper.map_variable(spec.variables[0], spaces)
        assert "EuclideanSpace ℝ (Fin 3)" in var_result

        func_result = mapper.map_function(spec.functions[0])
        assert "EuclideanSpace ℝ (Fin 3)" in func_result

    def test_game_theory_real_n_no_dimension(self):
        mapper = GameTheoryMapper()
        spec = _make_game_theory_spec(
            spaces=[Space(name="Strat", base_type=BaseType.REAL_N)],
        )
        mapper.set_context(spec)

        space_result = mapper.map_space(spec.spaces[0])
        assert "EuclideanSpace ℝ (Fin n)" in space_result

        spaces = {s.name: s for s in spec.spaces}
        var_result = mapper.map_variable(spec.variables[0], spaces)
        assert "EuclideanSpace ℝ (Fin n)" in var_result

        func_result = mapper.map_function(spec.functions[0])
        assert "EuclideanSpace ℝ (Fin n)" in func_result

    def test_game_theory_real_type_unchanged(self):
        mapper = GameTheoryMapper()
        spec = _make_game_theory_spec(
            spaces=[Space(name="Strat", base_type=BaseType.REAL)],
        )
        mapper.set_context(spec)

        space_result = mapper.map_space(spec.spaces[0])
        assert "ℝ" in space_result
        assert "EuclideanSpace" not in space_result

        spaces = {s.name: s for s in spec.spaces}
        var_result = mapper.map_variable(spec.variables[0], spaces)
        assert "ℝ" in var_result
        assert "EuclideanSpace" not in var_result

        func_result = mapper.map_function(spec.functions[0])
        assert "ℝ" in func_result
        assert "EuclideanSpace" not in func_result


# ---------------------------------------------------------------------------
# GameTheoryMapper multi-domain curried type tests
# ---------------------------------------------------------------------------


class TestGameTheoryMapperMultiDomain:

    def test_single_domain_game_utility_type(self):
        mapper = GameTheoryMapper()
        spec = _make_game_theory_spec(
            player_count=2,
            spaces=[Space(name="Strat", base_type=BaseType.REAL)],
            functions=[
                Function(
                    symbol="u",
                    domain=["Strat"],
                    codomain="Real",
                    properties=[FunctionProperty.CONTINUOUS],
                )
            ],
        )
        mapper.set_context(spec)
        result = mapper.map_function(spec.functions[0])
        assert "Fin 2" in result
        assert "u : Fin 2 → (Fin 2 → ℝ) → ℝ" in result

    def test_game_utility_with_concrete_player_count(self):
        mapper = GameTheoryMapper()
        spec = _make_game_theory_spec(
            player_count=2,
            spaces=[Space(name="Strat", base_type=BaseType.REAL)],
        )
        mapper.set_context(spec)
        result = mapper.map_function(spec.functions[0])
        assert "u : Fin 2 → (Fin 2 → ℝ) → ℝ" in result

    def test_game_utility_real_n_strategy(self):
        mapper = GameTheoryMapper()
        spec = _make_game_theory_spec(
            player_count=2,
            spaces=[Space(name="Strat", base_type=BaseType.REAL_N, dimension=3)],
        )
        mapper.set_context(spec)
        result = mapper.map_function(spec.functions[0])
        assert "Fin 2 → (Fin 2 → EuclideanSpace ℝ (Fin 3)) → ℝ" in result

    def test_empty_domain_fallback(self):
        mapper = GameTheoryMapper()
        func = Function(symbol="f", domain=[], codomain="Real", properties=[FunctionProperty.CONTINUOUS])
        result = mapper.map_function(func)
        assert "f : ℝ → ℝ" in result

    def test_no_context_produces_curried_type(self):
        mapper = GameTheoryMapper()
        func = Function(
            symbol="u",
            domain=["S1", "S2"],
            codomain="Real",
            properties=[FunctionProperty.CONTINUOUS],
        )
        result = mapper.map_function(func)
        assert "u : ℝ → ℝ → ℝ" in result


# ---------------------------------------------------------------------------
# Corner-case: game theory fallback theorem comments
# ---------------------------------------------------------------------------
class TestGameTheoryFallbackComments:

    def _make_fallback_spec(self, direction: ObjectiveDirection) -> ProblemSpec:
        return ProblemSpec(
            problem_domain=ProblemDomain.NON_COOPERATIVE_GAME,
            spaces=[Space(name="S", base_type=BaseType.REAL)],
            variables=[
                Variable(
                    symbol="profile",
                    classification=VariableClassification.STRATEGY_PROFILE,
                    space_reference="S",
                ),
            ],
            functions=[
                Function(symbol="u", domain=["S"], codomain="Real",
                         properties=[FunctionProperty.CONTINUOUS]),
            ],
            objective=Objective(
                direction=direction,
                expression_latex="u(profile)",
            ),
            player_count=2,
        )

    def test_minimize_fallback_has_comments(self):
        mapper = GameTheoryMapper()
        spec = self._make_fallback_spec(ObjectiveDirection.MINIMIZE)
        mapper.set_context(spec)
        result = mapper.map_objective(spec.objective, spec)
        assert "FormalConstruct does not derive" in result
        assert "MINIMIZE" in result
        assert "sorry" in result

    def test_maximize_fallback_has_comments(self):
        mapper = GameTheoryMapper()
        spec = self._make_fallback_spec(ObjectiveDirection.MAXIMIZE)
        mapper.set_context(spec)
        result = mapper.map_objective(spec.objective, spec)
        assert "FormalConstruct does not derive" in result
        assert "MAXIMIZE" in result
        assert "sorry" in result

    def test_generic_fallback_has_comments(self):
        mapper = GameTheoryMapper()
        spec = ProblemSpec(
            problem_domain=ProblemDomain.NON_COOPERATIVE_GAME,
            spaces=[Space(name="S", base_type=BaseType.REAL)],
            variables=[
                Variable(
                    symbol="profile",
                    classification=VariableClassification.STRATEGY_PROFILE,
                    space_reference="S",
                ),
            ],
            functions=[
                Function(symbol="u", domain=["S"], codomain="Real",
                         properties=[FunctionProperty.CONTINUOUS]),
            ],
            objective=Objective(
                direction=ObjectiveDirection.EQUILIBRIUM,
                expression_latex="",
            ),
            player_count=2,
        )
        mapper.set_context(spec)
        result = mapper.map_objective(spec.objective, spec)
        # Generic fallback (not EQUILIBRIUM with strategy spaces) should still have sorry
        assert "sorry" in result
