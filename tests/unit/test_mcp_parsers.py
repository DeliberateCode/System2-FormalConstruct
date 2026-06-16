"""Unit tests for formalconstruct.mcp_client.parsers -- AxleResponseParser.

Tests each of the 7 parse methods with representative JSON payloads,
missing key fallback, and verified/okay logic.
"""

from formalconstruct.mcp_client.parsers import AxleResponseParser
from formalconstruct.schemas.axle_responses import (
    AxleCheckResult,
    AxleExtractDeclsResult,
    AxleHave2LemmaResult,
    AxleNormalizeResult,
    AxleRepairResult,
    AxleTheorem2SorryResult,
    AxleVerifyResult,
)


class TestParseCheck:
    def test_parse_check_no_errors(self):
        raw = {
            "lean_messages": {"errors": [], "warnings": [], "infos": []},
            "tool_messages": {"errors": [], "warnings": [], "infos": []},
        }
        result = AxleResponseParser.parse_check(raw)
        assert isinstance(result, AxleCheckResult)
        assert result.has_errors is False
        assert result.lean_messages.errors == []
        assert result.tool_messages.errors == []

    def test_parse_check_with_lean_errors(self):
        raw = {
            "lean_messages": {"errors": ["type mismatch", "unknown identifier 'x'"]},
            "tool_messages": {"errors": [], "warnings": [], "infos": []},
        }
        result = AxleResponseParser.parse_check(raw)
        assert result.has_errors is True
        assert len(result.lean_messages.errors) == 2
        assert "type mismatch" in result.lean_messages.errors

    def test_parse_check_with_tool_errors(self):
        raw = {
            "lean_messages": {"errors": [], "warnings": [], "infos": []},
            "tool_messages": {"errors": ["timeout waiting for server"]},
        }
        result = AxleResponseParser.parse_check(raw)
        assert result.has_errors is True
        assert result.tool_messages.errors == ["timeout waiting for server"]

    def test_parse_check_missing_keys(self):
        raw = {}
        result = AxleResponseParser.parse_check(raw)
        assert isinstance(result, AxleCheckResult)
        assert result.has_errors is False
        assert result.lean_messages.errors == []
        assert result.lean_messages.warnings == []
        assert result.lean_messages.infos == []
        assert result.tool_messages.errors == []

    def test_parse_check_with_warnings_and_infos(self):
        raw = {
            "lean_messages": {
                "errors": [],
                "warnings": ["unused variable"],
                "infos": ["Try this: simp"],
            },
            "tool_messages": {"errors": [], "warnings": [], "infos": []},
        }
        result = AxleResponseParser.parse_check(raw)
        assert result.has_errors is False
        assert result.lean_messages.warnings == ["unused variable"]
        assert result.lean_messages.infos == ["Try this: simp"]


class TestParseVerify:
    def test_parse_verify_missing_verified_key_defaults_false(self):
        raw = {
            "lean_messages": {"errors": [], "warnings": [], "infos": []},
            "tool_messages": {"errors": [], "warnings": [], "infos": []},
        }
        result = AxleResponseParser.parse_verify(raw)
        assert isinstance(result, AxleVerifyResult)
        assert result.verified is False
        assert result.has_errors is False

    def test_parse_verify_verified_false_lean_errors(self):
        raw = {
            "lean_messages": {"errors": ["declaration has sorry"]},
            "tool_messages": {"errors": [], "warnings": [], "infos": []},
        }
        result = AxleResponseParser.parse_verify(raw)
        assert result.verified is False
        assert result.has_errors is True

    def test_parse_verify_verified_false_tool_errors(self):
        raw = {
            "lean_messages": {"errors": [], "warnings": [], "infos": []},
            "tool_messages": {"errors": ["unsafe native code detected"]},
        }
        result = AxleResponseParser.parse_verify(raw)
        assert result.verified is False

    def test_parse_verify_missing_keys(self):
        raw = {}
        result = AxleResponseParser.parse_verify(raw)
        assert result.verified is False
        assert result.lean_messages.errors == []

    def test_parse_verify_honors_explicit_verified_false(self):
        raw = {
            "verified": False,
            "lean_messages": {"errors": [], "warnings": [], "infos": []},
            "tool_messages": {"errors": [], "warnings": [], "infos": []},
        }
        result = AxleResponseParser.parse_verify(raw)
        assert result.verified is False

    def test_parse_verify_honors_explicit_verified_true(self):
        raw = {
            "verified": True,
            "lean_messages": {"errors": ["some warning treated as error"]},
            "tool_messages": {},
        }
        result = AxleResponseParser.parse_verify(raw)
        assert result.verified is True


