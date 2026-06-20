"""Unit tests for all Pydantic schema models in formalconstruct.schemas."""

import datetime
import json

import pytest
from pydantic import ValidationError

from formalconstruct.schemas.axle_responses import (
    AxleCheckResult,
    AxleRepairResult,
    AxleVerifyResult,
    MessageSet,
    RepairStats,
    RepairTimings,
)
from formalconstruct.schemas.failures import (
    FailureClassification,
    StructuredFailure,
)
from formalconstruct.schemas.lean_source import LeanGoal, LeanSource
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
from formalconstruct.schemas.translation import (
    NodeState,
    PipelinePhase,
    SourceMapping,
    TranslationContextSnapshot,
    TranslationNode,
)


# ---------------------------------------------------------------------------
# Helpers: minimal valid sub-models reused across ProblemSpec tests
# ---------------------------------------------------------------------------

def _space(name: str = "X", base_type: BaseType = BaseType.REAL_N) -> Space:
    return Space(name=name, base_type=base_type)


def _variable(
    symbol: str = "x",
    classification: VariableClassification = VariableClassification.ENDOGENOUS,
    space_ref: str = "X",
) -> Variable:
    return Variable(symbol=symbol, classification=classification, space_reference=space_ref)


def _function(symbol: str = "f") -> Function:
    return Function(
        symbol=symbol,
        domain=["X"],
        codomain="Real",
        properties=[FunctionProperty.CONTINUOUS],
    )


def _objective(
    direction: ObjectiveDirection = ObjectiveDirection.MINIMIZE,
) -> Objective:
    return Objective(direction=direction, expression_latex="f(x)")


def _problem_spec(domain: ProblemDomain, **overrides) -> ProblemSpec:
    obj = overrides.get("objective", _objective())
    is_game_objective = obj.direction in (
        ObjectiveDirection.EQUILIBRIUM,
        ObjectiveDirection.PARETO_OPTIMAL,
    )
    if is_game_objective:
        defaults = dict(
            problem_domain=domain,
            spaces=[_space()],
            variables=[_variable(classification=VariableClassification.STRATEGY_PROFILE)],
            functions=[_function()],
            objective=obj,
        )
    else:
        defaults = dict(
            problem_domain=domain,
            spaces=[_space()],
            variables=[_variable()],
            functions=[_function()],
            objective=obj,
        )
    defaults.update(overrides)
    return ProblemSpec(**defaults)


# ===================================================================
# ProblemSpec tests
# ===================================================================


class TestProblemSpec:
    def test_valid_continuous_optimization(self):
        ps = _problem_spec(ProblemDomain.CONTINUOUS_OPTIMIZATION)
        assert ps.problem_domain == ProblemDomain.CONTINUOUS_OPTIMIZATION
        assert len(ps.spaces) == 1
        assert ps.domain_components == []

    def test_valid_non_cooperative_game(self):
        ps = _problem_spec(
            ProblemDomain.NON_COOPERATIVE_GAME,
            objective=_objective(ObjectiveDirection.EQUILIBRIUM),
        )
        assert ps.problem_domain == ProblemDomain.NON_COOPERATIVE_GAME

    def test_valid_cooperative_game(self):
        ps = _problem_spec(
            ProblemDomain.COOPERATIVE_GAME,
            objective=_objective(ObjectiveDirection.PARETO_OPTIMAL),
        )
        assert ps.problem_domain == ProblemDomain.COOPERATIVE_GAME

    def test_valid_composite_non_cooperative_plus_optimization(self):
        ps = _problem_spec(
            ProblemDomain.NON_COOPERATIVE_GAME,
            primary_domain=ProblemDomain.NON_COOPERATIVE_GAME,
            domain_components=[
                ProblemDomain.NON_COOPERATIVE_GAME,
                ProblemDomain.CONTINUOUS_OPTIMIZATION,
            ],
        )
        assert ps.primary_domain == ProblemDomain.NON_COOPERATIVE_GAME
        assert len(ps.domain_components) == 2

    def test_valid_composite_cooperative_plus_optimization(self):
        ps = _problem_spec(
            ProblemDomain.COOPERATIVE_GAME,
            primary_domain=ProblemDomain.COOPERATIVE_GAME,
            domain_components=[
                ProblemDomain.COOPERATIVE_GAME,
                ProblemDomain.CONTINUOUS_OPTIMIZATION,
            ],
        )
        assert len(ps.domain_components) == 2

    def test_missing_primary_domain_with_components_raises(self):
        with pytest.raises(ValidationError, match="primary_domain is required"):
            _problem_spec(
                ProblemDomain.NON_COOPERATIVE_GAME,
                domain_components=[
                    ProblemDomain.NON_COOPERATIVE_GAME,
                    ProblemDomain.CONTINUOUS_OPTIMIZATION,
                ],
            )

    def test_unsupported_composite_two_game_domains_raises(self):
        with pytest.raises(ValidationError, match="Unsupported domain composition"):
            _problem_spec(
                ProblemDomain.NON_COOPERATIVE_GAME,
                primary_domain=ProblemDomain.NON_COOPERATIVE_GAME,
                domain_components=[
                    ProblemDomain.NON_COOPERATIVE_GAME,
                    ProblemDomain.COOPERATIVE_GAME,
                ],
            )

    def test_all_problem_domain_values(self):
        assert set(ProblemDomain) == {
            ProblemDomain.CONTINUOUS_OPTIMIZATION,
            ProblemDomain.NON_COOPERATIVE_GAME,
            ProblemDomain.COOPERATIVE_GAME,
        }
        assert ProblemDomain.CONTINUOUS_OPTIMIZATION.value == "continuous_optimization"
        assert ProblemDomain.NON_COOPERATIVE_GAME.value == "non_cooperative_game"
        assert ProblemDomain.COOPERATIVE_GAME.value == "cooperative_game"

    def test_all_topological_property_values(self):
        expected = {"compact", "connected", "hausdorff", "convex", "closed", "open", "bounded"}
        assert {t.value for t in TopologicalProperty} == expected

    def test_all_function_property_values(self):
        expected = {
            "StrictConvex", "Convex", "Linear", "Continuous",
            "Differentiable", "StrictConcave", "Concave",
        }
        assert {fp.value for fp in FunctionProperty} == expected

    def test_all_variable_classification_values(self):
        expected = {"endogenous", "exogenous", "strategy_profile"}
        assert {vc.value for vc in VariableClassification} == expected

    def test_all_objective_direction_values(self):
        expected = {
            "minimize", "maximize", "equilibrium", "pareto_optimal",
            "inequality", "existential_bound",
        }
        assert {od.value for od in ObjectiveDirection} == expected

    def test_all_base_type_values(self):
        expected = {"Real", "NonnegReal", "PosReal", "RealN", "Int", "Nat", "Bool"}
        assert {bt.value for bt in BaseType} == expected

    def test_variable_bounds_defaults(self):
        vb = VariableBounds()
        assert vb.lower_bound is None
        assert vb.upper_bound is None
        assert vb.strict_inequality is False

    # --- Space.dimension tests ---

    def test_space_dimension_defaults_to_none(self):
        s = Space(name="S", base_type=BaseType.REAL)
        assert s.dimension is None

    def test_space_dimension_positive_real_n(self):
        s = Space(name="S", base_type=BaseType.REAL_N, dimension=3)
        assert s.dimension == 3

    def test_space_dimension_zero_real_n_raises(self):
        with pytest.raises(ValidationError, match="must be a positive integer"):
            Space(name="S", base_type=BaseType.REAL_N, dimension=0)

    def test_space_dimension_negative_real_n_raises(self):
        with pytest.raises(ValidationError, match="must be a positive integer"):
            Space(name="S", base_type=BaseType.REAL_N, dimension=-1)

    def test_space_dimension_on_non_real_n_allowed(self):
        """dimension on non-REAL_N types is accepted without validation."""
        s = Space(name="S", base_type=BaseType.REAL, dimension=5)
        assert s.dimension == 5


