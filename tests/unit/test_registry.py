"""Unit tests for DomainRegistry mechanics: registration, lookup, composite routing."""

import pytest

from formalconstruct.core.exceptions import UnknownDomainError
from formalconstruct.domains import create_default_registry
from formalconstruct.domains.composite_mapper import CompositeDomainMapper
from formalconstruct.domains.registry import DomainRegistry

from tests.unit.conftest import _StubMapper


class TestDomainRegistry:

    def test_register_and_retrieve(self):
        reg = DomainRegistry()
        mapper = _StubMapper("my_domain")
        reg.register(mapper)
        assert reg.get_mapper("my_domain") is mapper

    def test_list_domains_contains_registered(self):
        reg = DomainRegistry()
        reg.register(_StubMapper("alpha"))
        reg.register(_StubMapper("beta"))
        domains = reg.list_domains()
        assert "alpha" in domains
        assert "beta" in domains
        assert len(domains) == 2

    def test_unknown_domain_raises(self):
        reg = DomainRegistry()
        with pytest.raises(UnknownDomainError):
            reg.get_mapper("nonexistent")

    def test_composite_routing_returns_composite_mapper(self):
        reg = DomainRegistry()
        reg.register(_StubMapper("a"))
        reg.register(_StubMapper("b"))
        mapper = reg.get_mapper("a", domain_components=["a", "b"])
        assert isinstance(mapper, CompositeDomainMapper)

    def test_composite_unknown_component_raises(self):
        reg = DomainRegistry()
        reg.register(_StubMapper("a"))
        with pytest.raises(UnknownDomainError):
            reg.get_mapper("a", domain_components=["a", "missing"])


class TestExtensibility:

    def test_register_custom_mapper_no_core_changes(self):
        """A new domain mapper can be registered without modifying
        any existing source files."""
        reg = create_default_registry()
        custom = _StubMapper("custom_domain")
        reg.register(custom)
        assert reg.get_mapper("custom_domain") is custom
        # Built-in mappers still work
        assert reg.get_mapper("continuous_optimization").domain_name == "continuous_optimization"

    def test_default_registry_has_builtin_domains(self):
        reg = create_default_registry()
        domains = reg.list_domains()
        assert "continuous_optimization" in domains
        assert "non_cooperative_game" in domains
        assert "cooperative_game" in domains
