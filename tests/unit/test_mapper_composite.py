"""Unit tests for CompositeDomainMapper and composite context forwarding."""

from formalconstruct.domains.composite_mapper import CompositeDomainMapper
from formalconstruct.domains.continuous_opt_mapper import ContinuousOptMapper
from formalconstruct.domains.game_theory_mapper import GameTheoryMapper

from tests.unit.conftest import _make_continuous_opt_spec


# ---------------------------------------------------------------------------
# CompositeDomainMapper tests
# ---------------------------------------------------------------------------


class TestCompositeDomainMapper:

    def test_import_merging_deduplicated(self):
        spec = _make_continuous_opt_spec()
        cont = ContinuousOptMapper()
        game = GameTheoryMapper()
        composite = CompositeDomainMapper(
            primary_domain="continuous_optimization",
            child_mappers=[cont, game],
        )
        imports = composite.required_imports(spec)
        assert imports == ["import Mathlib"]

    def test_objective_delegates_to_primary(self):
        spec = _make_continuous_opt_spec()
        cont = ContinuousOptMapper()
        game = GameTheoryMapper()
        composite = CompositeDomainMapper(
            primary_domain="continuous_optimization",
            child_mappers=[cont, game],
        )
        result = composite.map_objective(spec.objective, spec)
        assert "StrictConvexOn" in result

    def test_domain_name_prefix(self):
        composite = CompositeDomainMapper(
            primary_domain="non_cooperative_game",
            child_mappers=[GameTheoryMapper(), ContinuousOptMapper()],
        )
        assert composite.domain_name == "composite:non_cooperative_game"


# ---------------------------------------------------------------------------
# Composite context forwarding
# ---------------------------------------------------------------------------


class TestCompositeContextForwarding:

    def test_composite_forwards_set_context_to_children(self):
        cont = ContinuousOptMapper()
        game = GameTheoryMapper()
        spec = _make_continuous_opt_spec()
        composite = CompositeDomainMapper(
            primary_domain="continuous_optimization",
            child_mappers=[cont, game],
        )
        composite.set_context(spec)
        assert len(cont._spaces) > 0
        assert len(game._spaces) > 0

    def test_composite_forwards_clear_context(self):
        cont = ContinuousOptMapper()
        game = GameTheoryMapper()
        spec = _make_continuous_opt_spec()
        composite = CompositeDomainMapper(
            primary_domain="continuous_optimization",
            child_mappers=[cont, game],
        )
        composite.set_context(spec)
        assert len(cont._spaces) > 0
        assert len(game._spaces) > 0

        composite.clear_context()
        assert len(cont._spaces) == 0
        assert len(game._spaces) == 0
