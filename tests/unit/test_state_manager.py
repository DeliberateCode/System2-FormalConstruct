"""Unit tests for formalconstruct.core.state_manager.StateManager."""

import json

from formalconstruct.core.state_manager import StateManager
from formalconstruct.schemas.translation import NodeState, PipelinePhase


# ---------------------------------------------------------------------------
# create_node
# ---------------------------------------------------------------------------


class TestCreateNode:

    def test_new_node_is_pending(self):
        sm = StateManager("narrative")
        node = sm.create_node("n1", PipelinePhase.INFORMAL_RIGOR)
        assert node.state == NodeState.PENDING

    def test_parent_child_links(self):
        sm = StateManager("narrative")
        parent = sm.create_node("p1", PipelinePhase.INFORMAL_RIGOR)
        child = sm.create_node("c1", PipelinePhase.SCAFFOLDING, parent_ids=["p1"])
        assert "c1" in parent.child_ids
        assert "p1" in child.parent_ids

    def test_multiple_children(self):
        sm = StateManager("narrative")
        sm.create_node("p1", PipelinePhase.INFORMAL_RIGOR)
        sm.create_node("c1", PipelinePhase.SCAFFOLDING, parent_ids=["p1"])
        sm.create_node("c2", PipelinePhase.SCAFFOLDING, parent_ids=["p1"])
        snapshot = sm.snapshot()
        parent = snapshot.nodes["p1"]
        assert set(parent.child_ids) == {"c1", "c2"}

    def test_data_dict_stored(self):
        sm = StateManager("narrative")
        node = sm.create_node("n1", PipelinePhase.INFORMAL_RIGOR, data={"key": "val"})
        assert node.data == {"key": "val"}


# ---------------------------------------------------------------------------
# update_node_state
# ---------------------------------------------------------------------------


class TestUpdateNodeState:

    def test_pending_to_in_progress(self):
        sm = StateManager("narrative")
        sm.create_node("n1", PipelinePhase.INFORMAL_RIGOR)
        sm.update_node_state("n1", NodeState.IN_PROGRESS)
        snap = sm.snapshot()
        assert snap.nodes["n1"].state == NodeState.IN_PROGRESS

    def test_in_progress_to_completed_sets_completed_at(self):
        sm = StateManager("narrative")
        sm.create_node("n1", PipelinePhase.INFORMAL_RIGOR)
        sm.update_node_state("n1", NodeState.IN_PROGRESS)
        sm.update_node_state("n1", NodeState.COMPLETED)
        snap = sm.snapshot()
        assert snap.nodes["n1"].state == NodeState.COMPLETED
        assert snap.nodes["n1"].completed_at is not None

    def test_failed_sets_completed_at_and_error(self):
        sm = StateManager("narrative")
        sm.create_node("n1", PipelinePhase.INFORMAL_RIGOR)
        sm.update_node_state("n1", NodeState.FAILED, error="boom")
        snap = sm.snapshot()
        node = snap.nodes["n1"]
        assert node.state == NodeState.FAILED
        assert node.completed_at is not None
        assert node.error == "boom"


# ---------------------------------------------------------------------------
# Source mapping + traceback
# ---------------------------------------------------------------------------


