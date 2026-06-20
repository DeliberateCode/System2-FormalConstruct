"""Unit tests for ContinuousOptMapper and related helpers."""

import pytest
from pydantic import ValidationError

from formalconstruct.core.exceptions import ScaffoldingError
from formalconstruct.domains.continuous_opt_mapper import (
    ContinuousOptMapper,
    _check_expression_convexity_safe,
    _derive_theorem_predicate,
    _expression_to_lean_body,
    _lean_type_for_space,
)
from formalconstruct.domains.registry import _tuple_projections
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

from tests.unit.conftest import _make_continuous_opt_spec


# ---------------------------------------------------------------------------
# ContinuousOptMapper tests
# ---------------------------------------------------------------------------


class TestContinuousOptMapper:

    def test_domain_name(self):
        assert ContinuousOptMapper().domain_name == "continuous_optimization"

    def test_required_imports_base(self):
        spec = _make_continuous_opt_spec()
        imports = ContinuousOptMapper().required_imports(spec)
        assert len(imports) >= 1
        assert any("Mathlib" in i for i in imports)

    @pytest.mark.parametrize("lower,upper,strict,expected", [
        ("0", None, False, "Set.Ici 0"),
        ("0", None, True, "Set.Ioi 0"),
        (None, "1", False, "Set.Iic 1"),
        (None, "1", True, "Set.Iio 1"),
        ("0", "1", False, "Set.Icc 0 1"),
        ("0", "1", True, "Set.Ioo 0 1"),
        (None, None, False, "Set.univ"),
    ])
    def test_map_bounds(self, lower, upper, strict, expected):
        has_bounds = lower is not None or upper is not None
        var = Variable(
            symbol="x",
            classification=VariableClassification.ENDOGENOUS,
            space_reference="S",
            bounds=VariableBounds(
                lower_bound=lower, upper_bound=upper, strict_inequality=strict,
            ) if has_bounds else None,
        )
        result = ContinuousOptMapper().map_bounds(var)
        assert result == expected

    def test_map_function_strict_convex(self):
        func = Function(
            symbol="f",
            domain=["S"],
            codomain="Real",
            properties=[FunctionProperty.STRICT_CONVEX],
        )
        result = ContinuousOptMapper().map_function(func)
        assert "StrictConvexOn" in result
        assert "f" in result

    def test_map_function_continuous(self):
        func = Function(
            symbol="g",
            domain=["S"],
            codomain="Real",
            properties=[FunctionProperty.CONTINUOUS],
        )
        result = ContinuousOptMapper().map_function(func)
        assert "ContinuousOn" in result
        assert "g" in result

    def test_map_function_linear(self):
        func = Function(
            symbol="h",
            domain=["S"],
            codomain="Real",
            properties=[FunctionProperty.LINEAR],
        )
        result = ContinuousOptMapper().map_function(func)
        assert "ConvexOn" in result

    def test_map_function_multiple_properties(self):
        func = Function(
            symbol="f",
            domain=["S"],
            codomain="Real",
            properties=[FunctionProperty.CONVEX, FunctionProperty.DIFFERENTIABLE],
        )
        result = ContinuousOptMapper().map_function(func)
        assert "ConvexOn" in result
        assert "DifferentiableOn" in result

    def test_map_objective_minimize(self):
        spec = _make_continuous_opt_spec()
        result = ContinuousOptMapper().map_objective(spec.objective, spec)
        assert "theorem" in result
        assert "StrictConvexOn" in result
        assert "sorry" in result

    def test_map_objective_maximize(self):
        spec = _make_continuous_opt_spec(
            functions=[
                Function(
                    symbol="f",
                    domain=["S"],
                    codomain="Real",
                    properties=[FunctionProperty.STRICT_CONCAVE],
                )
            ],
            objective=Objective(direction=ObjectiveDirection.MAXIMIZE, expression_latex="f(x)"),
        )
        result = ContinuousOptMapper().map_objective(spec.objective, spec)
        assert "StrictConcaveOn" in result
        assert "sorry" in result

    def test_map_objective_minimize_convex_only(self):
        """MINIMIZE with Convex-only functions should produce ConvexOn."""
        spec = _make_continuous_opt_spec(
            functions=[
                Function(symbol="f", domain=["S"], codomain="Real",
                         properties=[FunctionProperty.CONVEX]),
            ],
        )
        result = ContinuousOptMapper().map_objective(spec.objective, spec)
        assert "ConvexOn" in result
        assert "minimize_x_convexon" in result
        assert "sorry" in result

    def test_map_objective_minimize_mixed_strict_and_convex(self):
        """MINIMIZE with a mix of StrictConvex and Convex in the expression should produce ConvexOn."""
        spec = _make_continuous_opt_spec(
            functions=[
                Function(symbol="f", domain=["S"], codomain="Real",
                         properties=[FunctionProperty.STRICT_CONVEX]),
                Function(symbol="g", domain=["S"], codomain="Real",
                         properties=[FunctionProperty.CONVEX]),
            ],
            objective=Objective(
                direction=ObjectiveDirection.MINIMIZE,
                expression_latex="f(x) + g(x)",
            ),
        )
        result = ContinuousOptMapper().map_objective(spec.objective, spec)
        assert "ConvexOn" in result
        assert "minimize_x_convexon" in result

    def test_map_objective_minimize_linear_counts_as_convex(self):
        """MINIMIZE with Linear-only functions should produce ConvexOn."""
        spec = _make_continuous_opt_spec(
            functions=[
                Function(symbol="f", domain=["S"], codomain="Real",
                         properties=[FunctionProperty.LINEAR]),
            ],
        )
        result = ContinuousOptMapper().map_objective(spec.objective, spec)
        assert "ConvexOn" in result

    def test_map_objective_minimize_no_convexity_raises(self):
        """MINIMIZE with only Continuous properties should raise ScaffoldingError."""
        spec = _make_continuous_opt_spec(
            functions=[
                Function(symbol="f", domain=["S"], codomain="Real",
                         properties=[FunctionProperty.CONTINUOUS]),
            ],
        )
        with pytest.raises(ScaffoldingError, match="No convexity property"):
            ContinuousOptMapper().map_objective(spec.objective, spec)

    def test_map_objective_maximize_concave_only(self):
        """MAXIMIZE with Concave-only functions should produce ConcaveOn."""
        spec = _make_continuous_opt_spec(
            functions=[
                Function(symbol="f", domain=["S"], codomain="Real",
                         properties=[FunctionProperty.CONCAVE]),
            ],
            objective=Objective(direction=ObjectiveDirection.MAXIMIZE, expression_latex="f(x)"),
        )
        result = ContinuousOptMapper().map_objective(spec.objective, spec)
        assert "ConcaveOn" in result
        assert "maximize_x_concaveon" in result

    def test_map_objective_maximize_no_concavity_raises(self):
        """MAXIMIZE with only convex functions should raise ScaffoldingError."""
        spec = _make_continuous_opt_spec(
            functions=[
                Function(symbol="f", domain=["S"], codomain="Real",
                         properties=[FunctionProperty.STRICT_CONVEX]),
            ],
            objective=Objective(direction=ObjectiveDirection.MAXIMIZE, expression_latex="f(x)"),
        )
        with pytest.raises(ScaffoldingError, match="No concavity property"):
            ContinuousOptMapper().map_objective(spec.objective, spec)

    # -- set_context and dynamic type signatures --

    def test_set_context_caches_spaces(self):
        mapper = ContinuousOptMapper()
        spec = _make_continuous_opt_spec()
        mapper.set_context(spec)
        assert "S" in mapper._spaces

    def test_map_function_no_context_fallback(self):
        """Without set_context, map_function falls back to R -> R."""
        func = Function(
            symbol="f", domain=["S"], codomain="Real",
            properties=[FunctionProperty.STRICT_CONVEX],
        )
        mapper = ContinuousOptMapper()
        result = mapper.map_function(func)
        assert "variable (f : ℝ → ℝ)" in result

    def test_map_function_real_space_backward_compat(self):
        """REAL space + 'Real' codomain must still produce R -> R."""
        mapper = ContinuousOptMapper()
        spec = _make_continuous_opt_spec()
        mapper.set_context(spec)
        func = Function(
            symbol="f", domain=["S"], codomain="Real",
            properties=[FunctionProperty.STRICT_CONVEX],
        )
        result = mapper.map_function(func)
        assert "variable (f : ℝ → ℝ)" in result

    def test_map_function_nonneg_real_domain(self):
        mapper = ContinuousOptMapper()
        spec = _make_continuous_opt_spec(
            spaces=[Space(name="S", base_type=BaseType.NONNEG_REAL)],
        )
        mapper.set_context(spec)
        func = Function(
            symbol="f", domain=["S"], codomain="Real",
            properties=[FunctionProperty.CONVEX],
        )
        result = mapper.map_function(func)
        assert "variable (f : ℝ → ℝ)" in result

    def test_map_function_real_n_domain(self):
        mapper = ContinuousOptMapper()
        spec = _make_continuous_opt_spec(
            spaces=[Space(name="S", base_type=BaseType.REAL_N)],
        )
        mapper.set_context(spec)
        func = Function(
            symbol="f", domain=["S"], codomain="Real",
            properties=[],
        )
        result = mapper.map_function(func)
        assert "EuclideanSpace ℝ (Fin n)" in result

    def test_map_function_pos_real_maps_to_r(self):
        mapper = ContinuousOptMapper()
        spec = _make_continuous_opt_spec(
            spaces=[Space(name="S", base_type=BaseType.POS_REAL)],
        )
        mapper.set_context(spec)
        func = Function(
            symbol="f", domain=["S"], codomain="Real",
            properties=[],
        )
        result = mapper.map_function(func)
        assert "variable (f : ℝ → ℝ)" in result

    def test_map_function_multiple_domains_curried_type(self):
        mapper = ContinuousOptMapper()
        spec = _make_continuous_opt_spec(
            spaces=[
                Space(name="A", base_type=BaseType.REAL),
                Space(name="B", base_type=BaseType.NONNEG_REAL),
            ],
            variables=[
                Variable(
                    symbol="x",
                    classification=VariableClassification.ENDOGENOUS,
                    space_reference="A",
                    bounds=VariableBounds(lower_bound="0", strict_inequality=False),
                )
            ],
            functions=[
                Function(symbol="f", domain=["A", "B"], codomain="Real",
                         properties=[FunctionProperty.CONTINUOUS]),
            ],
            objective=Objective(
                direction=ObjectiveDirection.MINIMIZE,
                expression_latex="f(x, x)",
            ),
        )
        mapper.set_context(spec)
        func = Function(
            symbol="f", domain=["A", "B"], codomain="Real",
            properties=[],
        )
        result = mapper.map_function(func)
        assert "variable (f : ℝ → ℝ → ℝ)" in result

    def test_map_function_codomain_from_space(self):
        mapper = ContinuousOptMapper()
        spec = _make_continuous_opt_spec(
            spaces=[
                Space(name="A", base_type=BaseType.REAL),
                Space(name="B", base_type=BaseType.NONNEG_REAL),
            ],
            variables=[
                Variable(
                    symbol="x",
                    classification=VariableClassification.ENDOGENOUS,
                    space_reference="A",
                    bounds=VariableBounds(lower_bound="0", strict_inequality=False),
                )
            ],
            functions=[
                Function(symbol="f", domain=["A"], codomain="B",
                         properties=[FunctionProperty.CONTINUOUS]),
            ],
        )
        mapper.set_context(spec)
        func = Function(
            symbol="f", domain=["A"], codomain="B",
            properties=[],
        )
        result = mapper.map_function(func)
        assert "variable (f : ℝ → ℝ)" in result

    def test_map_function_unknown_domain_fallback(self):
        """Domain referencing unknown space falls back to R."""
        mapper = ContinuousOptMapper()
        spec = _make_continuous_opt_spec()
        mapper.set_context(spec)
        func = Function(
            symbol="f", domain=["Unknown"], codomain="Real",
            properties=[],
        )
        result = mapper.map_function(func)
        assert "variable (f : ℝ → ℝ)" in result


