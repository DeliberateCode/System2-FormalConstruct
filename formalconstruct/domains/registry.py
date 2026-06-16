from __future__ import annotations

from abc import ABC, abstractmethod

from formalconstruct.schemas.problem_spec import (
    BaseType,
    Function,
    FunctionProperty,
    IndexedVariable,
    Objective,
    ParametricConstraint,
    ProblemSpec,
    SequenceRelation,
    Space,
    Variable,
    VariableClassification,
)


def _lean_type_for_space(space: Space) -> str:
    """Map a Space to its Lean 4 type string.

    Shared utility used by ContinuousOptMapper and GameTheoryMapper.
    Handles REAL_N with concrete dimensions via ``space.dimension``.
    REAL, NONNEG_REAL, and POS_REAL all use ℝ as the carrier type.
    NONNEG_REAL and POS_REAL are modeled as bounded subsets of ℝ.
    INT maps to ℤ, NAT maps to ℕ, BOOL maps to Bool.
    """
    if space.base_type == BaseType.REAL_N:
        if space.dimension is not None:
            return f"EuclideanSpace ℝ (Fin {space.dimension})"
        return "EuclideanSpace ℝ (Fin n)"
    type_map = {
        BaseType.INT: "ℤ",
        BaseType.NAT: "ℕ",
        BaseType.BOOL: "Bool",
    }
    return type_map.get(space.base_type, "ℝ")


def property_hypothesis(symbol: str, domain_set: str, prop: FunctionProperty) -> str:
    """Shared mapping from FunctionProperty to Mathlib type class hypothesis."""
    mapping = {
        FunctionProperty.STRICT_CONVEX:
            f"variable (h_{symbol}_strict_convex : StrictConvexOn ℝ {domain_set} {symbol})",
        FunctionProperty.CONVEX:
            f"variable (h_{symbol}_convex : ConvexOn ℝ {domain_set} {symbol})",
        FunctionProperty.STRICT_CONCAVE:
            f"variable (h_{symbol}_strict_concave : StrictConcaveOn ℝ {domain_set} {symbol})",
        FunctionProperty.CONCAVE:
            f"variable (h_{symbol}_concave : ConcaveOn ℝ {domain_set} {symbol})",
        FunctionProperty.CONTINUOUS:
            f"variable (h_{symbol}_continuous : ContinuousOn {symbol} {domain_set})",
        FunctionProperty.DIFFERENTIABLE:
            f"variable (h_{symbol}_diff : DifferentiableOn ℝ {symbol} {domain_set})",
        FunctionProperty.LINEAR:
            f"variable (h_{symbol}_convex : ConvexOn ℝ {domain_set} {symbol})\n"
            f"variable (h_{symbol}_concave : ConcaveOn ℝ {domain_set} {symbol})",
    }
    return mapping.get(prop, "")


class DomainMapper(ABC):
    """Abstract base class for domain-specific Lean mapping."""

    @property
    @abstractmethod
    def domain_name(self) -> str:
        """Identifier matching ProblemDomain enum values."""
        ...

    @abstractmethod
    def required_imports(self, spec: ProblemSpec) -> list[str]:
        """Return the Mathlib import strings required for this domain."""
        ...

    @abstractmethod
    def map_space(self, space: Space) -> str:
        """Map a Space model to Lean 4 definition code."""
        ...

    @abstractmethod
    def map_variable(self, var: Variable, spaces: dict[str, Space]) -> str:
        """Map a Variable model to Lean 4 variable declaration."""
        ...

    @abstractmethod
    def map_function(self, func: Function) -> str:
        """Map a Function model to Lean 4 hypothesis declaration."""
        ...

    @abstractmethod
    def map_objective(self, objective: Objective, spec: ProblemSpec) -> str:
        """Map an Objective to a Lean 4 theorem signature."""
        ...

    @abstractmethod
    def map_bounds(self, var: Variable) -> str:
        """Map variable bounds to Mathlib interval notation."""
        ...

    def supported_classifications(self) -> list[VariableClassification]:
        """Variable classifications this mapper handles.

        Used by CompositeDomainMapper for routing. Non-abstract with a
        default empty implementation so existing mappers don't break."""
        return []

    # -- Schema-extension hooks (default no-op; overridden where supported) --

    def map_indexed_variable(self, iv: IndexedVariable) -> str:
        """Map an indexed/sequence variable to Lean declarations."""
        return ""

    def map_constraint(self, constraint: ParametricConstraint, idx: int) -> str:
        """Map a parametric constraint to a Lean hypothesis declaration."""
        return ""

    def map_sequence_relation(self, relation: SequenceRelation, idx: int) -> str:
        """Map a sequence relation to a Lean hypothesis declaration."""
        return ""


class DomainRegistry:
    """Plugin registration system."""

    def __init__(self) -> None:
        self._mappers: dict[str, DomainMapper] = {}

    def register(self, mapper: DomainMapper) -> None:
        """Register a DomainMapper instance. Keyed by mapper.domain_name."""
        self._mappers[mapper.domain_name] = mapper

    def get_mapper(
        self,
        problem_domain: str,
        domain_components: list[str] | None = None,
    ) -> DomainMapper:
        """Return the appropriate mapper.

        If domain_components is non-empty, returns a CompositeDomainMapper.
        Raises UnknownDomainError if no mapper registered."""
        from formalconstruct.core.exceptions import UnknownDomainError

        if domain_components:
            from formalconstruct.domains.composite_mapper import (
                CompositeDomainMapper,
            )

            child_mappers = []
            for component in domain_components:
                if component not in self._mappers:
                    raise UnknownDomainError(component)
                child_mappers.append(self._mappers[component])
            return CompositeDomainMapper(
                primary_domain=problem_domain,
                child_mappers=child_mappers,
            )
        if problem_domain not in self._mappers:
            raise UnknownDomainError(problem_domain)
        return self._mappers[problem_domain]

    def list_domains(self) -> list[str]:
        return list(self._mappers.keys())