class TestTraceback:

    def test_round_trip_known_line(self):
        sm = StateManager("narrative text here")
        sm.add_source_mapping(
            lean_line=10,
            schema_field="functions[0].properties[0]",
            narrative_start=0,
            narrative_end=9,
        )
        result = sm.traceback(10)
        assert result is not None
        schema_field, (start, end), text = result
        assert schema_field == "functions[0].properties[0]"
        assert start == 0
        assert end == 9
        assert text == "narrative"[:9]

    def test_unknown_line_returns_none(self):
        sm = StateManager("narrative")
        sm.add_source_mapping(lean_line=10, schema_field="f", narrative_start=0, narrative_end=5)
        assert sm.traceback(999) is None

    def test_traceback_from_error_parses_line(self):
        sm = StateManager("narrative")
        sm.add_source_mapping(lean_line=5, schema_field="obj", narrative_start=10, narrative_end=20)
        results = sm.traceback_from_error(["error at line 5: type mismatch"])
        assert len(results) == 1
        error_msg, field, span, text = results[0]
        assert "line 5" in error_msg
        assert field == "obj"
        assert span == (10, 20)

    def test_traceback_from_error_no_line_number(self):
        sm = StateManager("narrative")
        sm.add_source_mapping(lean_line=5, schema_field="obj", narrative_start=0, narrative_end=5)
        results = sm.traceback_from_error(["unknown error without line info"])
        assert results == []

    def test_traceback_from_error_unmapped_line(self):
        sm = StateManager("narrative")
        sm.add_source_mapping(lean_line=5, schema_field="obj", narrative_start=0, narrative_end=5)
        results = sm.traceback_from_error(["error at line 99"])
        assert results == []

    def test_traceback_from_error_lean_file_colon_format(self):
        """Lean diagnostic: file.lean:12:4: error message."""
        sm = StateManager("narrative text here")
        sm.add_source_mapping(
            lean_line=12, schema_field="obj", narrative_start=0, narrative_end=9
        )
        results = sm.traceback_from_error(["file.lean:12:4: type mismatch"])
        assert len(results) == 1
        error_msg, field, span, text = results[0]
        assert field == "obj"
        assert span == (0, 9)

    def test_traceback_from_error_stdin_colon_format(self):
        """Lean diagnostic: stdin:12:4: error message."""
        sm = StateManager("narrative text here")
        sm.add_source_mapping(
            lean_line=12, schema_field="obj", narrative_start=0, narrative_end=9
        )
        results = sm.traceback_from_error(["stdin:12:4: unknown identifier"])
        assert len(results) == 1
        error_msg, field, span, _text = results[0]
        assert field == "obj"
        assert span == (0, 9)

    def test_traceback_from_error_colon_line_only(self):
        """Lean diagnostic with line but no column: file.lean:12."""
        sm = StateManager("narrative text here")
        sm.add_source_mapping(
            lean_line=12, schema_field="obj", narrative_start=0, narrative_end=9
        )
        results = sm.traceback_from_error(["file.lean:12: some warning"])
        assert len(results) == 1
        error_msg, field, span, _text = results[0]
        assert field == "obj"

    def test_traceback_from_error_line_pattern_preferred_over_colon(self):
        """When both 'line N' and ':N:' appear, first match wins (line N)."""
        sm = StateManager("narrative text here")
        sm.add_source_mapping(
            lean_line=5, schema_field="obj_a", narrative_start=0, narrative_end=5
        )
        sm.add_source_mapping(
            lean_line=12, schema_field="obj_b", narrative_start=5, narrative_end=9
        )
        results = sm.traceback_from_error(["file.lean:12:4: error at line 5"])
        assert len(results) == 1
        _, field, _, _ = results[0]
        assert field == "obj_a"


# ---------------------------------------------------------------------------
# Traceback regex contract tests
# ---------------------------------------------------------------------------


class TestTracebackFormats:
    """Contract tests for traceback_from_error regex patterns.

    Verifies that the three supported error format patterns are correctly
    parsed: stdin/file colon format (Lean diagnostics), traditional 'line N'
    format, and the priority rule when both patterns appear.
    """

    def test_lean_colon_format_extracted(self):
        """stdin:15:4: type mismatch -- colon format extracts line 15."""
        sm = StateManager("some narrative text")
        sm.add_source_mapping(
            lean_line=15, schema_field="functions[0]", narrative_start=0, narrative_end=9
        )
        results = sm.traceback_from_error(["stdin:15:4: type mismatch"])
        assert len(results) == 1
        error_msg, field, span, text = results[0]
        assert field == "functions[0]"
        assert span == (0, 9)
        assert "type mismatch" in error_msg

    def test_file_colon_format_extracted(self):
        """MyFile.lean:7:0: unknown identifier -- colon format extracts line 7."""
        sm = StateManager("narrative text here")
        sm.add_source_mapping(
            lean_line=7, schema_field="variables[0]", narrative_start=0, narrative_end=9
        )
        results = sm.traceback_from_error(["MyFile.lean:7:0: unknown identifier"])
        assert len(results) == 1
        error_msg, field, span, text = results[0]
        assert field == "variables[0]"
        assert span == (0, 9)
        assert "unknown identifier" in error_msg

    def test_traditional_line_format_still_works(self):
        """error at line 10 -- traditional format extracts line 10 (regression guard)."""
        sm = StateManager("narrative text here")
        sm.add_source_mapping(
            lean_line=10, schema_field="objective", narrative_start=0, narrative_end=9
        )
        results = sm.traceback_from_error(["error at line 10"])
        assert len(results) == 1
        error_msg, field, span, text = results[0]
        assert field == "objective"
        assert span == (0, 9)
        assert "line 10" in error_msg

    def test_line_format_preferred_over_colon(self):
        """Error containing both 'line 5' and ':10:0:' -- 'line 5' wins."""
        sm = StateManager("narrative text here")
        sm.add_source_mapping(
            lean_line=5, schema_field="spaces[0]", narrative_start=0, narrative_end=5
        )
        sm.add_source_mapping(
            lean_line=10, schema_field="functions[1]", narrative_start=5, narrative_end=9
        )
        results = sm.traceback_from_error(["file.lean:10:0: error at line 5"])
        assert len(results) == 1
        _, field, _, _ = results[0]
        assert field == "spaces[0]"


