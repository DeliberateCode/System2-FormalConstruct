"""Shared test fixtures for FormalConstruct tests.

FakeAxleClient: playbook-driven mock returning deterministic AXLE responses.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from formalconstruct.core.config import PipelineConfig
from formalconstruct.schemas.axle_responses import (
    AxleCheckResult,
    AxleExtractDeclsResult,
    AxleHave2LemmaResult,
    AxleNormalizeResult,
    AxleRepairResult,
    AxleTheorem2SorryResult,
    AxleVerifyResult,
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
    Variable,
    VariableClassification,
    VariableBounds,
)


class FakeAxleClient:
    """Returns deterministic pre-recorded responses.

    Configured with a response playbook: an ordered list of
    (tool_name, response_dict) tuples. Each call pops the next matching
    response. If no match, raises AssertionError.
    """

    def __init__(self, playbook: list[tuple[str, dict]] | None = None) -> None:
        self._playbook = list(playbook or [])
        self._call_log: list[tuple[str, dict]] = []

    def _next_response(self, tool: str, result_type: type[BaseModel]) -> BaseModel:
        self._call_log.append((tool, {}))
        for i, (name, data) in enumerate(self._playbook):
            if name == tool:
                self._playbook.pop(i)
                return result_type(**data)
        raise AssertionError(f"No playbook entry for {tool}")

    async def normalize(self, content: str) -> AxleNormalizeResult:
        return self._next_response("normalize", AxleNormalizeResult)

    async def check(self, content: str) -> AxleCheckResult:
        return self._next_response("check", AxleCheckResult)

    async def verify_proof(self, content: str) -> AxleVerifyResult:
        return self._next_response("verify_proof", AxleVerifyResult)

    async def repair_proofs(self, content: str, **kwargs) -> AxleRepairResult:
        return self._next_response("repair_proofs", AxleRepairResult)

    async def extract_decls(self, content: str) -> AxleExtractDeclsResult:
        return self._next_response("extract_decls", AxleExtractDeclsResult)

    async def theorem2sorry(self, content: str) -> AxleTheorem2SorryResult:
        return self._next_response("theorem2sorry", AxleTheorem2SorryResult)

    async def have2lemma(self, content: str) -> AxleHave2LemmaResult:
        return self._next_response("have2lemma", AxleHave2LemmaResult)

    @property
    def call_log(self) -> list[tuple[str, dict]]:
        return self._call_log


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_axle_client() -> FakeAxleClient:
    return FakeAxleClient()


@pytest.fixture
def sample_narrative() -> str:
    return (
        "A firm chooses an output level to minimize total costs, "
        "balancing a strictly convex capital cost against a linear "
        "labor cost."
    )


@pytest.fixture
def sample_problem_spec() -> ProblemSpec:
    return ProblemSpec(
        problem_domain=ProblemDomain.CONTINUOUS_OPTIMIZATION,
        spaces=[Space(name="OutputSpace", base_type=BaseType.REAL)],
        variables=[
            Variable(
                symbol="x",
                classification=VariableClassification.ENDOGENOUS,
                space_reference="OutputSpace",
                bounds=VariableBounds(lower_bound="0", strict_inequality=False),
            ),
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


@pytest.fixture
def sample_lean_source() -> LeanSource:
    lean_content = (
        "import Mathlib\n\n"
        "def OutputSpace : Set ℝ := Set.Ici 0\n\n"
        "variable (CostCapital : ℝ → ℝ)\n"
        "variable (h_CostCapital_strict_convex : StrictConvexOn ℝ OutputSpace CostCapital)\n"
        "variable (CostLabor : ℝ → ℝ)\n"
        "variable (h_CostLabor_convex : ConvexOn ℝ OutputSpace CostLabor)\n\n"
        "theorem minimize_x_strictconvexon :\n"
        "    StrictConvexOn ℝ OutputSpace (fun x => CostCapital x + CostLabor x) := by\n"
        "  sorry\n"
    )
    return LeanSource(
        content=lean_content,
        imports=["Mathlib"],
        goals=[
            LeanGoal(
                goal_id="goal_0",
                theorem_name="minimize_x_strictconvexon",
                goal_state="",
                line_number=10,
                sorry_offset=lean_content.index("sorry"),
            ),
        ],
        mathlib_modules=["Mathlib"],
    )


@pytest.fixture
def pipeline_config() -> PipelineConfig:
    return PipelineConfig()
