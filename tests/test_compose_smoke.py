"""Smoke tests: validate that FormalConstruct composes cleanly against System2."""

import json
import os
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OVERLAY_ROOT = os.path.join(REPO_ROOT, "plugin")
SYSTEM2_ROOT = os.path.join(os.path.dirname(REPO_ROOT), "System2")
SYSTEM2_PLUGIN = os.path.join(SYSTEM2_ROOT, "plugin")
COMPOSER_DIR = os.path.join(SYSTEM2_PLUGIN, "scripts")

_SYSTEM2_AVAILABLE = os.path.isdir(SYSTEM2_ROOT)

if _SYSTEM2_AVAILABLE:
    sys.path.insert(0, COMPOSER_DIR)
    from composer import compose, validate_manifest, _scan_for_injection  # noqa: E402

MANIFEST_PATH = os.path.join(OVERLAY_ROOT, "system2.overlay.json")
CONTRIBUTIONS_DIR = os.path.join(OVERLAY_ROOT, "contributions")

EXPECTED_CONTRIBUTION_IDS = {
    # Orchestrator
    "fc-principle-proof-pipeline",
    # Executor
    "fc-executor-safety",
    "fc-executor-discipline",
    "fc-executor-verification",
    # Spec-coordinator
    "fc-spec-context",
    "fc-spec-style",
    # Design-architect
    "fc-architect-constraints",
    "fc-architect-sections",
    # Task-planner
    "fc-planner-rules",
    "fc-planner-fields",
    # Test-engineer
    "fc-test-workflow",
    "fc-test-authoring",
    # Code-reviewer
    "fc-reviewer-criteria",
    "fc-reviewer-surface",
    "fc-reviewer-simplification",
    # Requirements-engineer
    "fc-requirements-guardrails",
    # MCP-toolsmith
    "fc-mcp-design",
    # Docs-release
    "fc-docs-writing",
    # Spec artifact sections
    "fc-spec-context-domain",
    "fc-spec-context-lean-env",
    "fc-spec-design-lean-arch",
    "fc-spec-design-sorry",
    # Advisory sources
    "fc-advisory-validate",
    "fc-advisory-scaffold",
    "fc-advisory-schema",
}

CORE_6_AGENTS = {
    "executor", "spec-coordinator", "design-architect",
    "task-planner", "test-engineer", "code-reviewer",
}


def _require_system2():
    if not _SYSTEM2_AVAILABLE:
        try:
            import pytest
            pytest.skip("System2 not found at ../System2")
        except ImportError:
            raise RuntimeError("System2 not found at ../System2")


def _load_schema_and_anchor_map():
    schema_path = os.path.join(SYSTEM2_PLUGIN, "schemas", "overlay.schema.json")
    anchor_path = os.path.join(SYSTEM2_PLUGIN, "schemas", "anchor-map.json")
    with open(schema_path) as f:
        schema = json.load(f)
    with open(anchor_path) as f:
        anchor_map = json.load(f)
    return schema, anchor_map


def _load_manifest():
    with open(MANIFEST_PATH) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Tests requiring System2
# ---------------------------------------------------------------------------


def test_manifest_validates():
    _require_system2()
    manifest = _load_manifest()
    schema, anchor_map = _load_schema_and_anchor_map()
    result = validate_manifest(manifest, schema, OVERLAY_ROOT, anchor_map)
    assert result.valid, f"Validation errors: {result.errors}"
    assert result.errors == []


def test_no_validation_warnings():
    _require_system2()
    manifest = _load_manifest()
    schema, anchor_map = _load_schema_and_anchor_map()
    result = validate_manifest(manifest, schema, OVERLAY_ROOT, anchor_map)
    assert result.warnings == [], f"Validation warnings: {result.warnings}"


def test_no_injection_patterns_in_content():
    """Content files must not trigger the composer's injection scanner."""
    _require_system2()
    issues = []
    for root, _dirs, files in os.walk(CONTRIBUTIONS_DIR):
        for fname in sorted(files):
            if not fname.endswith(".md"):
                continue
            fpath = os.path.join(root, fname)
            with open(fpath) as f:
                content = f.read()
            warnings = _scan_for_injection(content, fpath)
            issues.extend(warnings)
    assert issues == [], f"Injection patterns found: {issues}"