# ---------------------------------------------------------------------------
# Rollback
# ---------------------------------------------------------------------------


class TestRollback:

    def test_rollback_to_informal_rigor(self):
        sm = StateManager("narrative")
        sm.create_node("ir", PipelinePhase.INFORMAL_RIGOR)
        sm.update_node_state("ir", NodeState.COMPLETED)
        sm.create_node("sc", PipelinePhase.SCAFFOLDING)
        sm.update_node_state("sc", NodeState.COMPLETED)
        sm.create_node("pr", PipelinePhase.PROVING)
        sm.update_node_state("pr", NodeState.IN_PROGRESS)

        sm.rollback(PipelinePhase.INFORMAL_RIGOR)

        snap = sm.snapshot()
        assert snap.nodes["ir"].state == NodeState.COMPLETED
        assert snap.nodes["sc"].state == NodeState.ROLLED_BACK
        assert snap.nodes["pr"].state == NodeState.ROLLED_BACK
        assert snap.current_phase == PipelinePhase.INFORMAL_RIGOR

    def test_rollback_to_scaffolding(self):
        sm = StateManager("narrative")
        sm.create_node("ir", PipelinePhase.INFORMAL_RIGOR)
        sm.update_node_state("ir", NodeState.COMPLETED)
        sm.create_node("sc", PipelinePhase.SCAFFOLDING)
        sm.update_node_state("sc", NodeState.COMPLETED)
        sm.create_node("pr", PipelinePhase.PROVING)
        sm.update_node_state("pr", NodeState.IN_PROGRESS)

        sm.rollback(PipelinePhase.SCAFFOLDING)

        snap = sm.snapshot()
        assert snap.nodes["ir"].state == NodeState.COMPLETED
        assert snap.nodes["sc"].state == NodeState.COMPLETED
        assert snap.nodes["pr"].state == NodeState.ROLLED_BACK
        assert snap.current_phase == PipelinePhase.SCAFFOLDING


# ---------------------------------------------------------------------------
# Snapshot serialization
# ---------------------------------------------------------------------------


class TestSnapshot:

    def test_json_round_trip(self):
        sm = StateManager("narrative")
        sm.create_node("n1", PipelinePhase.INFORMAL_RIGOR, data={"k": "v"})
        sm.add_source_mapping(lean_line=1, schema_field="f", narrative_start=0, narrative_end=5)
        snap = sm.snapshot()
        json_str = snap.model_dump_json()
        parsed = json.loads(json_str)
        assert parsed["narrative"] == "narrative"
        assert "n1" in parsed["nodes"]
        assert len(parsed["source_mappings"]) == 1

    def test_snapshot_copies_nodes(self):
        sm = StateManager("narrative")
        sm.create_node("n1", PipelinePhase.INFORMAL_RIGOR)
        snap = sm.snapshot()
        # Mutating the snapshot should not affect the state manager
        snap.nodes["n1"].state = NodeState.FAILED
        sm_snap2 = sm.snapshot()
        assert sm_snap2.nodes["n1"].state == NodeState.PENDING


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:

    def test_empty_dag_snapshot(self):
        sm = StateManager("empty")
        snap = sm.snapshot()
        assert snap.nodes == {}
        assert snap.source_mappings == []
        assert snap.narrative == "empty"

    def test_empty_dag_traceback(self):
        sm = StateManager("empty")
        assert sm.traceback(1) is None

    def test_current_phase_property(self):
        sm = StateManager("narrative")
        assert sm.current_phase == PipelinePhase.INFORMAL_RIGOR
        sm.current_phase = PipelinePhase.SCAFFOLDING
        assert sm.current_phase == PipelinePhase.SCAFFOLDING
