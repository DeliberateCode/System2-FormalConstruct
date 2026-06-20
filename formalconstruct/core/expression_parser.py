"""Recursive-descent expression parser and Lean 4 emitter.

Parses mathematical expressions into an AST and emits Lean 4 syntax.
Domain-agnostic infrastructure used by domain mappers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Union

from formalconstruct.core.exceptions import ExpressionParseError


# ---------------------------------------------------------------------------
# AST node types (frozen dataclasses)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class NumberLit:
    """Numeric literal: 2, 3.14"""
    value: str


@dataclass(frozen=True)
class Ident:
    """Variable or symbol reference: x, y, CostCapital"""
    name: str


@dataclass(frozen=True)
class FuncApp:
    """Function application: f(x), f(x, y), f(g(x))"""
    func: str
    args: tuple  # tuple of ExprNode (use tuple for frozen hashability)


@dataclass(frozen=True)
class BinOp:
    """Binary operator: +, -, *, /, ^"""
    op: str
    left: ExprNode
    right: ExprNode


@dataclass(frozen=True)
class UnaryNeg:
    """Unary negation: -expr"""
    operand: ExprNode


ExprNode = Union[NumberLit, Ident, FuncApp, BinOp, UnaryNeg]


# Transcendental functions that map directly to Mathlib's `Real.*` namespace.
# These need no ProblemSpec Function declaration: the emitter rewrites them to
# their qualified Lean name.
KNOWN_BUILTIN_FUNCTIONS = frozenset({
    "sin", "cos", "tan", "exp", "log", "sqrt",
    "arctan", "arcsin", "arccos", "sinh", "cosh", "tanh",
})
BUILTIN_TO_LEAN: dict[str, str] = {name: f"Real.{name}" for name in KNOWN_BUILTIN_FUNCTIONS}


# ---------------------------------------------------------------------------
# LaTeX normalization
# ---------------------------------------------------------------------------

_FORMATTING_SHORT = re.compile(r'\\[,;!]')
_FORMATTING_WORD = re.compile(r'\\(?:quad|qquad)\b')
_REMAINING_CMD = re.compile(r'\\([a-zA-Z]+)')
_LEAN_IDENT_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_']*$")


def _is_escaped(text: str, pos: int) -> bool:
    """Return True if the character at *pos* is preceded by an odd number of backslashes."""
    n = 0
    i = pos - 1
    while i >= 0 and text[i] == '\\':
        n += 1
        i -= 1
    return n % 2 == 1


def _find_balanced_brace(text: str, open_pos: int) -> int | None:
    """Return index of '}' matching '{' at *open_pos*, or ``None``.

    Ignores escaped braces (``\\{`` and ``\\}``)."""
    depth = 1
    pos = open_pos + 1
    while pos < len(text):
        if text[pos] == '{' and not _is_escaped(text, pos):
            depth += 1
        elif text[pos] == '}' and not _is_escaped(text, pos):
            depth -= 1
            if depth == 0:
                return pos
        pos += 1
    return None


def normalize_expression(expr: str) -> str:
    r"""Convert common LaTeX macros to plain syntax before parsing.

    Supports ``\frac``, ``\sqrt{...}``, ``\cdot``, ``\times``,
    ``\left``/``\right`` delimiters, ``^{...}`` exponent brace stripping,
    and formatting-only commands (``\,``, ``\;``, ``\!``, ``\quad``).
    Raises :class:`ExpressionParseError` for unsupported constructs
    (``\sum``, ``\int``, ``\prod``) and for ``\sqrt`` without braces.
    """
    while r'\sqrt' in expr:
        idx = expr.index(r'\sqrt')
        after = expr[idx + 5:]
        after_stripped = after.lstrip()
        if after_stripped.startswith('{'):
            end = _find_balanced_brace(after_stripped, 0)
            if end is None:
                raise ExpressionParseError(expr, idx, r"unbalanced braces in \sqrt")
            inner = after_stripped[1:end]
            expr = expr[:idx] + f"sqrt({inner})" + after_stripped[end + 1:]
        elif after_stripped and (after_stripped[0].isalpha() or after_stripped[0] == '_'):
            i = 0
            while i < len(after_stripped) and (after_stripped[i].isalnum() or after_stripped[i] == '_'):
                i += 1
            token = after_stripped[:i]
            expr = expr[:idx] + f"sqrt({token})" + after_stripped[i:]
        else:
            raise ExpressionParseError(
                expr, idx,
                r"\sqrt requires braces or a single token: use \sqrt{...} or \sqrt x",
            )
    for cmd in (r'\sum', r'\int', r'\prod'):
        if cmd in expr:
            raise ExpressionParseError(
                expr, expr.index(cmd),
                f"{cmd} is not supported: decompose into function application",
            )
    result = expr
    while True:
        idx = result.find(r'\frac{')
        if idx == -1:
            break
        open_num = idx + 5
        close_num = _find_balanced_brace(result, open_num)
        if close_num is None:
            raise ExpressionParseError(result, idx, r"unbalanced braces in \frac")
        numerator = result[open_num + 1 : close_num]
        den_pos = close_num + 1
        while den_pos < len(result) and result[den_pos] in (' ', '\t'):
            den_pos += 1
        if den_pos >= len(result) or result[den_pos] != '{':
            raise ExpressionParseError(
                result, min(den_pos, len(result) - 1),
                r"expected '{' for \frac denominator",
            )
        close_den = _find_balanced_brace(result, den_pos)
        if close_den is None:
            raise ExpressionParseError(result, den_pos, r"unbalanced braces in \frac")
        denominator = result[den_pos + 1 : close_den]
        result = result[:idx] + f"({numerator}) / ({denominator})" + result[close_den + 1 :]

    # Strip LaTeX exponent braces: x^{expr} -> x^(expr) or x^atom
    while True:
        idx = result.find('^{')
        if idx == -1:
            break
        close = _find_balanced_brace(result, idx + 1)
        if close is None:
            raise ExpressionParseError(result, idx, "unbalanced braces in exponent")
        inner = result[idx + 2 : close]
        stripped_inner = inner.strip()
        if stripped_inner.isdigit() or _LEAN_IDENT_RE.match(stripped_inner):
            result = result[:idx] + '^' + stripped_inner + result[close + 1:]
        else:
            result = result[:idx] + '^(' + stripped_inner + ')' + result[close + 1:]

    result = result.replace(r'\left(', '(')
    result = result.replace(r'\right)', ')')
    result = result.replace(r'\left[', '(')
    result = result.replace(r'\right]', ')')
    result = result.replace(r'\cdot', '*')
    result = result.replace(r'\times', '*')

    result = _FORMATTING_SHORT.sub('', result)
    result = _FORMATTING_WORD.sub('', result)

    m = _REMAINING_CMD.search(result)
    if m:
        pos = max(expr.find('\\' + m.group(1)), 0)
        raise ExpressionParseError(
            expr, pos,
            f"unrecognized LaTeX command '\\{m.group(1)}'",
        )

    return result


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

_MAX_DEPTH = 50


class ExpressionParser:
    """Recursive-descent parser for mathematical expressions.

    Produces an AST of ExprNode values. Deterministic, no LLM involvement.

    Grammar (BNF):
        expression    ::= term (('+' | '-') term)*
        term          ::= power (('*' | '/') power | implicit_mul)*
        implicit_mul  ::= number (identifier | '(' expression ')')
        power         ::= unary ('^' power)?
        unary         ::= '-' unary | atom
        atom          ::= number | function_call | identifier | '(' expression ')'
        function_call ::= identifier '(' arg_list ')'
        arg_list      ::= expression (',' expression)*
        identifier    ::= [a-zA-Z_][a-zA-Z0-9_']*
        number        ::= [0-9]+ ('.' [0-9]+)?
    """

    def __init__(self, text: str, known_functions: list[str] | None = None):
        self._text = normalize_expression(text)
        self._pos = 0
        self._depth = 0
        self._known_functions: set[str] | None = (
            set(known_functions) if known_functions is not None else None
        )

    def parse(self) -> ExprNode:
        """Parse the full expression. Raises ExpressionParseError on failure."""
        self._skip_whitespace()
        if self._pos >= len(self._text):
            raise ExpressionParseError(self._text or "", 0, "empty expression")
        node = self._parse_expression()
        self._skip_whitespace()
        if self._pos < len(self._text):
            raise ExpressionParseError(
                self._text, self._pos,
                f"unexpected character '{self._text[self._pos]}'"
            )
        return node

    # -- grammar methods ---------------------------------------------------

    def _parse_expression(self) -> ExprNode:
        """expression ::= term (('+' | '-') term)*"""
        self._enter()
        try:
            left = self._parse_term()
            while self._peek() in ('+', '-'):
                op = self._advance()
                self._skip_whitespace()
                right = self._parse_term()
                left = BinOp(op=op, left=left, right=right)
            return left
        finally:
            self._leave()

    def _parse_term(self) -> ExprNode:
        """term ::= unary (('*' | '/') unary | implicit_mul)*

        Implicit multiplication triggers in two cases:
        1. A numeric literal (or negated numeric) followed by an identifier
           or '(': ``2x``, ``-3f(x)``, ``2(x+1)``.
        2. Any expression followed by '(' when the expression is not a bare
           identifier (bare ident + '(' is a function call, already handled
           by the atom parser): ``(x+1)(y+1)``, ``f(x)(y)``.
        """
        left = self._parse_unary()
        while True:
            self._skip_whitespace()
            ch = self._peek()
            if ch in ('*', '/'):
                op = self._advance()
                self._skip_whitespace()
                right = self._parse_unary()
                left = BinOp(op=op, left=left, right=right)
            elif (
                (isinstance(left, NumberLit)
                 or (isinstance(left, UnaryNeg) and isinstance(left.operand, NumberLit)))
                and ch is not None
                and (ch.isalpha() or ch == '_' or ch == '(')):
                right = self._parse_unary()
                left = BinOp(op='*', left=left, right=right)
            elif ch == '(' and not isinstance(left, Ident):
                right = self._parse_unary()
                left = BinOp(op='*', left=left, right=right)
            else:
                break
        return left

    def _parse_power(self) -> ExprNode:
        """power ::= atom ('^' power)?  -- right-associative"""
        base = self._parse_atom()
        self._skip_whitespace()
        if self._pos < len(self._text) and self._text[self._pos] == '^':
            self._pos += 1
            self._skip_whitespace()
            exponent = self._parse_power()  # recursive for right-associativity
            return BinOp(op='^', left=base, right=exponent)
        return base

    def _parse_unary(self) -> ExprNode:
        """unary ::= '-' power | power"""
        if self._peek() == '-':
            self._advance()
            self._skip_whitespace()
            operand = self._parse_power()
            return UnaryNeg(operand=operand)
        return self._parse_power()

    def _parse_atom(self) -> ExprNode:
        """atom ::= number | function_call | identifier | '(' expression ')'"""
        self._skip_whitespace()
        ch = self._peek()

        if ch is None:
            raise ExpressionParseError(
                self._text, self._pos, "unexpected end of expression"
            )

        if ch == '\\':
            raise ExpressionParseError(
                self._text, self._pos,
                "unexpected character '\\' (LaTeX commands are not supported; "
                "normalize the expression to plain syntax)"
            )

        # parenthesized sub-expression
        if ch == '(':
            self._advance()  # consume '('
            self._skip_whitespace()
            node = self._parse_expression()
            self._skip_whitespace()
            self._expect(')')
            self._skip_whitespace()
            return node

        # number
        if ch.isdigit():
            return self._parse_number()

        # identifier or function call
        if ch.isalpha() or ch == '_':
            return self._parse_identifier_or_func()

        raise ExpressionParseError(
            self._text, self._pos,
            f"unexpected character '{ch}'"
        )

    def _parse_number(self) -> NumberLit:
        """number ::= [0-9]+ ('.' [0-9]+)?"""
        start = self._pos
        while self._pos < len(self._text) and self._text[self._pos].isdigit():
            self._pos += 1
        if self._pos < len(self._text) and self._text[self._pos] == '.':
            self._pos += 1
            if self._pos >= len(self._text) or not self._text[self._pos].isdigit():
                raise ExpressionParseError(
                    self._text, self._pos,
                    "expected digit after decimal point"
                )
            while self._pos < len(self._text) and self._text[self._pos].isdigit():
                self._pos += 1
        value = self._text[start:self._pos]
        self._skip_whitespace()
        return NumberLit(value=value)

    def _parse_identifier_or_func(self) -> ExprNode:
        """identifier ::= [a-zA-Z_][a-zA-Z0-9_']*
        function_call ::= identifier '(' arg_list ')'
        """
        start = self._pos
        while self._pos < len(self._text) and (
            self._text[self._pos].isalnum()
            or self._text[self._pos] == '_'
            or self._text[self._pos] == "'"
        ):
            self._pos += 1
        name = self._text[start:self._pos]
        self._skip_whitespace()

        # check for function call: identifier followed by '('
        if self._peek() == '(':
            is_func = (
                self._known_functions is None
                or name in self._known_functions
            )
            if is_func:
                self._advance()  # consume '('
                self._skip_whitespace()
                args = [self._parse_expression()]
                while self._peek() == ',':
                    self._advance()  # consume ','
                    self._skip_whitespace()
                    args.append(self._parse_expression())
                self._skip_whitespace()
                self._expect(')')
                self._skip_whitespace()
                return FuncApp(func=name, args=tuple(args))

        return Ident(name=name)

    # -- helpers ------------------------------------------------------------

    def _skip_whitespace(self) -> None:
        while self._pos < len(self._text) and self._text[self._pos].isspace():
            self._pos += 1

    def _peek(self) -> str | None:
        if self._pos < len(self._text):
            return self._text[self._pos]
        return None

    def _advance(self) -> str:
        ch = self._text[self._pos]
        self._pos += 1
        self._skip_whitespace()
        return ch

    def _expect(self, ch: str) -> None:
        if self._pos >= len(self._text):
            raise ExpressionParseError(
                self._text, self._pos,
                f"expected '{ch}' but reached end of expression"
            )
        if self._text[self._pos] != ch:
            raise ExpressionParseError(
                self._text, self._pos,
                f"expected '{ch}' but found '{self._text[self._pos]}'"
            )
        self._pos += 1

    def _enter(self) -> None:
        self._depth += 1
        if self._depth > _MAX_DEPTH:
            raise ExpressionParseError(
                self._text, self._pos,
                f"expression exceeds maximum nesting depth of {_MAX_DEPTH}"
            )

    def _leave(self) -> None:
        self._depth -= 1


# ---------------------------------------------------------------------------
# Lean emitter
# ---------------------------------------------------------------------------

def _precedence(node: ExprNode) -> int:
    """Return precedence level for parenthesization decisions."""
    if isinstance(node, BinOp):
        if node.op in ('+', '-'):
            return 1
        if node.op in ('*', '/'):
            return 2
        if node.op == '^':
            return 3
    if isinstance(node, UnaryNeg):
        return 4
    # atoms and function applications don't need outer parens
    return 5


def _is_simple(node: ExprNode) -> bool:
    """Return True if node needs no parentheses as a function argument."""
    return isinstance(node, (NumberLit, Ident))


def _emit_with_parens(node: ExprNode, parent_prec: int, is_right: bool = False,
                      parent_op: str = "",
                      func_rename: dict[str, str] | None = None) -> str:
    """Emit a node, adding parens if its precedence is lower than parent."""
    node_prec = _precedence(node)
    needs_parens = False
    if isinstance(node, BinOp):
        if node_prec < parent_prec:
            needs_parens = True
        elif node_prec == parent_prec:
            if parent_op == '^':
                # Right-associative: parens needed on LEFT child only
                needs_parens = not is_right
            else:
                # Left-associative: parens needed on RIGHT child
                needs_parens = is_right
    elif isinstance(node, UnaryNeg) and parent_op == '^':
        # Lean 4: HPow (prec 80) binds tighter than Neg (prec 75),
        # so -x ^ 2 means -(x ^ 2). Parenthesize to preserve (-x) ^ 2.
        needs_parens = True
    result = emit_lean(node, func_rename=func_rename)
    if needs_parens:
        return f"({result})"
    return result


def emit_lean(node: ExprNode, func_rename: dict[str, str] | None = None) -> str:
    """Convert an ExprNode AST to a Lean 4 expression string.

    When *func_rename* is provided, function-application names are rewritten
    via the mapping (e.g. ``sin`` -> ``Real.sin``); unmapped names emit as-is.
    """
    if isinstance(node, NumberLit):
        return node.value

    if isinstance(node, Ident):
        return node.name

    if isinstance(node, UnaryNeg):
        if _is_simple(node.operand):
            return f"-{emit_lean(node.operand, func_rename=func_rename)}"
        return f"-({emit_lean(node.operand, func_rename=func_rename)})"

    if isinstance(node, FuncApp):
        func_name = func_rename.get(node.func, node.func) if func_rename else node.func
        parts = [func_name]
        for arg in node.args:
            if _is_simple(arg):
                parts.append(emit_lean(arg, func_rename=func_rename))
            else:
                parts.append(f"({emit_lean(arg, func_rename=func_rename)})")
        return " ".join(parts)

    if isinstance(node, BinOp):
        prec = _precedence(node)
        left_str = _emit_with_parens(node.left, prec, is_right=False, parent_op=node.op, func_rename=func_rename)
        right_str = _emit_with_parens(node.right, prec, is_right=True, parent_op=node.op, func_rename=func_rename)
        return f"{left_str} {node.op} {right_str}"

    raise TypeError(f"Unknown AST node type: {type(node)}")
