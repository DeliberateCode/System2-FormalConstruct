from __future__ import annotations

from formalconstruct.core.exceptions import ScaffoldingError
from formalconstruct.domains.registry import DomainMapper
from formalconstruct.schemas.problem_spec import (
    Function,
    FunctionProperty,
    Objective,
    ProblemSpec,
    Space,
    Variable,
)


class CompositeDomainMapper(DomainMapper):
    """Delegates to child mappers based on domain_components.

    The primary_domain mapper controls the top-level theorem shape
    (map_objective). Other methods delegate to the first child mapper
    that can handle the request."""

    def __init__(
        self,
        primary_domain: str,
        child_mappers: list[DomainMapper],
    ) -> None:
        self._primary_domain = primary_domain
        self._children: dict[str, DomainMapper] = {
            m.domain_name: m for m in child_mappers
        }

    def set_context(self, spec: ProblemSpec) -> None:
        for mapper in self._children.values():
            if hasattr(mapper, 'set_context'):
                mapper.set_context(spec)

    def clear_context(self) -> None:
        for mapper in self._children.values():
            if hasattr(mapper, 'clear_context'):
                mapper.clear_context()

    @property
    def domain_name(self) -> str:
        return f"composite:{self._primary_domain}"

    def required_imports(self, spec: ProblemSpec) -> list[str]:
        imports: list[str] = []
        for mapper in self._children.values():
            for imp in mapper.required_imports(spec):
                if imp not in imports:
                    imports.append(imp)
        return imports

    def _primary_mapper(self) -> DomainMapper:
        if self._primary_domain in self._children:
            return self._children[self._primary_domain]
        if not self._children:
            raise ScaffoldingError("CompositeDomainMapper has no child mappers")
        return next(iter(self._children.values()))

    def _mapper_for_variable(self, var: Variable) -> DomainMapper:
        """Route variable to the domain mapper matching its classification.

        Uses supported_classifications() on each child mapper for routing.
        Falls back to the primary mapper when no child declares support."""
        for m in self._children.values():
            if var.classification in m.supported_classifications():
                return m
        return self._primary_mapper()

    _OPT_PROPERTIES = frozenset({
        FunctionProperty.CONVEX,
        FunctionProperty.STRICT_CONVEX,
        FunctionProperty.CONCAVE,
        FunctionProperty.STRICT_CONCAVE,
        FunctionProperty.LINEAR,
        FunctionProperty.DIFFERENTIABLE,
    })

    def _mapper_for_function(self, func: Function) -> DomainMapper:
        """Route function to the mapper that best fits its properties.

        Functions with convexity/optimization properties route to the
        continuous_optimization mapper so hypotheses are emitted correctly.
        All other functions route to the primary mapper."""
        if set(func.properties) & self._OPT_PROPERTIES:
            if "continuous_optimization" in self._children:
                return self._children["continuous_optimization"]
        return self._primary_mapper()

    def map_space(self, space: Space) -> str:
        return self._primary_mapper().map_space(space)

    def map_variable(self, var: Variable, spaces: dict[str, Space]) -> str:
        return self._mapper_for_variable(var).map_variable(var, spaces)

    def map_function(self, func: Function) -> str:
        return self._mapper_for_function(func).map_function(func)

    def map_objective(self, objective: Objective, spec: ProblemSpec) -> str:
        return self._primary_mapper().map_objective(objective, spec)

    def map_bounds(self, var: Variable) -> str:
        return self._mapper_for_variable(var).map_bounds(var)
