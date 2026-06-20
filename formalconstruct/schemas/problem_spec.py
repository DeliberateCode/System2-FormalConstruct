from __future__ import annotations
import re
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, model_validator

_LEAN_IDENT = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_']*$")
_NUMERIC_LITERAL = re.compile(r"^-?[0-9]+(\.[0-9]+)?$")
_LEAN_RESERVED = frozenset({
    "by", "theorem", "def", "lemma", "instance", "class", "structure",
    "where", "let", "in", "do", "return", "if", "then", "else", "match",
    "with", "fun", "forall", "exists", "import", "open", "namespace",
    "section", "end", "variable", "axiom", "sorry", "Type", "Prop",
    "true", "false", "have", "show", "calc", "at", "set_option",
})


class ProblemDomain(str, Enum):
    CONTINUOUS_OPTIMIZATION = "continuous_optimization"
    NON_COOPERATIVE_GAME = "non_cooperative_game"
    COOPERATIVE_GAME = "cooperative_game"


class TopologicalProperty(str, Enum):
    COMPACT = "compact"
    CONNECTED = "connected"
    HAUSDORFF = "hausdorff"
    CONVEX = "convex"
    CLOSED = "closed"
    OPEN = "open"
    BOUNDED = "bounded"


class FunctionProperty(str, Enum):
    STRICT_CONVEX = "StrictConvex"
    CONVEX = "Convex"
    LINEAR = "Linear"
    CONTINUOUS = "Continuous"
    DIFFERENTIABLE = "Differentiable"
    STRICT_CONCAVE = "StrictConcave"
    CONCAVE = "Concave"


class VariableClassification(str, Enum):
    ENDOGENOUS = "endogenous"
    EXOGENOUS = "exogenous"
    STRATEGY_PROFILE = "strategy_profile"


class ObjectiveDirection(str, Enum):
    MINIMIZE = "minimize"
    MAXIMIZE = "maximize"
    EQUILIBRIUM = "equilibrium"
    PARETO_OPTIMAL = "pareto_optimal"
    INEQUALITY = "inequality"
    EXISTENTIAL_BOUND = "existential_bound"


class RelationOp(str, Enum):
    LE = "<="
    GE = ">="
    LT = "<"
    GT = ">"
    EQ = "="


class IndexType(str, Enum):
    NAT = "Nat"
    FIN_N = "FinN"


class SequenceRelationType(str, Enum):
    MAJORIZATION = "majorization"
    POINTWISE = "pointwise"
    SUM_CONSTRAINT = "sum_constraint"
    PRODUCT_CONSTRAINT = "product_constraint"
    RECURRENCE = "recurrence"
    INITIAL = "initial"


class BaseType(str, Enum):
    REAL = "Real"
    NONNEG_REAL = "NonnegReal"
    POS_REAL = "PosReal"
    REAL_N = "RealN"
    INT = "Int"
    NAT = "Nat"
    BOOL = "Bool"


class VariableBounds(BaseModel):
    lower_bound: Optional[str] = None
    upper_bound: Optional[str] = None
    strict_inequality: bool = False

    @model_validator(mode="after")
    def validate_bound_order(self) -> "VariableBounds":
        # Only ordered when both bounds are numeric literals; symbolic bounds
        # (e.g. parameter names) are not comparable and skip the check.
        if (
            self.lower_bound is not None
            and self.upper_bound is not None
            and _NUMERIC_LITERAL.match(self.lower_bound)
            and _NUMERIC_LITERAL.match(self.upper_bound)
            and float(self.lower_bound) > float(self.upper_bound)
        ):
            raise ValueError(
                f"lower_bound ({self.lower_bound}) must not exceed "
                f"upper_bound ({self.upper_bound})"
            )
        return self


class Space(BaseModel):
    name: str
    base_type: BaseType
    dimension: Optional[int] = None
    topological_properties: list[TopologicalProperty] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_dimension(self) -> "Space":
        if self.dimension is not None:
            if self.base_type == BaseType.REAL_N and self.dimension < 1:
                raise ValueError(
                    f"Space '{self.name}' has dimension={self.dimension}, "
                    f"but dimension must be a positive integer for REAL_N spaces"
                )
        return self


