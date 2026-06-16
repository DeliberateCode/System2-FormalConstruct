from __future__ import annotations

from formalconstruct.core.exceptions import ExpressionParseError, ScaffoldingError
from formalconstruct.core.expression_parser import (
    BUILTIN_TO_LEAN,
    KNOWN_BUILTIN_FUNCTIONS,
    BinOp,
    ExprNode,
    ExpressionParser,
    FuncApp,
    Ident,
    NumberLit,
    UnaryNeg,
    emit_lean,
)
from formalconstruct.domains.registry import (
    DomainMapper,
    _lean_type_for_space,
    property_hypothesis,
)
from formalconstruct.schemas.problem_spec import (
    BaseType,
    Function,
    FunctionProperty,
    IndexedVariable,
    IndexType,
    Objective,
    ObjectiveDirection,
    ParametricConstraint,
    ProblemSpec,
    RelationOp,
    SequenceRelation,
    SequenceRelationType,
    Space,
    Variable,
    VariableClassification,
)

_RELATION_TO_LEAN: dict[RelationOp, str] = {
    RelationOp.LE: "≤",
    RelationOp.GE: "≥",
    RelationOp.LT: "<",
    RelationOp.GT: ">",
    RelationOp.EQ: "=",
}

_INDEXED_VALUE_TYPE: dict[BaseType, str] = {
    BaseType.INT: "ℤ",
    BaseType.NAT: "ℕ",
    BaseType.BOOL: "Bool",
}


def _emit_expression_with_builtins(expr: str, declared_funcs: list[str]) -> str:
    """Parse a scalar expression and emit Lean, rewriting builtins to Real.*."""
    known = list(set(declared_funcs) | KNOWN_BUILTIN_FUNCTIONS)
    ast = ExpressionParser(expr, known_functions=known).parse()
    return emit_lean(ast, func_rename=BUILTIN_TO_LEAN)


def _subst_ident(node: ExprNode, name: str, replacement: ExprNode) -> ExprNode:
    """Replace every ``Ident(name)`` in *node* with *replacement*."""
    if isinstance(node, Ident):
        return replacement if node.name == name else node
    if isinstance(node, FuncApp):
        return FuncApp(
            func=node.func,
            args=tuple(_subst_ident(a, name, replacement) for a in node.args),
        )
    if isinstance(node, BinOp):
        return BinOp(
            op=node.op,
            left=_subst_ident(node.left, name, replacement),
            right=_subst_ident(node.right, name, replacement),
        )
    if isinstance(node, UnaryNeg):
        return UnaryNeg(operand=_subst_ident(node.operand, name, replacement))
    return node


def _emit_summand_term(
    summand: str, summand_var: str, sequence: str, index_var: str,
    declared_funcs: list[str],
) -> str:
    """Emit a concrete summand with the placeholder replaced by ``seq k``."""
    known = list(set(declared_funcs) | KNOWN_BUILTIN_FUNCTIONS)
    ast = ExpressionParser(summand, known_functions=known).parse()
    replacement = FuncApp(func=sequence, args=(Ident(name=index_var),))
    rewritten = _subst_ident(ast, summand_var, replacement)
    return emit_lean(rewritten, func_rename=BUILTIN_TO_LEAN)

# AXLE requires a single `import Mathlib`, not individual module imports.
_BASE_IMPORTS = ["import Mathlib"]


_CONVEXITY_INTERVAL_LEMMA: dict[str, str] = {
    "Set.Ici": "convex_Ici",
    "Set.Ioi": "convex_Ioi",
    "Set.Iic": "convex_Iic",
    "Set.Iio": "convex_Iio",
    "Set.Icc": "convex_Icc",
    "Set.Ioo": "convex_Ioo",
    "Set.univ": "convex_univ",
}


def _parse_expression_ast(
    expression_latex: str, func_symbols: list[str]
) -> ExprNode:
    """Parse expression_latex into an AST. Raises ScaffoldingError on failure."""
    if not expression_latex.strip():
        raise ScaffoldingError("expression_latex is empty")
    try:
        return ExpressionParser(expression_latex, known_functions=func_symbols).parse()
    except ExpressionParseError as e:
        raise ScaffoldingError(
            f"Cannot parse expression_latex '{expression_latex}': {e}"
        ) from e


def _expression_to_lean_body(
    expression_latex: str, func_symbols: list[str]
) -> tuple[str, ExprNode]:
    """Convert expression_latex to Lean syntax. Returns (lean_body, ast)."""
    ast = _parse_expression_ast(expression_latex, func_symbols)
    result = emit_lean(ast)
    if not (_collect_func_names_from_ast(ast) & set(func_symbols)):
        raise ScaffoldingError(
            f"Cannot parse expression_latex '{expression_latex}': "
            f"no recognized function symbols found. "
            f"Declared functions: {func_symbols}"
        )
    return result, ast