# ===================================================================
# Cross-field reference validation tests
# ===================================================================


class TestCrossFieldValidation:
    """Contract tests for ProblemSpec.validate_cross_field_references."""

    def test_dangling_space_reference_raises(self):
        """Variable referencing an undeclared space must be rejected."""
        with pytest.raises(ValidationError, match="undeclared space"):
            _problem_spec(
                ProblemDomain.CONTINUOUS_OPTIMIZATION,
                variables=[_variable(symbol="x", space_ref="NonExistent")],
            )

    def test_function_domain_unresolvable_raises(self):
        """Function with a domain entry not matching any declared space must be rejected."""
        bad_func = Function(
            symbol="g",
            domain=["NonExistent"],
            codomain="Real",
            properties=[FunctionProperty.CONTINUOUS],
        )
        with pytest.raises(ValidationError, match="does not match any declared space"):
            _problem_spec(
                ProblemDomain.CONTINUOUS_OPTIMIZATION,
                functions=[bad_func],
            )

    def test_invalid_lean_symbol_space_raises(self):
        """Variable symbol containing a space is not a valid Lean 4 identifier."""
        with pytest.raises(ValidationError, match="not a valid Lean 4 identifier"):
            _problem_spec(
                ProblemDomain.CONTINUOUS_OPTIMIZATION,
                variables=[_variable(symbol="my var", space_ref="X")],
            )

    def test_invalid_lean_symbol_leading_digit_raises(self):
        """Variable symbol starting with a digit is not a valid Lean 4 identifier."""
        with pytest.raises(ValidationError, match="not a valid Lean 4 identifier"):
            _problem_spec(
                ProblemDomain.CONTINUOUS_OPTIMIZATION,
                variables=[_variable(symbol="2fast", space_ref="X")],
            )

    def test_empty_function_properties_raises(self):
        """Function with an empty properties list must be rejected."""
        empty_props_func = Function(
            symbol="h",
            domain=["X"],
            codomain="Real",
            properties=[],
        )
        with pytest.raises(ValidationError, match="empty properties list"):
            _problem_spec(
                ProblemDomain.CONTINUOUS_OPTIMIZATION,
                functions=[empty_props_func],
            )

    def test_valid_lean_symbol_with_apostrophe(self):
        """Lean 4 identifiers may contain trailing apostrophes (primes)."""
        ps = _problem_spec(
            ProblemDomain.CONTINUOUS_OPTIMIZATION,
            variables=[_variable(symbol="x'", space_ref="X")],
            objective=Objective(direction=ObjectiveDirection.MINIMIZE, expression_latex="f(x')"),
        )
        assert ps.variables[0].symbol == "x'"

    def test_optimization_objective_requires_functions(self):
        """MINIMIZE/MAXIMIZE with empty functions list must be rejected."""
        for direction in (ObjectiveDirection.MINIMIZE, ObjectiveDirection.MAXIMIZE):
            with pytest.raises(ValidationError, match="requires at least one function"):
                _problem_spec(
                    ProblemDomain.CONTINUOUS_OPTIMIZATION,
                    functions=[],
                    objective=_objective(direction),
                )

    def test_non_optimization_objective_requires_functions(self):
        """EQUILIBRIUM and PARETO_OPTIMAL require at least one function."""
        for direction in (ObjectiveDirection.EQUILIBRIUM, ObjectiveDirection.PARETO_OPTIMAL):
            with pytest.raises(ValidationError, match="requires at least one utility"):
                _problem_spec(
                    ProblemDomain.NON_COOPERATIVE_GAME,
                    functions=[],
                    objective=Objective(direction=direction, expression_latex="x"),
                )

    # --- Space.name Lean identifier validation ---

    def test_invalid_space_name_with_space_raises(self):
        """Space name containing a space is not a valid Lean 4 identifier."""
        with pytest.raises(ValidationError, match="Space name.*not a valid Lean 4 identifier"):
            _problem_spec(
                ProblemDomain.CONTINUOUS_OPTIMIZATION,
                spaces=[Space(name="my space", base_type=BaseType.REAL)],
                variables=[_variable(symbol="x", space_ref="my space")],
            )

    def test_invalid_space_name_leading_digit_raises(self):
        """Space name starting with a digit is not a valid Lean 4 identifier."""
        with pytest.raises(ValidationError, match="Space name.*not a valid Lean 4 identifier"):
            _problem_spec(
                ProblemDomain.CONTINUOUS_OPTIMIZATION,
                spaces=[Space(name="3D", base_type=BaseType.REAL)],
                variables=[_variable(symbol="x", space_ref="3D")],
            )

    def test_valid_space_name_with_underscore(self):
        """Space name with underscores is a valid Lean 4 identifier."""
        ps = _problem_spec(
            ProblemDomain.CONTINUOUS_OPTIMIZATION,
            spaces=[Space(name="my_space", base_type=BaseType.REAL)],
            variables=[_variable(symbol="x", space_ref="my_space")],
            functions=[Function(
                symbol="f", domain=["my_space"], codomain="Real",
                properties=[FunctionProperty.CONTINUOUS],
            )],
        )
        assert ps.spaces[0].name == "my_space"

    # --- Objective.target_variable Lean identifier validation ---

    def test_invalid_target_variable_raises(self):
        """Objective target_variable that is not a Lean identifier must be rejected."""
        with pytest.raises(ValidationError, match="target_variable.*not a valid Lean 4 identifier"):
            _problem_spec(
                ProblemDomain.CONTINUOUS_OPTIMIZATION,
                objective=Objective(
                    direction=ObjectiveDirection.MINIMIZE,
                    expression_latex="f(x)",
                    target_variable="bad var",
                ),
            )

    def test_valid_target_variable_none_accepted(self):
        """Objective with target_variable=None passes validation."""
        ps = _problem_spec(
            ProblemDomain.CONTINUOUS_OPTIMIZATION,
            objective=Objective(
                direction=ObjectiveDirection.MINIMIZE,
                expression_latex="f(x)",
                target_variable=None,
            ),
        )
        assert ps.objective.target_variable is None

    def test_valid_target_variable_accepted(self):
        """Objective with a valid Lean identifier as target_variable passes."""
        ps = _problem_spec(
            ProblemDomain.CONTINUOUS_OPTIMIZATION,
            objective=Objective(
                direction=ObjectiveDirection.MINIMIZE,
                expression_latex="f(x)",
                target_variable="x",
            ),
        )
        assert ps.objective.target_variable == "x"

    # --- VariableBounds numeric literal validation ---

    def test_invalid_lower_bound_expression_raises(self):
        """lower_bound that is not a safe numeric literal must be rejected."""
        with pytest.raises(ValidationError, match="not a safe numeric literal"):
            _problem_spec(
                ProblemDomain.CONTINUOUS_OPTIMIZATION,
                variables=[Variable(
                    symbol="x",
                    classification=VariableClassification.ENDOGENOUS,
                    space_reference="X",
                    bounds=VariableBounds(lower_bound="a + b"),
                )],
            )

    def test_invalid_upper_bound_expression_raises(self):
        """upper_bound that is not a safe numeric literal must be rejected."""
        with pytest.raises(ValidationError, match="not a safe numeric literal"):
            _problem_spec(
                ProblemDomain.CONTINUOUS_OPTIMIZATION,
                variables=[Variable(
                    symbol="x",
                    classification=VariableClassification.ENDOGENOUS,
                    space_reference="X",
                    bounds=VariableBounds(upper_bound="2*pi"),
                )],
            )

    def test_valid_integer_bound_accepted(self):
        """Integer bound values pass validation."""
        ps = _problem_spec(
            ProblemDomain.CONTINUOUS_OPTIMIZATION,
            variables=[Variable(
                symbol="x",
                classification=VariableClassification.ENDOGENOUS,
                space_reference="X",
                bounds=VariableBounds(lower_bound="0", upper_bound="10"),
            )],
        )
        assert ps.variables[0].bounds.lower_bound == "0"
        assert ps.variables[0].bounds.upper_bound == "10"

    def test_valid_negative_bound_accepted(self):
        """Negative integer bound values pass validation."""
        ps = _problem_spec(
            ProblemDomain.CONTINUOUS_OPTIMIZATION,
            variables=[Variable(
                symbol="x",
                classification=VariableClassification.ENDOGENOUS,
                space_reference="X",
                bounds=VariableBounds(lower_bound="-1"),
            )],
        )
        assert ps.variables[0].bounds.lower_bound == "-1"

    def test_valid_decimal_bound_accepted(self):
        """Decimal bound values pass validation."""
        ps = _problem_spec(
            ProblemDomain.CONTINUOUS_OPTIMIZATION,
            variables=[Variable(
                symbol="x",
                classification=VariableClassification.ENDOGENOUS,
                space_reference="X",
                bounds=VariableBounds(lower_bound="-0.5", upper_bound="3.14"),
            )],
        )
        assert ps.variables[0].bounds.lower_bound == "-0.5"
        assert ps.variables[0].bounds.upper_bound == "3.14"

    # --- Identifier validation contract tests ---

    def test_space_name_with_operator_rejected(self):
        """Space name containing an operator character is rejected."""
        with pytest.raises(ValidationError, match="Space name.*not a valid Lean 4 identifier"):
            _problem_spec(
                ProblemDomain.CONTINUOUS_OPTIMIZATION,
                spaces=[Space(name="S+T", base_type=BaseType.REAL)],
                variables=[_variable(symbol="x", space_ref="S+T")],
            )

    def test_target_variable_not_in_declared_vars_rejected(self):
        """target_variable 'z' when only 'x' declared is rejected."""
        with pytest.raises(ValidationError, match="does not match any declared variable"):
            _problem_spec(
                ProblemDomain.CONTINUOUS_OPTIMIZATION,
                objective=Objective(
                    direction=ObjectiveDirection.MINIMIZE,
                    expression_latex="f(x)",
                    target_variable="z",
                ),
            )

    def test_valid_spec_passes_unchanged(self):
        """The default _problem_spec helper produces a valid ProblemSpec."""
        ps = _problem_spec(ProblemDomain.CONTINUOUS_OPTIMIZATION)
        assert len(ps.spaces) == 1
        assert len(ps.variables) == 1
        assert len(ps.functions) == 1
        assert ps.variables[0].space_reference == ps.spaces[0].name


