"""Integration test: golden path scaffolding of a convex optimization problem.

Verifies that the canonical convex cost minimization example produces valid
Lean 4 scaffolding with the expected structure: imports, theorem signature,
sorry placeholders, and no free variables.
"""

from __future__ import annotations

import re

import pytest

from formalconstruct.agents.lean_scaffolding import LeanScaffoldingAgent
from formalconstruct.domains import create_default_registry
from formalconstruct.schemas.problem_spec import (
    BaseType,
    Function,
    FunctionProperty,
    Objective,
    ObjectiveDirection,
    ProblemDomain,
    ProblemSpec,
    Space,
    Variable,
    VariableBounds,
    VariableClassification,
)


@pytest.fixture()
def continuous_opt_spec() -> ProblemSpec:
    """Canonical convex cost minimization ProblemSpec."""
    return ProblemSpec(
        problem_domain=ProblemDomain.CONTINUOUS_OPTIMIZATION,
        spaces=[Space(name="OutputSpace", base_type=BaseType.REAL)],
        variables=[
            Variable(
                symbol="x",
                classification=VariableClassification.ENDOGENOUS,
                space_reference="OutputSpace",
                bounds=VariableBounds(lower_bound="0", strict_inequality=False),
            )
        ],
        functions=[
            Function(
                symbol="CostCapital",
                domain=["OutputSpace"],
                codomain="Real",
                properties=[FunctionProperty.STRICT_CONVEX],
            ),
            Function(
                symbol="CostLabor",
                domain=["OutputSpace"],
                codomain="Real",
                properties=[FunctionProperty.LINEAR, FunctionProperty.CONVEX],
            ),
        ],
        objective=Objective(
            direction=ObjectiveDirection.MINIMIZE,
            expression_latex="CostCapital(x) + CostLabor(x)",
            target_variable="x",
        ),
    )


class TestGoldenPathScaffolding:
    """End-to-end scaffolding of the canonical convex optimization example."""

    def test_imports_present(self, continuous_opt_spec):
        """Generated Lean must contain Mathlib import."""
        registry = create_default_registry()
        agent = LeanScaffoldingAgent(registry)
        result = agent.scaffold(continuous_opt_spec)
        assert "import Mathlib" in result.content

    def test_theorem_signature_present(self, continuous_opt_spec):
        """Generated Lean must contain a theorem statement."""
        registry = create_default_registry()
        agent = LeanScaffoldingAgent(registry)
        result = agent.scaffold(continuous_opt_spec)
        assert re.search(r"\btheorem\b", result.content), (
            "Scaffolded output must contain a 'theorem' keyword"
        )

    def test_sorry_present(self, continuous_opt_spec):
        """Generated Lean must contain at least one sorry placeholder."""
        registry = create_default_registry()
        agent = LeanScaffoldingAgent(registry)
        result = agent.scaffold(continuous_opt_spec)
        assert "sorry" in result.content

    def test_no_free_variables(self, continuous_opt_spec):
        """All variable identifiers in the theorem body must be bound.

        The expression uses 'x' which must appear as a lambda binder
        (fun x =>) in the theorem body. No other lowercase single-letter
        identifiers should appear unbound in the theorem section.
        """
        registry = create_default_registry()
        agent = LeanScaffoldingAgent(registry)
        result = agent.scaffold(continuous_opt_spec)
        content = result.content

        # The binder 'fun x =>' must be present
        assert "fun x =>" in content, (
            "Theorem body must bind 'x' via 'fun x =>'"
        )

        # Extract the theorem block (from 'theorem' to 'sorry')
        theorem_match = re.search(
            r"theorem\s+\w+.*?sorry", content, re.DOTALL
        )
        assert theorem_match is not None, (
            "Could not find theorem...sorry block in output"
        )
        theorem_block = theorem_match.group()

        # After the binder, function names (CostCapital, CostLabor) and
        # the bound variable (x) should be the only identifiers.
        # Check that no single lowercase letter other than x appears as a
        # standalone word token (which would indicate a free variable).
        after_binder = theorem_block.split("fun x =>")[-1] if "fun x =>" in theorem_block else ""
        free_vars = re.findall(r"\b([a-z])\b", after_binder)
        # Filter out 'x' (bound) and known Lean keywords
        lean_keywords = {"by", "x"}
        unexpected = [v for v in free_vars if v not in lean_keywords]
        assert not unexpected, (
            f"Found potentially free variables in theorem body: {unexpected}"
        )

    def test_domain_definition_present(self, continuous_opt_spec):
        """Generated Lean must define the OutputSpace domain set."""
        registry = create_default_registry()
        agent = LeanScaffoldingAgent(registry)
        result = agent.scaffold(continuous_opt_spec)
        assert "def OutputSpace" in result.content

    def test_function_hypotheses_present(self, continuous_opt_spec):
        """Generated Lean must declare function hypotheses with correct properties."""
        registry = create_default_registry()
        agent = LeanScaffoldingAgent(registry)
        result = agent.scaffold(continuous_opt_spec)
        assert "StrictConvexOn" in result.content
        assert "ConvexOn" in result.content

    def test_expression_in_theorem_body(self, continuous_opt_spec):
        """The expression 'CostCapital x + CostLabor x' must appear in the theorem."""
        registry = create_default_registry()
        agent = LeanScaffoldingAgent(registry)
        result = agent.scaffold(continuous_opt_spec)
        assert "CostCapital x + CostLabor x" in result.content

    def test_goals_extracted(self, continuous_opt_spec):
        """At least one goal must be extracted from the scaffolded output."""
        registry = create_default_registry()
        agent = LeanScaffoldingAgent(registry)
        result = agent.scaffold(continuous_opt_spec)
        assert len(result.goals) >= 1
        goal = result.goals[0]
        assert goal.goal_id == "goal_0"
        assert goal.theorem_name != "unknown"
        assert goal.line_number > 0