_CONVEXITY_PROPS = {FunctionProperty.STRICT_CONVEX, FunctionProperty.CONVEX, FunctionProperty.LINEAR}
_CONCAVITY_PROPS = {FunctionProperty.STRICT_CONCAVE, FunctionProperty.CONCAVE, FunctionProperty.LINEAR}


def _scalar_value(node: ExprNode) -> float | None:
    if isinstance(node, NumberLit):
        return float(node.value)
    if isinstance(node, UnaryNeg) and isinstance(node.operand, NumberLit):
        return -float(node.operand.value)
    return None


def _is_convexity_preserving(
    node: ExprNode,
    func_props: dict[str, set[FunctionProperty]],
) -> bool:
    """Recursively check if an AST node preserves convexity."""
    if isinstance(node, FuncApp):
        props = func_props.get(node.func, set())
        has_convexity = bool(props & _CONVEXITY_PROPS)
        has_concavity = bool(props & _CONCAVITY_PROPS)
        if has_concavity and not has_convexity:
            return False
        return True
    if isinstance(node, Ident):
        return True  # bare variable is affine (both convex and concave)
    if isinstance(node, NumberLit):
        return True  # constant is convex
    if isinstance(node, BinOp):
        if node.op == '+':
            return (_is_convexity_preserving(node.left, func_props)
                    and _is_convexity_preserving(node.right, func_props))
        if node.op == '-':
            return (_is_convexity_preserving(node.left, func_props)
                    and _is_concavity_preserving(node.right, func_props))
        if node.op == '*':
            left_val = _scalar_value(node.left)
            right_val = _scalar_value(node.right)
            if left_val is not None:
                if left_val > 0:
                    return _is_convexity_preserving(node.right, func_props)
                if left_val < 0:
                    return _is_concavity_preserving(node.right, func_props)
                return True
            if right_val is not None:
                if right_val > 0:
                    return _is_convexity_preserving(node.left, func_props)
                if right_val < 0:
                    return _is_concavity_preserving(node.left, func_props)
                return True
            return False
        return False
    if isinstance(node, UnaryNeg):
        return _is_concavity_preserving(node.operand, func_props)
    return False


def _is_concavity_preserving(
    node: ExprNode,
    func_props: dict[str, set[FunctionProperty]],
) -> bool:
    """Recursively check if an AST node preserves concavity."""
    if isinstance(node, FuncApp):
        props = func_props.get(node.func, set())
        has_convexity = bool(props & _CONVEXITY_PROPS)
        has_concavity = bool(props & _CONCAVITY_PROPS)
        if has_convexity and not has_concavity:
            return False
        return True
    if isinstance(node, Ident):
        return True  # bare variable is affine
    if isinstance(node, NumberLit):
        return True  # constant is concave
    if isinstance(node, BinOp):
        if node.op == '+':
            return (_is_concavity_preserving(node.left, func_props)
                    and _is_concavity_preserving(node.right, func_props))
        if node.op == '-':
            return (_is_concavity_preserving(node.left, func_props)
                    and _is_convexity_preserving(node.right, func_props))
        if node.op == '*':
            left_val = _scalar_value(node.left)
            right_val = _scalar_value(node.right)
            if left_val is not None:
                if left_val > 0:
                    return _is_concavity_preserving(node.right, func_props)
                if left_val < 0:
                    return _is_convexity_preserving(node.right, func_props)
                return True
            if right_val is not None:
                if right_val > 0:
                    return _is_concavity_preserving(node.left, func_props)
                if right_val < 0:
                    return _is_convexity_preserving(node.left, func_props)
                return True
            return False
        return False
    if isinstance(node, UnaryNeg):
        return _is_convexity_preserving(node.operand, func_props)
    return False


def _build_func_props(
    func_symbols: list[str],
    functions: list[Function] | None,
) -> dict[str, set[FunctionProperty]]:
    """Build function-symbol-to-property-set mapping.

    When *functions* is ``None``, all symbols are assumed convex (legacy mode).
    """
    if functions is not None:
        return {f.symbol: set(f.properties) for f in functions}
    return {sym: {FunctionProperty.CONVEX} for sym in func_symbols}


def _check_expression_convexity_safe(
    expression_latex: str,
    func_symbols: list[str],
    functions: list[Function] | None = None,
) -> bool:
    """Check if the expression structure preserves convexity.

    Returns True only if the expression is a sum (using +) of function
    applications and non-negative scalar multiples, or a difference where
    the left operand is convex and the right operand is concave.

    When *functions* is provided, real function properties are used to
    determine concavity. When *functions* is ``None``, all functions are
    assumed convex (legacy behavior: subtraction returns False).
    """
    try:
        parser = ExpressionParser(expression_latex, known_functions=func_symbols)
        ast = parser.parse()
    except Exception:
        return False

    func_props = _build_func_props(func_symbols, functions)
    return _is_convexity_preserving(ast, func_props)