class Variable(BaseModel):
    symbol: str
    classification: VariableClassification
    space_reference: str
    bounds: Optional[VariableBounds] = None


class Function(BaseModel):
    symbol: str
    domain: list[str] = Field(default_factory=list)
    codomain: str = "Real"
    properties: list[FunctionProperty]
    # When set, the function is applied pointwise to a declared indexed
    # variable (e.g. Karamata's f(x_k)). Its convexity/concavity hypothesis is
    # then stated over `Set.univ` rather than a declared domain space.
    applied_to: Optional[str] = None


class IndexedVariable(BaseModel):
    """A sequence-valued variable, e.g. ``x : ℕ → ℝ``.

    *bounds*, when present, are interpreted pointwise (``∀ k, ...``)."""
    symbol: str
    index_type: IndexType = IndexType.NAT
    value_type: BaseType = BaseType.REAL
    bounds: Optional[VariableBounds] = None


class ParametricConstraint(BaseModel):
    """A scalar constraint emitted as a theorem hypothesis, e.g.
    ``a^2 + b^2 = 1``."""
    expression: str
    relation: RelationOp
    value: str
    description: Optional[str] = None


class SequenceRelation(BaseModel):
    """A relation over indexed variables emitted as a hypothesis.

    - ``pointwise`` / ``majorization``: ``∀ k, left k <rel> right k``
    - ``sum_constraint``: ``∑ k ∈ Finset.range n, left k = value``
    - ``product_constraint``: ``∏ k ∈ Finset.range n, left k = value``
    - ``recurrence``: ``∀ n, left (n + 1) = <expression>`` where the placeholder
      ``expr_var`` in ``expression`` is replaced by the previous term
      ``left n`` (e.g. ``expression="sqrt(3*t + 1)"``, ``expr_var="t"`` →
      ``∀ n, a (n + 1) = Real.sqrt (3 * a n + 1)``)
    - ``initial``: ``left index = value`` (e.g. ``a 0 = 1``)
    """
    type: SequenceRelationType
    left: str
    right: Optional[str] = None
    relation: RelationOp = RelationOp.LE
    value: Optional[str] = None
    expression: Optional[str] = None
    expr_var: str = "t"
    index: str = "0"
    index_var: str = "k"
    index_upper: str = "n"


class ExistentialBound(BaseModel):
    """A boundedness objective goal: ``∃ M, ∀ n, sequence n <rel> M``."""
    sequence: str
    bound_var: str = "M"
    relation: RelationOp = RelationOp.LT
    index_var: str = "n"


class Summation(BaseModel):
    """A structured summation-relation objective goal:
    ``∑ <term>(left_k) <rel> ∑ <term>(right_k)``.

    The per-term expression is either:
    - ``function``: an abstract declared function applied as ``f (x k)``, or
    - ``summand`` + ``summand_var``: a concrete expression template where the
      placeholder ``summand_var`` is replaced by the k-th sequence term, e.g.
      ``summand="log((1 + t)/t)"``, ``summand_var="t"`` →
      ``Real.log ((1 + x k) / x k)``.
    """
    left_sequence: str
    right_sequence: str
    function: Optional[str] = None
    summand: Optional[str] = None
    summand_var: str = "t"
    index_var: str = "k"
    index_upper: str = "n"


class Objective(BaseModel):
    direction: ObjectiveDirection
    expression_latex: str = ""
    target_variable: Optional[str] = None
    # INEQUALITY-direction goal shape:
    #  - scalar relation: `expression_latex <relation> bound`
    #  - summation relation: `summation` with `relation`
    relation: Optional[RelationOp] = None
    bound: Optional[str] = None
    summation: Optional[Summation] = None
    # EXISTENTIAL_BOUND-direction goal: `∃ M, ∀ n, sequence n <rel> M`
    existential_bound: Optional[ExistentialBound] = None