class TestParseVerifyFailClosed:
    """Contract tests: parse_verify must fail-closed.

    When the ``verified`` key is absent from the raw AXLE response,
    ``parse_verify`` must default to ``verified=False`` rather than
    inferring success from the absence of errors.  These tests guard
    against regressions that re-introduce fail-open semantics.
    """

    def test_empty_dict_returns_not_verified(self):
        result = AxleResponseParser.parse_verify({})
        assert result.verified is False

    def test_messages_only_no_verified_key_returns_not_verified(self):
        raw = {"lean_messages": {}, "tool_messages": {}}
        result = AxleResponseParser.parse_verify(raw)
        assert result.verified is False

    def test_messages_no_errors_no_verified_key_still_not_verified(self):
        """Critical safety test: even when there are zero errors, absence of
        an explicit ``verified`` key must NOT be interpreted as success."""
        raw = {
            "lean_messages": {"errors": []},
            "tool_messages": {"errors": []},
        }
        result = AxleResponseParser.parse_verify(raw)
        assert result.verified is False

    def test_explicit_verified_true_honored(self):
        raw = {"verified": True}
        result = AxleResponseParser.parse_verify(raw)
        assert result.verified is True

    def test_explicit_verified_false_honored(self):
        raw = {"verified": False, "lean_messages": {"errors": []}}
        result = AxleResponseParser.parse_verify(raw)
        assert result.verified is False

    def test_verified_integer_one_rejected(self):
        """Strict boolean: integer 1 must NOT be treated as verified."""
        raw = {"verified": 1}
        result = AxleResponseParser.parse_verify(raw)
        assert result.verified is False

    def test_verified_string_true_rejected(self):
        """Strict boolean: string 'true' must NOT be treated as verified."""
        raw = {"verified": "true"}
        result = AxleResponseParser.parse_verify(raw)
        assert result.verified is False

    def test_verified_string_false_rejected(self):
        """Strict boolean: string 'false' must NOT be treated as verified."""
        raw = {"verified": "false"}
        result = AxleResponseParser.parse_verify(raw)
        assert result.verified is False

    def test_verified_string_zero_rejected(self):
        """Strict boolean: string '0' must NOT be treated as verified."""
        raw = {"verified": "0"}
        result = AxleResponseParser.parse_verify(raw)
        assert result.verified is False

    def test_verified_none_rejected(self):
        """Strict boolean: None must NOT be treated as verified."""
        raw = {"verified": None}
        result = AxleResponseParser.parse_verify(raw)
        assert result.verified is False


class TestParseVerifyOkayContract:
    """AXLE's verify_proof reports success via ``okay`` + empty
    ``failed_declarations`` (not a ``verified`` key)."""

    def test_okay_true_no_failures_verified(self):
        raw = {
            "okay": True,
            "failed_declarations": [],
            "lean_messages": {"errors": [], "warnings": [], "infos": []},
            "tool_messages": {"errors": [], "warnings": [], "infos": []},
        }
        result = AxleResponseParser.parse_verify(raw)
        assert result.verified is True
        assert result.okay is True
        assert result.failed_declarations == []

    def test_okay_true_missing_failed_declarations_verified(self):
        """An absent ``failed_declarations`` key is treated as no failures."""
        raw = {"okay": True}
        result = AxleResponseParser.parse_verify(raw)
        assert result.verified is True

    def test_okay_true_with_failed_declarations_not_verified(self):
        raw = {"okay": True, "failed_declarations": ["thm_main"]}
        result = AxleResponseParser.parse_verify(raw)
        assert result.verified is False
        assert result.failed_declarations == ["thm_main"]

    def test_okay_true_with_lean_errors_not_verified(self):
        raw = {"okay": True, "lean_messages": {"errors": ["uses sorry"]}}
        result = AxleResponseParser.parse_verify(raw)
        assert result.verified is False

    def test_okay_true_with_tool_errors_not_verified(self):
        raw = {"okay": True, "tool_messages": {"errors": ["unsafe code"]}}
        result = AxleResponseParser.parse_verify(raw)
        assert result.verified is False

    def test_okay_false_not_verified(self):
        raw = {"okay": False, "failed_declarations": []}
        result = AxleResponseParser.parse_verify(raw)
        assert result.verified is False

    def test_explicit_verified_takes_precedence_over_okay(self):
        """If both keys are present, the explicit ``verified`` flag wins."""
        raw = {"verified": False, "okay": True, "failed_declarations": []}
        result = AxleResponseParser.parse_verify(raw)
        assert result.verified is False

    def test_okay_non_bool_not_verified(self):
        """Strict boolean: ``okay`` must be exactly True."""
        raw = {"okay": 1, "failed_declarations": []}
        result = AxleResponseParser.parse_verify(raw)
        assert result.verified is False