# ===================================================================
# AXLE Response tests
# ===================================================================


class TestAxleResponses:
    def test_message_set_defaults_to_empty(self):
        ms = MessageSet()
        assert ms.errors == []
        assert ms.warnings == []
        assert ms.infos == []

    def test_check_result_no_errors(self):
        r = AxleCheckResult(lean_messages=MessageSet(), tool_messages=MessageSet())
        assert r.has_errors is False

    def test_check_result_lean_errors(self):
        r = AxleCheckResult(
            lean_messages=MessageSet(errors=["type mismatch"]),
            tool_messages=MessageSet(),
        )
        assert r.has_errors is True

    def test_check_result_tool_errors(self):
        r = AxleCheckResult(
            lean_messages=MessageSet(),
            tool_messages=MessageSet(errors=["timeout"]),
        )
        assert r.has_errors is True

    def test_verify_result_verified_true(self):
        r = AxleVerifyResult(
            lean_messages=MessageSet(),
            tool_messages=MessageSet(),
            verified=True,
        )
        assert r.verified is True
        assert r.has_errors is False

    def test_verify_result_verified_false(self):
        r = AxleVerifyResult(
            lean_messages=MessageSet(),
            tool_messages=MessageSet(),
            verified=False,
        )
        assert r.verified is False

    def test_repair_result_okay(self):
        r = AxleRepairResult(okay=True)
        assert r.okay is True
        assert r.content == ""
        assert r.repair_stats.remove_extraneous_tactics == 0

    def test_repair_result_not_okay(self):
        r = AxleRepairResult(okay=False, content="repaired source")
        assert r.okay is False
        assert r.content == "repaired source"

    def test_repair_stats_defaults(self):
        rs = RepairStats()
        assert rs.remove_extraneous_tactics == 0
        assert rs.replace_unsafe_tactics == 0
        assert rs.apply_terminal_tactics == 0

    def test_repair_timings_defaults(self):
        rt = RepairTimings()
        assert rt.total_ms == 0
        assert rt.repair_ms == 0