def test_full_anchor_coverage():
    """Every anchor point for Core 6 agents in the anchor map has a contribution."""
    _require_system2()
    manifest = _load_manifest()
    _, anchor_map = _load_schema_and_anchor_map()
    agents_contrib = manifest["contributions"].get("agents", {})

    missing = []
    for agent_name, agent_info in anchor_map["agents"].items():
        if agent_name not in CORE_6_AGENTS:
            continue
        for anchor_name in agent_info.get("anchors", {}):
            sections = agents_contrib.get(agent_name, {}).get("prompt_sections", {})
            if anchor_name not in sections:
                missing.append(f"{agent_name}.{anchor_name}")
    assert not missing, f"Uncovered anchors: {missing}"


def test_dry_run_compose_succeeds():
    _require_system2()
    with tempfile.TemporaryDirectory() as tmp:
        result = compose(
            base_path=SYSTEM2_PLUGIN,
            overlay_paths=[OVERLAY_ROOT],
            project_path=tmp,
            dry_run=True,
        )
        assert result["errors"] == [], f"Compose errors: {result['errors']}"
        assert result["claude_md"], "Composed CLAUDE.md is empty"


def test_composed_output_contains_overlay_markers():
    """Composed CLAUDE.md must contain key overlay content markers."""
    _require_system2()
    with tempfile.TemporaryDirectory() as tmp:
        result = compose(
            base_path=SYSTEM2_PLUGIN,
            overlay_paths=[OVERLAY_ROOT],
            project_path=tmp,
            dry_run=True,
        )
        claude_md = result["claude_md"]

        markers = [
            "formalconstruct",
            "AXLE",
            "Lean 4",
            "ProblemSpec",
            "sorry",
        ]
        for marker in markers:
            assert marker in claude_md, (
                f"Composed CLAUDE.md missing expected marker: {marker!r}"
            )


def test_all_contribution_ids_applied():
    _require_system2()
    with tempfile.TemporaryDirectory() as tmp:
        result = compose(
            base_path=SYSTEM2_PLUGIN,
            overlay_paths=[OVERLAY_ROOT],
            project_path=tmp,
            dry_run=True,
        )
        lock = result.get("lock", {})
        applied_ids = set()
        for id_list in lock.get("contributions_applied", {}).values():
            applied_ids.update(id_list)

        missing = EXPECTED_CONTRIBUTION_IDS - applied_ids
        assert not missing, f"Contributions not applied: {missing}"


# ---------------------------------------------------------------------------
# Tests that only read the manifest (no System2 required)
# ---------------------------------------------------------------------------


def test_content_files_exist_and_nonempty():
    manifest = _load_manifest()
    contributions = manifest["contributions"]

    for principle in contributions.get("orchestrator", {}).get("principles", []):
        path = os.path.join(OVERLAY_ROOT, principle["content_file"])
        assert os.path.isfile(path), f"Missing: {principle['content_file']}"
        assert os.path.getsize(path) > 0, f"Empty: {principle['content_file']}"

    for agent_name, agent_data in contributions.get("agents", {}).items():
        for anchor, sections in agent_data.get("prompt_sections", {}).items():
            for section in sections:
                path = os.path.join(OVERLAY_ROOT, section["content_file"])
                assert os.path.isfile(path), f"Missing: {section['content_file']}"
                assert os.path.getsize(path) > 0, f"Empty: {section['content_file']}"


def test_light_agents_covered():
    """Each of requirements-engineer, mcp-toolsmith, docs-release has at least one prompt_sections entry."""
    manifest = _load_manifest()
    agents = manifest["contributions"].get("agents", {})
    light_agents = {"requirements-engineer", "mcp-toolsmith", "docs-release"}
    for agent_name in light_agents:
        sections = agents.get(agent_name, {}).get("prompt_sections", {})
        assert len(sections) >= 1, f"{agent_name} has no prompt_sections entries"


def test_contribution_id_prefix():
    """All contribution IDs use the fc- prefix."""
    manifest = _load_manifest()
    bad_ids = []

    def collect_ids(obj):
        if isinstance(obj, dict):
            if "id" in obj and isinstance(obj["id"], str):
                if not obj["id"].startswith("fc-"):
                    bad_ids.append(obj["id"])
            for v in obj.values():
                collect_ids(v)
        elif isinstance(obj, list):
            for item in obj:
                collect_ids(item)

    collect_ids(manifest["contributions"])
    assert not bad_ids, f"IDs without fc- prefix: {bad_ids}"


def test_summaries_present_for_non_inline():
    """Every non-inline prompt_section contribution has a summary."""
    manifest = _load_manifest()
    missing = []
    for agent_name, agent_data in manifest["contributions"].get("agents", {}).items():
        for anchor, sections in agent_data.get("prompt_sections", {}).items():
            for section in sections:
                if not section.get("inline", False) and "summary" not in section:
                    missing.append(f"{agent_name}.{anchor}.{section.get('id', '?')}")
    assert not missing, f"Missing summaries: {missing}"