class TestParseRepair:
    def test_parse_repair_okay_true(self):
        raw = {
            "okay": True,
            "content": "theorem foo : 1 = 1 := rfl",
            "repair_stats": {
                "remove_extraneous_tactics": 2,
                "replace_unsafe_tactics": 1,
                "apply_terminal_tactics": 3,
            },
            "timings": {
                "total_ms": 500,
                "repair_ms": 300,
            },
            "lean_messages": {"errors": [], "warnings": [], "infos": []},
            "tool_messages": {"errors": [], "warnings": [], "infos": []},
        }
        result = AxleResponseParser.parse_repair(raw)
        assert isinstance(result, AxleRepairResult)
        assert result.okay is True
        assert result.content == "theorem foo : 1 = 1 := rfl"
        assert result.repair_stats.remove_extraneous_tactics == 2
        assert result.repair_stats.replace_unsafe_tactics == 1
        assert result.repair_stats.apply_terminal_tactics == 3
        assert result.timings.total_ms == 500
        assert result.timings.repair_ms == 300

    def test_parse_repair_okay_false(self):
        raw = {
            "okay": False,
            "content": "",
            "lean_messages": {"errors": ["type mismatch"]},
            "tool_messages": {"errors": []},
        }
        result = AxleResponseParser.parse_repair(raw)
        assert result.okay is False
        assert result.content == ""
        assert result.lean_messages.errors == ["type mismatch"]

    def test_parse_repair_missing_keys_defaults(self):
        raw = {}
        result = AxleResponseParser.parse_repair(raw)
        assert result.okay is False
        assert result.content == ""
        assert result.repair_stats.remove_extraneous_tactics == 0
        assert result.repair_stats.replace_unsafe_tactics == 0
        assert result.repair_stats.apply_terminal_tactics == 0
        assert result.timings.total_ms == 0
        assert result.timings.repair_ms == 0


class TestParseNormalize:
    def test_parse_normalize(self):
        raw = {
            "content": "import Mathlib\n\ntheorem foo : 1 = 1 := by rfl",
            "lean_messages": {"errors": [], "warnings": [], "infos": []},
            "tool_messages": {"errors": [], "warnings": [], "infos": []},
        }
        result = AxleResponseParser.parse_normalize(raw)
        assert isinstance(result, AxleNormalizeResult)
        assert result.content == "import Mathlib\n\ntheorem foo : 1 = 1 := by rfl"

    def test_parse_normalize_missing_content(self):
        raw = {}
        result = AxleResponseParser.parse_normalize(raw)
        assert result.content == ""


class TestParseExtractDecls:
    def test_parse_extract_decls(self):
        raw = {
            "declarations": [
                {
                    "name": "thm_main",
                    "kind": "theorem",
                    "content": "theorem thm_main : 1 = 1 := rfl",
                    "dependencies": [],
                },
                {
                    "name": "helper_lemma",
                    "kind": "lemma",
                    "content": "lemma helper_lemma : True := trivial",
                    "dependencies": ["thm_main"],
                },
            ],
            "lean_messages": {"errors": [], "warnings": [], "infos": []},
            "tool_messages": {"errors": [], "warnings": [], "infos": []},
        }
        result = AxleResponseParser.parse_extract_decls(raw)
        assert isinstance(result, AxleExtractDeclsResult)
        assert len(result.declarations) == 2
        assert result.declarations[0]["name"] == "thm_main"
        assert result.declarations[1]["dependencies"] == ["thm_main"]

    def test_parse_extract_decls_empty(self):
        raw = {}
        result = AxleResponseParser.parse_extract_decls(raw)
        assert result.declarations == []


class TestParseTheorem2Sorry:
    def test_parse_theorem2sorry(self):
        raw = {
            "content": "theorem thm_main : 1 = 1 := by sorry",
            "lean_messages": {"errors": [], "warnings": [], "infos": []},
            "tool_messages": {"errors": [], "warnings": [], "infos": []},
        }
        result = AxleResponseParser.parse_theorem2sorry(raw)
        assert isinstance(result, AxleTheorem2SorryResult)
        assert "sorry" in result.content

    def test_parse_theorem2sorry_missing_content(self):
        raw = {}
        result = AxleResponseParser.parse_theorem2sorry(raw)
        assert result.content == ""


class TestParseHave2Lemma:
    def test_parse_have2lemma(self):
        raw = {
            "content": "lemma sub_goal_1 : True := trivial\ntheorem main : True := sub_goal_1",
            "lemmas": ["sub_goal_1"],
            "lean_messages": {"errors": [], "warnings": [], "infos": []},
            "tool_messages": {"errors": [], "warnings": [], "infos": []},
        }
        result = AxleResponseParser.parse_have2lemma(raw)
        assert isinstance(result, AxleHave2LemmaResult)
        assert "sub_goal_1" in result.content
        assert result.lemmas == ["sub_goal_1"]

    def test_parse_have2lemma_multiple_lemmas(self):
        raw = {
            "content": "extracted",
            "lemmas": ["lemma_a", "lemma_b", "lemma_c"],
        }
        result = AxleResponseParser.parse_have2lemma(raw)
        assert len(result.lemmas) == 3

    def test_parse_have2lemma_missing_keys(self):
        raw = {}
        result = AxleResponseParser.parse_have2lemma(raw)
        assert result.content == ""
        assert result.lemmas == []