# ===================================================================
# StructuredFailure tests
# ===================================================================


class TestStructuredFailure:
    def test_construction_with_required_fields(self):
        sf = StructuredFailure(
            classification=FailureClassification.MATHLIB_GAP,
            final_lean_goal="0 < 1",
        )
        assert sf.classification == FailureClassification.MATHLIB_GAP
        assert sf.final_lean_goal == "0 < 1"

    def test_all_17_fields_present_with_defaults(self):
        sf = StructuredFailure(
            classification=FailureClassification.PROOF_SEARCH_EXHAUSTION,
            final_lean_goal="goal",
        )
        field_names = set(StructuredFailure.model_fields.keys())
        assert len(field_names) == 17
        assert sf.compiler_errors == []
        assert sf.tool_errors == []
        assert sf.originating_schema_fields == []
        assert sf.originating_narrative_indices == []
        assert sf.attempted_tactics == []
        assert sf.attempted_repairs == []
        assert sf.tactic_attempts_used == 0
        assert sf.repair_attempts_used == 0
        assert sf.replans_used == 0
        assert sf.schema_rollbacks_used == 0
        assert sf.axle_calls_used == 0
        assert sf.wall_clock_seconds == 0.0
        assert sf.exhausted_bound == ""
        assert sf.phase == ""
        assert sf.traceback_path == []

    def test_json_round_trip(self):
        sf = StructuredFailure(
            classification=FailureClassification.SCHEMA_INSUFFICIENCY,
            final_lean_goal="x > 0",
            compiler_errors=["unknown identifier 'x'"],
            tactic_attempts_used=5,
            wall_clock_seconds=12.3,
        )
        json_str = sf.model_dump_json()
        restored = StructuredFailure.model_validate_json(json_str)
        assert restored.classification == sf.classification
        assert restored.final_lean_goal == sf.final_lean_goal
        assert restored.compiler_errors == sf.compiler_errors
        assert restored.tactic_attempts_used == 5
        assert restored.wall_clock_seconds == 12.3

    def test_failure_classification_has_3_values(self):
        assert len(FailureClassification) == 3
        assert set(FailureClassification) == {
            FailureClassification.SCHEMA_INSUFFICIENCY,
            FailureClassification.MATHLIB_GAP,
            FailureClassification.PROOF_SEARCH_EXHAUSTION,
        }


# ===================================================================
# Translation context tests
# ===================================================================


class TestTranslation:
    def test_node_state_has_5_values(self):
        assert len(NodeState) == 5
        assert {ns.value for ns in NodeState} == {
            "pending", "in_progress", "completed", "failed", "rolled_back",
        }

    def test_pipeline_phase_has_3_values(self):
        assert len(PipelinePhase) == 3
        assert {pp.value for pp in PipelinePhase} == {
            "informal_rigor", "scaffolding", "proving",
        }

    def test_translation_node_defaults(self):
        node = TranslationNode(
            node_id="n1",
            phase=PipelinePhase.INFORMAL_RIGOR,
        )
        assert node.state == NodeState.PENDING
        assert node.parent_ids == []
        assert node.child_ids == []
        assert node.data == {}
        assert node.error is None
        assert isinstance(node.created_at, datetime.datetime)
        assert node.completed_at is None

    def test_translation_node_custom_state(self):
        node = TranslationNode(
            node_id="n2",
            phase=PipelinePhase.PROVING,
            state=NodeState.COMPLETED,
            parent_ids=["n1"],
            data={"result": "ok"},
        )
        assert node.state == NodeState.COMPLETED
        assert node.parent_ids == ["n1"]
        assert node.data == {"result": "ok"}

    def test_source_mapping_construction(self):
        sm = SourceMapping(
            lean_line=42,
            schema_field="functions[0].properties[0]",
            narrative_start=100,
            narrative_end=150,
        )
        assert sm.lean_line == 42
        assert sm.schema_field == "functions[0].properties[0]"
        assert sm.narrative_start == 100
        assert sm.narrative_end == 150

    def test_translation_context_snapshot_json_serialization(self):
        node = TranslationNode(
            node_id="root",
            phase=PipelinePhase.SCAFFOLDING,
            state=NodeState.IN_PROGRESS,
        )
        mapping = SourceMapping(
            lean_line=1,
            schema_field="spaces[0].name",
            narrative_start=0,
            narrative_end=10,
        )
        snap = TranslationContextSnapshot(
            narrative="Minimize f(x) subject to x in X.",
            nodes={"root": node},
            source_mappings=[mapping],
            current_phase=PipelinePhase.SCAFFOLDING,
        )
        json_str = snap.model_dump_json()
        parsed = json.loads(json_str)
        assert parsed["narrative"] == "Minimize f(x) subject to x in X."
        assert "root" in parsed["nodes"]
        assert len(parsed["source_mappings"]) == 1
        assert parsed["current_phase"] == "scaffolding"
        assert parsed["problem_spec"] is None
        assert parsed["lean_source"] is None
        assert parsed["verified_source"] is None


