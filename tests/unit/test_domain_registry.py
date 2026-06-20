"""Backward-compatible re-export module.

Tests have been split into focused modules:
- tests/unit/test_registry.py (registry mechanics)
- tests/unit/test_mapper_continuous_opt.py (ContinuousOptMapper)
- tests/unit/test_mapper_game_theory.py (GameTheoryMapper)
- tests/unit/test_mapper_composite.py (CompositeDomainMapper)

This file re-exports all test classes for backward compatibility.
"""

from tests.unit.test_registry import *  # noqa: F401, F403
from tests.unit.test_mapper_continuous_opt import *  # noqa: F401, F403
from tests.unit.test_mapper_game_theory import *  # noqa: F401, F403
from tests.unit.test_mapper_composite import *  # noqa: F401, F403