def _check_expression_concavity_safe(
    expression_latex: str,
    func_symbols: list[str],
    functions: list[Function] | None = None,
) -> bool:
    """Check if the expression structure preserves concavity.

    Dual of ``_check_expression_convexity_safe``: returns True when the
    expression is a sum of concave functions, positive-scalar multiples of
    concave functions, or a difference where the left operand is concave and
    the right operand is convex.
    """
    try:
        parser = ExpressionParser(expression_latex, known_functions=func_symbols)
        ast = parser.parse()
    except Exception:
        return False

    func_props = _build_func_props(func_symbols, functions)
    return _is_concavity_preserving(ast, func_props)


def _collect_variable_idents(node: ExprNode, func_syms: set[str], out: set[str]) -> None:
    """Walk AST and collect Ident nodes that are not function names."""
    if isinstance(node, Ident):
        if node.name not in func_syms:
            out.add(node.name)
    elif isinstance(node, FuncApp):
        for arg in node.args:
            _collect_variable_idents(arg, func_syms, out)
    elif isinstance(node, BinOp):
        _collect_variable_idents(node.left, func_syms, out)
        _collect_variable_idents(node.right, func_syms, out)
    elif isinstance(node, UnaryNeg):
        _collect_variable_idents(node.operand, func_syms, out)


def _collect_func_names_from_ast(node: ExprNode) -> set[str]:
    """Walk AST and collect function names from FuncApp nodes."""
    result: set[str] = set()
    if isinstance(node, FuncApp):
        result.add(node.func)
        for arg in node.args:
            result |= _collect_func_names_from_ast(arg)
    elif isinstance(node, BinOp):
        result |= _collect_func_names_from_ast(node.left)
        result |= _collect_func_names_from_ast(node.right)
    elif isinstance(node, UnaryNeg):
        result |= _collect_func_names_from_ast(node.operand)
    return result


def _build_projections(n: int) -> list[str]:
    """Build Lean tuple projection accessors for n variables.

    For n=1: ["p"]
    For n=2: ["p.1", "p.2"]
    For n=3: ["p.1", "p.2.1", "p.2.2"]
    For n=4: ["p.1", "p.2.1", "p.2.2.1", "p.2.2.2"]

    Follows Lean's right-associated tuple nesting:
    (a, b, c) : A x (B x C), so p.1=a, p.2.1=b, p.2.2=c
    """
    if n == 1:
        return ["p"]
    if n == 2:
        return ["p.1", "p.2"]
    result = ["p.1"]
    suffix = "p.2"
    for i in range(1, n - 1):
        result.append(f"{suffix}.1")
        suffix = f"{suffix}.2"
    result.append(suffix)
    return result


def _rewrite_ast_projections(
    node: ExprNode,
    var_to_proj: dict[str, str],
    func_syms: set[str],
) -> ExprNode:
    """Rewrite Ident nodes in an AST, replacing variable names with projections.

    Operates at the AST level to avoid substring replacement issues.
    """
    if isinstance(node, Ident):
        if node.name in var_to_proj:
            return Ident(name=var_to_proj[node.name])
        return node
    if isinstance(node, NumberLit):
        return node
    if isinstance(node, FuncApp):
        new_args = tuple(
            _rewrite_ast_projections(arg, var_to_proj, func_syms)
            for arg in node.args
        )
        return FuncApp(func=node.func, args=new_args)
    if isinstance(node, BinOp):
        return BinOp(
            op=node.op,
            left=_rewrite_ast_projections(node.left, var_to_proj, func_syms),
            right=_rewrite_ast_projections(node.right, var_to_proj, func_syms),
        )
    if isinstance(node, UnaryNeg):
        return UnaryNeg(
            operand=_rewrite_ast_projections(node.operand, var_to_proj, func_syms),
        )
    return node