# ===================================================================
# LeanSource tests
# ===================================================================


class TestLeanSource:
    def test_basic_construction(self):
        ls = LeanSource(content="import Mathlib\nsorry", imports=["Mathlib"])
        assert ls.content == "import Mathlib\nsorry"
        assert ls.imports == ["Mathlib"]

    def test_goals_list(self):
        goal = LeanGoal(
            goal_id="g1",
            theorem_name="thm_main",
            goal_state="0 < 1",
            line_number=10,
            sorry_offset=42,
        )
        ls = LeanSource(content="sorry", imports=["Mathlib"], goals=[goal])
        assert len(ls.goals) == 1
        assert ls.goals[0].goal_id == "g1"
        assert ls.goals[0].theorem_name == "thm_main"
        assert ls.goals[0].sorry_offset == 42

    def test_empty_defaults(self):
        ls = LeanSource(content="", imports=[])
        assert ls.goals == []
        assert ls.mathlib_modules == []


# ===================================================================
# REAL_N Space Dimension Contract Tests
# ===================================================================


class TestSpaceDimensionRealN:
    """Contract tests verifying Space validates correctly for REAL_N with
    concrete and generic dimensions."""

    def test_space_dimension_3_real_n(self):
        """Space with dimension=3, base_type=REAL_N validates and stores dimension."""
        s = Space(name="Portfolio", base_type=BaseType.REAL_N, dimension=3)
        assert s.base_type == BaseType.REAL_N
        assert s.dimension == 3
        assert s.name == "Portfolio"

    def test_space_dimension_none_real_n(self):
        """Space with dimension=None, base_type=REAL_N validates (generic dimension)."""
        s = Space(name="Portfolio", base_type=BaseType.REAL_N, dimension=None)
        assert s.base_type == BaseType.REAL_N
        assert s.dimension is None

    def test_space_dimension_none_real_n_default(self):
        """Space with base_type=REAL_N and no dimension arg defaults to None."""
        s = Space(name="Portfolio", base_type=BaseType.REAL_N)
        assert s.dimension is None

    def test_space_dimension_real_n_in_problem_spec(self):
        """A ProblemSpec containing a REAL_N space with dimension=3 validates
        through cross-field validation."""
        ps = _problem_spec(
            ProblemDomain.CONTINUOUS_OPTIMIZATION,
            spaces=[Space(name="X", base_type=BaseType.REAL_N, dimension=3)],
        )
        assert ps.spaces[0].dimension == 3
        assert ps.spaces[0].base_type == BaseType.REAL_N

    def test_space_dimension_none_real_n_in_problem_spec(self):
        """A ProblemSpec containing a REAL_N space with dimension=None validates."""
        ps = _problem_spec(
            ProblemDomain.CONTINUOUS_OPTIMIZATION,
            spaces=[Space(name="X", base_type=BaseType.REAL_N, dimension=None)],
        )
        assert ps.spaces[0].dimension is None


# ===================================================================
# Empty functions optimization rejection
# ===================================================================


class TestEmptyFunctionsOptimizationRejection:
    """Contract tests verifying that MINIMIZE/MAXIMIZE objectives require
    at least one function, while EQUILIBRIUM permits an empty functions list.

    Note: test_optimization_objective_requires_functions and
    test_non_optimization_objective_allows_empty_functions in
    TestCrossFieldValidation already cover these cases. These tests
    provide individually named contract coverage for traceability.
    """

    def test_minimize_with_empty_functions_raises(self):
        """MINIMIZE + functions=[] must raise ValidationError."""
        with pytest.raises(ValidationError, match="requires at least one function"):
            _problem_spec(
                ProblemDomain.CONTINUOUS_OPTIMIZATION,
                functions=[],
                objective=_objective(ObjectiveDirection.MINIMIZE),
            )

    def test_maximize_with_empty_functions_raises(self):
        """MAXIMIZE + functions=[] must raise ValidationError."""
        with pytest.raises(ValidationError, match="requires at least one function"):
            _problem_spec(
                ProblemDomain.CONTINUOUS_OPTIMIZATION,
                functions=[],
                objective=_objective(ObjectiveDirection.MAXIMIZE),
            )

    def test_equilibrium_with_empty_functions_rejected(self):
        """EQUILIBRIUM + functions=[] must raise validation error."""
        with pytest.raises(ValidationError, match="requires at least one utility"):
            _problem_spec(
                ProblemDomain.NON_COOPERATIVE_GAME,
                functions=[],
                objective=Objective(direction=ObjectiveDirection.EQUILIBRIUM, expression_latex="x"),
            )


# ===================================================================
# Identifier uniqueness in ProblemSpec
# ===================================================================