# ---------------------------------------------------------------------------
# _derive_theorem_predicate tests
# ---------------------------------------------------------------------------


class TestDeriveTheoremPredicate:

    def test_all_strict_convex_minimize(self):
        funcs = [
            Function(symbol="f", domain=["S"], codomain="Real",
                     properties=[FunctionProperty.STRICT_CONVEX]),
        ]
        assert _derive_theorem_predicate(funcs, ObjectiveDirection.MINIMIZE) == "StrictConvexOn"

    def test_mixed_strict_convex_and_convex_minimize(self):
        funcs = [
            Function(symbol="f", domain=["S"], codomain="Real",
                     properties=[FunctionProperty.STRICT_CONVEX]),
            Function(symbol="g", domain=["S"], codomain="Real",
                     properties=[FunctionProperty.CONVEX]),
        ]
        assert _derive_theorem_predicate(funcs, ObjectiveDirection.MINIMIZE) == "ConvexOn"

    def test_linear_implies_convex_minimize(self):
        funcs = [
            Function(symbol="f", domain=["S"], codomain="Real",
                     properties=[FunctionProperty.LINEAR]),
        ]
        assert _derive_theorem_predicate(funcs, ObjectiveDirection.MINIMIZE) == "ConvexOn"

    def test_strict_convex_plus_linear_minimize(self):
        funcs = [
            Function(symbol="f", domain=["S"], codomain="Real",
                     properties=[FunctionProperty.STRICT_CONVEX]),
            Function(symbol="g", domain=["S"], codomain="Real",
                     properties=[FunctionProperty.LINEAR]),
        ]
        assert _derive_theorem_predicate(funcs, ObjectiveDirection.MINIMIZE) == "StrictConvexOn"

    def test_no_convexity_minimize_raises(self):
        funcs = [
            Function(symbol="f", domain=["S"], codomain="Real",
                     properties=[FunctionProperty.CONTINUOUS]),
        ]
        with pytest.raises(ScaffoldingError, match="No convexity property.*f"):
            _derive_theorem_predicate(funcs, ObjectiveDirection.MINIMIZE)

    def test_all_strict_concave_maximize(self):
        funcs = [
            Function(symbol="f", domain=["S"], codomain="Real",
                     properties=[FunctionProperty.STRICT_CONCAVE]),
        ]
        assert _derive_theorem_predicate(funcs, ObjectiveDirection.MAXIMIZE) == "StrictConcaveOn"

    def test_concave_only_maximize(self):
        funcs = [
            Function(symbol="f", domain=["S"], codomain="Real",
                     properties=[FunctionProperty.CONCAVE]),
        ]
        assert _derive_theorem_predicate(funcs, ObjectiveDirection.MAXIMIZE) == "ConcaveOn"

    def test_no_concavity_maximize_raises(self):
        funcs = [
            Function(symbol="f", domain=["S"], codomain="Real",
                     properties=[FunctionProperty.CONVEX]),
        ]
        with pytest.raises(ScaffoldingError, match="No concavity property.*f"):
            _derive_theorem_predicate(funcs, ObjectiveDirection.MAXIMIZE)

    def test_equilibrium_returns_none(self):
        funcs = [
            Function(symbol="f", domain=["S"], codomain="Real",
                     properties=[FunctionProperty.CONTINUOUS]),
        ]
        assert _derive_theorem_predicate(funcs, ObjectiveDirection.EQUILIBRIUM) is None

    def test_pareto_optimal_returns_none(self):
        funcs = [
            Function(symbol="f", domain=["S"], codomain="Real",
                     properties=[FunctionProperty.CONTINUOUS]),
        ]
        assert _derive_theorem_predicate(funcs, ObjectiveDirection.PARETO_OPTIMAL) is None


