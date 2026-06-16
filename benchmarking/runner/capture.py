"""Parse and structure agent output from claude -p JSON format."""

from __future__ import annotations

import json
import re


def parse_transcript(raw_json: str) -> dict:
    """Parse the JSON output from `claude -p --output-format json`.

    Returns a structured summary of the agent's actions.
    """
    messages: list[dict] = []

    for line in raw_json.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
            messages.append(msg)
        except json.JSONDecodeError:
            continue

    tool_calls: list[dict] = []
    final_text = ""
    cost_usd = 0.0

    for msg in messages:
        if msg.get("type") == "assistant":
            content = msg.get("content", [])
            for block in content if isinstance(content, list) else []:
                if block.get("type") == "tool_use":
                    tool_calls.append({
                        "tool": block.get("name", ""),
                        "input_preview": str(block.get("input", ""))[:200],
                    })
                elif block.get("type") == "text":
                    final_text = block.get("text", "")

        if "usage" in msg:
            usage = msg["usage"]
            input_tokens = usage.get("input_tokens", 0)
            output_tokens = usage.get("output_tokens", 0)
            cost_usd += (input_tokens * 15 + output_tokens * 75) / 1_000_000

    return {
        "message_count": len(messages),
        "tool_call_count": len(tool_calls),
        "tool_calls": tool_calls,
        "final_text": final_text[:2000],
        "estimated_cost_usd": round(cost_usd, 4),
    }


def extract_failure_classification(text: str) -> str | None:
    """Extract failure classification from agent's final output text."""
    classifications = [
        "schema gap",
        "Mathlib gap",
        "proof search exhaustion",
    ]
    text_lower = text.lower()
    for classification in classifications:
        if classification.lower() in text_lower:
            return classification.replace(" ", "_")
    return None


def extract_verify_result(text: str) -> bool | None:
    """Check if the agent reported verification success.

    Handles both raw text and JSON transcript format from `claude -p`.
    """
    # Try to extract result text from JSON transcript
    search_text = text
    try:
        parsed = json.loads(text)
        if parsed.get("subtype") == "success" and "result" in parsed:
            search_text = parsed["result"]
        elif parsed.get("subtype") in ("error_max_turns", "error"):
            return False
    except (json.JSONDecodeError, TypeError):
        pass

    # An unambiguous AXLE success signal wins outright.
    if re.search(r"verify_proof.*okay.*true", search_text, re.IGNORECASE):
        return True
    # Check explicit failure phrasing before the looser positive keywords, so a
    # "could not verify" explanation is not misread as success on the bare word
    # "verified".
    if re.search(r"verification failed|could not verify", search_text, re.IGNORECASE):
        return False
    if re.search(r"\bverified\b|proof complete|verification succeeded|proof is.*verified", search_text, re.IGNORECASE):
        return True
    if re.search(r"sorry.?count.*0|zero errors|zero warnings", search_text, re.IGNORECASE):
        return True
    return None


def extract_failure_from_transcript(text: str) -> str | None:
    """Extract failure classification from JSON transcript."""
    try:
        parsed = json.loads(text)
        result_text = parsed.get("result", "")
        return extract_failure_classification(result_text)
    except (json.JSONDecodeError, TypeError):
        return extract_failure_classification(text)