class TestIdentifierUniqueness:
    """Contract tests for duplicate identifier rejection."""

    def test_duplicate_space_names_raises(self):
        """Two spaces with the same name must be rejected."""
        with pytest.raises(ValidationError, match="Duplicate space names"):
            _problem_spec(
                ProblemDomain.CONTINUOUS_OPTIMIZATION,
                spaces=[
                    Space(name="X", base_type=BaseType.REAL),
                    Space(name="X", base_type=BaseType.REAL_N),
                ],
                variables=[_variable(symbol="x", space_ref="X")],
            )

    def test_duplicate_variable_symbols_raises(self):
        """Two variables with the same symbol must be rejected."""
        with pytest.raises(ValidationError, match="Duplicate variable symbols"):
            _problem_spec(
                ProblemDomain.CONTINUOUS_OPTIMIZATION,
                variables=[
                    _variable(symbol="x", space_ref="X"),
                    _variable(symbol="x", space_ref="X"),
                ],
            )

    def test_duplicate_function_symbols_raises(self):
        """Two functions with the same symbol must be rejected."""
        with pytest.raises(ValidationError, match="Duplicate function symbols"):
            _problem_spec(
                ProblemDomain.CONTINUOUS_OPTIMIZATION,
                functions=[_function(symbol="f"), _function(symbol="f")],
            )

    def test_variable_function_symbol_collision_raises(self):
        """A variable and function sharing the same symbol must be rejected."""
        with pytest.raises(ValidationError, match="Symbol collision between variables and functions"):
            _problem_spec(
                ProblemDomain.CONTINUOUS_OPTIMIZATION,
                variables=[_variable(symbol="f", space_ref="X")],
                functions=[_function(symbol="f")],
            )

    def test_distinct_identifiers_accepted(self):
        """Distinct space names, variable symbols, and function symbols pass."""
        ps = _problem_spec(
            ProblemDomain.CONTINUOUS_OPTIMIZATION,
            spaces=[
                Space(name="X", base_type=BaseType.REAL),
                Space(name="Y", base_type=BaseType.REAL),
            ],
            variables=[
                _variable(symbol="x", space_ref="X"),
                _variable(symbol="y", space_ref="Y"),
            ],
            functions=[
                Function(symbol="f", domain=["X"], codomain="Real",
                         properties=[FunctionProperty.CONTINUOUS]),
                Function(symbol="g", domain=["Y"], codomain="Real",
                         properties=[FunctionProperty.CONTINUOUS]),
            ],
            objective=Objective(
                direction=ObjectiveDirection.MINIMIZE,
                expression_latex="f(x)",
                target_variable="x",
            ),
        )
        assert len(ps.spaces) == 2
        assert len(ps.variables) == 2
        assert len(ps.functions) == 2


# ===================================================================
# expression_latex identifier validation
# ===================================================================


class TestExpressionLatexIdentifiers:
    """expression_latex identifiers must be declared as variables or functions."""

    def test_undeclared_variable_in_expression_raises(self):
        """expression_latex='f(z)' with variable 'x' declared (not 'z') must fail."""
        with pytest.raises(ValidationError, match="undeclared identifiers"):
            _problem_spec(
                ProblemDomain.CONTINUOUS_OPTIMIZATION,
                variables=[_variable(symbol="x", space_ref="X")],
                functions=[_function(symbol="f")],
                objective=Objective(
                    direction=ObjectiveDirection.MINIMIZE,
                    expression_latex="f(z)",
                ),
            )

    def test_undeclared_function_in_expression_raises(self):
        """expression_latex='g(x)' with function 'f' declared (not 'g') must fail."""
        with pytest.raises(ValidationError, match="undeclared identifiers"):
            _problem_spec(
                ProblemDomain.CONTINUOUS_OPTIMIZATION,
                variables=[_variable(symbol="x", space_ref="X")],
                functions=[_function(symbol="f")],
                objective=Objective(
                    direction=ObjectiveDirection.MINIMIZE,
                    expression_latex="g(x)",
                ),
            )

    def test_all_declared_identifiers_pass(self):
        """expression_latex='f(x)' with both f and x declared must pass."""
        ps = _problem_spec(
            ProblemDomain.CONTINUOUS_OPTIMIZATION,
            variables=[_variable(symbol="x", space_ref="X")],
            functions=[_function(symbol="f")],
            objective=Objective(
                direction=ObjectiveDirection.MINIMIZE,
                expression_latex="f(x)",
            ),
        )
        assert ps.objective.expression_latex == "f(x)"

    def test_complex_expression_all_declared_pass(self):
        """expression_latex='f(x) + g(x)' with both f, g, and x declared must pass."""
        ps = _problem_spec(
            ProblemDomain.CONTINUOUS_OPTIMIZATION,
            variables=[_variable(symbol="x", space_ref="X")],
            functions=[
                _function(symbol="f"),
                Function(
                    symbol="g",
                    domain=["X"],
                    codomain="Real",
                    properties=[FunctionProperty.CONTINUOUS],
                ),
            ],
            objective=Objective(
                direction=ObjectiveDirection.MINIMIZE,
                expression_latex="f(x) + g(x)",
            ),
        )
        assert ps.objective.expression_latex == "f(x) + g(x)"

    def test_latex_expression_silently_skipped(self):
        r"""expression_latex='\min_{x} f(x)' with LaTeX commands cannot be parsed.
        Parse failure is silently skipped (not a validation error)."""
        ps = _problem_spec(
            ProblemDomain.CONTINUOUS_OPTIMIZATION,
            objective=Objective(
                direction=ObjectiveDirection.MINIMIZE,
                expression_latex="f(x)",
            ),
        )
        assert ps.objective.expression_latex == "f(x)"

    def test_empty_expression_silently_skipped(self):
        """Empty expression_latex is skipped (no validation error from identifier check)."""
        ps = _problem_spec(
            ProblemDomain.CONTINUOUS_OPTIMIZATION,
            objective=Objective(
                direction=ObjectiveDirection.MINIMIZE,
                expression_latex="",
            ),
        )
        assert ps.objective.expression_latex == ""

    def test_numeric_only_expression_pass(self):
        """expression_latex='2 + 3' with no identifiers must pass."""
        ps = _problem_spec(
            ProblemDomain.CONTINUOUS_OPTIMIZATION,
            objective=Objective(
                direction=ObjectiveDirection.MINIMIZE,
                expression_latex="2 + 3",
            ),
        )
        assert ps.objective.expression_latex == "2 + 3"

    def test_undeclared_bare_identifier_raises(self):
        """expression_latex='z' where z is not declared must fail."""
        with pytest.raises(ValidationError, match="undeclared identifiers"):
            _problem_spec(
                ProblemDomain.CONTINUOUS_OPTIMIZATION,
                variables=[_variable(symbol="x", space_ref="X")],
                functions=[_function(symbol="f")],
                objective=Objective(
                    direction=ObjectiveDirection.MINIMIZE,
                    expression_latex="z",
                ),
            )


