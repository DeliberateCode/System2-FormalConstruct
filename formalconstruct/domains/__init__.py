from formalconstruct.domains.registry import DomainMapper, DomainRegistry
from formalconstruct.domains.continuous_opt_mapper import ContinuousOptMapper
from formalconstruct.domains.game_theory_mapper import GameTheoryMapper


def create_default_registry() -> DomainRegistry:
    """Factory that creates a registry with the initial built-in mappers."""
    registry = DomainRegistry()
    registry.register(ContinuousOptMapper())
    registry.register(GameTheoryMapper(domain="non_cooperative_game"))
    registry.register(GameTheoryMapper(domain="cooperative_game"))
    return registry


__all__ = [
    "ContinuousOptMapper",
    "DomainMapper",
    "DomainRegistry",
    "GameTheoryMapper",
    "create_default_registry",
]
