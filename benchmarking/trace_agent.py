#!/usr/bin/env python3
"""Trace formalize agent execution to analyze turn consumption."""

import json
import subprocess

def trace_agent(narrative: str, max_turns: int = 20):
    """Run formalize agent and trace each turn."""
    cmd = [
        "claude", "-p",
        "--agent", "formalize",
        "--output-format", "json",
        "--max-turns", str(max_turns),
        "--dangerously-skip-permissions",
        f"Narrative: {narrative}"
    ]

    print(f"Running: {narrative[:80]}...\n")

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    turn_count = 0
    tool_sequence = []

    for line in proc.stdout:
        line = line.strip()
        if not line:
            continue

        try:
            msg = json.loads(line)
            msg_type = msg.get('type')

            if msg_type == 'assistant':
                turn_count += 1
                content = msg.get('content', [])

                # Extract text and tool calls
                text_blocks = []
                tools = []
                for block in content:
                    if block.get('type') == 'text':
                        text = block.get('text', '')
                        text_blocks.append(text[:100])
                    elif block.get('type') == 'tool_use':
                        tool_name = block.get('name', 'unknown')
                        tools.append(tool_name)
                        tool_sequence.append(tool_name)

                print(f"Turn {turn_count}:")
                if text_blocks:
                    print(f"  Text: {text_blocks[0][:80]}...")
                if tools:
                    print(f"  Tools: {', '.join(tools)}")

            elif msg_type == 'result':
                print("\n=== Final Result ===")
                print(f"Total turns: {msg.get('num_turns')}")
                print(f"Duration: {msg.get('duration_ms')/1000:.1f}s")
                print(f"Subtype: {msg.get('subtype')}")
                print(f"Stop reason: {msg.get('stop_reason')}")

        except json.JSONDecodeError:
            continue

    proc.wait()

    print("\n=== Tool Call Summary ===")
    from collections import Counter
    for tool, count in Counter(tool_sequence).most_common():
        print(f"  {tool}: {count}")

if __name__ == "__main__":
    narrative = "Find the maximum value of xy given x+y=10."
    trace_agent(narrative, max_turns=20)
