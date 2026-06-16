"""CLI entry points for FormalConstruct.

Designed to be called from Claude Code or any shell environment.
Run with: python -m formalconstruct <command> [args]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> None:
    from formalconstruct import __version__

    parser = argparse.ArgumentParser(
        prog="formalconstruct",
        description="FormalConstruct: narrative-to-Lean formalization toolkit",
    )
    parser.add_argument(
        "--version", action="version", version=f"formalconstruct {__version__}",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # --- validate ---
    p_validate = sub.add_parser(
        "validate",
        help="Validate a ProblemSpec JSON file against the Pydantic schema.",
    )
    p_validate.add_argument("spec_file", help="Path to ProblemSpec JSON file")

    # --- scaffold ---
    p_scaffold = sub.add_parser(
        "scaffold",
        help="Generate Lean 4 source from a validated ProblemSpec JSON.",
    )
    p_scaffold.add_argument("spec_file", help="Path to ProblemSpec JSON file")
    p_scaffold.add_argument(
        "-o", "--out", default=None,
        help="Output file for Lean source (default: stdout)",
    )
    p_scaffold.add_argument(
        "--narrative", default="",
        help="Original narrative text for source mapping (optional)",
    )

    # --- schema ---
    sub.add_parser(
        "schema",
        help="Print the ProblemSpec JSON schema.",
    )

    # --- list-domains ---
    sub.add_parser(
        "list-domains",
        help="List available domain mappers.",
    )

    # --- parse-axle ---
    p_parse = sub.add_parser(
        "parse-axle",
        help="Parse an AXLE JSON response into typed fields.",
    )
    p_parse.add_argument("tool", choices=[
        "check", "verify", "repair", "normalize",
        "extract_decls", "theorem2sorry", "have2lemma",
    ])
    p_parse.add_argument(
        "response_file", nargs="?", default=None,
        help="Path to AXLE response JSON (default: stdin)",
    )

    args = parser.parse_args()

    if args.command == "validate":
        cmd_validate(args)
    elif args.command == "scaffold":
        cmd_scaffold(args)
    elif args.command == "schema":
        cmd_schema(args)
    elif args.command == "list-domains":
        cmd_list_domains(args)
    elif args.command == "parse-axle":
        cmd_parse_axle(args)


def cmd_validate(args: argparse.Namespace) -> None:
    from pydantic import ValidationError
    from formalconstruct.schemas.problem_spec import ProblemSpec

    path = Path(args.spec_file)
    if not path.exists():
        print(f"Error: file not found: {args.spec_file}", file=sys.stderr)
        sys.exit(1)

    raw = path.read_text()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"Error: invalid JSON in {args.spec_file}: {e.msg} (line {e.lineno})", file=sys.stderr)
        sys.exit(1)

    try:
        spec = ProblemSpec.model_validate(data)
    except ValidationError as e:
        print(f"INVALID: {e}", file=sys.stderr)
        sys.exit(1)

    print(json.dumps({
        "valid": True,
        "problem_domain": spec.problem_domain.value,
        "spaces": len(spec.spaces),
        "variables": len(spec.variables),
        "functions": len(spec.functions),
        "objective_direction": spec.objective.direction.value,
        "composite": bool(spec.domain_components),
    }, indent=2))


def cmd_scaffold(args: argparse.Namespace) -> None:
    from pydantic import ValidationError
    from formalconstruct.schemas.problem_spec import ProblemSpec
    from formalconstruct.agents.lean_scaffolding import LeanScaffoldingAgent
    from formalconstruct.domains import create_default_registry

    path = Path(args.spec_file)
    if not path.exists():
        print(f"Error: file not found: {args.spec_file}", file=sys.stderr)
        sys.exit(1)

    raw = path.read_text()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"Error: invalid JSON in {args.spec_file}: {e.msg} (line {e.lineno})", file=sys.stderr)
        sys.exit(1)

    try:
        spec = ProblemSpec.model_validate(data)
    except ValidationError as e:
        print(f"Error: invalid ProblemSpec: {e}", file=sys.stderr)
        sys.exit(1)

    from formalconstruct.core.exceptions import FormalConstructError

    registry = create_default_registry()
    agent = LeanScaffoldingAgent(registry)
    try:
        result = agent.scaffold(spec, narrative=args.narrative)
    except FormalConstructError as e:
        print(f"Error: scaffolding failed: {e}", file=sys.stderr)
        sys.exit(1)

    if args.out:
        from formalconstruct.core.config import AxleConfig
        out_path = Path(args.out)
        out_path.write_text(result.content)
        meta = {
            "imports": result.imports,
            "goals": [g.model_dump() for g in result.goals],
            "mathlib_modules": result.mathlib_modules,
            "source_mappings": [m.model_dump() for m in result.source_mappings],
        }
        Path(args.out + ".meta.json").write_text(json.dumps(meta, indent=2))
        toolchain_path = out_path.parent / "lean-toolchain"
        if not toolchain_path.exists():
            lean_env = AxleConfig().lean_environment
            toolchain_path.write_text(f"leanprover/lean4:{lean_env}\n")
            print(f"Wrote {toolchain_path}")
        print(f"Wrote {args.out} ({len(result.goals)} goals)")
        print(f"Wrote {args.out}.meta.json")
    else:
        print(result.content)


def cmd_schema(args: argparse.Namespace) -> None:
    from formalconstruct.schemas.problem_spec import ProblemSpec
    print(json.dumps(ProblemSpec.model_json_schema(), indent=2))


def cmd_list_domains(args: argparse.Namespace) -> None:
    from formalconstruct.domains import create_default_registry

    registry = create_default_registry()
    print("Available domains:")
    for domain in registry.list_domains():
        print(f"  {domain}")


def cmd_parse_axle(args: argparse.Namespace) -> None:
    from formalconstruct.mcp_client.parsers import AxleResponseParser

    if args.response_file:
        path = Path(args.response_file)
        if not path.exists():
            print(f"Error: file not found: {args.response_file}", file=sys.stderr)
            sys.exit(1)
        raw_text = path.read_text()
    else:
        raw_text = sys.stdin.read()

    try:
        raw = json.loads(raw_text)
    except json.JSONDecodeError as e:
        print(f"Error: invalid JSON: {e.msg} (line {e.lineno})", file=sys.stderr)
        sys.exit(1)

    parser_map = {
        "check": AxleResponseParser.parse_check,
        "verify": AxleResponseParser.parse_verify,
        "repair": AxleResponseParser.parse_repair,
        "normalize": AxleResponseParser.parse_normalize,
        "extract_decls": AxleResponseParser.parse_extract_decls,
        "theorem2sorry": AxleResponseParser.parse_theorem2sorry,
        "have2lemma": AxleResponseParser.parse_have2lemma,
    }

    result = parser_map[args.tool](raw)
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