def test_mcp_server_declared():
    """mcp_servers[] has entry with name 'axiom-axle-mcp'."""
    manifest = _load_manifest()
    mcp_servers = manifest["contributions"].get("mcp_servers", [])
    names = [s["name"] for s in mcp_servers]
    assert "axiom-axle-mcp" in names, (
        f"Expected 'axiom-axle-mcp' in mcp_servers, got: {names}"
    )


def test_advisory_sources_declared():
    """advisory_sources[] has entries for fc-advisory-validate, fc-advisory-scaffold, fc-advisory-schema."""
    manifest = _load_manifest()
    sources = manifest["contributions"].get("delegation", {}).get("advisory_sources", [])
    source_ids = {s["id"] for s in sources}
    expected = {"fc-advisory-validate", "fc-advisory-scaffold", "fc-advisory-schema"}
    missing = expected - source_ids
    assert not missing, f"Missing advisory sources: {missing}"


def test_orchestrator_principles_present():
    """orchestrator.principles[] has len >= 1."""
    manifest = _load_manifest()
    principles = manifest["contributions"].get("orchestrator", {}).get("principles", [])
    assert len(principles) >= 1, (
        f"Expected at least 1 orchestrator principle, got {len(principles)}"
    )


def test_spec_required_sections():
    """spec.context and spec.design each have required_sections with len >= 2."""
    manifest = _load_manifest()
    spec = manifest["contributions"].get("spec", {})

    context_sections = spec.get("context", {}).get("required_sections", [])
    assert len(context_sections) >= 2, (
        f"spec.context.required_sections has {len(context_sections)} entries, expected >= 2"
    )

    design_sections = spec.get("design", {}).get("required_sections", [])
    assert len(design_sections) >= 2, (
        f"spec.design.required_sections has {len(design_sections)} entries, expected >= 2"
    )


def test_skipped_agents_absent():
    """agents{} does NOT contain security-sentinel, eval-engineer, repo-governor, postmortem-scribe."""
    manifest = _load_manifest()
    agents = manifest["contributions"].get("agents", {})
    skipped = {"security-sentinel", "eval-engineer", "repo-governor", "postmortem-scribe"}
    present = skipped & set(agents.keys())
    assert not present, f"Skipped agents should not be in manifest: {present}"


def test_auxiliary_agents():
    """Auxiliary agents declared in the manifest have valid agent files."""
    manifest = _load_manifest()
    aux = manifest["contributions"].get("auxiliary_agents", [])
    assert len(aux) >= 1, "Expected at least one auxiliary agent"
    for agent in aux:
        assert "name" in agent, f"Auxiliary agent missing 'name': {agent}"
        assert "agent_file" in agent, f"Auxiliary agent missing 'agent_file': {agent}"
        path = os.path.join(OVERLAY_ROOT, agent["agent_file"])
        assert os.path.exists(path), f"Agent file not found: {path}"
        assert os.path.getsize(path) > 0, f"Agent file is empty: {path}"


# ---------------------------------------------------------------------------
# Standalone runner
# ---------------------------------------------------------------------------

ALL_TESTS = [
    test_manifest_validates,
    test_no_validation_warnings,
    test_content_files_exist_and_nonempty,
    test_no_injection_patterns_in_content,
    test_full_anchor_coverage,
    test_light_agents_covered,
    test_contribution_id_prefix,
    test_summaries_present_for_non_inline,
    test_dry_run_compose_succeeds,
    test_composed_output_contains_overlay_markers,
    test_all_contribution_ids_applied,
    test_mcp_server_declared,
    test_advisory_sources_declared,
    test_orchestrator_principles_present,
    test_spec_required_sections,
    test_skipped_agents_absent,
    test_auxiliary_agents,
]


if __name__ == "__main__":
    passed = 0
    failed = 0
    skipped = 0
    for test_fn in ALL_TESTS:
        try:
            test_fn()
            print(f"  [PASS] {test_fn.__name__}")
            passed += 1
        except RuntimeError as e:
            if "System2 not found" in str(e):
                print(f"  [SKIP] {test_fn.__name__}: {e}")
                skipped += 1
            else:
                print(f"  [ERROR] {test_fn.__name__}: {e}")
                failed += 1
        except AssertionError as e:
            print(f"  [FAIL] {test_fn.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  [ERROR] {test_fn.__name__}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed, {skipped} skipped, {passed + failed + skipped} total")
    sys.exit(0 if failed == 0 else 1)
