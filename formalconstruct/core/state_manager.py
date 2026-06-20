import datetime
import re

from formalconstruct.schemas.translation import (
    NodeState,
    PipelinePhase,
    SourceMapping,
    TranslationContextSnapshot,
    TranslationNode,
)


class StateManager:
    """DAG-based execution tracking with bidirectional source mappings."""

    def __init__(self, narrative: str) -> None:
        self._narrative = narrative
        self._nodes: dict[str, TranslationNode] = {}
        self._source_mappings: list[SourceMapping] = []
        self._current_phase = PipelinePhase.INFORMAL_RIGOR
        self._problem_spec: dict | None = None
        self._lean_source: str | None = None
        self._verified_source: str | None = None

    def create_node(
        self,
        node_id: str,
        phase: PipelinePhase,
        parent_ids: list[str] | None = None,
        data: dict | None = None,
    ) -> TranslationNode:
        """Create a new DAG node."""
        node = TranslationNode(
            node_id=node_id,
            phase=phase,
            parent_ids=parent_ids or [],
            data=data or {},
        )
        self._nodes[node_id] = node
        for pid in node.parent_ids:
            if pid in self._nodes:
                if node_id not in self._nodes[pid].child_ids:
                    self._nodes[pid].child_ids.append(node_id)
        return node

    def update_node_state(
        self,
        node_id: str,
        state: NodeState,
        error: str | None = None,
    ) -> None:
        """Transition a node state."""
        node = self._nodes[node_id]
        node.state = state
        node.error = error
        if state in (NodeState.COMPLETED, NodeState.FAILED):
            node.completed_at = datetime.datetime.now(datetime.UTC)

    def add_source_mapping(
        self,
        lean_line: int,
        schema_field: str,
        narrative_start: int,
        narrative_end: int,
    ) -> None:
        """Add a bidirectional mapping entry."""
        self._source_mappings.append(
            SourceMapping(
                lean_line=lean_line,
                schema_field=schema_field,
                narrative_start=narrative_start,
                narrative_end=narrative_end,
            )
        )

    def traceback(self, lean_line: int) -> tuple[str, tuple[int, int], str] | None:
        """Given Lean line, trace to (schema_field, narrative_span, narrative_text).

        Returns None if no mapping exists for the given line.
        """
        for mapping in self._source_mappings:
            if mapping.lean_line == lean_line:
                start, end = mapping.narrative_start, mapping.narrative_end
                text = ""
                if start >= 0 and end > start and end <= len(self._narrative):
                    text = self._narrative[start:end]
                return (mapping.schema_field, (start, end), text)
        return None

    def traceback_from_error(
        self,
        lean_errors: list[str],
    ) -> list[tuple[str, str, tuple[int, int], str]]:
        """Parse line numbers from errors, trace each back.

        Returns list of (error, schema_field, narrative_span, narrative_text).
        """
        results: list[tuple[str, str, tuple[int, int], str]] = []
        patterns = [
            re.compile(r"line (\d+)"),   # "line 42"
            re.compile(r":(\d+):\d+"),   # "file.lean:12:4" or "stdin:12:4"
            re.compile(r":(\d+)"),       # "file.lean:12"
        ]
        for error in lean_errors:
            line_num: int | None = None
            for pattern in patterns:
                match = pattern.search(error)
                if match:
                    line_num = int(match.group(1))
                    break
            if line_num is not None:
                tb = self.traceback(line_num)
                if tb:
                    results.append((error, tb[0], tb[1], tb[2]))
        return results

    def rollback(self, to_phase: PipelinePhase) -> None:
        """Roll back nodes after to_phase to ROLLED_BACK."""
        phase_order = {
            PipelinePhase.INFORMAL_RIGOR: 0,
            PipelinePhase.SCAFFOLDING: 1,
            PipelinePhase.PROVING: 2,
        }
        target_order = phase_order[to_phase]
        for node in self._nodes.values():
            if (
                phase_order[node.phase] > target_order
                and node.state != NodeState.ROLLED_BACK
            ):
                node.state = NodeState.ROLLED_BACK
                node.completed_at = None
        self._current_phase = to_phase

    def snapshot(self) -> TranslationContextSnapshot:
        """Serialize full state."""
        return TranslationContextSnapshot(
            narrative=self._narrative,
            nodes={k: v.model_copy() for k, v in self._nodes.items()},
            source_mappings=[m.model_copy() for m in self._source_mappings],
            current_phase=self._current_phase,
            problem_spec=self._problem_spec,
            lean_source=self._lean_source,
            verified_source=self._verified_source,
        )

    @property
    def current_phase(self) -> PipelinePhase:
        return self._current_phase

    @current_phase.setter
    def current_phase(self, phase: PipelinePhase) -> None:
        self._current_phase = phase
