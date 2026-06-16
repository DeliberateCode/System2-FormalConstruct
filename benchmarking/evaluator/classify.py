"""Classify benchmark outcomes into the failure taxonomy."""

from __future__ import annotations

import re
from enum import Enum

from benchmarking.evaluator.verify import VerificationResult
from benchmarking.runner.capture import extract_failure_from_transcript, extract_verify_result
from benchmarking.runner.invoke import RunResult


class Outcome(str, Enum):
    VERIFIED = "verified"
    DOMAIN_MISMATCH = "domain_mismatch"
    SCHEMA_GAP = "schema_gap"
    SCAFFOLDING_FAILURE = "scaffolding_failure"
    PROOF_SEARCH_EXHAUSTION = "proof_search_exhaustion"
    MATHLIB_GAP = "mathlib_gap"
    TIMEOUT = "timeout"
    AGENT_ERROR = "agent_error"


def classify(
    run_result: RunResult,
    verification: VerificationResult | None = None,
) -> Outcome:
    """Classify a benchmark outcome based on run result and optional verification.

    Priority order:
    1. If verification confirms proof → VERIFIED
    2. If timeout → TIMEOUT
    3. If agent crashed → AGENT_ERROR
    4. If agent reported failure classification → use it
    5. If no lean source produced → classify from transcript
    6. If sorry remains → PROOF_SEARCH_EXHAUSTION
    """
    if run_result.exit_code == -1:
        return Outcome.TIMEOUT

    if run_result.exit_code == -2:
        return Outcome.AGENT_ERROR

    if verification and verification.verified:
        return Outcome.VERIFIED

    transcript = run_result.agent_transcript

    # Check agent self-reported verification first (handles JSON transcript)
    agent_verified = extract_verify_result(transcript)

    # Strict AXLE success signal: an explicit `verify_proof okay: true`. Distinct
    # from the loose keyword match in extract_verify_result (which fires on a bare
    # "verified", e.g. in "cannot be verified"). Only this strong signal is
    # allowed to override a keyword-based failure label.
    strict_okay = bool(re.search(r"okay['\"\s:`*]+true", transcript, re.IGNORECASE))

    if not run_result.success and run_result.exit_code != 0:
        return Outcome.AGENT_ERROR

    # If we have lean source and agent self-reports verified, trust it
    if run_result.lean_source and agent_verified is True:
        if not re.search(r"\bsorry\b", run_result.lean_source):
            return Outcome.VERIFIED

    agent_classification = extract_failure_from_transcript(transcript)
    if agent_classification and not strict_okay:
        # An agent that merely *mentions* "schema gap" while reporting
        # `verify_proof okay: true` (worked around the gap) is not a failure.
        mapping = {
            "schema_gap": Outcome.SCHEMA_GAP,
            "mathlib_gap": Outcome.MATHLIB_GAP,
            "proof_search_exhaustion": Outcome.PROOF_SEARCH_EXHAUSTION,
        }
        return mapping.get(agent_classification, Outcome.AGENT_ERROR)

    # A confirmed `verify_proof okay: true` with no remaining `sorry` is verified,
    # even if the proof artifact could not be harvested into lean_source.
    if strict_okay and "sorry" not in (run_result.lean_source or ""):
        return Outcome.VERIFIED

    if run_result.lean_source is None:
        # Try to classify from the JSON result text
        try:
            import json
            parsed = json.loads(transcript)
            result_text = parsed.get("result", "").lower()
        except (json.JSONDecodeError, TypeError):
            result_text = transcript.lower()

        if "domain" in result_text and "not supported" in result_text:
            return Outcome.DOMAIN_MISMATCH
        if "scaffold" in result_text and "error" in result_text:
            return Outcome.SCAFFOLDING_FAILURE
        return Outcome.AGENT_ERROR

    if "sorry" in (run_result.lean_source or ""):
        return Outcome.PROOF_SEARCH_EXHAUSTION

    if agent_verified is True:
        return Outcome.VERIFIED

    return Outcome.PROOF_SEARCH_EXHAUSTION
