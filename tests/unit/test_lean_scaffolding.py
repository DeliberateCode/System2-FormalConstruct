"""Backward-compatible re-export module.

Tests have been split into focused modules:
- tests/unit/test_scaffolding_continuous.py (continuous optimization scaffolding)
- tests/unit/test_scaffolding_game_theory.py (game theory scaffolding)
- tests/unit/test_scaffolding_mapping.py (source mapping attribution)
- tests/unit/test_scaffolding_expressions.py (expression tests, convexity, binder)
- tests/unit/test_scaffolding_composite.py (composite domain scaffolding)

This file re-exports all test classes for backward compatibility.
"""

from tests.unit.test_scaffolding_continuous import *  # noqa: F401, F403
from tests.unit.test_scaffolding_game_theory import *  # noqa: F401, F403
from tests.unit.test_scaffolding_mapping import *  # noqa: F401, F403
from tests.unit.test_scaffolding_expressions import *  # noqa: F401, F403
from tests.unit.test_scaffolding_composite import *  # noqa: F401, F403