# ===================================================================
# player_count schema field
# ===================================================================


class TestPlayerCount:
    """Contract tests for ProblemSpec.player_count."""

    def test_player_count_none_default(self):
        """ProblemSpec without player_count validates with default None."""
        ps = _problem_spec(ProblemDomain.CONTINUOUS_OPTIMIZATION)
        assert ps.player_count is None

    def test_player_count_positive_valid(self):
        """ProblemSpec with player_count=2 validates."""
        ps = _problem_spec(
            ProblemDomain.NON_COOPERATIVE_GAME,
            player_count=2,
            objective=_objective(ObjectiveDirection.EQUILIBRIUM),
        )
        assert ps.player_count == 2

    def test_player_count_zero_rejected(self):
        """ProblemSpec with player_count=0 raises ValidationError."""
        with pytest.raises(ValidationError, match="player_count must be a positive integer"):
            _problem_spec(
                ProblemDomain.NON_COOPERATIVE_GAME,
                player_count=0,
                objective=_objective(ObjectiveDirection.EQUILIBRIUM),
            )

    def test_player_count_negative_rejected(self):
        """ProblemSpec with player_count=-1 raises ValidationError."""
        with pytest.raises(ValidationError, match="player_count must be a positive integer"):
            _problem_spec(
                ProblemDomain.NON_COOPERATIVE_GAME,
                player_count=-1,
                objective=_objective(ObjectiveDirection.EQUILIBRIUM),
            )

    def test_player_count_ignored_continuous_opt(self):
        """ProblemSpec with problem_domain=continuous_optimization and player_count=2
        validates (field accepted but semantically ignored)."""
        ps = _problem_spec(
            ProblemDomain.CONTINUOUS_OPTIMIZATION,
            player_count=2,
        )
        assert ps.player_count == 2
        assert ps.problem_domain == ProblemDomain.CONTINUOUS_OPTIMIZATION


# ===================================================================
# Per-Player Strategy Spaces
# ===================================================================


class TestStrategySpaces:
    """strategy_spaces schema field validation."""

    def test_strategy_spaces_none_default(self):
        """ProblemSpec without strategy_spaces validates with default None."""
        ps = _problem_spec(ProblemDomain.NON_COOPERATIVE_GAME,
                           objective=_objective(ObjectiveDirection.EQUILIBRIUM))
        assert ps.strategy_spaces is None

    def test_valid_strategy_spaces(self):
        """ProblemSpec with valid strategy_spaces for 2 players validates."""
        ps = ProblemSpec(
            problem_domain=ProblemDomain.NON_COOPERATIVE_GAME,
            spaces=[
                Space(name="PriceSpace", base_type=BaseType.REAL),
                Space(name="QuantitySpace", base_type=BaseType.REAL),
            ],
            variables=[
                Variable(
                    symbol="s",
                    classification=VariableClassification.STRATEGY_PROFILE,
                    space_reference="PriceSpace",
                ),
            ],
            functions=[
                Function(symbol="u", domain=["PriceSpace"], codomain="Real",
                         properties=[FunctionProperty.CONTINUOUS]),
            ],
            objective=Objective(
                direction=ObjectiveDirection.EQUILIBRIUM,
                expression_latex="u(s)",
            ),
            player_count=2,
            strategy_spaces={"0": "PriceSpace", "1": "QuantitySpace"},
        )
        assert ps.strategy_spaces == {"0": "PriceSpace", "1": "QuantitySpace"}
        assert ps.player_count == 2

    def test_strategy_spaces_without_player_count_rejected(self):
        """strategy_spaces without player_count raises ValidationError."""
        with pytest.raises(ValidationError, match="strategy_spaces requires player_count"):
            ProblemSpec(
                problem_domain=ProblemDomain.NON_COOPERATIVE_GAME,
                spaces=[
                    Space(name="S0", base_type=BaseType.REAL),
                    Space(name="S1", base_type=BaseType.REAL),
                ],
                variables=[
                    Variable(
                        symbol="s",
                        classification=VariableClassification.STRATEGY_PROFILE,
                        space_reference="S0",
                    ),
                ],
                functions=[],
                objective=Objective(
                    direction=ObjectiveDirection.EQUILIBRIUM,
                    expression_latex="s",
                ),
                strategy_spaces={"0": "S0", "1": "S1"},
            )

    def test_strategy_spaces_count_mismatch_rejected(self):
        """strategy_spaces with wrong number of entries raises ValidationError."""
        with pytest.raises(ValidationError, match="strategy_spaces has 3 entries but player_count is 2"):
            ProblemSpec(
                problem_domain=ProblemDomain.NON_COOPERATIVE_GAME,
                spaces=[
                    Space(name="S0", base_type=BaseType.REAL),
                    Space(name="S1", base_type=BaseType.REAL),
                    Space(name="S2", base_type=BaseType.REAL),
                ],
                variables=[
                    Variable(
                        symbol="s",
                        classification=VariableClassification.STRATEGY_PROFILE,
                        space_reference="S0",
                    ),
                ],
                functions=[],
                objective=Objective(
                    direction=ObjectiveDirection.EQUILIBRIUM,
                    expression_latex="s",
                ),
                player_count=2,
                strategy_spaces={"0": "S0", "1": "S1", "2": "S2"},
            )

    def test_strategy_spaces_undeclared_space_rejected(self):
        """strategy_spaces referencing undeclared space raises ValidationError."""
        with pytest.raises(ValidationError, match="strategy_spaces\\['1'\\] references undeclared space"):
            ProblemSpec(
                problem_domain=ProblemDomain.NON_COOPERATIVE_GAME,
                spaces=[
                    Space(name="S0", base_type=BaseType.REAL),
                ],
                variables=[
                    Variable(
                        symbol="s",
                        classification=VariableClassification.STRATEGY_PROFILE,
                        space_reference="S0",
                    ),
                ],
                functions=[],
                objective=Objective(
                    direction=ObjectiveDirection.EQUILIBRIUM,
                    expression_latex="s",
                ),
                player_count=2,
                strategy_spaces={"0": "S0", "1": "NonExistent"},
            )

    def test_strategy_spaces_more_than_4_players_rejected(self):
        """strategy_spaces with > 4 players raises ValidationError."""
        with pytest.raises(ValidationError, match="limited to 4 players"):
            ProblemSpec(
                problem_domain=ProblemDomain.NON_COOPERATIVE_GAME,
                spaces=[Space(name=f"S{i}", base_type=BaseType.REAL) for i in range(5)],
                variables=[
                    Variable(
                        symbol="s",
                        classification=VariableClassification.STRATEGY_PROFILE,
                        space_reference="S0",
                    ),
                ],
                functions=[],
                objective=Objective(
                    direction=ObjectiveDirection.EQUILIBRIUM,
                    expression_latex="s",
                ),
                player_count=5,
                strategy_spaces={str(i): f"S{i}" for i in range(5)},
            )


