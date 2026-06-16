# Contributing to FormalConstruct

## Versioning

`VERSION` at the repository root is the single source of truth for the package version. After editing it, sync all manifests and commit the result:

```bash
make sync-version
git add VERSION .claude-plugin/marketplace.json plugin/.claude-plugin/plugin.json plugin/system2.overlay.json
git commit -m "Bump version to $(cat VERSION)"
```

CI will fail if the manifests are out of sync with `VERSION`.

## Architecture Orientation

The Python package (`formalconstruct/`) is **pure deterministic infrastructure** — schema validation, domain mapping, expression parsing, Lean scaffolding, and AXLE MCP client. There are no LLM calls in the Python package. All reasoning — narrative interpretation, tactic selection, repair decisions — lives in `.claude/agents/formalize.md`, which instructs Claude Code through the three pipeline stages.

**Where to look when something breaks:**
- Wrong Lean output / bad structure → `formalconstruct/agents/lean_scaffolding.py` and the domain mappers
- Schema validation rejects valid input (or accepts invalid) → `formalconstruct/schemas/problem_spec.py`
- AXLE communication failures → `formalconstruct/mcp_client/`
- Tactic selection / repair strategy / proof loop → `.claude/agents/formalize.md` (agent protocol, not Python)

## Test Layers

```bash
pytest tests/ -m "not live"           # unit + integration (no AXLE required)
pytest tests/test_compose_smoke.py    # overlay smoke tests (requires ../System2)
pytest tests/ -m live                 # live AXLE tests (requires AXLE_API_KEY)
```

`FakeAxleClient` in `tests/conftest.py` is a playbook-driven mock: configure it with an ordered list of `(tool_name, response_dict)` pairs and it returns deterministic responses without a running AXLE server. All unit and integration tests use this — only `tests/live/` requires a real key.

Goal state in `LeanGoal` is always `""` at scaffold time. It is populated by the agent from the `tool_messages.infos` field of an AXLE `check` response during the Proof stage — the Python package never fills it in.

## Design Constraints

**Mapper context lifecycle.** `ContinuousOptMapper` and `GameTheoryMapper` are stateful during a scaffold call — `set_context(spec)` caches data that `map_function()` needs for type resolution. `LeanScaffoldingAgent.scaffold()` clears this in a `finally` block. If you add a mapper that uses `set_context`, always clear in `finally` — a raised exception will otherwise leave stale state for the next call.

**Source mapping line counting is manual.** `LeanScaffoldingAgent` tracks Lean line numbers by counting lines in each output block plus hard-coded blank-line constants that match the Jinja2 template. Any whitespace change to `lean_scaffold.jinja2` will silently produce wrong source mappings without failing tests. Update the offset arithmetic in `scaffold()` any time you touch the template.

**Expression convexity analysis is conservative.** `_is_convexity_preserving()` in `ContinuousOptMapper` only returns `True` for structurally provable cases (sum of convex, positive literal scalar multiple, etc.). A `ScaffoldingError` with a hint is raised if the theorem predicate cannot be derived — this is intentional, not a bug.

**Multi-variable optimization with 3+ variables gets a `sorry` for `convex_domain`.** Only 2-variable uses `Convex.prod` automatically. Three or more requires a manual proof and will scaffold with a sorry at that lemma.

## Known Limitations

| Limitation | Location | Notes |
|---|---|---|
| `REAL_N` bounds rejected | `ContinuousOptMapper.map_bounds()` | Express as a hypothesis on the function instead |
| 4-player cap for heterogeneous games | `ProblemSpec` validator | Enforced at validation; homogeneous games are unlimited |
| No three-way composite domains | `ProblemSpec` validator | Only `{game, continuous_optimization}` allowed |
| `GameTheoryMapper` MINIMIZE/MAXIMIZE | `map_objective()` | Returns `True := by sorry` — not implemented for game theory |
| `\sqrt x` (bare token) unimplemented | `expression_parser.py` | Use `\sqrt{x}` |

## Adding a New AXLE Tool

Adding a tool requires changes in four files:

1. **`formalconstruct/schemas/axle_responses.py`** — add a typed result model (follow `AxleCheckResult` as a template)
2. **`formalconstruct/mcp_client/parsers.py`** — add a `parse_<tool>()` static method on `AxleResponseParser`
3. **`formalconstruct/mcp_client/tools.py`** — add an `async <tool>(self, content, ...) -> TypedResult` method on `AxleToolClient`; call `_call_with_retry(tool_name, params, AxleResponseParser.parse_<tool>)`
4. **`formalconstruct/mcp_client/__init__.py`** — export the new result type if needed

Then add tests in `tests/unit/test_mcp_parsers.py` and `tests/unit/test_axle_tools.py`.

## Adding a New Domain Mapper

FormalConstruct supports new mathematical domains via the `DomainMapper` plugin system.

### Steps

1. **Create a mapper class** in `formalconstruct/domains/`:

```python
from formalconstruct.domains.registry import DomainMapper
from formalconstruct.schemas.problem_spec import (
    Function, Objective, ProblemSpec, Space, Variable, VariableClassification,
)

class MyDomainMapper(DomainMapper):
    @property
    def domain_name(self) -> str:
        return "my_domain"

    def supported_classifications(self) -> list[VariableClassification]:
        return [VariableClassification.ENDOGENOUS]

    def required_imports(self, spec: ProblemSpec) -> list[str]:
        return ["import Mathlib"]

    def map_space(self, space: Space) -> str:
        # Return Lean 4 space definition or empty string
        ...

    def map_variable(self, var: Variable, spaces: dict[str, Space]) -> str:
        # Return Lean 4 variable declaration or empty string
        ...

    def map_function(self, func: Function) -> str:
        # Return Lean 4 function variable + hypotheses
        ...

    def map_objective(self, objective: Objective, spec: ProblemSpec) -> str:
        # Return Lean 4 theorem with sorry
        ...

    def map_bounds(self, var: Variable) -> str:
        # Return Mathlib interval notation
        ...
```

2. **Register it** in `formalconstruct/domains/__init__.py`:

```python
from .my_domain_mapper import MyDomainMapper

def create_default_registry() -> DomainRegistry:
    registry = DomainRegistry()
    registry.register(ContinuousOptMapper())
    registry.register(GameTheoryMapper())
    registry.register(MyDomainMapper())  # Add here
    return registry
```

3. **Add a ProblemDomain enum value** in `schemas/problem_spec.py` if needed.

4. **Write tests** in `tests/unit/test_mapper_my_domain.py`.

5. **Run the full suite**: `make test`

### Architecture

- Mappers return **strings** (Lean 4 source fragments)
- The scaffolding agent parses these into `LeanDeclaration` objects for deduplication
- Final output is rendered via the `lean_scaffold.jinja2` template
- All generated Lean uses `import Mathlib` (AXLE requirement)
- Theorem bodies use `sorry` — proof search is the Proof stage (AXLE-driven)

### Testing

```bash
make setup    # Create venv + install deps
make test     # Run all tests
make lint     # Run ruff
make format   # Format with ruff
```

### Code Style

- No comments unless the WHY is non-obvious
- Pydantic for all data contracts
- Type hints on all public functions
- Tests in `tests/unit/` organized by feature
