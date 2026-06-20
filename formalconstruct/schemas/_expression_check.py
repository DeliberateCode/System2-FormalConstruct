"""Optional expression identifier validation.

Thin wrapper that imports the expression parser and extracts identifiers.
If the parser is not available (import error), validation is skipped with
a warning. This isolates the schemas/ -> core/ boundary crossing to a
single internal module.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def collect_expression_identifiers(
    expression_latex: str,
    func_symbols: set[str],
) -> set[str] | None:
    """Parse expression_latex and return non-function identifiers.

    Returns None if the expression parser is not available or the
    expression cannot be parsed (validation skipped).
    Raises ValueError if the expression is syntactically malformed.
    """
    try:
        from formalconstruct.core.expression_parser import (
            ExpressionParser,
            Ident,
            FuncApp,
            BinOp,
            UnaryNeg,
        )
    except ImportError:
        logger.debug(
            "Expression parser not available; skipping expression_latex validation"
        )
        return None

    try:
        parser = ExpressionParser(expression_latex)
        ast = parser.parse()
    except Exception as exc:
        raise ValueError(f"expression_latex is malformed: {exc}") from exc

    idents: set[str] = set()

    def _walk(node):
        if isinstance(node, Ident):
            idents.add(node.name)
        elif isinstance(node, FuncApp):
            if node.func not in func_symbols:
                idents.add(node.func)
            for arg in node.args:
                _walk(arg)
        elif isinstance(node, BinOp):
            _walk(node.left)
            _walk(node.right)
        elif isinstance(node, UnaryNeg):
            _walk(node.operand)

    _walk(ast)
    return idents


def check_function_arity(
    expression_latex: str,
    func_symbols: set[str],
    func_arities: dict[str, int],
) -> list[str]:
    """Check that function applications match declared arities.

    Returns a list of error messages (empty if all calls are valid).
    """
    try:
        from formalconstruct.core.expression_parser import (
            ExpressionParser,
            FuncApp,
            BinOp,
            UnaryNeg,
        )
    except ImportError:
        return []

    try:
        ast = ExpressionParser(expression_latex).parse()
    except Exception:
        return []

    errors: list[str] = []

    def _walk(node):
        if isinstance(node, FuncApp):
            if node.func in func_arities:
                expected = func_arities[node.func]
                actual = len(node.args)
                if actual != expected:
                    errors.append(
                        f"Function '{node.func}' expects {expected} "
                        f"argument(s) but was called with {actual}"
                    )
            for arg in node.args:
                _walk(arg)
        elif isinstance(node, BinOp):
            _walk(node.left)
            _walk(node.right)
        elif isinstance(node, UnaryNeg):
            _walk(node.operand)

    _walk(ast)
    return errors
