"""Jinja2 template loader and rendering helpers for prompt templates."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import jinja2


_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(Path(__file__).parent)),
    keep_trailing_newline=True,
    undefined=jinja2.StrictUndefined,
)

_scaffold_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(Path(__file__).parent)),
    keep_trailing_newline=True,
    trim_blocks=True,
    lstrip_blocks=True,
    undefined=jinja2.StrictUndefined,
)


def load_template(name: str) -> jinja2.Template:
    """Load a Jinja2 template by filename from the prompts directory."""
    return _env.get_template(name)


def render_error_feedback(
    goal_state: str,
    error_message: str,
    type_mismatch_details: str | None = None,
) -> str:
    """Render the error feedback prompt.

    Combines the prior valid goal state, specific error message, and optional
    type mismatch details into a structured prompt for the next tactic attempt.
    """
    template = load_template("error_feedback.jinja2")
    return template.render(
        goal_state=goal_state,
        error_message=error_message,
        type_mismatch_details=type_mismatch_details,
    )


def render_tactic_generation(
    theorem_signature: str,
    goal_state: str,
    hypotheses: list[str],
    domain_hints: list[str] | None = None,
) -> str:
    """Render the tactic generation prompt.

    Combines the theorem signature, current goal state, available hypotheses,
    and optional domain-specific hints into a structured prompt.
    """
    template = load_template("tactic_generation.jinja2")
    return template.render(
        theorem_signature=theorem_signature,
        goal_state=goal_state,
        hypotheses=hypotheses,
        domain_hints=domain_hints,
    )


def render_lean_scaffold(**kwargs: Any) -> str:
    """Render the Lean scaffold template with categorized blocks.

    Uses a separate Jinja2 environment with trim_blocks and lstrip_blocks
    for precise whitespace control in generated Lean 4 source code.

    Expected keyword arguments:
        import_block: str
        dimension_variable: bool
        space_block: str | None
        variable_block: str | None
        preamble_block: str | None
        function_block: str | None
        theorem_block: str | None
    """
    template = _scaffold_env.get_template("lean_scaffold.jinja2")
    return template.render(**kwargs)
