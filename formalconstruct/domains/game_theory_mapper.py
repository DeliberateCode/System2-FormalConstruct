from __future__ import annotations

from formalconstruct.core.exceptions import ScaffoldingError
from formalconstruct.domains.registry import (
    DomainMapper,
    _lean_type_for_space,
    _tuple_projections,
    property_hypothesis,
)
from formalconstruct.schemas.problem_spec import (
    Function,
    Objective,
    ObjectiveDirection,
    ProblemSpec,
    Space,
    Variable,
    VariableClassification,
)


_BASE_IMPORTS = ["import Mathlib"]


def _build_deviated_profile(
    profile: str,
    projections: list[str],
    player_idx: int,
    dev_var: str,
    n: int,
) -> str:
    """Build a deviated profile tuple for player_idx.

    For n=2, player 0: (s_0', profile.2)
    For n=2, player 1: (profile.1, s_1')
    """
    parts: list[str] = []
    for i in range(n):
        if i == player_idx:
            parts.append(dev_var)
        else:
            parts.append(projections[i])
    return f"({', '.join(parts)})"


class GameTheoryMapper(DomainMapper):
    """Domain mapper for game theory problems (non-cooperative and cooperative).
    Handles strategy profiles, best response formulations, Nash equilibrium,
    and Pareto optimality."""

    def __init__(self, domain: str = "non_cooperative_game") -> None:
        self._domain = domain
        self._spaces: dict[str, Space] = {}
        self._player_count: int | None = None
        self._strategy_spaces: dict[str, str] | None = None
        self._emitted_n_variable: bool = False
        self._emitted_dim_variable: bool = False

    def set_context(self, spec: ProblemSpec) -> None:
        """Cache the spec's spaces and player_count for type resolution."""
        self._spaces = {s.name: s for s in spec.spaces}
        self._player_count = spec.player_count
        self._strategy_spaces = spec.strategy_spaces
        self._emitted_n_variable = False
        self._emitted_dim_variable = False

    def clear_context(self) -> None:
        """Reset cached state to prevent leaking between calls."""
        self._spaces = {}
        self._player_count = None
        self._strategy_spaces = None
        self._emitted_n_variable = False
        self._emitted_dim_variable = False

    def supported_classifications(self) -> list[VariableClassification]:
        return [VariableClassification.STRATEGY_PROFILE]

    @property
    def domain_name(self) -> str:
        return self._domain

    def required_imports(self, spec: ProblemSpec) -> list[str]:
        return list(_BASE_IMPORTS)

    def map_space(self, space: Space) -> str:
        lean_type = _lean_type_for_space(space)
        if " " in lean_type:
            return f"def {space.name} : Set ({lean_type}) := Set.univ"
        return f"def {space.name} : Set {lean_type} := Set.univ"

    def map_variable(self, var: Variable, spaces: dict[str, Space]) -> str:
        space = spaces.get(var.space_reference)
        lean_type = _lean_type_for_space(space) if space else "ℝ"

        if var.classification == VariableClassification.STRATEGY_PROFILE:
            if self._strategy_spaces is not None and self._player_count is not None:
                return self._emit_product_profile_variable(var, spaces)
            player_type = self._player_index_type()
            profile_type = f"{player_type} → {lean_type}"
            lines: list[str] = []
            if self._player_count is None and not self._emitted_n_variable:
                lines.append("variable (N : ℕ)")
                self._emitted_n_variable = True
            lines.append(f"variable ({var.symbol} : {profile_type})")
            return "\n".join(lines)

        lines_out: list[str] = []
        if "Fin n" in lean_type and not self._emitted_dim_variable:
            lines_out.append("variable (n : ℕ)")
            self._emitted_dim_variable = True
        lines_out.append(f"variable ({var.symbol} : {lean_type})")
        return "\n".join(lines_out)

    def _emit_product_profile_variable(
        self, var: Variable, spaces: dict[str, Space],
    ) -> str:
        """Emit a product-typed profile variable for heterogeneous Nash."""
        n = self._player_count
        types = []
        for i in range(n):
            space_name = self._strategy_spaces[str(i)]
            space = spaces.get(space_name) or self._spaces.get(space_name)
            types.append(_lean_type_for_space(space) if space else "ℝ")
        if n == 1:
            product_type = types[0]
        else:
            product_type = " × ".join(types)
        return f"variable ({var.symbol} : {product_type})"

    def map_function(self, func: Function) -> str:
        if self._is_game_utility_function(func):
            return self._emit_game_utility(func)

        domain_set = func.domain[0] if func.domain else "Set.univ"

        # Build curried type signature from all domain entries
        domain_types = [self._resolve_type(d) for d in func.domain] if func.domain else ["ℝ"]
        codomain_type = self._resolve_type(func.codomain)
        type_sig = " → ".join(domain_types) + f" → {codomain_type}"

        lines: list[str] = [f"variable ({func.symbol} : {type_sig})"]
        for prop in func.properties:
            hyp = property_hypothesis(func.symbol, domain_set, prop)
            if hyp:
                lines.append(hyp)
        return "\n".join(lines)

    def map_objective(self, objective: Objective, spec: ProblemSpec) -> str:
        if objective.direction == ObjectiveDirection.EQUILIBRIUM:
            if spec.strategy_spaces is not None:
                return self._emit_heterogeneous_nash(spec)
            return self._emit_nash_equilibrium(spec)
        if objective.direction == ObjectiveDirection.PARETO_OPTIMAL:
            return self._emit_pareto_optimality(spec)
        if objective.direction == ObjectiveDirection.MINIMIZE:
            return (
                "-- Note: FormalConstruct does not derive optimization predicates\n"
                "-- for game-theory objectives with MINIMIZE direction.\n"
                "-- Replace 'True' with the appropriate theorem statement.\n"
                "theorem objective_optimal :\n"
                "    True := by\n"
                "  sorry"
            )
        if objective.direction == ObjectiveDirection.MAXIMIZE:
            return (
                "-- Note: FormalConstruct does not derive optimization predicates\n"
                "-- for game-theory objectives with MAXIMIZE direction.\n"
                "-- Replace 'True' with the appropriate theorem statement.\n"
                "theorem objective_optimal :\n"
                "    True := by\n"
                "  sorry"
            )
        return (
            "-- Note: FormalConstruct does not derive optimization predicates\n"
            "-- for this game-theory objective direction.\n"
            "-- Replace 'True' with the appropriate theorem statement.\n"
            "theorem objective_statement :\n"
            "    True := by\n"
            "  sorry"
        )

    def _player_index_type(self) -> str:
        """Return Lean type for player index: 'Fin N' or 'Fin 2' etc."""
        if self._player_count is not None:
            return f"Fin {self._player_count}"
        return "Fin N"

    def _strategy_lean_type(self) -> str:
        """Return the Lean type of a single strategy from the first space."""
        if self._spaces:
            first_space = next(iter(self._spaces.values()))
            return _lean_type_for_space(first_space)
        return "ℝ"

    def _is_game_utility_function(self, func: Function) -> bool:
        """Return True if func should be typed as a game-theory utility function.

        A function is a utility function only when the mapper has an explicit
        game-theory context via player_count being set.  This avoids giving
        non-game functions the utility type signature when spaces happen to be
        cached from set_context.
        """
        if not self._spaces:
            return False
        return self._player_count is not None

    def _emit_game_utility(self, func: Function) -> str:
        """Emit a game-theory utility function variable.

        No property hypotheses are emitted: a utility's type is
        ``profile_product → ℝ`` (heterogeneous) or ``player → profile → ℝ``
        (homogeneous), neither of which is the scalar ``S → ℝ`` shape that
        Mathlib predicates such as ``ContinuousOn u S`` require — emitting them
        would produce type-invalid Lean."""
        if self._strategy_spaces is not None and self._player_count is not None:
            types = []
            for i in range(self._player_count):
                space_name = self._strategy_spaces[str(i)]
                space = self._spaces.get(space_name)
                types.append(_lean_type_for_space(space) if space else "ℝ")
            product_type = " × ".join(types) if len(types) > 1 else types[0]
            return f"variable ({func.symbol} : {product_type} → ℝ)"
        player_type = self._player_index_type()
        profile_type = f"{player_type} → {self._strategy_lean_type()}"
        type_sig = f"{player_type} → ({profile_type}) → ℝ"
        return f"variable ({func.symbol} : {type_sig})"

    def _emit_heterogeneous_nash(self, spec: ProblemSpec) -> str:
        """Nash equilibrium with per-player strategy spaces (product type).

        For 2-player games, generates deviations as explicit tuple
        reconstruction instead of Function.update.
        """
        n = spec.player_count
        if n is None or spec.strategy_spaces is None:
            raise ScaffoldingError(
                "Heterogeneous Nash equilibrium requires player_count and strategy_spaces"
            )

        profile_var = next(
            (v for v in spec.variables
             if v.classification == VariableClassification.STRATEGY_PROFILE),
            None,
        )
        profile_name = profile_var.symbol if profile_var else "profile"

        missing_keys = [str(i) for i in range(n) if str(i) not in spec.strategy_spaces]
        if missing_keys:
            raise ScaffoldingError(
                f"strategy_spaces missing expected keys: {missing_keys}"
            )
        spaces_ordered = [spec.strategy_spaces[str(i)] for i in range(n)]

        # Build per-player utility functions
        utility_funcs = [f for f in spec.functions if f.domain]
        if len(utility_funcs) < n:
            raise ScaffoldingError(
                f"Heterogeneous Nash equilibrium with {n} players requires "
                f"at least {n} utility functions, got {len(utility_funcs)}"
            )

        # Build feasibility hypothesis
        projections = _tuple_projections(profile_name, n)
        feasibility_parts = [
            f"{projections[i]} ∈ {spaces_ordered[i]}" for i in range(n)
        ]
        feasibility = " ∧ ".join(feasibility_parts)

        # Build per-player deviation clauses
        deviation_clauses: list[str] = []
        for i in range(n):
            dev_var = f"s_{i}'"
            deviated = _build_deviated_profile(
                profile_name, projections, i, dev_var, n,
            )
            u_name = utility_funcs[i].symbol if i < len(utility_funcs) else f"u_{i}"
            deviation_clauses.append(
                f"    (∀ {dev_var} ∈ {spaces_ordered[i]}, "
                f"{u_name} {profile_name} ≥ {u_name} {deviated})"
            )

        lines: list[str] = [
            "theorem nash_equilibrium :",
            f"    ({feasibility}) →",
            " ∧\n".join(deviation_clauses) + " := by",
            "  sorry",
        ]
        return "\n".join(lines)

    def _emit_nash_equilibrium(self, spec: ProblemSpec) -> str:
        """Emit the Nash equilibrium predicate theorem."""
        player_type = self._player_index_type()
        strategy_set = spec.spaces[0].name if spec.spaces else "S"

        profile_var = next(
            (v for v in spec.variables
             if v.classification == VariableClassification.STRATEGY_PROFILE),
            None,
        )
        profile_name = profile_var.symbol if profile_var else "profile"

        utility_funcs = [f for f in spec.functions if f.domain]
        u_name = utility_funcs[0].symbol if utility_funcs else "u"

        lines: list[str] = [
            "theorem nash_equilibrium :",
            f"    ∀ i : {player_type}, ∀ s_i' ∈ {strategy_set},",
            f"      {u_name} i {profile_name} ≥ {u_name} i (Function.update {profile_name} i s_i') := by",
            "  sorry",
        ]
        return "\n".join(lines)

    def _emit_pareto_optimality(self, spec: ProblemSpec) -> str:
        """Emit the Pareto optimality predicate theorem."""
        player_type = self._player_index_type()
        strategy_set = spec.spaces[0].name if spec.spaces else "S"
        strategy_lean_type = _lean_type_for_space(spec.spaces[0]) if spec.spaces else "ℝ"
        profile_type = f"{player_type} → {strategy_lean_type}"

        profile_var = next(
            (v for v in spec.variables
             if v.classification == VariableClassification.STRATEGY_PROFILE),
            None,
        )
        profile_name = profile_var.symbol if profile_var else "profile"

        utility_funcs = [f for f in spec.functions if f.domain]
        u_name = utility_funcs[0].symbol if utility_funcs else "u"

        lines: list[str] = [
            "theorem pareto_optimal :",
            f"    ¬∃ profile' : {profile_type},",
            f"      (∀ j, profile' j ∈ {strategy_set}) ∧",
            f"      (∀ i : {player_type}, {u_name} i profile' ≥ {u_name} i {profile_name}) ∧",
            f"      (∃ i : {player_type}, {u_name} i profile' > {u_name} i {profile_name}) := by",
            "  sorry",
        ]
        return "\n".join(lines)

    def _resolve_type(self, name: str) -> str:
        """Resolve a domain/codomain name to its Lean type string."""
        if name in self._spaces:
            return _lean_type_for_space(self._spaces[name])
        if name == "Real":
            return "ℝ"
        return "ℝ"

    def map_bounds(self, var: Variable) -> str:
        if var.bounds is None:
            return "Set.univ"
        lb = var.bounds.lower_bound
        ub = var.bounds.upper_bound
        strict = var.bounds.strict_inequality

        has_lower = lb is not None
        has_upper = ub is not None

        if has_lower and has_upper:
            if strict:
                return f"Set.Ioo {lb} {ub}"
            return f"Set.Icc {lb} {ub}"
        if has_lower:
            if strict:
                return f"Set.Ioi {lb}"
            return f"Set.Ici {lb}"
        if has_upper:
            if strict:
                return f"Set.Iio {ub}"
            return f"Set.Iic {ub}"
        return "Set.univ"