# ---------------------------------------------------------------------------
# _expression_to_lean_body tests
# ---------------------------------------------------------------------------


class TestExpressionToLeanBody:

    def test_single_function(self):
        result, _ = _expression_to_lean_body("CostCapital(x)", ["CostCapital"])
        assert result == "CostCapital x"

    def test_sum_of_two_functions(self):
        result, _ = _expression_to_lean_body(
            "CostCapital(x) + CostLabor(x)",
            ["CostCapital", "CostLabor"],
        )
        assert result == "CostCapital x + CostLabor x"

    def test_difference_of_functions(self):
        result, _ = _expression_to_lean_body(
            "CostCapital(x) - CostLabor(x)",
            ["CostCapital", "CostLabor"],
        )
        assert result == "CostCapital x - CostLabor x"

    def test_subset_of_func_symbols_used(self):
        """Only functions appearing in expression_latex are included."""
        result, _ = _expression_to_lean_body("f(x)", ["f", "g"])
        assert result == "f x"

    def test_different_variable_name(self):
        result, _ = _expression_to_lean_body("f(y)", ["f"])
        assert result == "f y"

    def test_empty_expression_raises(self):
        with pytest.raises(ScaffoldingError, match="expression_latex is empty"):
            _expression_to_lean_body("", ["f"])

    def test_whitespace_only_expression_raises(self):
        with pytest.raises(ScaffoldingError, match="expression_latex is empty"):
            _expression_to_lean_body("   ", ["f"])

    def test_no_recognized_symbols_raises(self):
        with pytest.raises(ScaffoldingError, match="no recognized function symbols"):
            _expression_to_lean_body("x + y", ["f", "g"])

    def test_backward_compat_canonical_example(self):
        """Canonical example must produce identical output."""
        result, _ = _expression_to_lean_body(
            "CostCapital(x) + CostLabor(x)",
            ["CostCapital", "CostLabor"],
        )
        assert result == "CostCapital x + CostLabor x"


# ---------------------------------------------------------------------------
# Contract tests: REAL_N and multi-domain type signatures
# ---------------------------------------------------------------------------


class TestCR008TypeSignatures:
    """Contract tests verifying ContinuousOptMapper supports REAL_N
    types and multi-domain function signatures via set_context()."""

    def test_real_space_produces_r_to_r(self):
        mapper = ContinuousOptMapper()
        spec = _make_continuous_opt_spec(
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
        )
        mapper.set_context(spec)
        func = spec.functions[0]
        result = mapper.map_function(func)
        assert "ℝ → ℝ" in result

    def test_real_n_space_produces_euclidean_signature(self):
        mapper = ContinuousOptMapper()
        spec = _make_continuous_opt_spec(
            spaces=[Space(name="S", base_type=BaseType.REAL_N)],
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
                )
            ],
        )
        mapper.set_context(spec)
        func = spec.functions[0]
        result = mapper.map_function(func)
        assert "EuclideanSpace" in result
        assert "ℝ → ℝ" not in result

    def test_multiple_domain_entries_curried_type(self):
        mapper = ContinuousOptMapper()
        spec = _make_continuous_opt_spec(
            spaces=[
                Space(name="S1", base_type=BaseType.REAL),
                Space(name="S2", base_type=BaseType.REAL),
            ],
            variables=[
                Variable(
                    symbol="x",
                    classification=VariableClassification.ENDOGENOUS,
                    space_reference="S1",
                    bounds=VariableBounds(lower_bound="0", strict_inequality=False),
                )
            ],
            functions=[
                Function(
                    symbol="f",
                    domain=["S1", "S2"],
                    codomain="Real",
                    properties=[FunctionProperty.CONTINUOUS],
                )
            ],
            objective=Objective(
                direction=ObjectiveDirection.MINIMIZE,
                expression_latex="f(x, x)",
            ),
        )
        mapper.set_context(spec)
        func = spec.functions[0]
        result = mapper.map_function(func)
        assert "ℝ → ℝ → ℝ" in result

    def test_codomain_from_space(self):
        mapper = ContinuousOptMapper()
        spec = _make_continuous_opt_spec(
            spaces=[
                Space(name="Dom", base_type=BaseType.REAL),
                Space(name="Cod", base_type=BaseType.NONNEG_REAL),
            ],
            variables=[
                Variable(
                    symbol="x",
                    classification=VariableClassification.ENDOGENOUS,
                    space_reference="Dom",
                    bounds=VariableBounds(lower_bound="0", strict_inequality=False),
                )
            ],
            functions=[
                Function(
                    symbol="f",
                    domain=["Dom"],
                    codomain="Cod",
                    properties=[FunctionProperty.CONVEX],
                )
            ],
        )
        mapper.set_context(spec)
        func = spec.functions[0]
        result = mapper.map_function(func)
        assert "ℝ → ℝ" in result


# ---------------------------------------------------------------------------
# _lean_type_for_space and REAL_N handling
# ---------------------------------------------------------------------------


