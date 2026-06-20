"""Tests for the ProblemSpec schema extensions: indexed variables, parametric
constraints, sequence relations, convex-on-sequence functions, and the
`inequality` objective direction — plus their Lean scaffolding."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from formalconstruct.core.expression_parser import (
    BUILTIN_TO_LEAN,
    ExpressionParser,
    emit_lean,
)
from formalconstruct.schemas.problem_spec import (
    BaseType,
    ExistentialBound,
    Function,
    FunctionProperty,
    IndexedVariable,
    Objective,
    ObjectiveDirection,
    ParametricConstraint,
    ProblemDomain,
    ProblemSpec,
    RelationOp,
    SequenceRelation,
    SequenceRelationType,
    Space,
    Summation,
    Variable,
    VariableBounds,
    VariableClassification,
)

SPECS_DIR = Path(__file__).parents[1] / "data" / "specs"


def _real_line() -> Space:
    return Space(name="RealLine", base_type=BaseType.REAL)


def _exogenous(symbol: str) -> Variable:
    return Variable(
        symbol=symbol,
        classification=VariableClassification.EXOGENOUS,
        space_reference="RealLine",
    )


# ===================================================================
# Builtin transcendental emission
# ===================================================================


class TestBuiltinEmission:
    def test_sin_cos_emit_qualified(self):
        ast = ExpressionParser(
            "a * sin(x) + b * cos(x)", known_functions=["sin", "cos"]
        ).parse()
        assert emit_lean(ast, func_rename=BUILTIN_TO_LEAN) == (
            "a * Real.sin x + b * Real.cos x"
        )

    def test_no_rename_leaves_names(self):
        ast = ExpressionParser("sin(x)", known_functions=["sin"]).parse()
        assert emit_lean(ast) == "sin x"

    def test_sqrt_is_builtin(self):
        assert BUILTIN_TO_LEAN["sqrt"] == "Real.sqrt"


# ===================================================================
# Schema validation
# ===================================================================


class TestInequalityObjective:
    def test_scalar_inequality_with_builtins_validates(self):
        ps = ProblemSpec(
            problem_domain=ProblemDomain.CONTINUOUS_OPTIMIZATION,
            spaces=[_real_line()],
            variables=[_exogenous("a"), _exogenous("b"), _exogenous("x")],
            functions=[],
            constraints=[
                ParametricConstraint(expression="a^2 + b^2", relation=RelationOp.EQ, value="1")
            ],
            objective=Objective(
                direction=ObjectiveDirection.INEQUALITY,
                expression_latex="a * sin(x) + b * cos(x)",
                relation=RelationOp.LE,
                bound="1",
            ),
        )
        assert ps.objective.direction == ObjectiveDirection.INEQUALITY

    def test_constraint_non_numeric_value_rejected(self):
        with pytest.raises(ValidationError, match="not a safe numeric literal"):
            ProblemSpec(
                problem_domain=ProblemDomain.CONTINUOUS_OPTIMIZATION,
                spaces=[_real_line()],
                variables=[_exogenous("a")],
                functions=[],
                constraints=[
                    ParametricConstraint(expression="a", relation=RelationOp.EQ, value="c")
                ],
                objective=Objective(
                    direction=ObjectiveDirection.INEQUALITY,
                    expression_latex="a",
                    relation=RelationOp.LE,
                    bound="1",
                ),
            )

    def test_constraint_undeclared_identifier_rejected(self):
        with pytest.raises(ValidationError, match="undeclared identifiers"):
            ProblemSpec(
                problem_domain=ProblemDomain.CONTINUOUS_OPTIMIZATION,
                spaces=[_real_line()],
                variables=[_exogenous("a")],
                functions=[],
                constraints=[
                    ParametricConstraint(expression="a + z", relation=RelationOp.EQ, value="1")
                ],
                objective=Objective(
                    direction=ObjectiveDirection.INEQUALITY,
                    expression_latex="a",
                    relation=RelationOp.LE,
                    bound="1",
                ),
            )


class TestIndexedVariables:
    def test_indexed_variable_validates(self):
        ps = ProblemSpec(
            problem_domain=ProblemDomain.CONTINUOUS_OPTIMIZATION,
            spaces=[_real_line()],
            variables=[],
            indexed_variables=[IndexedVariable(symbol="x")],
            functions=[Function(symbol="f", properties=[FunctionProperty.CONVEX], applied_to="x")],
            objective=Objective(
                direction=ObjectiveDirection.INEQUALITY,
                summation=Summation(function="f", left_sequence="x", right_sequence="x"),
                relation=RelationOp.GE,
            ),
        )
        assert ps.indexed_variables[0].symbol == "x"

    def test_indexed_symbol_collision_with_function_rejected(self):
        with pytest.raises(ValidationError, match="collide with variables/functions"):
            ProblemSpec(
                problem_domain=ProblemDomain.CONTINUOUS_OPTIMIZATION,
                spaces=[_real_line()],
                variables=[],
                indexed_variables=[IndexedVariable(symbol="f")],
                functions=[Function(symbol="f", properties=[FunctionProperty.CONVEX], applied_to="f")],
                objective=Objective(
                    direction=ObjectiveDirection.INEQUALITY,
                    summation=Summation(function="f", left_sequence="f", right_sequence="f"),
                    relation=RelationOp.GE,
                ),
            )

    def test_applied_to_undeclared_indexed_rejected(self):
        with pytest.raises(ValidationError, match="applied_to.*indexed variable"):
            ProblemSpec(
                problem_domain=ProblemDomain.CONTINUOUS_OPTIMIZATION,
                spaces=[_real_line()],
                variables=[],
                indexed_variables=[IndexedVariable(symbol="x")],
                functions=[Function(symbol="f", properties=[FunctionProperty.CONVEX], applied_to="missing")],
                objective=Objective(
                    direction=ObjectiveDirection.INEQUALITY,
                    summation=Summation(function="f", left_sequence="x", right_sequence="x"),
                    relation=RelationOp.GE,
                ),
            )


class TestSequenceRelations:
    def test_pointwise_requires_right(self):
        with pytest.raises(ValidationError, match="requires 'right'"):
            ProblemSpec(
                problem_domain=ProblemDomain.CONTINUOUS_OPTIMIZATION,
                spaces=[_real_line()],
                variables=[],
                indexed_variables=[IndexedVariable(symbol="x")],
                functions=[Function(symbol="f", properties=[FunctionProperty.CONVEX], applied_to="x")],
                sequence_relations=[
                    SequenceRelation(type=SequenceRelationType.POINTWISE, left="x")
                ],
                objective=Objective(
                    direction=ObjectiveDirection.INEQUALITY,
                    summation=Summation(function="f", left_sequence="x", right_sequence="x"),
                    relation=RelationOp.GE,
                ),
            )

    def test_sum_constraint_requires_value(self):
        with pytest.raises(ValidationError, match="requires a numeric 'value'"):
            ProblemSpec(
                problem_domain=ProblemDomain.CONTINUOUS_OPTIMIZATION,
                spaces=[_real_line()],
                variables=[],
                indexed_variables=[IndexedVariable(symbol="x")],
                functions=[Function(symbol="f", properties=[FunctionProperty.CONVEX], applied_to="x")],
                sequence_relations=[
                    SequenceRelation(type=SequenceRelationType.SUM_CONSTRAINT, left="x")
                ],
                objective=Objective(
                    direction=ObjectiveDirection.INEQUALITY,
                    summation=Summation(function="f", left_sequence="x", right_sequence="x"),
                    relation=RelationOp.GE,
                ),
            )


# ===================================================================
# Scaffolding
# ===================================================================


class TestScalarInequalityScaffold:
    def test_emits_constraint_hypothesis_and_goal(self, agent):
        ps = ProblemSpec(
            problem_domain=ProblemDomain.CONTINUOUS_OPTIMIZATION,
            spaces=[_real_line()],
            variables=[_exogenous("a"), _exogenous("b"), _exogenous("x")],
            functions=[],
            constraints=[
                ParametricConstraint(expression="a^2 + b^2", relation=RelationOp.EQ, value="1")
            ],
            objective=Objective(
                direction=ObjectiveDirection.INEQUALITY,
                expression_latex="a * sin(x) + b * cos(x)",
                relation=RelationOp.LE,
                bound="1",
            ),
        )
        content = agent.scaffold(ps).content
        assert "variable (h_constr_0 : a ^ 2 + b ^ 2 = 1)" in content
        assert "include h_constr_0" in content
        assert "a * Real.sin x + b * Real.cos x ≤ 1" in content
        assert "theorem inequality_goal" in content
        assert "sorry" in content


class TestSummationScaffold:
    def test_emits_indexed_vars_and_summation_goal(self, agent):
        ps = ProblemSpec(
            problem_domain=ProblemDomain.CONTINUOUS_OPTIMIZATION,
            spaces=[_real_line()],
            variables=[],
            indexed_variables=[
                IndexedVariable(symbol="x", bounds=VariableBounds(lower_bound="0", strict_inequality=True)),
                IndexedVariable(symbol="y", bounds=VariableBounds(lower_bound="0", strict_inequality=True)),
            ],
            functions=[Function(symbol="f", properties=[FunctionProperty.CONVEX], applied_to="x")],
            sequence_relations=[
                SequenceRelation(
                    type=SequenceRelationType.MAJORIZATION, left="x", right="y", relation=RelationOp.LE
                )
            ],
            objective=Objective(
                direction=ObjectiveDirection.INEQUALITY,
                summation=Summation(function="f", left_sequence="x", right_sequence="y"),
                relation=RelationOp.GE,
            ),
        )
        content = agent.scaffold(ps).content
        assert "variable (n : ℕ)" in content
        assert "variable (x : ℕ → ℝ)" in content
        assert "variable (y : ℕ → ℝ)" in content
        assert "∀ k, 0 < x k" in content
        assert "variable (h_seq_0 : ∀ k, x k ≤ y k)" in content
        assert "ConvexOn ℝ Set.univ f" in content
        assert "include h_x_lb h_y_lb h_seq_0" in content
        assert "∑ k ∈ Finset.range n, f (x k) ≥ ∑ k ∈ Finset.range n, f (y k)" in content
        assert "sorry" in content

    def test_summand_template_emits_concrete_term(self, agent):
        ps = ProblemSpec(
            problem_domain=ProblemDomain.CONTINUOUS_OPTIMIZATION,
            spaces=[_real_line()],
            variables=[],
            indexed_variables=[
                IndexedVariable(symbol="x", bounds=VariableBounds(lower_bound="0", strict_inequality=True)),
                IndexedVariable(symbol="y", bounds=VariableBounds(lower_bound="0", strict_inequality=True)),
            ],
            functions=[],
            sequence_relations=[
                SequenceRelation(
                    type=SequenceRelationType.POINTWISE, left="x", right="y", relation=RelationOp.LE
                )
            ],
            objective=Objective(
                direction=ObjectiveDirection.INEQUALITY,
                summation=Summation(
                    summand="log((1 + t) / t)", summand_var="t",
                    left_sequence="x", right_sequence="y",
                ),
                relation=RelationOp.GE,
            ),
        )
        content = agent.scaffold(ps).content
        assert (
            "∑ k ∈ Finset.range n, Real.log ((1 + x k) / x k) ≥ "
            "∑ k ∈ Finset.range n, Real.log ((1 + y k) / y k)"
        ) in content
        assert "include h_x_lb h_y_lb h_seq_0" in content


# ===================================================================
# End-to-end from the shipped failing-problem specs
# ===================================================================


class TestFailingProblemSpecs:
    @pytest.mark.parametrize("name", ["lean_workbook_plus_18380", "lean_workbook_plus_32710"])
    def test_spec_validates(self, name):
        data = json.loads((SPECS_DIR / f"{name}.json").read_text())
        ps = ProblemSpec.model_validate(data)
        assert ps.objective.direction == ObjectiveDirection.INEQUALITY

    @pytest.mark.parametrize("name", ["lean_workbook_plus_18380", "lean_workbook_plus_32710"])
    def test_spec_scaffolds(self, agent, name):
        data = json.loads((SPECS_DIR / f"{name}.json").read_text())
        ps = ProblemSpec.model_validate(data)
        result = agent.scaffold(ps)
        assert "theorem inequality_goal" in result.content
        assert "sorry" in result.content
        assert len(result.goals) == 1

    def test_18380_matches_ground_truth_shape(self, agent):
        data = json.loads((SPECS_DIR / "lean_workbook_plus_18380.json").read_text())
        content = agent.scaffold(ProblemSpec.model_validate(data)).content
        assert "a * Real.sin x + b * Real.cos x ≤ 1" in content
        assert "a ^ 2 + b ^ 2 = 1" in content

    def test_32710_matches_ground_truth_shape(self, agent):
        data = json.loads((SPECS_DIR / "lean_workbook_plus_32710.json").read_text())
        content = agent.scaffold(ProblemSpec.model_validate(data)).content
        assert "x : ℕ → ℝ" in content
        assert "include h_x_lb h_y_lb h_seq_0" in content
        assert (
            "∑ k ∈ Finset.range n, Real.log ((1 + x k) / x k) ≥ "
            "∑ k ∈ Finset.range n, Real.log ((1 + y k) / y k)"
        ) in content


# ===================================================================
# Recursive sequences + existential-bound objective
# ===================================================================


def _bounded_recurrence_spec(**overrides) -> dict:
    base = dict(
        problem_domain=ProblemDomain.CONTINUOUS_OPTIMIZATION,
        spaces=[_real_line()],
        variables=[],
        indexed_variables=[IndexedVariable(symbol="a")],
        functions=[],
        sequence_relations=[
            SequenceRelation(type=SequenceRelationType.INITIAL, left="a", index="0", value="1"),
            SequenceRelation(
                type=SequenceRelationType.RECURRENCE, left="a",
                expression="sqrt(3*t + 1)", expr_var="t", index_var="n",
            ),
        ],
        objective=Objective(
            direction=ObjectiveDirection.EXISTENTIAL_BOUND,
            existential_bound=ExistentialBound(
                sequence="a", bound_var="M", relation=RelationOp.LT, index_var="n",
            ),
        ),
    )
    base.update(overrides)
    return base


class TestRecursiveSequence:
    def test_validates(self):
        ps = ProblemSpec(**_bounded_recurrence_spec())
        assert ps.objective.direction == ObjectiveDirection.EXISTENTIAL_BOUND

    def test_recurrence_requires_expression(self):
        with pytest.raises(ValidationError, match="recurrence.*requires 'expression'"):
            ProblemSpec(**_bounded_recurrence_spec(sequence_relations=[
                SequenceRelation(type=SequenceRelationType.RECURRENCE, left="a", index_var="n"),
            ]))

    def test_initial_requires_numeric_value(self):
        with pytest.raises(ValidationError, match="initial.*requires a numeric 'value'"):
            ProblemSpec(**_bounded_recurrence_spec(sequence_relations=[
                SequenceRelation(type=SequenceRelationType.INITIAL, left="a", index="0", value="x"),
            ]))

    def test_recurrence_undeclared_identifier_rejected(self):
        with pytest.raises(ValidationError, match="recurrence.*undeclared identifiers"):
            ProblemSpec(**_bounded_recurrence_spec(sequence_relations=[
                SequenceRelation(
                    type=SequenceRelationType.RECURRENCE, left="a",
                    expression="sqrt(3*t + z)", expr_var="t", index_var="n",
                ),
            ]))

    def test_existential_bound_undeclared_sequence_rejected(self):
        with pytest.raises(ValidationError, match="existential_bound sequence.*not a declared indexed"):
            ProblemSpec(**_bounded_recurrence_spec(
                objective=Objective(
                    direction=ObjectiveDirection.EXISTENTIAL_BOUND,
                    existential_bound=ExistentialBound(sequence="b", relation=RelationOp.LT),
                ),
            ))

    def test_scaffold_shape(self, agent):
        content = agent.scaffold(ProblemSpec(**_bounded_recurrence_spec())).content
        assert "variable (a : ℕ → ℝ)" in content
        assert "variable (h_seq_0 : a 0 = 1)" in content
        assert "variable (h_seq_1 : ∀ n, a (n + 1) = Real.sqrt (3 * a n + 1))" in content
        assert "include h_seq_0 h_seq_1" in content
        assert "theorem bound_goal" in content
        assert "∃ M, ∀ n, a n < M" in content

    def test_62528_spec_validates_and_scaffolds(self, agent):
        data = json.loads((SPECS_DIR / "lean_workbook_plus_62528.json").read_text())
        ps = ProblemSpec.model_validate(data)
        assert ps.objective.direction == ObjectiveDirection.EXISTENTIAL_BOUND
        content = agent.scaffold(ps).content
        assert "∃ M, ∀ n, a n < M" in content
        assert "Real.sqrt (3 * a n + 1)" in content
        assert len(agent.scaffold(ps).goals) == 1


# ===================================================================
# Code-review fixes
# ===================================================================


class TestReviewFixes:
    def test_indexed_variable_non_numeric_bound_rejected(self):
        with pytest.raises(ValidationError, match="bound.*not a safe numeric literal"):
            ProblemSpec(
                problem_domain=ProblemDomain.CONTINUOUS_OPTIMIZATION,
                spaces=[_real_line()],
                variables=[],
                indexed_variables=[
                    IndexedVariable(symbol="x", bounds=VariableBounds(lower_bound="abc")),
                ],
                functions=[Function(symbol="f", properties=[FunctionProperty.CONVEX], applied_to="x")],
                objective=Objective(
                    direction=ObjectiveDirection.INEQUALITY,
                    summation=Summation(function="f", left_sequence="x", right_sequence="x"),
                    relation=RelationOp.GE,
                ),
            )

    def test_endogenous_var_declared_for_inequality(self, agent):
        ps = ProblemSpec(
            problem_domain=ProblemDomain.CONTINUOUS_OPTIMIZATION,
            spaces=[Space(name="S", base_type=BaseType.REAL)],
            variables=[
                Variable(symbol="x", classification=VariableClassification.ENDOGENOUS, space_reference="S"),
            ],
            functions=[],
            constraints=[
                ParametricConstraint(expression="x", relation=RelationOp.GE, value="0"),
            ],
            objective=Objective(
                direction=ObjectiveDirection.INEQUALITY,
                expression_latex="x",
                relation=RelationOp.LE,
                bound="1",
            ),
        )
        content = agent.scaffold(ps).content
        # Without the fix the endogenous `x` would be undeclared in the relation goal.
        assert "variable (x : ℝ)" in content
        assert "x ≤ 1" in content

    def test_inequality_undeclared_bound_rejected(self):
        with pytest.raises(ValidationError, match="objective.bound.*numeric literal"):
            ProblemSpec(
                problem_domain=ProblemDomain.CONTINUOUS_OPTIMIZATION,
                spaces=[_real_line()],
                variables=[_exogenous("x")],
                functions=[],
                objective=Objective(
                    direction=ObjectiveDirection.INEQUALITY,
                    expression_latex="x", relation=RelationOp.LE, bound="B",
                ),
            )

    def test_constraint_function_declared_before_hypothesis(self, agent):
        ps = ProblemSpec(
            problem_domain=ProblemDomain.CONTINUOUS_OPTIMIZATION,
            spaces=[Space(name="S", base_type=BaseType.REAL)],
            variables=[_exogenous_s("x")],
            functions=[Function(symbol="f", domain=["S"], codomain="Real", properties=[FunctionProperty.CONVEX])],
            constraints=[ParametricConstraint(expression="f(x)", relation=RelationOp.EQ, value="1")],
            objective=Objective(
                direction=ObjectiveDirection.INEQUALITY,
                expression_latex="x", relation=RelationOp.LE, bound="1",
            ),
        )
        lines = agent.scaffold(ps).content.split("\n")
        f_idx = next(i for i, ln in enumerate(lines) if ln.startswith("variable (f "))
        h_idx = next(i for i, ln in enumerate(lines) if "h_constr_0" in ln and ln.startswith("variable"))
        assert f_idx < h_idx  # function declared before the constraint that uses it


def _exogenous_s(symbol: str) -> Variable:
    return Variable(
        symbol=symbol,
        classification=VariableClassification.EXOGENOUS,
        space_reference="S",
    )