class ContinuousOptMapper(DomainMapper):
    """Maps continuous optimization ProblemSpecs to valid Lean 4 + Mathlib code.

    Validated against AXLE lean-4.29.0.
    """

    def __init__(self) -> None:
        self._spaces: dict[str, Space] = {}
        self._spec: ProblemSpec | None = None

    def set_context(self, spec: ProblemSpec) -> None:
        """Cache the spec's spaces for type resolution in map_function."""
        self._spaces = {s.name: s for s in spec.spaces}
        self._spec = spec

    def clear_context(self) -> None:
        """Reset cached spaces to prevent state leaking between calls."""
        self._spaces = {}
        self._spec = None

    def _declared_func_symbols(self) -> list[str]:
        return [f.symbol for f in self._spec.functions] if self._spec else []

    def supported_classifications(self) -> list[VariableClassification]:
        return [VariableClassification.ENDOGENOUS, VariableClassification.EXOGENOUS]

    @property
    def domain_name(self) -> str:
        return "continuous_optimization"

    def required_imports(self, spec: ProblemSpec) -> list[str]:
        return list(_BASE_IMPORTS)

    def map_space(self, space: Space) -> str:
        return ""

    def map_variable(self, var: Variable, spaces: dict[str, Space]) -> str:
        # Endogenous variables are normally bound by the objective's `fun x =>`
        # lambda, so they need no top-level declaration. The relation and
        # existential-bound directions emit a plain theorem with no such lambda,
        # so an endogenous variable referenced there (e.g. in a constraint) must
        # be declared explicitly to avoid an "unknown identifier" error.
        direction = self._spec.objective.direction if self._spec else None
        relation_like = direction in (
            ObjectiveDirection.INEQUALITY,
            ObjectiveDirection.EXISTENTIAL_BOUND,
        )
        if var.classification == VariableClassification.EXOGENOUS or (
            relation_like and var.classification == VariableClassification.ENDOGENOUS
        ):
            space = spaces.get(var.space_reference)
            lean_type = _lean_type_for_space(space) if space else "ℝ"
            return f"variable ({var.symbol} : {lean_type})"
        return ""

    def map_function(self, func: Function) -> str:
        # Convex-on-sequence application: f : ℝ → ℝ with its convexity stated
        # over all of ℝ (Set.univ), independent of any declared domain space.
        if func.applied_to is not None:
            lines = [f"variable ({func.symbol} : ℝ → ℝ)"]
            for prop in func.properties:
                hyp = property_hypothesis(func.symbol, "Set.univ", prop)
                if hyp:
                    lines.append(hyp)
            return "\n".join(lines)

        domain_set = func.domain[0] if func.domain else "Set.univ"

        # Build the Lean type signature from domain/codomain space types.
        domain_types = [self._resolve_type(d) for d in func.domain] if func.domain else ["ℝ"]
        codomain_type = self._resolve_type(func.codomain)

        if len(domain_types) == 1:
            type_sig = f"{domain_types[0]} → {codomain_type}"
        else:
            type_sig = f"{' → '.join(domain_types)} → {codomain_type}"

        lines: list[str] = []
        lines.append(f"variable ({func.symbol} : {type_sig})")
        if len(func.domain) <= 1:
            space = self._spaces.get(func.domain[0]) if func.domain else None
            is_discrete = space and space.base_type in (BaseType.INT, BaseType.NAT, BaseType.BOOL)
            if not is_discrete:
                for prop in func.properties:
                    hyp = property_hypothesis(func.symbol, domain_set, prop)
                    if hyp:
                        lines.append(hyp)
        return "\n".join(lines)

    def map_objective(self, objective: Objective, spec: ProblemSpec) -> str:
        if objective.direction == ObjectiveDirection.INEQUALITY:
            return self._emit_relation_theorem(objective, spec)
        if objective.direction == ObjectiveDirection.EXISTENTIAL_BOUND:
            return self._emit_existential_theorem(objective)

        target = self._resolve_target(objective, spec)
        func_syms = [f.symbol for f in spec.functions]
        if not func_syms:
            func_syms = ["f"]

        obj_body, ast = _expression_to_lean_body(
            objective.expression_latex, func_syms
        )

        try:
            expr_vars: set[str] = set()
            _collect_variable_idents(ast, set(func_syms), expr_vars)
            free_vars = expr_vars - {target}
            if free_vars:
                declared_syms = {v.symbol for v in spec.variables}
                undeclared = free_vars - declared_syms
                if undeclared:
                    raise ScaffoldingError(
                        f"Expression contains undeclared variables {undeclared}. "
                        f"Declared variables: {sorted(declared_syms)}. "
                        f"Hint: Add these variables to the ProblemSpec, or check "
                        f"for typos in the expression_latex."
                    )
                endogenous_free = [
                    v for v in spec.variables
                    if v.symbol in free_vars
                    and v.classification == VariableClassification.ENDOGENOUS
                ]
                if endogenous_free:
                    target_var_obj = next(
                        (v for v in spec.variables if v.symbol == target),
                        None,
                    )
                    if target_var_obj and target_var_obj.classification == VariableClassification.ENDOGENOUS:
                        endogenous_vars = [target_var_obj] + endogenous_free
                    else:
                        endogenous_vars = endogenous_free
                    var_order = {v.symbol: i for i, v in enumerate(spec.variables)}
                    endogenous_vars.sort(key=lambda v: var_order.get(v.symbol, 0))

                    # Multi-variable: rewrite AST with tuple projections
                    projections = _build_projections(len(endogenous_vars))
                    var_to_proj = {
                        v.symbol: proj
                        for v, proj in zip(endogenous_vars, projections)
                    }
                    rewritten = _rewrite_ast_projections(
                        ast, var_to_proj, set(func_syms)
                    )
                    return self._emit_objective_theorem(
                        objective, spec, endogenous_vars,
                        emit_lean(rewritten), "fun p =>", func_syms,
                    )
        except ExpressionParseError:
            pass

        # Single variable
        target_var_obj = next(
            (v for v in spec.variables if v.symbol == target), None
        )
        return self._emit_objective_theorem(
            objective, spec,
            [target_var_obj] if target_var_obj else [],
            obj_body, f"fun {target} =>", func_syms,
        )

    def _resolve_target(
        self, objective: Objective, spec: ProblemSpec
    ) -> str:
        if objective.target_variable:
            return objective.target_variable
        endogenous = [
            v for v in spec.variables
            if v.classification == VariableClassification.ENDOGENOUS
        ]
        return endogenous[0].symbol if endogenous else "x"

    def _emit_objective_theorem(
        self,
        objective: Objective,
        spec: ProblemSpec,
        target_vars: list[Variable],
        obj_body: str,
        binder: str,
        func_syms: list[str],
    ) -> str:
        """Unified theorem emission for single and multi-variable optimization.

        Treats the univariate case as a product of one space.
        """
        n = len(target_vars)
        lines: list[str] = []

        if n > 1:
            # -- Multi-variable domain definitions (deduplicated by space name) --
            for v in target_vars:
                space = self._spaces.get(v.space_reference)
                if space and space.base_type not in (BaseType.REAL, BaseType.NONNEG_REAL, BaseType.POS_REAL):
                    raise ScaffoldingError(
                        f"Multi-variable optimization only supports scalar real spaces, "
                        f"but variable '{v.symbol}' references space '{v.space_reference}' "
                        f"with base_type '{space.base_type.value}'"
                    )
            emitted_spaces: dict[str, str] = {}
            domain_names: list[str] = []
            for v in target_vars:
                bounds_expr = self.map_bounds(v)
                if v.space_reference in emitted_spaces:
                    if emitted_spaces[v.space_reference] == bounds_expr:
                        domain_names.append(v.space_reference)
                    else:
                        dn = f"{v.space_reference}_{v.symbol}"
                        domain_names.append(dn)
                        lines.append(f"def {dn} : Set ℝ := {bounds_expr}")
                else:
                    emitted_spaces[v.space_reference] = bounds_expr
                    domain_names.append(v.space_reference)
                    lines.append(f"def {v.space_reference} : Set ℝ := {bounds_expr}")
            lines.append("")

            product_domain = f"{domain_names[-2]} ×ˢ {domain_names[-1]}"
            for name in reversed(domain_names[:-2]):
                product_domain = f"{name} ×ˢ ({product_domain})"
            product_type = " × ".join("ℝ" for _ in target_vars)
            lines.append(f"def Domain : Set ({product_type}) := {product_domain}")
            lines.append("")

            emitted_lemmas: set[str] = set()
            convex_lemma_names: list[str] = []
            for i_var, v in enumerate(target_vars):
                dn = domain_names[i_var]
                lemma_name = f"convex_{dn.lower()}"
                convex_lemma_names.append(lemma_name)
                if lemma_name not in emitted_lemmas:
                    emitted_lemmas.add(lemma_name)
                    bounds_expr = self.map_bounds(v)
                    convex_lemma = _CONVEXITY_INTERVAL_LEMMA.get(
                        bounds_expr.split()[0] if " " in bounds_expr else bounds_expr,
                        "convex_univ",
                    )
                    arg = bounds_expr.split(" ", 1)[1] if " " in bounds_expr else ""
                    lines.append(f"lemma {lemma_name} : Convex ℝ {dn} :=")
                    lines.append(f"  {convex_lemma} {arg}".rstrip())
            lines.append("")

            if n == 2:
                lines.append("lemma convex_domain : Convex ℝ Domain :=")
                lines.append(f"  Convex.prod {convex_lemma_names[0]} {convex_lemma_names[1]}")
            else:
                lines.append("lemma convex_domain : Convex ℝ Domain := by")
                lines.append("  sorry")
            lines.append("")

            domain_set = "Domain"
        else:
            # -- Single-variable domain definition --
            target_sym = target_vars[0].symbol if target_vars else binder.split()[1]
            domain_set, domain_expr = self._domain_info(spec, target_var=target_sym)

            target_space = None
            for v in spec.variables:
                if v.symbol == target_sym:
                    target_space = self._spaces.get(v.space_reference)
                    break
            if not target_space and spec.spaces:
                target_space = spec.spaces[0]

            _DISCRETE_TYPES = (BaseType.INT, BaseType.NAT, BaseType.BOOL)

            if target_space and target_space.base_type in _DISCRETE_TYPES:
                lean_type = _lean_type_for_space(target_space)
                if " " in lean_type:
                    lines.append(f"def {domain_set} : Set ({lean_type}) := {domain_expr}")
                else:
                    lines.append(f"def {domain_set} : Set {lean_type} := {domain_expr}")
                lines.append("")
                lines.append("theorem objective_statement :")
                lines.append("    True := by")
                lines.append("  sorry")
                return "\n".join(lines)

            if target_space and target_space.base_type == BaseType.REAL_N:
                lean_type = _lean_type_for_space(target_space)
                lines.append(f"def {domain_set} : Set ({lean_type}) := {domain_expr}")
            else:
                lines.append(f"def {domain_set} : Set ℝ := {domain_expr}")
            lines.append("")

            convex_lemma = _CONVEXITY_INTERVAL_LEMMA.get(
                domain_expr.split()[0] if " " in domain_expr else domain_expr,
                "convex_univ",
            )
            arg = domain_expr.split(" ", 1)[1] if " " in domain_expr else ""
            lines.append(f"lemma convex_{domain_set.lower()} : Convex ℝ {domain_set} :=")
            lines.append(f"  {convex_lemma} {arg}".rstrip())
            lines.append("")

        # -- Shared: convexity check, predicate derivation, theorem emission --
        try:
            _obj_ast = _parse_expression_ast(objective.expression_latex, func_syms)
            expr_func_syms = _collect_func_names_from_ast(_obj_ast) & set(func_syms)
        except Exception:
            expr_func_syms = set(func_syms)
        expr_functions = [f for f in spec.functions if f.symbol in expr_func_syms]

        if objective.direction == ObjectiveDirection.MINIMIZE:
            structure_ok = _check_expression_convexity_safe(
                objective.expression_latex, func_syms, functions=expr_functions
            )
        elif objective.direction == ObjectiveDirection.MAXIMIZE:
            structure_ok = _check_expression_concavity_safe(
                objective.expression_latex, func_syms, functions=expr_functions
            )
        else:
            structure_ok = False

        has_subtraction = '-' in objective.expression_latex

        if objective.direction in (ObjectiveDirection.MINIMIZE, ObjectiveDirection.MAXIMIZE):
            if not structure_ok:
                if expr_functions:
                    _derive_theorem_predicate(expr_functions, objective.direction)
                predicate = None
            elif not expr_functions:
                predicate = None
            else:
                try:
                    predicate = _derive_theorem_predicate(expr_functions, objective.direction)
                except ScaffoldingError:
                    if not has_subtraction:
                        raise
                    if objective.direction == ObjectiveDirection.MINIMIZE:
                        predicate = "ConvexOn"
                    elif objective.direction == ObjectiveDirection.MAXIMIZE:
                        predicate = "ConcaveOn"
                    else:
                        predicate = None
        else:
            predicate = _derive_theorem_predicate(
                expr_functions if expr_functions else spec.functions,
                objective.direction,
            )

        if predicate:
            target_name = target_vars[0].symbol if target_vars else "x"
            direction_word = "minimize" if objective.direction == ObjectiveDirection.MINIMIZE else "maximize"
            theorem_name = f"{direction_word}_{target_name}_{predicate.lower()}"
            lines.append(f"theorem {theorem_name} :")
            lines.append(f"    {predicate} ℝ {domain_set} ({binder} {obj_body}) := by")
            lines.append("  sorry")
        else:
            lines.append("-- Note: FormalConstruct could not derive a convexity/concavity")
            lines.append("-- predicate for this objective. The expression may contain")
            lines.append("-- operators (-, /, ^) that do not preserve convexity in general.")
            lines.append("-- Replace 'True' with the appropriate theorem statement.")
            lines.append("theorem objective_statement :")
            lines.append("    True := by")
            lines.append("  sorry")

        return "\n".join(lines)

    def _emit_relation_theorem(self, objective: Objective, spec: ProblemSpec) -> str:
        """Emit a plain inequality/relation theorem with a sorry proof.

        Handles two goal shapes:
          - summation: ``∑ f(left_k) <rel> ∑ f(right_k)``
          - scalar:    ``<expression> <rel> <bound>``
        """
        if objective.summation is not None:
            s = objective.summation
            rel = _RELATION_TO_LEAN[objective.relation] if objective.relation else "≥"
            declared_funcs = [f.symbol for f in spec.functions]

            def _term(seq: str) -> str:
                if s.summand is not None:
                    return _emit_summand_term(
                        s.summand, s.summand_var, seq, s.index_var, declared_funcs
                    )
                return f"{s.function} ({seq} {s.index_var})"

            lhs = f"∑ {s.index_var} ∈ Finset.range {s.index_upper}, {_term(s.left_sequence)}"
            rhs = f"∑ {s.index_var} ∈ Finset.range {s.index_upper}, {_term(s.right_sequence)}"
            goal = f"{lhs} {rel} {rhs}"
        else:
            lhs = _emit_expression_with_builtins(
                objective.expression_latex, [f.symbol for f in spec.functions]
            )
            rel = _RELATION_TO_LEAN[objective.relation] if objective.relation else "≤"
            bound = objective.bound if objective.bound is not None else "0"
            goal = f"{lhs} {rel} {bound}"
        return f"theorem inequality_goal :\n    {goal} := by\n  sorry"

    def _emit_existential_theorem(self, objective: Objective) -> str:
        """Emit a boundedness theorem: ``∃ M, ∀ n, a n <rel> M``."""
        eb = objective.existential_bound
        if eb is None:
            return "theorem bound_goal :\n    True := by\n  sorry"
        rel = _RELATION_TO_LEAN[eb.relation]
        goal = f"∃ {eb.bound_var}, ∀ {eb.index_var}, {eb.sequence} {eb.index_var} {rel} {eb.bound_var}"
        return f"theorem bound_goal :\n    {goal} := by\n  sorry"

    def map_indexed_variable(self, iv: IndexedVariable) -> str:
        index_type = "ℕ" if iv.index_type == IndexType.NAT else "Fin n"
        value_type = _INDEXED_VALUE_TYPE.get(iv.value_type, "ℝ")
        lines = [f"variable ({iv.symbol} : {index_type} → {value_type})"]
        if iv.bounds is not None:
            op = "<" if iv.bounds.strict_inequality else "≤"
            if iv.bounds.lower_bound is not None:
                lines.append(
                    f"variable (h_{iv.symbol}_lb : ∀ k, {iv.bounds.lower_bound} {op} {iv.symbol} k)"
                )
            if iv.bounds.upper_bound is not None:
                lines.append(
                    f"variable (h_{iv.symbol}_ub : ∀ k, {iv.symbol} k {op} {iv.bounds.upper_bound})"
                )
        return "\n".join(lines)

    def map_constraint(self, constraint: ParametricConstraint, idx: int) -> str:
        lhs = _emit_expression_with_builtins(
            constraint.expression, self._declared_func_symbols()
        )
        rel = _RELATION_TO_LEAN[constraint.relation]
        return f"variable (h_constr_{idx} : {lhs} {rel} {constraint.value})"

    def map_sequence_relation(self, relation: SequenceRelation, idx: int) -> str:
        sr = relation
        if sr.type in (SequenceRelationType.MAJORIZATION, SequenceRelationType.POINTWISE):
            rel = _RELATION_TO_LEAN[sr.relation]
            return (
                f"variable (h_seq_{idx} : ∀ {sr.index_var}, "
                f"{sr.left} {sr.index_var} {rel} {sr.right} {sr.index_var})"
            )
        if sr.type == SequenceRelationType.RECURRENCE:
            term = _emit_summand_term(
                sr.expression or "", sr.expr_var, sr.left, sr.index_var,
                self._declared_func_symbols(),
            )
            return (
                f"variable (h_seq_{idx} : ∀ {sr.index_var}, "
                f"{sr.left} ({sr.index_var} + 1) = {term})"
            )
        if sr.type == SequenceRelationType.INITIAL:
            return f"variable (h_seq_{idx} : {sr.left} {sr.index} = {sr.value})"
        big_op = "∑" if sr.type == SequenceRelationType.SUM_CONSTRAINT else "∏"
        return (
            f"variable (h_seq_{idx} : {big_op} {sr.index_var} ∈ "
            f"Finset.range {sr.index_upper}, {sr.left} {sr.index_var} = {sr.value})"
        )

    def map_bounds(self, var: Variable) -> str:
        if var.bounds is not None and var.space_reference in self._spaces:
            space = self._spaces[var.space_reference]
            if space.base_type == BaseType.REAL_N:
                if var.bounds.lower_bound is not None or var.bounds.upper_bound is not None:
                    raise ScaffoldingError(
                        f"Variable '{var.symbol}' has bounds on a REAL_N space. "
                        f"Per-component bounds for multi-dimensional spaces are not supported. "
                        f"Hint: Remove the bounds and express constraints as hypotheses, "
                        f"or use a single-variable Real space with bounds instead."
                    )
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

    def _resolve_type(self, name: str) -> str:
        """Resolve a domain/codomain name to its Lean type string.

        Looks up *name* in the cached spaces dict, then handles bare base-type
        names (e.g. a codomain given as ``"Int"``). Falls back to ``ℝ`` for the
        real family and anything unrecognized.
        """
        if name in self._spaces:
            return _lean_type_for_space(self._spaces[name])
        return {"Int": "ℤ", "Nat": "ℕ", "Bool": "Bool"}.get(name, "ℝ")

    def _domain_info(self, spec: ProblemSpec, target_var: str | None = None) -> tuple[str, str]:
        """Derive the domain set name and its Mathlib expression from the spec.

        When *target_var* is given, uses that variable's space and bounds.
        Otherwise falls back to the first space / first bounded variable.
        """
        target_variable = None
        if target_var:
            for v in spec.variables:
                if v.symbol == target_var:
                    target_variable = v
                    break

        if target_variable:
            domain_name = target_variable.space_reference
            if target_variable.bounds and (
                target_variable.bounds.lower_bound is not None
                or target_variable.bounds.upper_bound is not None
            ):
                return domain_name, self.map_bounds(target_variable)
            return domain_name, "Set.univ"

        domain_name = spec.spaces[0].name if spec.spaces else "Domain"
        for var in spec.variables:
            if var.bounds and (var.bounds.lower_bound is not None or var.bounds.upper_bound is not None):
                return domain_name, self.map_bounds(var)
        return domain_name, "Set.univ"