class TestLeanTypeForSpace:

    def test_real_returns_r(self):
        space = Space(name="S", base_type=BaseType.REAL)
        assert _lean_type_for_space(space) == "ℝ"

    def test_nonneg_real_returns_r(self):
        space = Space(name="S", base_type=BaseType.NONNEG_REAL)
        assert _lean_type_for_space(space) == "ℝ"

    def test_pos_real_returns_r(self):
        space = Space(name="S", base_type=BaseType.POS_REAL)
        assert _lean_type_for_space(space) == "ℝ"

    def test_real_n_no_dimension_returns_fin_n(self):
        space = Space(name="S", base_type=BaseType.REAL_N)
        assert _lean_type_for_space(space) == "EuclideanSpace ℝ (Fin n)"

    def test_real_n_with_dimension_returns_fin_literal(self):
        space = Space(name="S", base_type=BaseType.REAL_N, dimension=3)
        assert _lean_type_for_space(space) == "EuclideanSpace ℝ (Fin 3)"

    def test_real_n_dimension_10(self):
        space = Space(name="S", base_type=BaseType.REAL_N, dimension=10)
        assert _lean_type_for_space(space) == "EuclideanSpace ℝ (Fin 10)"

    def test_int_returns_z(self):
        space = Space(name="S", base_type=BaseType.INT)
        assert _lean_type_for_space(space) == "ℤ"

    def test_nat_returns_n(self):
        space = Space(name="S", base_type=BaseType.NAT)
        assert _lean_type_for_space(space) == "ℕ"

    def test_bool_returns_bool(self):
        space = Space(name="S", base_type=BaseType.BOOL)
        assert _lean_type_for_space(space) == "Bool"


class TestRealNBoundsRejection:

    def test_real_n_with_lower_bound_raises(self):
        mapper = ContinuousOptMapper()
        spec = _make_continuous_opt_spec(
            spaces=[Space(name="S", base_type=BaseType.REAL_N)],
            variables=[
                Variable(
                    symbol="w",
                    classification=VariableClassification.ENDOGENOUS,
                    space_reference="S",
                    bounds=VariableBounds(lower_bound="0"),
                )
            ],
            objective=Objective(direction=ObjectiveDirection.MINIMIZE, expression_latex="f(w)"),
        )
        mapper.set_context(spec)
        var = spec.variables[0]
        with pytest.raises(ScaffoldingError, match="bounds on a REAL_N space"):
            mapper.map_bounds(var)

    def test_real_n_with_upper_bound_raises(self):
        mapper = ContinuousOptMapper()
        spec = _make_continuous_opt_spec(
            spaces=[Space(name="S", base_type=BaseType.REAL_N)],
            variables=[
                Variable(
                    symbol="w",
                    classification=VariableClassification.ENDOGENOUS,
                    space_reference="S",
                    bounds=VariableBounds(upper_bound="10"),
                )
            ],
            objective=Objective(direction=ObjectiveDirection.MINIMIZE, expression_latex="f(w)"),
        )
        mapper.set_context(spec)
        var = spec.variables[0]
        with pytest.raises(ScaffoldingError, match="bounds on a REAL_N space"):
            mapper.map_bounds(var)

    def test_real_n_no_bounds_passes(self):
        mapper = ContinuousOptMapper()
        spec = _make_continuous_opt_spec(
            spaces=[Space(name="S", base_type=BaseType.REAL_N)],
            variables=[
                Variable(
                    symbol="w",
                    classification=VariableClassification.ENDOGENOUS,
                    space_reference="S",
                )
            ],
            objective=Objective(direction=ObjectiveDirection.MINIMIZE, expression_latex="f(w)"),
        )
        mapper.set_context(spec)
        var = spec.variables[0]
        result = mapper.map_bounds(var)
        assert result == "Set.univ"

    def test_real_bounds_still_work(self):
        mapper = ContinuousOptMapper()
        spec = _make_continuous_opt_spec()
        mapper.set_context(spec)
        var = spec.variables[0]
        result = mapper.map_bounds(var)
        assert result == "Set.Ici 0"


