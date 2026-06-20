"""Unit tests for the expression parser and Lean emitter."""

import pytest

from formalconstruct.core.exceptions import ExpressionParseError
from formalconstruct.core.expression_parser import (
    BinOp,
    ExprNode,
    ExpressionParser,
    FuncApp,
    Ident,
    NumberLit,
    UnaryNeg,
    emit_lean,
    normalize_expression,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse(text: str, known_functions: list[str] | None = None) -> ExprNode:
    """Shorthand: parse text and return AST root node."""
    return ExpressionParser(text, known_functions=known_functions).parse()


def _parse_emit(text: str, known_functions: list[str] | None = None) -> str:
    """Shorthand: parse text and emit Lean."""
    return emit_lean(_parse(text, known_functions=known_functions))


# ===========================================================================
# Parsing + Emission tests (parse then emit_lean produces expected output)
# ===========================================================================


class TestParseAndEmit:
    """Tests that parse -> emit_lean produces the correct Lean 4 syntax."""

    def test_single_function(self) -> None:
        """f(x) -> 'f x' (juxtaposition)."""
        assert _parse_emit("f(x)") == "f x"

    def test_sum_of_functions(self) -> None:
        """f(x) + g(x) -> 'f x + g x' (infix addition)."""
        assert _parse_emit("f(x) + g(x)") == "f x + g x"

    def test_difference(self) -> None:
        """f(x) - g(x) -> 'f x - g x' (infix subtraction)."""
        assert _parse_emit("f(x) - g(x)") == "f x - g x"

    def test_nested_calls(self) -> None:
        """f(g(x)) -> 'f (g x)' (inner application parenthesized)."""
        assert _parse_emit("f(g(x))") == "f (g x)"

    def test_multi_arg(self) -> None:
        """f(x, y) -> 'f x y' (curried application)."""
        assert _parse_emit("f(x, y)") == "f x y"

    def test_weighted(self) -> None:
        """2 * f(x) -> '2 * f x' (infix multiplication)."""
        assert _parse_emit("2 * f(x)") == "2 * f x"

    def test_division(self) -> None:
        """f(x) / g(x) -> 'f x / g x' (infix division)."""
        assert _parse_emit("f(x) / g(x)") == "f x / g x"

    def test_unary_negation(self) -> None:
        """-f(x) -> '-(f x)' (prefix, parenthesized operand)."""
        assert _parse_emit("-f(x)") == "-(f x)"

    def test_complex_nested(self) -> None:
        """f(g(x)) + 2 * h(x) -> correct output with precedence."""
        result = _parse_emit("f(g(x)) + 2 * h(x)")
        assert result == "f (g x) + 2 * h x"

    def test_integer_literal(self) -> None:
        """integer '2' emitted verbatim."""
        assert _parse_emit("2") == "2"

    def test_decimal_literal(self) -> None:
        """decimal '3.14' emitted without type annotation (Lean infers)."""
        result = _parse_emit("3.14")
        assert result == "3.14"

    def test_parenthesized(self) -> None:
        """(f(x) + g(x)) * h(x) -> correct output with grouping."""
        result = _parse_emit("(f(x) + g(x)) * h(x)")
        assert result == "(f x + g x) * h x"


# ===========================================================================
# AST structure tests (verify parse produces expected node types)
# ===========================================================================


class TestASTStructure:
    """Tests that the parser builds the expected AST node hierarchy."""

    def test_ast_binop_structure(self) -> None:
        """f(x) + g(x) -> BinOp with op='+' and two FuncApp children."""
        node = _parse("f(x) + g(x)")
        assert isinstance(node, BinOp)
        assert node.op == "+"
        assert isinstance(node.left, FuncApp)
        assert isinstance(node.right, FuncApp)
        assert node.left.func == "f"
        assert node.right.func == "g"

    def test_ast_funcapp_structure(self) -> None:
        """f(x) -> FuncApp with func='f', args=(Ident('x'),)."""
        node = _parse("f(x)")
        assert isinstance(node, FuncApp)
        assert node.func == "f"
        assert len(node.args) == 1
        assert isinstance(node.args[0], Ident)
        assert node.args[0].name == "x"

    def test_ast_number_lit(self) -> None:
        """42 -> NumberLit with value='42'."""
        node = _parse("42")
        assert isinstance(node, NumberLit)
        assert node.value == "42"

    def test_ast_decimal_number_lit(self) -> None:
        """3.14 -> NumberLit with value='3.14'."""
        node = _parse("3.14")
        assert isinstance(node, NumberLit)
        assert node.value == "3.14"

    def test_ast_ident(self) -> None:
        """x -> Ident with name='x'."""
        node = _parse("x")
        assert isinstance(node, Ident)
        assert node.name == "x"

    def test_ast_unary_neg(self) -> None:
        """-x -> UnaryNeg with operand Ident('x')."""
        node = _parse("-x")
        assert isinstance(node, UnaryNeg)
        assert isinstance(node.operand, Ident)
        assert node.operand.name == "x"

    def test_ast_multi_arg_funcapp(self) -> None:
        """f(x, y, z) -> FuncApp with three args."""
        node = _parse("f(x, y, z)")
        assert isinstance(node, FuncApp)
        assert node.func == "f"
        assert len(node.args) == 3
        for i, name in enumerate(["x", "y", "z"]):
            assert isinstance(node.args[i], Ident)
            assert node.args[i].name == name

    def test_ast_nested_funcapp(self) -> None:
        """f(g(x)) -> FuncApp('f', [FuncApp('g', [Ident('x')])])."""
        node = _parse("f(g(x))")
        assert isinstance(node, FuncApp)
        assert node.func == "f"
        assert len(node.args) == 1
        inner = node.args[0]
        assert isinstance(inner, FuncApp)
        assert inner.func == "g"
        assert len(inner.args) == 1
        assert isinstance(inner.args[0], Ident)

    def test_ast_precedence_mul_over_add(self) -> None:
        """a + b * c -> BinOp(+, Ident(a), BinOp(*, Ident(b), Ident(c)))."""
        node = _parse("a + b * c")
        assert isinstance(node, BinOp)
        assert node.op == "+"
        assert isinstance(node.left, Ident)
        assert node.left.name == "a"
        assert isinstance(node.right, BinOp)
        assert node.right.op == "*"


# ===========================================================================
# Error tests (verify ExpressionParseError raised)
# ===========================================================================


class TestParseErrors:
    """Tests that invalid inputs raise ExpressionParseError with useful info."""

    def test_error_empty(self) -> None:
        """empty string raises ExpressionParseError."""
        with pytest.raises(ExpressionParseError, match="empty expression"):
            _parse("")

    def test_error_latex_backslash(self) -> None:
        r"""unsupported LaTeX constructs raise ExpressionParseError."""
        with pytest.raises(ExpressionParseError, match=r"\\sum is not supported"):
            _parse(r"\sum_{i} x")

    def test_error_unmatched_paren(self) -> None:
        """unmatched '(' raises ExpressionParseError."""
        with pytest.raises(ExpressionParseError, match="expected '\\)'"):
            _parse("f(x")

    def test_error_trailing_operator(self) -> None:
        """trailing operator 'f(x) +' raises ExpressionParseError."""
        with pytest.raises(ExpressionParseError, match="unexpected end of expression"):
            _parse("f(x) +")

    def test_error_whitespace_only(self) -> None:
        """whitespace-only string raises ExpressionParseError."""
        with pytest.raises(ExpressionParseError, match="empty expression"):
            _parse("   ")

    def test_error_position_in_message(self) -> None:
        """ExpressionParseError includes position and caret indicator."""
        with pytest.raises(ExpressionParseError) as exc_info:
            _parse("")
        err = exc_info.value
        assert err.position == 0
        assert err.expression == ""

    def test_error_unexpected_character(self) -> None:
        """Unexpected characters like '@' raise ExpressionParseError."""
        with pytest.raises(ExpressionParseError, match="unexpected character '@'"):
            _parse("f(x) @ g(x)")

    def test_error_double_operator(self) -> None:
        """Double operator '++' raises parse error."""
        with pytest.raises(ExpressionParseError):
            _parse("f(x) ++ g(x)")

    def test_error_leading_comma(self) -> None:
        """Leading comma raises parse error."""
        with pytest.raises(ExpressionParseError):
            _parse(",x")

    def test_error_unmatched_close_paren(self) -> None:
        """Unmatched ')' at top level raises parse error."""
        with pytest.raises(ExpressionParseError):
            _parse("f(x))")

    def test_error_decimal_no_digits_after_dot(self) -> None:
        """'3.' with no digits after decimal point raises parse error."""
        with pytest.raises(ExpressionParseError, match="expected digit after decimal point"):
            _parse("3.")


# ===========================================================================
# known_functions tests
# ===========================================================================


class TestKnownFunctions:
    """Tests for the known_functions parameter controlling function call parsing."""

    def test_known_functions_none_treats_all_as_functions(self) -> None:
        """When known_functions is None, any identifier( is a function call."""
        node = _parse("f(x) + g(x)", known_functions=None)
        assert isinstance(node, BinOp)
        assert isinstance(node.left, FuncApp)
        assert isinstance(node.right, FuncApp)

    def test_known_functions_filters(self) -> None:
        """With known_functions=['f'], f(x) + y: f is FuncApp, y is Ident."""
        node = _parse("f(x) + y", known_functions=["f"])
        assert isinstance(node, BinOp)
        assert isinstance(node.left, FuncApp)
        assert node.left.func == "f"
        assert isinstance(node.right, Ident)
        assert node.right.name == "y"

    def test_unknown_identifier_not_function(self) -> None:
        """With known_functions=['f'], g(x) raises because g is Ident
        and then '(' is unexpected at the top level."""
        with pytest.raises(ExpressionParseError):
            _parse("g(x)", known_functions=["f"])

    def test_known_functions_empty_list_treats_none_as_functions(self) -> None:
        """With known_functions=[] (empty list), no identifier is a function call.
        g(x) raises because g becomes Ident and ( is unexpected."""
        with pytest.raises(ExpressionParseError):
            _parse("g(x)", known_functions=[])

    def test_known_functions_mixed_expression(self) -> None:
        """With known_functions=['f'], f(x) + g parses f as FuncApp, g as Ident."""
        node = _parse("f(x) + g", known_functions=["f"])
        assert isinstance(node, BinOp)
        assert isinstance(node.left, FuncApp)
        assert isinstance(node.right, Ident)
        assert node.right.name == "g"


# ===========================================================================
# Backward compatibility test
# ===========================================================================


class TestBackwardCompat:
    """Tests that the canonical golden path expression produces identical output."""

    def test_backward_compat_canonical(self) -> None:
        """CostCapital(x) + CostLabor(x) with known_functions
        -> 'CostCapital x + CostLabor x'."""
        result = _parse_emit(
            "CostCapital(x) + CostLabor(x)",
            known_functions=["CostCapital", "CostLabor"],
        )
        assert result == "CostCapital x + CostLabor x"

    def test_backward_compat_single_function(self) -> None:
        """f(x) with known_functions=['f'] -> 'f x'."""
        result = _parse_emit("f(x)", known_functions=["f"])
        assert result == "f x"


# ===========================================================================
# Operator precedence and associativity tests
# ===========================================================================


class TestPrecedenceAndParenthesization:
    """Tests for correct precedence handling and minimal parenthesization."""

    def test_mul_higher_than_add(self) -> None:
        """2 * f(x) + g(x) -> '2 * f x + g x' (no extra parens)."""
        assert _parse_emit("2 * f(x) + g(x)") == "2 * f x + g x"

    def test_add_lower_than_mul_needs_parens(self) -> None:
        """(f(x) + g(x)) * h(x) -> '(f x + g x) * h x'."""
        assert _parse_emit("(f(x) + g(x)) * h(x)") == "(f x + g x) * h x"

    def test_subtraction_right_associativity_guard(self) -> None:
        """a - (b - c) -> 'a - (b - c)' (right child needs parens)."""
        assert _parse_emit("a - (b - c)") == "a - (b - c)"

    def test_subtraction_left_no_extra_parens(self) -> None:
        """a - b - c parses left-to-right: (a - b) - c -> 'a - b - c'."""
        result = _parse_emit("a - b - c")
        # Left-to-right: BinOp(-, BinOp(-, a, b), c)
        # Left child has same precedence but is not right, so no parens.
        # Right child 'c' is Ident, no parens needed.
        assert result == "a - b - c"

    def test_division_right_associativity_guard(self) -> None:
        """a / (b / c) -> 'a / (b / c)'."""
        assert _parse_emit("a / (b / c)") == "a / (b / c)"

    def test_nested_func_in_binop(self) -> None:
        """f(g(x)) + h(x) -> 'f (g x) + h x'."""
        assert _parse_emit("f(g(x)) + h(x)") == "f (g x) + h x"

    def test_unary_neg_simple_ident(self) -> None:
        """-x -> '-x' (no parens for simple operand)."""
        assert _parse_emit("-x") == "-x"

    def test_unary_neg_number(self) -> None:
        """-2 -> '-2' (no parens for number literal)."""
        assert _parse_emit("-2") == "-2"

    def test_unary_neg_complex_expr(self) -> None:
        """-(a + b) -> '-(a + b)' (parenthesized complex operand)."""
        assert _parse_emit("-(a + b)") == "-(a + b)"

    def test_deeply_nested_calls(self) -> None:
        """f(g(h(x))) -> 'f (g (h x))'."""
        assert _parse_emit("f(g(h(x)))") == "f (g (h x))"


# ===========================================================================
# Edge cases
# ===========================================================================


class TestEdgeCases:
    """Edge case tests for robustness."""

    def test_whitespace_around_operators(self) -> None:
        """Whitespace does not affect parsing: ' f( x ) + g( x ) '."""
        assert _parse_emit("  f( x ) + g( x )  ") == "f x + g x"

    def test_identifier_with_prime(self) -> None:
        """Identifiers may contain prime characters: f'(x)."""
        node = _parse("f'(x)")
        assert isinstance(node, FuncApp)
        assert node.func == "f'"
        assert emit_lean(node) == "f' x"

    def test_identifier_with_underscore(self) -> None:
        """Identifiers may contain underscores: cost_tech(x)."""
        assert _parse_emit("cost_tech(x)") == "cost_tech x"

    def test_multi_digit_number(self) -> None:
        """Multi-digit integer: 123."""
        node = _parse("123")
        assert isinstance(node, NumberLit)
        assert node.value == "123"

    def test_decimal_in_expression(self) -> None:
        """0.5 * f(x) -> '0.5 * f x' (Lean infers type from context)."""
        result = _parse_emit("0.5 * f(x)")
        assert result == "0.5 * f x"

    def test_long_function_name(self) -> None:
        """Long CamelCase function names parse correctly."""
        assert _parse_emit("CostCapitalnology(x)") == "CostCapitalnology x"

    def test_single_ident(self) -> None:
        """Bare identifier: x -> 'x'."""
        assert _parse_emit("x") == "x"

    def test_func_with_binop_arg(self) -> None:
        """f(x + y) -> 'f (x + y)' (binop arg parenthesized)."""
        assert _parse_emit("f(x + y)") == "f (x + y)"

    def test_func_with_nested_and_binop(self) -> None:
        """f(g(x) + h(x)) -> 'f (g x + h x)'."""
        assert _parse_emit("f(g(x) + h(x))") == "f (g x + h x)"

    def test_frozen_dataclass_hashability(self) -> None:
        """AST nodes are frozen dataclasses and can be used in sets/dicts."""
        node1 = _parse("f(x)")
        node2 = _parse("f(x)")
        assert node1 == node2
        assert hash(node1) == hash(node2)
        assert len({node1, node2}) == 1

    def test_maximum_nesting_depth_exceeded(self) -> None:
        """Exceeding _MAX_DEPTH (50) raises ExpressionParseError."""
        # Build a deeply nested expression: (((((...(x)...))))
        deep = "(" * 55 + "x" + ")" * 55
        with pytest.raises(ExpressionParseError, match="maximum nesting depth"):
            _parse(deep)


# ===========================================================================
# emit_lean standalone tests
# ===========================================================================


class TestEmitLean:
    """Tests for emit_lean on manually constructed AST nodes."""

    def test_emit_number_int(self) -> None:
        assert emit_lean(NumberLit(value="7")) == "7"

    def test_emit_number_decimal(self) -> None:
        assert emit_lean(NumberLit(value="2.71")) == "2.71"

    def test_emit_ident(self) -> None:
        assert emit_lean(Ident(name="alpha")) == "alpha"

    def test_emit_funcapp_single(self) -> None:
        node = FuncApp(func="f", args=(Ident(name="x"),))
        assert emit_lean(node) == "f x"

    def test_emit_funcapp_multi(self) -> None:
        node = FuncApp(func="f", args=(Ident(name="x"), Ident(name="y")))
        assert emit_lean(node) == "f x y"

    def test_emit_funcapp_complex_arg(self) -> None:
        """FuncApp with a BinOp argument gets parenthesized."""
        inner = BinOp(op="+", left=Ident(name="x"), right=Ident(name="y"))
        node = FuncApp(func="f", args=(inner,))
        assert emit_lean(node) == "f (x + y)"

    def test_emit_unary_neg_simple(self) -> None:
        node = UnaryNeg(operand=Ident(name="x"))
        assert emit_lean(node) == "-x"

    def test_emit_unary_neg_complex(self) -> None:
        inner = FuncApp(func="f", args=(Ident(name="x"),))
        node = UnaryNeg(operand=inner)
        assert emit_lean(node) == "-(f x)"

    def test_emit_binop(self) -> None:
        node = BinOp(op="+", left=Ident(name="a"), right=Ident(name="b"))
        assert emit_lean(node) == "a + b"

    def test_emit_unknown_node_type_raises(self) -> None:
        """emit_lean raises TypeError for unknown node types."""
        with pytest.raises(TypeError, match="Unknown AST node type"):
            emit_lean("not_a_node")  # type: ignore[arg-type]


# ===========================================================================
# LaTeX normalization tests
# ===========================================================================


class TestNormalizeExpression:
    r"""Tests for normalize_expression LaTeX-to-plain conversion."""

    def test_frac_simple(self) -> None:
        r"""\frac{a}{b} normalizes to (a) / (b)."""
        result = normalize_expression(r"\frac{a}{b}")
        assert result == "(a) / (b)"

    def test_frac_with_functions(self) -> None:
        r"""\frac{f(x)}{g(x)} normalizes to (f(x)) / (g(x))."""
        result = normalize_expression(r"\frac{f(x)}{g(x)}")
        assert result == "(f(x)) / (g(x))"

    def test_frac_nested(self) -> None:
        r"""Nested \frac: \frac{\frac{a}{b}}{c} normalizes correctly.

        Inner \frac is processed first (iterative while loop finds
        the innermost occurrence), producing (a) / (b), then outer
        \frac wraps it as ((a) / (b)) / (c).
        """
        result = normalize_expression(r"\frac{\frac{a}{b}}{c}")
        assert "(a) / (b)" in result
        # The full result should be ((a) / (b)) / (c)
        assert result == "((a) / (b)) / (c)"

    def test_cdot(self) -> None:
        r"""a \cdot b normalizes to a * b."""
        result = normalize_expression(r"a \cdot b")
        assert result == "a * b"

    def test_times(self) -> None:
        r"""a \times b normalizes to a * b."""
        result = normalize_expression(r"a \times b")
        assert result == "a * b"

    def test_left_right_parens(self) -> None:
        r"""\left( x \right) normalizes to ( x )."""
        result = normalize_expression(r"\left( x \right)")
        assert result == "( x )"

    def test_left_right_brackets(self) -> None:
        r"""\left[ x \right] normalizes to ( x )."""
        result = normalize_expression(r"\left[ x \right]")
        assert result == "( x )"

    def test_formatting_stripped(self) -> None:
        r"""a \, b has formatting command stripped: result is 'a  b'."""
        result = normalize_expression(r"a \, b")
        assert result == "a  b"

    def test_sqrt_normalized(self) -> None:
        r"""\sqrt{x} is normalized to Real.sqrt(x)."""
        result = normalize_expression(r"\sqrt{x}")
        assert result == "sqrt(x)"

    def test_sqrt_nested(self) -> None:
        r"""\sqrt{x+1} is normalized to Real.sqrt(x+1)."""
        result = normalize_expression(r"\sqrt{x+1}")
        assert result == "sqrt(x+1)"

    def test_exponent_passthrough(self) -> None:
        """x^2 passes through normalize_expression unchanged (^ is now supported)."""
        result = normalize_expression("x^2")
        assert result == "x^2"

    def test_sum_rejected(self) -> None:
        r"""\sum_{i} x_i raises ExpressionParseError."""
        with pytest.raises(ExpressionParseError, match=r"\\sum is not supported"):
            normalize_expression(r"\sum_{i} x_i")

    def test_int_rejected(self) -> None:
        r"""\int f(x) raises ExpressionParseError."""
        with pytest.raises(ExpressionParseError, match=r"\\int is not supported"):
            normalize_expression(r"\int f(x)")

    def test_plain_expression_unchanged(self) -> None:
        """f(x) + g(x) passes through unchanged (no LaTeX commands)."""
        expr = "f(x) + g(x)"
        result = normalize_expression(expr)
        assert result == expr

    def test_unknown_command_rejected(self) -> None:
        r"""\unknowncommand raises ExpressionParseError."""
        with pytest.raises(ExpressionParseError, match=r"unrecognized LaTeX command"):
            normalize_expression(r"\unknowncommand")

    def test_normalize_then_parse_roundtrip(self) -> None:
        r"""\frac{f(x)}{g(x)} normalizes and parses to f x / g x."""
        result = _parse_emit(r"\frac{f(x)}{g(x)}")
        assert result == "f x / g x"


# ===========================================================================
# Exponentiation tests
# ===========================================================================


class TestExponentiation:
    """Tests for the ^ (exponentiation) operator support.

    The parser treats ^ as a right-associative operator that binds tighter
    than + and *. LaTeX brace notation (x^{...}) is normalized before parsing.
    """

    def test_simple_exponent(self) -> None:
        """x^2 parses and emits 'x ^ 2'."""
        assert _parse_emit("x^2") == "x ^ 2"

    def test_function_exponent(self) -> None:
        """f(x)^2 parses and emits 'f x ^ 2'.

        The function application f(x) becomes 'f x' and then ^ 2 is applied
        as a binary operator on the result."""
        assert _parse_emit("f(x)^2") == "f x ^ 2"

    def test_right_associative(self) -> None:
        """x^y^z parses right-associatively as x^(y^z).

        Emits 'x ^ y ^ z' because the right child of ^ does not need
        parentheses when it is also ^, due to right-associativity."""
        result = _parse_emit("x^y^z")
        assert result == "x ^ y ^ z"
        # Verify the AST is right-associative: BinOp(^, x, BinOp(^, y, z))
        node = _parse("x^y^z")
        assert isinstance(node, BinOp)
        assert node.op == "^"
        assert isinstance(node.left, Ident)
        assert node.left.name == "x"
        assert isinstance(node.right, BinOp)
        assert node.right.op == "^"
        assert isinstance(node.right.left, Ident)
        assert node.right.left.name == "y"
        assert isinstance(node.right.right, Ident)
        assert node.right.right.name == "z"

    def test_exponent_precedence_over_addition(self) -> None:
        """x^2 + y emits 'x ^ 2 + y'. ^ binds tighter than +."""
        result = _parse_emit("x^2 + y")
        assert result == "x ^ 2 + y"
        # Verify AST: BinOp(+, BinOp(^, x, 2), y)
        node = _parse("x^2 + y")
        assert isinstance(node, BinOp)
        assert node.op == "+"
        assert isinstance(node.left, BinOp)
        assert node.left.op == "^"

    def test_exponent_precedence_over_multiplication(self) -> None:
        """2 * x^3 emits '2 * x ^ 3'. ^ binds tighter than *."""
        result = _parse_emit("2 * x^3")
        assert result == "2 * x ^ 3"
        # Verify AST: BinOp(*, 2, BinOp(^, x, 3))
        node = _parse("2 * x^3")
        assert isinstance(node, BinOp)
        assert node.op == "*"
        assert isinstance(node.right, BinOp)
        assert node.right.op == "^"

    def test_latex_brace_normalization(self) -> None:
        r"""x^{2} normalizes to x^2 then parses to 'x ^ 2'.

        The normalizer strips single-token brace groups in exponents."""
        result = _parse_emit("x^{2}")
        assert result == "x ^ 2"

    def test_latex_complex_exponent(self) -> None:
        r"""x^{n+1} normalizes to x^(n+1) then parses to 'x ^ (n + 1)'.

        Multi-token brace groups are wrapped in parentheses by the normalizer."""
        result = _parse_emit("x^{n+1}")
        assert result == "x ^ (n + 1)"

    def test_exponent_ast_structure(self) -> None:
        """x^2 produces BinOp(op='^', left=Ident('x'), right=NumberLit('2'))."""
        node = _parse("x^2")
        assert isinstance(node, BinOp)
        assert node.op == "^"
        assert isinstance(node.left, Ident)
        assert node.left.name == "x"
        assert isinstance(node.right, NumberLit)
        assert node.right.value == "2"


# ===========================================================================
# Implicit multiplication tests
# ===========================================================================


class TestImplicitMultiplication:
    """Tests for implicit multiplication: digit followed by identifier or '('.

    2x -> 2 * x, 2f(x) -> 2 * f(x).
    """

    def test_digit_then_ident(self) -> None:
        """2x parses as BinOp(*, NumberLit(2), Ident(x))."""
        node = _parse("2x")
        assert isinstance(node, BinOp)
        assert node.op == "*"
        assert isinstance(node.left, NumberLit)
        assert node.left.value == "2"
        assert isinstance(node.right, Ident)
        assert node.right.name == "x"

    def test_digit_then_ident_emit(self) -> None:
        """2x emits '2 * x'."""
        assert _parse_emit("2x") == "2 * x"

    def test_digit_then_function_call(self) -> None:
        """2f(x) parses as BinOp(*, NumberLit(2), FuncApp(f, x))."""
        node = _parse("2f(x)")
        assert isinstance(node, BinOp)
        assert node.op == "*"
        assert isinstance(node.left, NumberLit)
        assert node.left.value == "2"
        assert isinstance(node.right, FuncApp)
        assert node.right.func == "f"

    def test_digit_then_function_call_emit(self) -> None:
        """2f(x) emits '2 * f x'."""
        assert _parse_emit("2f(x)") == "2 * f x"

    def test_decimal_then_ident(self) -> None:
        """3.14x emits '3.14 * x'."""
        assert _parse_emit("3.14x") == "3.14 * x"

    def test_implicit_mul_in_addition(self) -> None:
        """2x + 3y parses correctly with implicit multiplication."""
        result = _parse_emit("2x + 3y")
        assert result == "2 * x + 3 * y"

    def test_explicit_mul_backward_compat(self) -> None:
        """2 * x still works identically."""
        assert _parse_emit("2 * x") == "2 * x"

    def test_implicit_mul_with_power(self) -> None:
        """2x^2 parses as 2 * (x^2) due to precedence."""
        result = _parse_emit("2x^2")
        assert result == "2 * x ^ 2"

    def test_no_implicit_mul_ident_then_number(self) -> None:
        """x2 is a single identifier, not x * 2."""
        node = _parse("x2")
        assert isinstance(node, Ident)
        assert node.name == "x2"

    def test_implicit_mul_parenthesized(self) -> None:
        """2(x + y) parses as 2 * (x + y)."""
        result = _parse_emit("2(x + y)")
        assert result == "2 * (x + y)"


# ===========================================================================
# Convex-minus-concave tests
# ===========================================================================


class TestConvexMinusConcave:
    """Tests for convex-minus-concave expression acceptance.

    The convex-minus-concave DCP rule extends _check_expression_convexity_safe
    to accept f(x) - g(x) when f is Convex and g is Concave. This requires
    the function to accept a `functions` parameter with Function models.
    """

    def test_convex_minus_concave_accepted(self) -> None:
        """f(x) - g(x) where f is Convex and g is Concave should be
        accepted as convexity-preserving (convex minus concave is convex)."""
        from formalconstruct.domains.continuous_opt_mapper import _check_expression_convexity_safe
        from formalconstruct.schemas.problem_spec import Function, FunctionProperty
        functions = [
            Function(symbol="f", domain=["S"], codomain="Real", properties=[FunctionProperty.CONVEX]),
            Function(symbol="g", domain=["S"], codomain="Real", properties=[FunctionProperty.CONCAVE]),
        ]
        assert _check_expression_convexity_safe("f(x) - g(x)", ["f", "g"], functions=functions) is True

    def test_convex_minus_convex_rejected(self) -> None:
        """f(x) - g(x) where both f and g are Convex should NOT be
        accepted as convexity-preserving (convex minus convex is not convex)."""
        from formalconstruct.domains.continuous_opt_mapper import _check_expression_convexity_safe
        from formalconstruct.schemas.problem_spec import Function, FunctionProperty
        functions = [
            Function(symbol="f", domain=["S"], codomain="Real", properties=[FunctionProperty.CONVEX]),
            Function(symbol="g", domain=["S"], codomain="Real", properties=[FunctionProperty.CONVEX]),
        ]
        assert _check_expression_convexity_safe("f(x) - g(x)", ["f", "g"], functions=functions) is False