_CONVEXITY_TAGS = {FunctionProperty.STRICT_CONVEX, FunctionProperty.CONVEX, FunctionProperty.LINEAR}
_CONCAVITY_TAGS = {FunctionProperty.STRICT_CONCAVE, FunctionProperty.CONCAVE}


def _derive_theorem_predicate(
    functions: list[Function], direction: ObjectiveDirection
) -> str | None:
    """Derive the Lean theorem predicate from function properties and direction.

    Returns None for directions that do not map to a convexity/concavity theorem
    (e.g. EQUILIBRIUM, PARETO_OPTIMAL).
    Raises ScaffoldingError when functions lack the properties needed for the direction.
    """
    if direction == ObjectiveDirection.MINIMIZE:
        all_strict = all(
            FunctionProperty.STRICT_CONVEX in f.properties for f in functions
        )
        if all_strict:
            return "StrictConvexOn"
        # StrictConvex + Linear = StrictConvexOn (linear is convex, preserves strictness)
        all_strict_or_linear = all(
            FunctionProperty.STRICT_CONVEX in f.properties
            or FunctionProperty.LINEAR in f.properties
            for f in functions
        )
        any_strict = any(
            FunctionProperty.STRICT_CONVEX in f.properties for f in functions
        )
        if all_strict_or_linear and any_strict:
            return "StrictConvexOn"
        all_convex = all(
            any(p in _CONVEXITY_TAGS for p in f.properties) for f in functions
        )
        if all_convex:
            return "ConvexOn"
        names = ", ".join(f.symbol for f in functions)
        raise ScaffoldingError(
            f"No convexity property supports MINIMIZE theorem for functions: {names}. "
            f"Hint: Add 'Convex' or 'StrictConvex' to the functions' properties in "
            f"the ProblemSpec, or change the objective direction."
        )
    if direction == ObjectiveDirection.MAXIMIZE:
        all_strict = all(
            FunctionProperty.STRICT_CONCAVE in f.properties for f in functions
        )
        if all_strict:
            return "StrictConcaveOn"
        # StrictConcave + Linear = StrictConcaveOn (linear is concave, preserves strictness)
        all_strict_or_linear = all(
            FunctionProperty.STRICT_CONCAVE in f.properties
            or FunctionProperty.LINEAR in f.properties
            for f in functions
        )
        any_strict = any(
            FunctionProperty.STRICT_CONCAVE in f.properties for f in functions
        )
        if all_strict_or_linear and any_strict:
            return "StrictConcaveOn"
        all_concave = all(
            any(p in _CONCAVITY_TAGS | {FunctionProperty.LINEAR} for p in f.properties)
            for f in functions
        )
        if all_concave:
            return "ConcaveOn"
        names = ", ".join(f.symbol for f in functions)
        raise ScaffoldingError(
            f"No concavity property supports MAXIMIZE theorem for functions: {names}. "
            f"Hint: Add 'Concave' or 'StrictConcave' to the functions' properties in "
            f"the ProblemSpec, or change the objective direction."
        )
    return None