class TestRealNObjectiveDomainDef:

    def test_real_n_domain_def_uses_euclidean_type(self):
        mapper = ContinuousOptMapper()
        spec = _make_continuous_opt_spec(
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
        result = mapper.map_objective(spec.objective, spec)
        assert "Set (EuclideanSpace" in result
        assert "Set ℝ" not in result

    def test_real_domain_def_still_uses_set_r(self):
        spec = _make_continuous_opt_spec()
        result = ContinuousOptMapper().map_objective(spec.objective, spec)
        assert "Set ℝ" in result


class TestMapFunctionNoDimVar:

    def test_real_n_no_dim_variable_emitted(self):
        mapper = ContinuousOptMapper()
        spec = _make_continuous_opt_spec(
            spaces=[Space(name="S", base_type=BaseType.REAL_N)],
        )
        mapper.set_context(spec)
        func = Function(
            symbol="f", domain=["S"], codomain="Real",
            properties=[],
        )
        result = mapper.map_function(func)
        assert "variable (n : ℕ)" not in result
        assert "variable (f :" in result


# ---------------------------------------------------------------------------
# REAL_N Domain Contract Tests
# ---------------------------------------------------------------------------


class TestF19LeanTypeForSpaceDimension:

    def test_lean_type_for_space_concrete_dimension(self):
        space = Space(name="S", base_type=BaseType.REAL_N, dimension=3)
        result = _lean_type_for_space(space)
        assert result == "EuclideanSpace ℝ (Fin 3)"

    def test_lean_type_for_space_generic_dimension(self):
        space = Space(name="S", base_type=BaseType.REAL_N, dimension=None)
        result = _lean_type_for_space(space)
        assert result == "EuclideanSpace ℝ (Fin n)"


class TestF19RealNBoundsContract:

    def test_real_n_bounds_rejection(self):
        mapper = ContinuousOptMapper()
        spec = _make_continuous_opt_spec(
            spaces=[Space(name="S", base_type=BaseType.REAL_N)],
            variables=[
                Variable(
                    symbol="w",
                    classification=VariableClassification.ENDOGENOUS,
                    space_reference="S",
                    bounds=VariableBounds(lower_bound="0"),
                )
            ],
            objective=Objective(direction=ObjectiveDirection.MINIMIZE, expression_latex="f(w)"),
        )
        mapper.set_context(spec)
        var = spec.variables[0]
        with pytest.raises(ScaffoldingError, match="bounds on a REAL_N space"):
            mapper.map_bounds(var)

    def test_real_n_no_bounds_returns_set_univ(self):
        mapper = ContinuousOptMapper()
        spec = _make_continuous_opt_spec(
            spaces=[Space(name="S", base_type=BaseType.REAL_N)],
            variables=[
                Variable(
                    symbol="w",
                    classification=VariableClassification.ENDOGENOUS,
                    space_reference="S",
                )
            ],
            objective=Objective(direction=ObjectiveDirection.MINIMIZE, expression_latex="f(w)"),
        )
        mapper.set_context(spec)
        var = spec.variables[0]
        result = mapper.map_bounds(var)
        assert result == "Set.univ"


class TestF19RealNObjectiveDomainContract:

    def test_real_n_domain_def_in_objective(self):
        mapper = ContinuousOptMapper()
        spec = _make_continuous_opt_spec(
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
        result = mapper.map_objective(spec.objective, spec)
        assert "Set (EuclideanSpace" in result
        assert "Set ℝ" not in result


class TestF19RealNConvexityLemma:

    def test_real_n_convexity_lemma_uses_convex_univ(self):
        mapper = ContinuousOptMapper()
        spec = _make_continuous_opt_spec(
            spaces=[Space(name="VectorDomain", base_type=BaseType.REAL_N)],
            variables=[
                Variable(
                    symbol="v",
                    classification=VariableClassification.ENDOGENOUS,
                    space_reference="VectorDomain",
                )
            ],
            functions=[
                Function(
                    symbol="Cost",
                    domain=["VectorDomain"],
                    codomain="Real",
                    properties=[FunctionProperty.CONVEX],
                )
            ],
            objective=Objective(
                direction=ObjectiveDirection.MINIMIZE,
                expression_latex="Cost(v)",
            ),
        )
        result = mapper.map_objective(spec.objective, spec)
        assert "convex_univ" in result


class TestF19MixedRealAndRealNSpaces:

    def test_mixed_real_and_real_n_spaces(self):
        mapper = ContinuousOptMapper()
        spec = _make_continuous_opt_spec(
            spaces=[
                Space(name="ScalarDomain", base_type=BaseType.REAL),
                Space(name="VectorDomain", base_type=BaseType.REAL_N, dimension=5),
            ],
            variables=[
                Variable(
                    symbol="x",
                    classification=VariableClassification.ENDOGENOUS,
                    space_reference="ScalarDomain",
                    bounds=VariableBounds(lower_bound="0", strict_inequality=False),
                )
            ],
            functions=[
                Function(
                    symbol="fScalar",
                    domain=["ScalarDomain"],
                    codomain="Real",
                    properties=[FunctionProperty.CONVEX],
                ),
                Function(
                    symbol="fVector",
                    domain=["VectorDomain"],
                    codomain="Real",
                    properties=[FunctionProperty.CONVEX],
                ),
            ],
            objective=Objective(
                direction=ObjectiveDirection.MINIMIZE,
                expression_latex="fScalar(x) + fVector(x)",
            ),
        )
        mapper.set_context(spec)

        func_scalar = spec.functions[0]
        result_scalar = mapper.map_function(func_scalar)
        assert "ℝ → ℝ" in result_scalar

        func_vector = spec.functions[1]
        result_vector = mapper.map_function(func_vector)
        assert "EuclideanSpace ℝ (Fin 5)" in result_vector
        assert "ℝ → ℝ" not in result_vector


# ---------------------------------------------------------------------------
# Domain correlates to target variable's space
# ---------------------------------------------------------------------------


class TestDomainInfoTargetCorrelation:

    def test_domain_uses_target_variable_space(self):
        mapper = ContinuousOptMapper()
        spec = ProblemSpec(
            problem_domain=ProblemDomain.CONTINUOUS_OPTIMIZATION,
            spaces=[
                Space(name="X", base_type=BaseType.REAL),
                Space(name="Y", base_type=BaseType.REAL),
            ],
            variables=[
                Variable(
                    symbol="x",
                    classification=VariableClassification.ENDOGENOUS,
                    space_reference="X",
                ),
                Variable(
                    symbol="y",
                    classification=VariableClassification.ENDOGENOUS,
                    space_reference="Y",
                    bounds=VariableBounds(lower_bound="0", strict_inequality=False),
                ),
            ],
            functions=[
                Function(
                    symbol="f",
                    domain=["Y"],
                    codomain="Real",
                    properties=[FunctionProperty.STRICT_CONVEX],
                ),
            ],
            objective=Objective(
                direction=ObjectiveDirection.MINIMIZE,
                expression_latex="f(y)",
                target_variable="y",
            ),
        )
        mapper.set_context(spec)
        domain_name, domain_expr = mapper._domain_info(spec, target_var="y")
        assert domain_name == "Y"
        assert domain_expr == "Set.Ici 0"

    def test_domain_falls_back_to_first_space(self):
        mapper = ContinuousOptMapper()
        spec = ProblemSpec(
            problem_domain=ProblemDomain.CONTINUOUS_OPTIMIZATION,
            spaces=[
                Space(name="OnlySpace", base_type=BaseType.REAL),
            ],
            variables=[
                Variable(
                    symbol="x",
                    classification=VariableClassification.ENDOGENOUS,
                    space_reference="OnlySpace",
                    bounds=VariableBounds(lower_bound="1", strict_inequality=True),
                ),
            ],
            functions=[
                Function(
                    symbol="f",
                    domain=["OnlySpace"],
                    codomain="Real",
                    properties=[FunctionProperty.CONVEX],
                ),
            ],
            objective=Objective(
                direction=ObjectiveDirection.MINIMIZE,
                expression_latex="f(x)",
            ),
        )
        mapper.set_context(spec)
        domain_name, domain_expr = mapper._domain_info(spec)
        assert domain_name == "OnlySpace"
        assert "Set." in domain_expr


# ---------------------------------------------------------------------------
# Multi-variable optimization tests
# ---------------------------------------------------------------------------


class TestProjectionBuilder:

    def test_single_variable(self):
        assert _tuple_projections("p", 1) == ["p"]

    def test_two_variables(self):
        assert _tuple_projections("p", 2) == ["p.1", "p.2"]

    def test_three_variables(self):
        assert _tuple_projections("p", 3) == ["p.1", "p.2.1", "p.2.2"]

    def test_four_variables(self):
        assert _tuple_projections("p", 4) == ["p.1", "p.2.1", "p.2.2.1", "p.2.2.2"]

    def test_five_variables(self):
        assert _tuple_projections("p", 5) == ["p.1", "p.2.1", "p.2.2.1", "p.2.2.2.1", "p.2.2.2.2"]


class TestMultiVariableBinding:

    def test_two_variable_product_binding(self):
        mapper = ContinuousOptMapper()
        spec = ProblemSpec(
            problem_domain=ProblemDomain.CONTINUOUS_OPTIMIZATION,
            spaces=[
                Space(name="PriceSpace", base_type=BaseType.REAL),
                Space(name="QuantitySpace", base_type=BaseType.REAL),
            ],
            variables=[
                Variable(
                    symbol="p",
                    classification=VariableClassification.ENDOGENOUS,
                    space_reference="PriceSpace",
                    bounds=VariableBounds(lower_bound="0", strict_inequality=False),
                ),
                Variable(
                    symbol="q",
                    classification=VariableClassification.ENDOGENOUS,
                    space_reference="QuantitySpace",
                    bounds=VariableBounds(lower_bound="0", strict_inequality=True),
                ),
            ],
            functions=[
                Function(
                    symbol="C",
                    domain=["PriceSpace"],
                    codomain="Real",
                    properties=[FunctionProperty.STRICT_CONVEX],
                ),
                Function(
                    symbol="D",
                    domain=["QuantitySpace"],
                    codomain="Real",
                    properties=[FunctionProperty.CONVEX],
                ),
            ],
            objective=Objective(
                direction=ObjectiveDirection.MINIMIZE,
                expression_latex="C(p) + D(q)",
                target_variable="p",
            ),
        )
        mapper.set_context(spec)
        result = mapper.map_objective(spec.objective, spec)
        assert "fun p =>" in result
        assert "p.1" in result
        assert "p.2" in result
        assert "PriceSpace" in result
        assert "QuantitySpace" in result

    def test_product_domain_notation(self):
        mapper = ContinuousOptMapper()
        spec = ProblemSpec(
            problem_domain=ProblemDomain.CONTINUOUS_OPTIMIZATION,
            spaces=[
                Space(name="DomainX", base_type=BaseType.REAL),
                Space(name="DomainY", base_type=BaseType.REAL),
            ],
            variables=[
                Variable(
                    symbol="x",
                    classification=VariableClassification.ENDOGENOUS,
                    space_reference="DomainX",
                    bounds=VariableBounds(lower_bound="0", strict_inequality=False),
                ),
                Variable(
                    symbol="y",
                    classification=VariableClassification.ENDOGENOUS,
                    space_reference="DomainY",
                ),
            ],
            functions=[
                Function(
                    symbol="f",
                    domain=["DomainX"],
                    codomain="Real",
                    properties=[FunctionProperty.CONVEX],
                ),
                Function(
                    symbol="g",
                    domain=["DomainY"],
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
        mapper.set_context(spec)
        result = mapper.map_objective(spec.objective, spec)
        assert "DomainX" in result
        assert "DomainY" in result

    def test_single_variable_backward_compat(self):
        spec = _make_continuous_opt_spec()
        result = ContinuousOptMapper().map_objective(spec.objective, spec)
        assert "fun x =>" in result
        assert "p.1" not in result
        assert "p.2" not in result
        assert "StrictConvexOn" in result

    def test_two_variable_theorem_predicate(self):
        mapper = ContinuousOptMapper()
        spec = ProblemSpec(
            problem_domain=ProblemDomain.CONTINUOUS_OPTIMIZATION,
            spaces=[
                Space(name="A", base_type=BaseType.REAL),
                Space(name="B", base_type=BaseType.REAL),
            ],
            variables=[
                Variable(
                    symbol="x",
                    classification=VariableClassification.ENDOGENOUS,
                    space_reference="A",
                ),
                Variable(
                    symbol="y",
                    classification=VariableClassification.ENDOGENOUS,
                    space_reference="B",
                ),
            ],
            functions=[
                Function(
                    symbol="f",
                    domain=["A"],
                    codomain="Real",
                    properties=[FunctionProperty.STRICT_CONVEX],
                ),
                Function(
                    symbol="g",
                    domain=["B"],
                    codomain="Real",
                    properties=[FunctionProperty.STRICT_CONVEX],
                ),
            ],
            objective=Objective(
                direction=ObjectiveDirection.MINIMIZE,
                expression_latex="f(x) + g(y)",
                target_variable="x",
            ),
        )
        mapper.set_context(spec)
        result = mapper.map_objective(spec.objective, spec)
        assert "StrictConvexOn" in result
        assert "sorry" in result

    def test_convexity_lemma_in_product_domain(self):
        mapper = ContinuousOptMapper()
        spec = ProblemSpec(
            problem_domain=ProblemDomain.CONTINUOUS_OPTIMIZATION,
            spaces=[
                Space(name="A", base_type=BaseType.REAL),
                Space(name="B", base_type=BaseType.REAL),
            ],
            variables=[
                Variable(
                    symbol="x",
                    classification=VariableClassification.ENDOGENOUS,
                    space_reference="A",
                    bounds=VariableBounds(lower_bound="0", strict_inequality=False),
                ),
                Variable(
                    symbol="y",
                    classification=VariableClassification.ENDOGENOUS,
                    space_reference="B",
                ),
            ],
            functions=[
                Function(
                    symbol="f",
                    domain=["A"],
                    codomain="Real",
                    properties=[FunctionProperty.CONVEX],
                ),
                Function(
                    symbol="g",
                    domain=["B"],
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
        mapper.set_context(spec)
        result = mapper.map_objective(spec.objective, spec)
        assert "convex_domain" in result or "Convex" in result
        assert "sorry" in result


class TestMultiVariableErrors:

    def test_exogenous_variable_in_expression_allowed(self):
        mapper = ContinuousOptMapper()
        spec = ProblemSpec(
            problem_domain=ProblemDomain.CONTINUOUS_OPTIMIZATION,
            spaces=[
                Space(name="A", base_type=BaseType.REAL),
                Space(name="B", base_type=BaseType.REAL),
            ],
            variables=[
                Variable(
                    symbol="x",
                    classification=VariableClassification.ENDOGENOUS,
                    space_reference="A",
                    bounds=VariableBounds(lower_bound="0", strict_inequality=False),
                ),
                Variable(
                    symbol="y",
                    classification=VariableClassification.EXOGENOUS,
                    space_reference="B",
                ),
            ],
            functions=[
                Function(
                    symbol="f",
                    domain=["A"],
                    codomain="Real",
                    properties=[FunctionProperty.STRICT_CONVEX],
                ),
                Function(
                    symbol="g",
                    domain=["B"],
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
        mapper.set_context(spec)
        result = mapper.map_objective(spec.objective, spec)
        assert "fun x =>" in result
        assert "sorry" in result


# ---------------------------------------------------------------------------
# Discrete type mapper behavior
# ---------------------------------------------------------------------------


class TestDiscreteTypeMapFunction:

    def test_int_domain_skips_convexity_hypotheses(self):
        mapper = ContinuousOptMapper()
        spec = _make_continuous_opt_spec(
            spaces=[Space(name="S", base_type=BaseType.INT)],
            variables=[
                Variable(
                    symbol="n",
                    classification=VariableClassification.ENDOGENOUS,
                    space_reference="S",
                    bounds=VariableBounds(lower_bound="0"),
                ),
            ],
            functions=[
                Function(
                    symbol="cost",
                    domain=["S"],
                    codomain="Real",
                    properties=[FunctionProperty.STRICT_CONVEX, FunctionProperty.CONTINUOUS],
                ),
            ],
            objective=Objective(
                direction=ObjectiveDirection.MINIMIZE,
                expression_latex="cost(n)",
            ),
        )
        mapper.set_context(spec)
        result = mapper.map_function(spec.functions[0])
        assert "variable (cost : ℤ → ℝ)" in result
        assert "StrictConvexOn" not in result
        assert "ContinuousOn" not in result

    def test_nat_domain_skips_convexity_hypotheses(self):
        mapper = ContinuousOptMapper()
        spec = _make_continuous_opt_spec(
            spaces=[Space(name="S", base_type=BaseType.NAT)],
            variables=[
                Variable(
                    symbol="n",
                    classification=VariableClassification.ENDOGENOUS,
                    space_reference="S",
                ),
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
                expression_latex="f(n)",
            ),
        )
        mapper.set_context(spec)
        result = mapper.map_function(spec.functions[0])
        assert "variable (f : ℕ → ℝ)" in result
        assert "ConvexOn" not in result

    def test_bool_domain_skips_convexity_hypotheses(self):
        mapper = ContinuousOptMapper()
        spec = ProblemSpec(
            problem_domain=ProblemDomain.CONTINUOUS_OPTIMIZATION,
            spaces=[Space(name="S", base_type=BaseType.BOOL)],
            variables=[
                Variable(
                    symbol="b",
                    classification=VariableClassification.ENDOGENOUS,
                    space_reference="S",
                ),
            ],
            functions=[
                Function(
                    symbol="f",
                    domain=["S"],
                    codomain="Real",
                    properties=[FunctionProperty.CONTINUOUS],
                ),
            ],
            objective=Objective(
                direction=ObjectiveDirection.MINIMIZE,
                expression_latex="f(b)",
            ),
        )
        mapper.set_context(spec)
        result = mapper.map_function(spec.functions[0])
        assert "variable (f : Bool → ℝ)" in result
        assert "ContinuousOn" not in result

    def test_real_domain_still_emits_hypotheses(self):
        mapper = ContinuousOptMapper()
        spec = _make_continuous_opt_spec()
        mapper.set_context(spec)
        result = mapper.map_function(spec.functions[0])
        assert "StrictConvexOn" in result


class TestDiscreteTypeMapObjective:

    def test_int_target_emits_generic_theorem(self):
        mapper = ContinuousOptMapper()
        spec = _make_continuous_opt_spec(
            spaces=[Space(name="IntDomain", base_type=BaseType.INT)],
            variables=[
                Variable(
                    symbol="n",
                    classification=VariableClassification.ENDOGENOUS,
                    space_reference="IntDomain",
                    bounds=VariableBounds(lower_bound="0"),
                ),
            ],
            functions=[
                Function(
                    symbol="cost",
                    domain=["IntDomain"],
                    codomain="Real",
                    properties=[FunctionProperty.CONTINUOUS],
                ),
            ],
            objective=Objective(
                direction=ObjectiveDirection.MINIMIZE,
                expression_latex="cost(n)",
                target_variable="n",
            ),
        )
        mapper.set_context(spec)
        result = mapper.map_objective(spec.objective, spec)
        assert "objective_statement" in result
        assert "True := by" in result
        assert "sorry" in result
        assert "StrictConvexOn" not in result
        assert "ConvexOn" not in result

    def test_nat_target_emits_generic_theorem(self):
        mapper = ContinuousOptMapper()
        spec = _make_continuous_opt_spec(
            spaces=[Space(name="NatDomain", base_type=BaseType.NAT)],
            variables=[
                Variable(
                    symbol="k",
                    classification=VariableClassification.ENDOGENOUS,
                    space_reference="NatDomain",
                ),
            ],
            functions=[
                Function(
                    symbol="f",
                    domain=["NatDomain"],
                    codomain="Real",
                    properties=[FunctionProperty.CONVEX],
                ),
            ],
            objective=Objective(
                direction=ObjectiveDirection.MINIMIZE,
                expression_latex="f(k)",
                target_variable="k",
            ),
        )
        mapper.set_context(spec)
        result = mapper.map_objective(spec.objective, spec)
        assert "objective_statement" in result
        assert "True := by" in result
        assert "sorry" in result

    def test_int_domain_def_uses_set_z(self):
        mapper = ContinuousOptMapper()
        spec = _make_continuous_opt_spec(
            spaces=[Space(name="IntDomain", base_type=BaseType.INT)],
            variables=[
                Variable(
                    symbol="n",
                    classification=VariableClassification.ENDOGENOUS,
                    space_reference="IntDomain",
                    bounds=VariableBounds(lower_bound="0"),
                ),
            ],
            functions=[
                Function(
                    symbol="cost",
                    domain=["IntDomain"],
                    codomain="Real",
                    properties=[FunctionProperty.CONTINUOUS],
                ),
            ],
            objective=Objective(
                direction=ObjectiveDirection.MINIMIZE,
                expression_latex="cost(n)",
                target_variable="n",
            ),
        )
        mapper.set_context(spec)
        result = mapper.map_objective(spec.objective, spec)
        assert "Set ℤ" in result
        assert "Set ℝ" not in result

    def test_real_target_unchanged(self):
        spec = _make_continuous_opt_spec()
        result = ContinuousOptMapper().map_objective(spec.objective, spec)
        assert "StrictConvexOn" in result
        assert "Set ℝ" in result

    def test_undeclared_variable_in_expression_rejected(self):
        with pytest.raises(ValidationError, match="undeclared identifiers"):
            ProblemSpec(
                problem_domain=ProblemDomain.CONTINUOUS_OPTIMIZATION,
                spaces=[Space(name="A", base_type=BaseType.REAL)],
                variables=[
                    Variable(
                        symbol="x",
                        classification=VariableClassification.ENDOGENOUS,
                        space_reference="A",
                        bounds=VariableBounds(lower_bound="0", strict_inequality=False),
                    ),
                ],
                functions=[
                    Function(
                        symbol="f",
                        domain=["A"],
                        codomain="Real",
                        properties=[FunctionProperty.STRICT_CONVEX],
                    ),
                ],
                objective=Objective(
                    direction=ObjectiveDirection.MINIMIZE,
                    expression_latex="f(x) + f(z)",
                    target_variable="x",
                ),
            )


# ---------------------------------------------------------------------------
# Convex-minus-concave recognition
# ---------------------------------------------------------------------------


class TestConvexMinusConcaveRecognition:

    def test_convex_minus_concave_is_convex(self):
        functions = [
            Function(symbol="f", domain=["S"], codomain="Real",
                     properties=[FunctionProperty.STRICT_CONVEX]),
            Function(symbol="g", domain=["S"], codomain="Real",
                     properties=[FunctionProperty.CONCAVE]),
        ]
        result = _check_expression_convexity_safe(
            "f(x) - g(x)", ["f", "g"], functions=functions
        )
        assert result is True

    def test_convex_minus_convex_not_convex(self):
        functions = [
            Function(symbol="f", domain=["S"], codomain="Real",
                     properties=[FunctionProperty.CONVEX]),
            Function(symbol="g", domain=["S"], codomain="Real",
                     properties=[FunctionProperty.CONVEX]),
        ]
        result = _check_expression_convexity_safe(
            "f(x) - g(x)", ["f", "g"], functions=functions
        )
        assert result is False

    def test_convex_plus_concave_not_convex(self):
        functions = [
            Function(symbol="f", domain=["S"], codomain="Real",
                     properties=[FunctionProperty.CONVEX]),
            Function(symbol="g", domain=["S"], codomain="Real",
                     properties=[FunctionProperty.CONCAVE]),
        ]
        result = _check_expression_convexity_safe(
            "f(x) + g(x)", ["f", "g"], functions=functions
        )
        assert result is False

    def test_negation_of_concave_is_convex(self):
        functions = [
            Function(symbol="g", domain=["S"], codomain="Real",
                     properties=[FunctionProperty.CONCAVE]),
        ]
        result = _check_expression_convexity_safe(
            "-g(x)", ["g"], functions=functions
        )
        assert result is True

    def test_legacy_mode_subtraction_returns_false(self):
        result = _check_expression_convexity_safe(
            "f(x) - g(x)", ["f", "g"]
        )
        assert result is False

    def test_predicate_fallback_convex_on_for_subtraction(self):
        spec = ProblemSpec(
            problem_domain=ProblemDomain.CONTINUOUS_OPTIMIZATION,
            spaces=[Space(name="S", base_type=BaseType.REAL,
                          topological_properties=[TopologicalProperty.CONVEX])],
            variables=[
                Variable(
                    symbol="x",
                    classification=VariableClassification.ENDOGENOUS,
                    space_reference="S",
                    bounds=VariableBounds(lower_bound="0", strict_inequality=False),
                )
            ],
            functions=[
                Function(symbol="f", domain=["S"], codomain="Real",
                         properties=[FunctionProperty.STRICT_CONVEX]),
                Function(symbol="g", domain=["S"], codomain="Real",
                         properties=[FunctionProperty.CONCAVE]),
            ],
            objective=Objective(
                direction=ObjectiveDirection.MINIMIZE,
                expression_latex="f(x) - g(x)",
                target_variable="x",
            ),
        )
        mapper = ContinuousOptMapper()
        mapper.set_context(spec)
        result = mapper.map_objective(spec.objective, spec)
        assert "minimize_x_convexon" in result
        assert "ConvexOn" in result


# ---------------------------------------------------------------------------
# Corner-case: product domain convexity lemma (n=2)
# ---------------------------------------------------------------------------
class TestProductDomainConvexityLemma:

    def test_two_variable_product_convexity_lemma(self):
        """n=2 multi-variable should emit Convex.prod lemma for the product domain."""
        mapper = ContinuousOptMapper()
        spec = ProblemSpec(
            problem_domain=ProblemDomain.CONTINUOUS_OPTIMIZATION,
            spaces=[
                Space(name="A", base_type=BaseType.REAL),
                Space(name="B", base_type=BaseType.REAL),
            ],
            variables=[
                Variable(
                    symbol="x",
                    classification=VariableClassification.ENDOGENOUS,
                    space_reference="A",
                    bounds=VariableBounds(lower_bound="0", strict_inequality=False),
                ),
                Variable(
                    symbol="y",
                    classification=VariableClassification.ENDOGENOUS,
                    space_reference="B",
                    bounds=VariableBounds(lower_bound="1", upper_bound="5",
                                         strict_inequality=False),
                ),
            ],
            functions=[
                Function(symbol="f", domain=["A"], codomain="Real",
                         properties=[FunctionProperty.CONVEX]),
                Function(symbol="g", domain=["B"], codomain="Real",
                         properties=[FunctionProperty.CONVEX]),
            ],
            objective=Objective(
                direction=ObjectiveDirection.MINIMIZE,
                expression_latex="f(x) + g(y)",
                target_variable="x",
            ),
        )
        mapper.set_context(spec)
        result = mapper.map_objective(spec.objective, spec)
        assert "lemma convex_domain : Convex ℝ Domain :=" in result
        # Lemma names preserve the exact (case-sensitive) space name.
        assert "Convex.prod convex_A convex_B" in result

    def test_case_distinct_spaces_do_not_collide(self):
        """Spaces differing only by case must yield distinct convexity lemmas.

        Regression guard: lowercasing the lemma name folded ``A`` and ``a`` to a
        single ``convex_a`` so the second lemma was swallowed by the dedup set and
        ``convex_domain`` referenced one space's proof term twice.
        """
        mapper = ContinuousOptMapper()
        spec = ProblemSpec(
            problem_domain=ProblemDomain.CONTINUOUS_OPTIMIZATION,
            spaces=[
                Space(name="A", base_type=BaseType.REAL),
                Space(name="a", base_type=BaseType.REAL),
            ],
            variables=[
                Variable(
                    symbol="x",
                    classification=VariableClassification.ENDOGENOUS,
                    space_reference="A",
                    bounds=VariableBounds(lower_bound="0", strict_inequality=False),
                ),
                Variable(
                    symbol="y",
                    classification=VariableClassification.ENDOGENOUS,
                    space_reference="a",
                    bounds=VariableBounds(lower_bound="1", upper_bound="5",
                                         strict_inequality=False),
                ),
            ],
            functions=[
                Function(symbol="f", domain=["A"], codomain="Real",
                         properties=[FunctionProperty.CONVEX]),
                Function(symbol="g", domain=["a"], codomain="Real",
                         properties=[FunctionProperty.CONVEX]),
            ],
            objective=Objective(
                direction=ObjectiveDirection.MINIMIZE,
                expression_latex="f(x) + g(y)",
                target_variable="x",
            ),
        )
        mapper.set_context(spec)
        result = mapper.map_objective(spec.objective, spec)
        assert "lemma convex_A : Convex ℝ A :=" in result
        assert "lemma convex_a : Convex ℝ a :=" in result
        assert "Convex.prod convex_A convex_a" in result

    def test_three_variable_product_convexity_sorry(self):
        """n>2 multi-variable should emit product convexity lemma with sorry."""
        mapper = ContinuousOptMapper()
        spec = ProblemSpec(
            problem_domain=ProblemDomain.CONTINUOUS_OPTIMIZATION,
            spaces=[
                Space(name="A", base_type=BaseType.REAL),
                Space(name="B", base_type=BaseType.REAL),
                Space(name="C", base_type=BaseType.REAL),
            ],
            variables=[
                Variable(symbol="x",
                         classification=VariableClassification.ENDOGENOUS,
                         space_reference="A"),
                Variable(symbol="y",
                         classification=VariableClassification.ENDOGENOUS,
                         space_reference="B"),
                Variable(symbol="z",
                         classification=VariableClassification.ENDOGENOUS,
                         space_reference="C"),
            ],
            functions=[
                Function(symbol="f", domain=["A"], codomain="Real",
                         properties=[FunctionProperty.CONVEX]),
                Function(symbol="g", domain=["B"], codomain="Real",
                         properties=[FunctionProperty.CONVEX]),
                Function(symbol="h", domain=["C"], codomain="Real",
                         properties=[FunctionProperty.CONVEX]),
            ],
            objective=Objective(
                direction=ObjectiveDirection.MINIMIZE,
                expression_latex="f(x) + g(y) + h(z)",
                target_variable="x",
            ),
        )
        mapper.set_context(spec)
        result = mapper.map_objective(spec.objective, spec)
        assert "lemma convex_domain : Convex ℝ Domain :=" in result
        assert "sorry" in result


# ---------------------------------------------------------------------------
# Corner-case: multi-variable convexity lemma arguments
# ---------------------------------------------------------------------------
class TestMultiVariableConvexityLemmaArgs:

    def test_convexity_lemma_includes_bound_arguments(self):
        """Multi-variable convexity lemmas must include bound arguments (e.g. convex_Ici 0)."""
        mapper = ContinuousOptMapper()
        spec = ProblemSpec(
            problem_domain=ProblemDomain.CONTINUOUS_OPTIMIZATION,
            spaces=[
                Space(name="A", base_type=BaseType.REAL),
                Space(name="B", base_type=BaseType.REAL),
            ],
            variables=[
                Variable(
                    symbol="x",
                    classification=VariableClassification.ENDOGENOUS,
                    space_reference="A",
                    bounds=VariableBounds(lower_bound="0", strict_inequality=False),
                ),
                Variable(
                    symbol="y",
                    classification=VariableClassification.ENDOGENOUS,
                    space_reference="B",
                    bounds=VariableBounds(lower_bound="1", upper_bound="5",
                                         strict_inequality=False),
                ),
            ],
            functions=[
                Function(symbol="f", domain=["A"], codomain="Real",
                         properties=[FunctionProperty.CONVEX]),
                Function(symbol="g", domain=["B"], codomain="Real",
                         properties=[FunctionProperty.CONVEX]),
            ],
            objective=Objective(
                direction=ObjectiveDirection.MINIMIZE,
                expression_latex="f(x) + g(y)",
                target_variable="x",
            ),
        )
        mapper.set_context(spec)
        result = mapper.map_objective(spec.objective, spec)
        assert "convex_Ici 0" in result
        assert "convex_Icc 1 5" in result
