"""Response parsing for AXLE MCP tool results.

Converts raw JSON-RPC response dicts into typed Pydantic models.
Handles missing keys gracefully with empty defaults.
"""

from __future__ import annotations

from formalconstruct.schemas.axle_responses import (
    AxleCheckResult,
    AxleExtractDeclsResult,
    AxleHave2LemmaResult,
    AxleNormalizeResult,
    AxleRepairResult,
    AxleTheorem2SorryResult,
    AxleVerifyResult,
    MessageSet,
    RepairStats,
    RepairTimings,
)


class AxleResponseParser:
    """Parses raw MCP JSON-RPC responses into typed models."""

    @staticmethod
    def _parse_message_set(raw: dict) -> MessageSet:
        return MessageSet(
            errors=raw.get("errors", []),
            warnings=raw.get("warnings", []),
            infos=raw.get("infos", []),
        )

    @staticmethod
    def parse_check(raw: dict) -> AxleCheckResult:
        return AxleCheckResult(
            lean_messages=AxleResponseParser._parse_message_set(
                raw.get("lean_messages", {})
            ),
            tool_messages=AxleResponseParser._parse_message_set(
                raw.get("tool_messages", {})
            ),
        )

    @staticmethod
    def parse_verify(raw: dict) -> AxleVerifyResult:
        lean_msgs = AxleResponseParser._parse_message_set(
            raw.get("lean_messages", {})
        )
        tool_msgs = AxleResponseParser._parse_message_set(
            raw.get("tool_messages", {})
        )
        okay = raw.get("okay") is True
        failed_declarations = raw.get("failed_declarations") or []
        if "verified" in raw:
            # Backward compatibility: honor an explicit boolean `verified` flag.
            verified = raw["verified"] is True
        elif "okay" in raw:
            # AXLE's verify_proof contract: success is reported via `okay`,
            # with an empty `failed_declarations` list and no errors. The
            # parser previously only read a `verified` key (which AXLE never
            # sends), so it reported False on every real success.
            verified = (
                okay
                and not failed_declarations
                and not lean_msgs.errors
                and not tool_msgs.errors
            )
        else:
            # Fail-closed: neither success key present.
            verified = False
        return AxleVerifyResult(
            lean_messages=lean_msgs,
            tool_messages=tool_msgs,
            verified=verified,
            okay=okay,
            failed_declarations=list(failed_declarations),
        )

    @staticmethod
    def parse_repair(raw: dict) -> AxleRepairResult:
        raw_stats = raw.get("repair_stats", {})
        raw_timings = raw.get("timings", {})
        return AxleRepairResult(
            okay=raw.get("okay", False),
            content=raw.get("content", ""),
            repair_stats=RepairStats(
                remove_extraneous_tactics=raw_stats.get(
                    "remove_extraneous_tactics", 0
                ),
                replace_unsafe_tactics=raw_stats.get(
                    "replace_unsafe_tactics", 0
                ),
                apply_terminal_tactics=raw_stats.get(
                    "apply_terminal_tactics", 0
                ),
            ),
            timings=RepairTimings(
                total_ms=raw_timings.get("total_ms", 0),
                repair_ms=raw_timings.get("repair_ms", 0),
            ),
            lean_messages=AxleResponseParser._parse_message_set(
                raw.get("lean_messages", {})
            ),
            tool_messages=AxleResponseParser._parse_message_set(
                raw.get("tool_messages", {})
            ),
        )

    @staticmethod
    def parse_normalize(raw: dict) -> AxleNormalizeResult:
        return AxleNormalizeResult(
            content=raw.get("content", ""),
            lean_messages=AxleResponseParser._parse_message_set(
                raw.get("lean_messages", {})
            ),
            tool_messages=AxleResponseParser._parse_message_set(
                raw.get("tool_messages", {})
            ),
        )

    @staticmethod
    def parse_extract_decls(raw: dict) -> AxleExtractDeclsResult:
        return AxleExtractDeclsResult(
            declarations=raw.get("declarations", []),
            lean_messages=AxleResponseParser._parse_message_set(
                raw.get("lean_messages", {})
            ),
            tool_messages=AxleResponseParser._parse_message_set(
                raw.get("tool_messages", {})
            ),
        )

    @staticmethod
    def parse_theorem2sorry(raw: dict) -> AxleTheorem2SorryResult:
        return AxleTheorem2SorryResult(
            content=raw.get("content", ""),
            lean_messages=AxleResponseParser._parse_message_set(
                raw.get("lean_messages", {})
            ),
            tool_messages=AxleResponseParser._parse_message_set(
                raw.get("tool_messages", {})
            ),
        )

    @staticmethod
    def parse_have2lemma(raw: dict) -> AxleHave2LemmaResult:
        return AxleHave2LemmaResult(
            content=raw.get("content", ""),
            lemmas=raw.get("lemmas", []),
            lean_messages=AxleResponseParser._parse_message_set(
                raw.get("lean_messages", {})
            ),
            tool_messages=AxleResponseParser._parse_message_set(
                raw.get("tool_messages", {})
            ),
        )
