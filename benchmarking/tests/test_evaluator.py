"""Unit tests for the evaluator classification logic."""

from __future__ import annotations

import json

from benchmarking.evaluator.classify import Outcome, classify
from benchmarking.evaluator.verify import VerificationResult, check_sorry_free
from benchmarking.runner.invoke import RunResult, _extract_lean_from_transcript


class TestCheckSorryFree:
    def test_clean_source(self):
        src = "theorem t : True := trivial"
        assert check_sorry_free(src) is True

    def test_sorry_present(self):
        src = "theorem t : True := by sorry"
        assert check_sorry_free(src) is False

    def test_sorry_in_comment_still_detected(self):
        # We do simple word-boundary matching, so sorry in a comment counts.
        # This is conservative — false negatives are worse than false positives.
        src = "-- sorry\ntheorem t : True := trivial"
        assert check_sorry_free(src) is False

    def test_sorry_substring_not_matched(self):
        src = "theorem sorry_free : True := trivial"
        # "sorry_free" contains "sorry" as a substring but not word boundary
        assert check_sorry_free(src) is True


class TestClassify:
    def test_verified_via_verification_result(self):
        run = RunResult(
            problem_id="test_01",
            success=True,
            exit_code=0,
            duration_seconds=10.0,
            lean_source="theorem t := by ring",
        )
        verification = VerificationResult(
            problem_id="test_01",
            verified=True,
            sorry_free=True,
            compiles=True,
        )
        assert classify(run, verification) == Outcome.VERIFIED

    def test_timeout(self):
        run = RunResult(
            problem_id="test_02",
            success=False,
            exit_code=-1,
            duration_seconds=600.0,
            error_message="Timeout exceeded",
        )
        assert classify(run) == Outcome.TIMEOUT

    def test_cli_not_found(self):
        run = RunResult(
            problem_id="test_03",
            success=False,
            exit_code=-2,
            duration_seconds=0.1,
            error_message="claude CLI not found",
        )
        assert classify(run) == Outcome.AGENT_ERROR

    def test_agent_reports_schema_gap(self):
        run = RunResult(
            problem_id="test_04",
            success=False,
            exit_code=0,
            duration_seconds=30.0,
            agent_transcript="Failure classification: schema gap. The problem requires...",
        )
        assert classify(run) == Outcome.SCHEMA_GAP

    def test_agent_reports_proof_search_exhaustion(self):
        run = RunResult(
            problem_id="test_05",
            success=False,
            exit_code=0,
            duration_seconds=120.0,
            agent_transcript="Failure classification: proof search exhaustion. Budget consumed.",
        )
        assert classify(run) == Outcome.PROOF_SEARCH_EXHAUSTION

    def test_sorry_in_output(self):
        run = RunResult(
            problem_id="test_06",
            success=True,
            exit_code=0,
            duration_seconds=45.0,
            lean_source="theorem t : True := by sorry",
        )
        assert classify(run) == Outcome.PROOF_SEARCH_EXHAUSTION

    def test_no_lean_source_scaffolding_error(self):
        run = RunResult(
            problem_id="test_07",
            success=False,
            exit_code=0,
            duration_seconds=20.0,
            lean_source=None,
            agent_transcript="The scaffold produced an error and could not compile.",
        )
        assert classify(run) == Outcome.SCAFFOLDING_FAILURE

    def test_agent_self_reports_verified(self):
        run = RunResult(
            problem_id="test_08",
            success=True,
            exit_code=0,
            duration_seconds=90.0,
            lean_source="theorem t : True := trivial",
            agent_transcript="verify_proof returned okay: true. Proof complete.",
        )
        assert classify(run) == Outcome.VERIFIED

    def test_json_transcript_verified(self):
        import json
        transcript = json.dumps({
            "type": "result",
            "subtype": "success",
            "result": "The proof is **verified** -- sorry count: 0, zero errors.",
        })
        run = RunResult(
            problem_id="test_09",
            success=True,
            exit_code=0,
            duration_seconds=90.0,
            lean_source="theorem t : True := trivial",
            agent_transcript=transcript,
        )
        assert classify(run) == Outcome.VERIFIED

    def test_json_transcript_max_turns(self):
        transcript = json.dumps({
            "type": "result",
            "subtype": "error_max_turns",
            "result": "Agent ran out of turns.",
        })
        run = RunResult(
            problem_id="test_10",
            success=False,
            exit_code=1,
            duration_seconds=300.0,
            lean_source=None,
            agent_transcript=transcript,
        )
        assert classify(run) == Outcome.AGENT_ERROR


class TestClassifyVerifiedBeatsGapKeyword:
    """`verify_proof okay: true` must win over an incidental "schema gap" mention."""

    def test_okay_true_overrides_schema_gap_with_source(self):
        transcript = json.dumps({"subtype": "success", "result":
            "Worked around a schema gap. `verify_proof` returned okay: true, no sorry."})
        run = RunResult(problem_id="p", success=True, exit_code=0, duration_seconds=10.0,
                        lean_source="theorem t : True := trivial", agent_transcript=transcript)
        assert classify(run) == Outcome.VERIFIED

    def test_okay_true_overrides_schema_gap_without_harvested_source(self):
        transcript = json.dumps({"subtype": "success", "result":
            "This is a schema gap, but verify_proof returned okay: true (no sorry). Wrote /tmp/p.lean."})
        run = RunResult(problem_id="p", success=False, exit_code=0, duration_seconds=10.0,
                        lean_source=None, agent_transcript=transcript)
        assert classify(run) == Outcome.VERIFIED

    def test_schema_gap_without_okay_true_stays_failure(self):
        # Mirrors 82245: prose contains "verified" only inside "cannot be ...-and-verified".
        transcript = json.dumps({"subtype": "success", "result":
            "Classified failure: schema gap. This cannot be faithfully formalized-and-verified."})
        run = RunResult(problem_id="p", success=False, exit_code=0, duration_seconds=10.0,
                        lean_source=None, agent_transcript=transcript)
        assert classify(run) == Outcome.SCHEMA_GAP


class TestExtractLeanFromTranscript:
    """Harvest the proof from any mentioned .lean path, not just workdir/fenced blocks."""

    def test_reads_backtick_quoted_path(self, tmp_path):
        f = tmp_path / "proof.lean"
        f.write_text("theorem t : True := trivial\n")
        transcript = json.dumps({"result": f"The verified Lean source is at `{f}`."})
        src, _ = _extract_lean_from_transcript(transcript)
        assert src == "theorem t : True := trivial\n"

    def test_reads_bare_path(self, tmp_path):
        f = tmp_path / "p2.lean"
        f.write_text("theorem u : True := trivial\n")
        transcript = json.dumps({"result": f"Wrote {f} and verified it."})
        src, _ = _extract_lean_from_transcript(transcript)
        assert src == "theorem u : True := trivial\n"

    def test_fenced_block_fallback(self):
        transcript = json.dumps({"result": "Proof:\n```lean\ntheorem v : True := trivial\n```"})
        src, _ = _extract_lean_from_transcript(transcript)
        assert "theorem v" in src

    def test_missing_path_and_no_block_returns_none(self):
        transcript = json.dumps({"result": "Wrote /tmp/does_not_exist_98765.lean (now gone)."})
        src, _ = _extract_lean_from_transcript(transcript)
        assert src is None
