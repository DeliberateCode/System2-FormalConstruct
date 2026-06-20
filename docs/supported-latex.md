# Supported LaTeX in expression_latex

The expression normalizer converts a subset of LaTeX to plain syntax before parsing. Expressions outside this subset are rejected at ProblemSpec validation time.

## Supported LaTeX macros

| LaTeX | Normalized to | Example |
|-------|--------------|---------|
| `\frac{a}{b}` | `(a) / (b)` | `\frac{x}{2}` becomes `(x) / (2)` |
| `\cdot` | `*` | `2 \cdot f(x)` becomes `2 * f(x)` |
| `\times` | `*` | `a \times b` becomes `a * b` |
| `\left(` | `(` | Delimiter removed |
| `\right)` | `)` | Delimiter removed |
| `\left[` | `(` | Bracket normalized to paren |
| `\right]` | `)` | Bracket normalized to paren |
| `\,` `\;` `\!` | (removed) | Formatting-only spacing |
| `\quad` `\qquad` | (removed) | Formatting-only spacing |

## Supported operators

| Syntax | Lean 4 output | Notes |
|--------|--------------|-------|
| `x^2` | `x ^ 2` | Exponentiation via `HPow.hPow` |
| `x^{n}` | `x ^ n` | LaTeX braces stripped |
| `x^{n+1}` | `x ^ (n + 1)` | Multi-token exponents parenthesized |
| `2x` | `2 * x` | Implicit multiplication |
| `2f(x)` | `2 * f x` | Implicit multiplication with function |

## Supported LaTeX functions

| LaTeX | Normalized to | Example |
|-------|--------------|---------|
| `\sqrt{x}` | `sqrt(x)` | `\sqrt{x+1}` becomes `sqrt(x+1)` — declare `sqrt` as a function in ProblemSpec |

## Rejected LaTeX constructs

These raise `ExpressionParseError` during ProblemSpec validation:

| LaTeX | Reason |
|-------|--------|
| `\sum` | Decompose into function application |
| `\int` | Decompose into function application |
| `\prod` | Decompose into function application |

Any other unrecognized `\command` is also rejected.

## Plain syntax (always accepted)

| Syntax | Meaning |
|--------|---------|
| `+` | Addition |
| `-` | Subtraction or unary negation |
| `*` | Multiplication |
| `/` | Division |
| `()` | Grouping |
| `f(x)` | Function application |
| `f(x, y)` | Multi-argument function application |
| `f(g(x))` | Nested function application |
| `123`, `3.14` | Numeric literals |
| `x`, `CostCapital` | Identifiers (variables and function names) |
