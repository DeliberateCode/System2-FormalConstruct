"""Unit tests for the curation filtering logic."""

from __future__ import annotations

import pytest

from benchmarking.data.curate import estimate_difficulty, is_suitable, match_domain


@pytest.fixture
def keywords():
    return {
        "continuous_optimization": [
            "minimize", "maximize", "minimum", "maximum", "convex", "concave", "optimal",
            "constraint", "feasible", "cost function",
        ],
        "non_cooperative_game": [
            "Nash", "equilibrium", "player", "strategy", "payoff",
        ],
        "cooperative_game": [
            "Pareto", "coalition", "cooperative", "Shapley",
        ],
    }


class TestMatchDomain:
    def test_optimization_keywords(self, keywords):
        text = "Minimize the strictly convex cost function subject to constraints"
        assert match_domain(text, keywords) == "continuous_optimization"

    def test_game_theory_keywords(self, keywords):
        text = "Find the Nash equilibrium for a two-player game with mixed strategies"
        assert match_domain(text, keywords) == "non_cooperative_game"

    def test_cooperative_keywords(self, keywords):
        text = "Show that the allocation is Pareto optimal for the coalition"
        assert match_domain(text, keywords) == "cooperative_game"

    def test_no_match(self, keywords):
        text = "Prove that the sum of two primes is even"
        assert match_domain(text, keywords) is None

    def test_highest_score_wins(self, keywords):
        text = "Minimize the payoff in a game with convex constraints and feasible strategies"
        # optimization: minimize, convex, constraints, feasible = 4
        # game: payoff, strategies = 2
        assert match_domain(text, keywords) == "continuous_optimization"


class TestIsSuitable:
    def test_proved_optimization(self, keywords):
        entry = {
            "status": "proved",
            "natural_language_statement": "Find the maximum value of sin(x) + cos(x)",
            "formal_statement": "theorem opt_exists (x : ℝ) : Real.sin x + Real.cos x ≤ Real.sqrt 2   :=  by sorry",
        }
        suitable, domain = is_suitable(entry, keywords)
        assert suitable is True
        assert domain == "continuous_optimization"

    def test_disproved_rejected(self, keywords):
        entry = {
            "status": "disproved",
            "natural_language_statement": "Minimize the convex function f(x) over the feasible set",
            "formal_statement": "theorem opt_exists : sorry",
        }
        suitable, _ = is_suitable(entry, keywords)
        assert suitable is False

    def test_short_statement_rejected(self, keywords):
        entry = {
            "status": "proved",
            "natural_language_statement": "Minimize f(x)",
            "formal_statement": "theorem t : sorry",
        }
        suitable, _ = is_suitable(entry, keywords)
        assert suitable is False

    def test_no_sorry_rejected(self, keywords):
        entry = {
            "status": "proved",
            "natural_language_statement": "Minimize the convex function f(x) over the feasible set",
            "formal_statement": "theorem opt_exists := by ring",
        }
        suitable, _ = is_suitable(entry, keywords)
        assert suitable is False

    def test_too_many_sorries_rejected(self, keywords):
        entry = {
            "status": "proved",
            "natural_language_statement": "Minimize the convex function f(x) over the feasible set",
            "formal_statement": "theorem t : sorry\nlemma a : sorry\nlemma b : sorry\nlemma c : sorry",
        }
        suitable, _ = is_suitable(entry, keywords)
        assert suitable is False

    def test_no_domain_match_rejected(self, keywords):
        entry = {
            "status": "proved",
            "natural_language_statement": "Prove that for all natural numbers n, n + 0 = n",
            "formal_statement": "theorem nat_add_zero (n : Nat) : sorry",
        }
        suitable, _ = is_suitable(entry, keywords)
        assert suitable is False


class TestEstimateDifficulty:
    def test_simple_tactic_easy(self):
        assert estimate_difficulty({"tactic": "ring"}) == "easy"
        assert estimate_difficulty({"tactic": "linarith"}) == "easy"
        assert estimate_difficulty({"tactic": "simp"}) == "easy"

    def test_short_tactic_medium(self):
        assert estimate_difficulty({"tactic": "exact h.add_convexOn h2"}) == "medium"

    def test_long_tactic_hard(self):
        tactic = "calc x = y := by ring\n_ ≤ z := by have h := foo; linarith"
        assert estimate_difficulty({"tactic": tactic}) == "hard"

    def test_empty_unknown(self):
        assert estimate_difficulty({"tactic": ""}) == "unknown"