# ===================================================================
# Discrete types (Int, Nat, Bool)
# ===================================================================


class TestDiscreteTypes:
    """BaseType.INT, BaseType.NAT, BaseType.BOOL schema validation."""

    def test_int_space_accepted(self):
        """INT space validates in a ProblemSpec."""
        ps = _problem_spec(
            ProblemDomain.CONTINUOUS_OPTIMIZATION,
            spaces=[Space(name="X", base_type=BaseType.INT)],
        )
        assert ps.spaces[0].base_type == BaseType.INT

    def test_nat_space_accepted(self):
        """NAT space validates in a ProblemSpec."""
        ps = _problem_spec(
            ProblemDomain.CONTINUOUS_OPTIMIZATION,
            spaces=[Space(name="X", base_type=BaseType.NAT)],
        )
        assert ps.spaces[0].base_type == BaseType.NAT

    def test_bool_space_accepted(self):
        """BOOL space validates in a ProblemSpec."""
        ps = _problem_spec(
            ProblemDomain.CONTINUOUS_OPTIMIZATION,
            spaces=[Space(name="X", base_type=BaseType.BOOL)],
            objective=Objective(
                direction=ObjectiveDirection.MINIMIZE,
                expression_latex="f(x)",
            ),
        )
        assert ps.spaces[0].base_type == BaseType.BOOL

    def test_int_variable_with_bounds_accepted(self):
        """INT variable with bounds passes validation."""
        ps = _problem_spec(
            ProblemDomain.CONTINUOUS_OPTIMIZATION,
            spaces=[Space(name="X", base_type=BaseType.INT)],
            variables=[Variable(
                symbol="x",
                classification=VariableClassification.ENDOGENOUS,
                space_reference="X",
                bounds=VariableBounds(lower_bound="0"),
            )],
        )
        assert ps.variables[0].bounds.lower_bound == "0"

    def test_nat_variable_with_bounds_accepted(self):
        """NAT variable with bounds passes validation."""
        ps = _problem_spec(
            ProblemDomain.CONTINUOUS_OPTIMIZATION,
            spaces=[Space(name="X", base_type=BaseType.NAT)],
            variables=[Variable(
                symbol="x",
                classification=VariableClassification.ENDOGENOUS,
                space_reference="X",
                bounds=VariableBounds(lower_bound="0"),
            )],
        )
        assert ps.variables[0].bounds.lower_bound == "0"

    def test_bool_variable_with_bounds_rejected(self):
        """BOOL variable with bounds raises ValidationError."""
        with pytest.raises(ValidationError, match="bounds on a Bool space"):
            _problem_spec(
                ProblemDomain.CONTINUOUS_OPTIMIZATION,
                spaces=[Space(name="X", base_type=BaseType.BOOL)],
                variables=[Variable(
                    symbol="x",
                    classification=VariableClassification.ENDOGENOUS,
                    space_reference="X",
                    bounds=VariableBounds(lower_bound="0"),
                )],
            )

    def test_bool_variable_without_bounds_accepted(self):
        """BOOL variable without bounds passes validation."""
        ps = _problem_spec(
            ProblemDomain.CONTINUOUS_OPTIMIZATION,
            spaces=[Space(name="X", base_type=BaseType.BOOL)],
            variables=[Variable(
                symbol="x",
                classification=VariableClassification.ENDOGENOUS,
                space_reference="X",
            )],
            objective=Objective(
                direction=ObjectiveDirection.MINIMIZE,
                expression_latex="f(x)",
            ),
        )
        assert ps.variables[0].bounds is None


# ---------------------------------------------------------------------------
# Corner-case: sqrt hint in undeclared identifier error
# ---------------------------------------------------------------------------
class TestSqrtHint:

    def test_sqrt_is_builtin_accepted(self):
        r"""sqrt is a recognized builtin (emits Real.sqrt); no declaration needed."""
        ps = _problem_spec(
            ProblemDomain.CONTINUOUS_OPTIMIZATION,
            variables=[_variable(symbol="x", space_ref="X")],
            functions=[_function(symbol="f")],
            objective=Objective(
                direction=ObjectiveDirection.MINIMIZE,
                expression_latex=r"f(\sqrt{x})",
            ),
        )
        assert ps.objective.expression_latex == r"f(\sqrt{x})"

    def test_non_sqrt_undeclared_no_hint(self):
        """When undeclared identifier is not sqrt, no sqrt hint should appear."""
        with pytest.raises(ValidationError, match="undeclared identifiers") as exc_info:
            _problem_spec(
                ProblemDomain.CONTINUOUS_OPTIMIZATION,
                variables=[_variable(symbol="x", space_ref="X")],
                functions=[_function(symbol="f")],
                objective=Objective(
                    direction=ObjectiveDirection.MINIMIZE,
                    expression_latex="f(z)",
                ),
            )
        assert "sqrt" not in str(exc_info.value).lower() or "Hint" not in str(exc_info.value)


# ===================================================================
# MockAgentRuntime for InformalRigorAgent tests
# ===================================================================