class ProblemSpec(BaseModel):
    """Canonical inter-stage data contract."""

    problem_domain: ProblemDomain
    primary_domain: Optional[ProblemDomain] = None
    domain_components: list[ProblemDomain] = Field(default_factory=list)
    spaces: list[Space]
    variables: list[Variable]
    functions: list[Function]
    objective: Objective
    indexed_variables: list[IndexedVariable] = Field(default_factory=list)
    constraints: list[ParametricConstraint] = Field(default_factory=list)
    sequence_relations: list[SequenceRelation] = Field(default_factory=list)
    player_count: Optional[int] = None
    strategy_spaces: Optional[dict[str, str]] = None

    @model_validator(mode="after")
    def validate_composite_domain(self) -> "ProblemSpec":
        """If domain_components is non-empty, primary_domain must be set.
        Only game_theory + continuous_optimization composites are allowed."""
        if self.domain_components:
            if self.primary_domain is None:
                raise ValueError(
                    "primary_domain is required when domain_components is specified"
                )
            allowed = {
                frozenset({
                    ProblemDomain.NON_COOPERATIVE_GAME,
                    ProblemDomain.CONTINUOUS_OPTIMIZATION,
                }),
                frozenset({
                    ProblemDomain.COOPERATIVE_GAME,
                    ProblemDomain.CONTINUOUS_OPTIMIZATION,
                }),
            }
            actual = frozenset(self.domain_components)
            if actual not in allowed:
                raise ValueError(
                    f"Unsupported domain composition: {self.domain_components}. "
                    f"Supported: game theory + continuous optimization."
                )
            if self.primary_domain not in self.domain_components:
                raise ValueError(
                    f"primary_domain '{self.primary_domain.value}' must be one of "
                    f"the domain_components {[d.value for d in self.domain_components]}"
                )
        return self

    @model_validator(mode="after")
    def validate_cross_field_references(self) -> "ProblemSpec":
        """Enforce cross-field reference integrity across spaces, variables, and functions."""
        errors: list[str] = []
        space_names = {s.name for s in self.spaces}
        self._check_player_count(errors)
        self._check_strategy_spaces(errors, space_names)
        self._check_identifiers(errors, space_names)
        self._check_uniqueness(errors)
        self._check_objective(errors)
        self._check_expression_identifiers(errors)
        self._check_extensions(errors)
        if errors:
            raise ValueError("; ".join(errors))
        return self

    def _check_player_count(self, errors: list[str]) -> None:
        if self.player_count is not None and self.player_count < 1:
            errors.append(f"player_count must be a positive integer, got {self.player_count}")

    def _check_strategy_spaces(self, errors: list[str], space_names: set[str]) -> None:
        if not self.strategy_spaces:
            return
        if self.player_count is None:
            errors.append("strategy_spaces requires player_count to be set")
        elif len(self.strategy_spaces) != self.player_count:
            errors.append(
                f"strategy_spaces has {len(self.strategy_spaces)} entries "
                f"but player_count is {self.player_count}"
            )
        if self.player_count is not None:
            expected_keys = {str(i) for i in range(self.player_count)}
            actual_keys = set(self.strategy_spaces.keys())
            unexpected = actual_keys - expected_keys
            missing = expected_keys - actual_keys
            if unexpected or missing:
                parts = [f"strategy_spaces keys must be \"0\"...\"{self.player_count - 1}\""]
                if unexpected:
                    parts.append(f"unexpected keys {unexpected}")
                if missing:
                    parts.append(f"missing keys {missing}")
                errors.append("; ".join(parts))
        for label, space_name in self.strategy_spaces.items():
            if space_name not in space_names:
                errors.append(f"strategy_spaces['{label}'] references undeclared space '{space_name}'")
        if self.player_count and self.player_count > 4:
            errors.append("Per-player strategy spaces are limited to 4 players maximum")

    def _check_identifiers(self, errors: list[str], space_names: set[str]) -> None:
        for space in self.spaces:
            if not _LEAN_IDENT.match(space.name):
                errors.append(f"Space name '{space.name}' is not a valid Lean 4 identifier")
            elif space.name in _LEAN_RESERVED:
                errors.append(f"Space name '{space.name}' is a Lean 4 reserved word")
        for var in self.variables:
            if var.space_reference not in space_names:
                errors.append(f"Variable '{var.symbol}' references undeclared space '{var.space_reference}'")
            if not _LEAN_IDENT.match(var.symbol):
                errors.append(f"Symbol '{var.symbol}' is not a valid Lean 4 identifier")
            elif var.symbol in _LEAN_RESERVED:
                errors.append(f"Symbol '{var.symbol}' is a Lean 4 reserved word")
            if var.bounds is not None:
                for val, _ in ((var.bounds.lower_bound, "lb"), (var.bounds.upper_bound, "ub")):
                    if val is not None and not _NUMERIC_LITERAL.match(val):
                        errors.append(f"Bound value '{val}' is not a safe numeric literal")
                if var.space_reference in space_names:
                    space = next(s for s in self.spaces if s.name == var.space_reference)
                    if space.base_type == BaseType.BOOL and (
                        var.bounds.lower_bound is not None or var.bounds.upper_bound is not None
                    ):
                        errors.append(
                            f"Variable '{var.symbol}' has bounds on a Bool space, "
                            f"which does not support interval notation"
                        )
        for func in self.functions:
            for d in func.domain:
                if d not in space_names:
                    errors.append(f"Function '{func.symbol}' domain entry '{d}' does not match any declared space")
            base_type_values = {bt.value for bt in BaseType}
            if func.codomain not in space_names and func.codomain not in base_type_values:
                errors.append(
                    f"Function '{func.symbol}' codomain '{func.codomain}' "
                    f"does not match any declared space or base type"
                )
            if not _LEAN_IDENT.match(func.symbol):
                errors.append(f"Symbol '{func.symbol}' is not a valid Lean 4 identifier")
            elif func.symbol in _LEAN_RESERVED:
                errors.append(f"Symbol '{func.symbol}' is a Lean 4 reserved word")
            if not func.properties:
                errors.append(f"Function '{func.symbol}' has empty properties list")

    def _check_uniqueness(self, errors: list[str]) -> None:
        space_names = [s.name for s in self.spaces]
        if len(space_names) != len(set(space_names)):
            errors.append(f"Duplicate space names: {set(n for n in space_names if space_names.count(n) > 1)}")
        var_syms = [v.symbol for v in self.variables]
        if len(var_syms) != len(set(var_syms)):
            errors.append(f"Duplicate variable symbols: {set(s for s in var_syms if var_syms.count(s) > 1)}")
        func_syms = [f.symbol for f in self.functions]
        if len(func_syms) != len(set(func_syms)):
            errors.append(f"Duplicate function symbols: {set(s for s in func_syms if func_syms.count(s) > 1)}")
        overlap = set(var_syms) & set(func_syms)
        if overlap:
            errors.append(f"Symbol collision between variables and functions: {overlap}")

    def _check_objective(self, errors: list[str]) -> None:
        tv = self.objective.target_variable
        if tv is not None and not _LEAN_IDENT.match(tv):
            errors.append(f"Objective target_variable '{tv}' is not a valid Lean 4 identifier")
        if tv:
            declared = {v.symbol for v in self.variables}
            if tv not in declared:
                errors.append(f"Objective target_variable '{tv}' does not match any declared variable symbol")
        if self.objective.direction in (ObjectiveDirection.MINIMIZE, ObjectiveDirection.MAXIMIZE):
            if not self.functions:
                errors.append(f"Optimization objective ({self.objective.direction.value}) requires at least one function")
            endogenous = [
                v for v in self.variables
                if v.classification == VariableClassification.ENDOGENOUS
            ]
            is_opt_domain = self.problem_domain == ProblemDomain.CONTINUOUS_OPTIMIZATION
            if is_opt_domain and not endogenous:
                errors.append(
                    f"Optimization objective ({self.objective.direction.value}) requires "
                    f"at least one endogenous variable"
                )
            if len(endogenous) > 1 and not tv:
                errors.append(
                    "target_variable is required when multiple endogenous "
                    "variables are declared"
                )
            if tv:
                tv_var = next((v for v in self.variables if v.symbol == tv), None)
                if tv_var and tv_var.classification != VariableClassification.ENDOGENOUS:
                    errors.append(
                        f"target_variable '{tv}' must be endogenous for "
                        f"{self.objective.direction.value}, got '{tv_var.classification.value}'"
                    )
        if self.objective.direction in (ObjectiveDirection.EQUILIBRIUM, ObjectiveDirection.PARETO_OPTIMAL):
            has_profile = any(
                v.classification == VariableClassification.STRATEGY_PROFILE
                for v in self.variables
            )
            if not has_profile:
                errors.append(
                    f"{self.objective.direction.value} objective requires at least "
                    f"one strategy_profile variable"
                )
            if not self.functions:
                errors.append(
                    f"{self.objective.direction.value} objective requires at least "
                    f"one utility/payoff function"
                )

    def _check_expression_identifiers(self, errors: list[str]) -> None:
        if not self.objective.expression_latex.strip():
            return
        try:
            from formalconstruct.schemas._expression_check import (
                collect_expression_identifiers,
                check_function_arity,
            )
            from formalconstruct.core.expression_parser import KNOWN_BUILTIN_FUNCTIONS
            func_sym_set = {f.symbol for f in self.functions}
            var_sym_set = {v.symbol for v in self.variables}
            indexed_sym_set = {iv.symbol for iv in self.indexed_variables}
            expr_idents = collect_expression_identifiers(self.objective.expression_latex, func_sym_set)
            if expr_idents is not None:
                undeclared = expr_idents - (
                    var_sym_set | func_sym_set | indexed_sym_set | set(KNOWN_BUILTIN_FUNCTIONS)
                )
                if undeclared:
                    errors.append(
                        f"expression_latex contains undeclared identifiers: {undeclared}"
                    )
            func_arities = {f.symbol: len(f.domain) for f in self.functions}
            arity_errors = check_function_arity(
                self.objective.expression_latex, func_sym_set, func_arities,
            )
            errors.extend(arity_errors)
        except ValueError as exc:
            errors.append(str(exc))
        except Exception as exc:
            errors.append(f"expression_latex is malformed: {exc}")

    def _check_extensions(self, errors: list[str]) -> None:
        """Validate indexed variables, parametric constraints, sequence
        relations, and convex-on-sequence function applications."""
        from formalconstruct.core.expression_parser import KNOWN_BUILTIN_FUNCTIONS

        var_syms = {v.symbol for v in self.variables}
        func_syms = {f.symbol for f in self.functions}
        indexed_syms = {iv.symbol for iv in self.indexed_variables}

        # -- indexed variables --
        for iv in self.indexed_variables:
            if not _LEAN_IDENT.match(iv.symbol):
                errors.append(f"Indexed variable '{iv.symbol}' is not a valid Lean 4 identifier")
            elif iv.symbol in _LEAN_RESERVED:
                errors.append(f"Indexed variable '{iv.symbol}' is a Lean 4 reserved word")
            if iv.bounds is not None:
                for val in (iv.bounds.lower_bound, iv.bounds.upper_bound):
                    if val is not None and not _NUMERIC_LITERAL.match(val):
                        errors.append(
                            f"Indexed variable '{iv.symbol}' bound '{val}' "
                            f"is not a safe numeric literal"
                        )
        dup_indexed = {s for s in indexed_syms if [iv.symbol for iv in self.indexed_variables].count(s) > 1}
        if dup_indexed:
            errors.append(f"Duplicate indexed variable symbols: {dup_indexed}")
        collisions = indexed_syms & (var_syms | func_syms)
        if collisions:
            errors.append(f"Indexed variable symbols collide with variables/functions: {collisions}")

        # -- functions applied to a sequence --
        for func in self.functions:
            if func.applied_to is not None and func.applied_to not in indexed_syms:
                errors.append(
                    f"Function '{func.symbol}' applied_to '{func.applied_to}' "
                    f"does not match any declared indexed variable"
                )

        # -- parametric constraints --
        allowed_idents = var_syms | func_syms | indexed_syms | set(KNOWN_BUILTIN_FUNCTIONS)
        for i, c in enumerate(self.constraints):
            if not _NUMERIC_LITERAL.match(c.value):
                errors.append(
                    f"constraints[{i}] value '{c.value}' is not a safe numeric literal"
                )
            try:
                from formalconstruct.schemas._expression_check import (
                    collect_expression_identifiers,
                )
                idents = collect_expression_identifiers(c.expression, func_syms)
                if idents is not None:
                    undeclared = idents - allowed_idents
                    if undeclared:
                        errors.append(
                            f"constraints[{i}] expression contains undeclared "
                            f"identifiers: {undeclared}"
                        )
            except ValueError as exc:
                errors.append(f"constraints[{i}] expression is malformed: {exc}")

        # -- sequence relations --
        from formalconstruct.schemas._expression_check import (
            collect_expression_identifiers,
        )
        for i, sr in enumerate(self.sequence_relations):
            if sr.left not in indexed_syms:
                errors.append(
                    f"sequence_relations[{i}] left '{sr.left}' is not a declared indexed variable"
                )
            if sr.type in (SequenceRelationType.MAJORIZATION, SequenceRelationType.POINTWISE):
                if sr.right is None:
                    errors.append(f"sequence_relations[{i}] ({sr.type.value}) requires 'right'")
                elif sr.right not in indexed_syms:
                    errors.append(
                        f"sequence_relations[{i}] right '{sr.right}' is not a declared indexed variable"
                    )
            elif sr.type == SequenceRelationType.RECURRENCE:
                if sr.expression is None:
                    errors.append(f"sequence_relations[{i}] (recurrence) requires 'expression'")
                else:
                    try:
                        idents = collect_expression_identifiers(sr.expression, func_syms)
                        if idents is not None:
                            undeclared = idents - (
                                func_syms | set(KNOWN_BUILTIN_FUNCTIONS) | {sr.expr_var}
                            )
                            if undeclared:
                                errors.append(
                                    f"sequence_relations[{i}] (recurrence) expression contains "
                                    f"undeclared identifiers: {undeclared} (expected the placeholder "
                                    f"'{sr.expr_var}', builtins, or declared functions)"
                                )
                    except ValueError as exc:
                        errors.append(f"sequence_relations[{i}] (recurrence) expression is malformed: {exc}")
            else:  # SUM_CONSTRAINT, PRODUCT_CONSTRAINT, INITIAL
                if sr.value is None or not _NUMERIC_LITERAL.match(sr.value):
                    errors.append(
                        f"sequence_relations[{i}] ({sr.type.value}) requires a numeric 'value'"
                    )

        # -- summation objective --
        summ = self.objective.summation
        if summ is not None:
            for seq_attr in (summ.left_sequence, summ.right_sequence):
                if seq_attr not in indexed_syms:
                    errors.append(
                        f"objective.summation references '{seq_attr}' "
                        f"which is not a declared indexed variable"
                    )
            if summ.summand is None and summ.function is None:
                errors.append(
                    "objective.summation requires either 'function' or 'summand'"
                )
            if summ.function is not None and summ.function not in func_syms:
                errors.append(
                    f"objective.summation function '{summ.function}' is not a declared function"
                )
            if summ.summand is not None:
                try:
                    from formalconstruct.schemas._expression_check import (
                        collect_expression_identifiers,
                    )
                    idents = collect_expression_identifiers(summ.summand, func_syms)
                    if idents is not None:
                        allowed = (
                            func_syms | set(KNOWN_BUILTIN_FUNCTIONS) | {summ.summand_var}
                        )
                        undeclared = idents - allowed
                        if undeclared:
                            errors.append(
                                f"objective.summation summand contains undeclared "
                                f"identifiers: {undeclared} (expected the placeholder "
                                f"'{summ.summand_var}', builtins, or declared functions)"
                            )
                except ValueError as exc:
                    errors.append(f"objective.summation summand is malformed: {exc}")

        # -- existential-bound objective --
        eb = self.objective.existential_bound
        if eb is not None and eb.sequence not in indexed_syms:
            errors.append(
                f"objective.existential_bound sequence '{eb.sequence}' "
                f"is not a declared indexed variable"
            )

        # -- scalar inequality bound --
        obj = self.objective
        if (
            obj.direction == ObjectiveDirection.INEQUALITY
            and obj.summation is None
            and obj.bound is not None
            and not (
                _NUMERIC_LITERAL.match(obj.bound)
                or obj.bound in var_syms
                or obj.bound in indexed_syms
            )
        ):
            errors.append(
                f"objective.bound '{obj.bound}' must be a numeric literal "
                f"or a declared variable"
            )
