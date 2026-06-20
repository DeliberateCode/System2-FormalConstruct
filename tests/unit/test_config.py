"""Unit tests for formalconstruct.core.config dataclasses."""

from dataclasses import fields


def test_axle_config_defaults():
    from formalconstruct.core.config import AxleConfig

    c = AxleConfig()
    assert c.lean_environment == "lean-4.29.0"
    assert c.timeout_seconds == 120
    assert c.max_retries == 3
    assert c.initial_delay_s == 1.0
    assert c.backoff_multiplier == 2.0
    assert c.max_delay_s == 10.0


def test_repair_budget_defaults():
    from formalconstruct.core.config import RepairBudget

    b = RepairBudget()
    assert b.max_tactic_attempts_per_goal == 8
    assert b.max_repair_attempts_per_goal == 2
    assert b.max_macro_replans_per_theorem == 3
    assert b.max_schema_rollbacks_per_problem == 1
    assert b.max_total_axle_calls_per_theorem == 40
    assert b.max_wall_clock_seconds_per_theorem == 900


def test_pipeline_config_composes_defaults():
    from formalconstruct.core.config import AxleConfig, PipelineConfig, RepairBudget

    c = PipelineConfig()
    assert isinstance(c.axle, AxleConfig)
    assert isinstance(c.repair, RepairBudget)
    assert c.axle.lean_environment == "lean-4.29.0"
    assert c.repair.max_tactic_attempts_per_goal == 8


def test_pipeline_config_independent_instances():
    """Each PipelineConfig gets its own AxleConfig and RepairBudget."""
    from formalconstruct.core.config import PipelineConfig

    c1 = PipelineConfig()
    c2 = PipelineConfig()
    c1.axle.timeout_seconds = 999
    assert c2.axle.timeout_seconds == 120


def test_pipeline_config_custom_values():
    from formalconstruct.core.config import AxleConfig, PipelineConfig, RepairBudget

    c = PipelineConfig(
        axle=AxleConfig(lean_environment="lean-4.30.0", timeout_seconds=60),
        repair=RepairBudget(max_tactic_attempts_per_goal=4),
    )
    assert c.axle.lean_environment == "lean-4.30.0"
    assert c.axle.timeout_seconds == 60
    assert c.repair.max_tactic_attempts_per_goal == 4
    # Other repair defaults unchanged
    assert c.repair.max_repair_attempts_per_goal == 2


def test_exports_from_core_init():
    from formalconstruct.core import AxleConfig, PipelineConfig, RepairBudget

    assert PipelineConfig is not None
    assert AxleConfig is not None
    assert RepairBudget is not None


def test_all_classes_are_dataclasses():
    import dataclasses

    from formalconstruct.core.config import AxleConfig, PipelineConfig, RepairBudget

    assert dataclasses.is_dataclass(AxleConfig)
    assert dataclasses.is_dataclass(RepairBudget)
    assert dataclasses.is_dataclass(PipelineConfig)


def test_axle_config_field_count():
    from formalconstruct.core.config import AxleConfig

    assert len(fields(AxleConfig)) == 8


def test_repair_budget_field_count():
    from formalconstruct.core.config import RepairBudget

    assert len(fields(RepairBudget)) == 6


def test_pipeline_config_field_count():
    from formalconstruct.core.config import PipelineConfig

    assert len(fields(PipelineConfig)) == 2
