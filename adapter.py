"""Adapter from institutional Prolog descriptions to simulation outcomes."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

import networkx as nx

from ngames.build import build_full_game
from ngames.equilibrium import build_subgame
from institutions import InstitutionSpec

ACTIONS: tuple[str, str, str] = ("take_other", "give_own", "refuse")
SUCCESS_OUTCOMES = {"a_executes_both", "b_executes_both"}
FAILURE_TYPES: tuple[str, ...] = (
    "success",
    "mutual_refusal",
    "one_refusal_failure",
    "mismatch_failure",
    "other_failure",
)


@dataclass(frozen=True)
class InstitutionalResolution:
    """Resolution of one action situation (one exchange opportunity)."""

    raw_profile: Tuple[str, str]
    applied_profile: Tuple[str, str]
    outcome: str
    state_facts: List[str]
    payoffs: Dict[str, float]
    welfare: float
    collaboration: bool
    probability: float
    notes: str = ""
    status_quo_welfare: float = 0.0
    realized_welfare: float = 0.0
    net_gain_over_status_quo: float = 0.0
    realized_collaboration_surplus: float = 0.0
    failure_type: str = "other_failure"


class NormsGamesAdapter:
    """Bridge from IAD rules in Prolog to round-level outcomes for Mesa."""

    def __init__(
        self,
        spec: InstitutionSpec,
        threshold: int = 1000,
        max_rounds: int = 1,
        seed: int | None = None,
    ) -> None:
        self.spec = spec
        self.threshold = threshold
        self.max_rounds = max_rounds
        self.random = random.Random(seed)
        self.game = build_full_game(
            folder=str(spec.folder).replace("\\", "/"),
            identifier=spec.identifier,
            threshold=threshold,
            max_rounds=max_rounds,
        )
        self.normal_game = None
        try:
            # build_subgame needs utilities assigned to all terminal nodes.
            self.normal_game = build_subgame(self.game, self.game.game_tree.root)
        except Exception:
            self.normal_game = None
        self.profile_outcomes = self._build_profile_outcomes()

    def _build_profile_outcomes(self) -> Dict[Tuple[str, str], List[Dict[str, Any]]]:
        table: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
        root = self.game.game_tree.root

        for terminal in self.game.game_tree.terminal_nodes:
            path = nx.shortest_path(self.game.game_tree, root, terminal)
            profile: Dict[str, str] = {}
            chance_prob = 1.0

            for u, v in zip(path[:-1], path[1:]):
                player = self.game.turn_function.get(u)
                if player == "chance":
                    chance_prob *= float(self.game.probability.get((u, v), 1.0))
                    continue
                if player is None:
                    continue
                action = str(self.game.game_tree.edges[u, v]["action"])
                profile[player] = action

            key = tuple(profile[p] for p in self.game.players)
            state_facts = [str(f) for f in self.game.state_fluents.get(terminal, [])]
            outcome = self._extract_outcome_label(state_facts)
            table.setdefault(key, []).append(
                {
                    "outcome": outcome,
                    "state_facts": state_facts,
                    "probability": chance_prob,
                }
            )

        for key, entries in table.items():
            total = sum(e["probability"] for e in entries)
            if total <= 0:
                continue
            for entry in entries:
                entry["probability"] = entry["probability"] / total
        return table

    @staticmethod
    def _extract_outcome_label(state_facts: List[str]) -> str:
        for fact in state_facts:
            stripped = fact.strip()
            if stripped.startswith("outcome(") and stripped.endswith(")"):
                return stripped[len("outcome("):-1]
        return "no_exchange"

    def _coerce_for_feasibility(
        self,
        action_a: str,
        action_b: str,
        opportunity: Any,
    ) -> Tuple[str, str]:
        for action in (action_a, action_b):
            if action not in ACTIONS:
                raise ValueError(
                    "Unsupported action '{}'. Allowed actions: {}".format(
                        action, ACTIONS
                    )
                )
        if action_a == "take_other" and not opportunity.a_can_take:
            action_a = "refuse"
        if action_b == "take_other" and not opportunity.b_can_take:
            action_b = "refuse"
        return action_a, action_b

    def _sample_institutional_outcome(
        self,
        profile: Tuple[str, str],
    ) -> Dict[str, Any]:
        entries = self.profile_outcomes.get(profile)
        if not entries:
            raise KeyError("No institutional outcome found for profile {}".format(profile))
        draw = self.random.random()
        cutoff = 0.0
        for entry in entries:
            cutoff += float(entry["probability"])
            if draw <= cutoff:
                return entry
        return entries[-1]

    def _payoffs_for_outcome(self, outcome: str, opportunity: Any) -> Dict[str, float]:
        # Economic structure:
        # U_i(o) = U_i^SQ + Delta_i(o) + T_i(o) - F_i(o)
        # Transfers and friction are applied in resolve_round; this helper returns
        # U_i^SQ + Delta_i(o) only.
        status_quo_payoffs = self._status_quo_payoffs(opportunity)

        if outcome == "a_executes_both":
            if self._has_structured_surplus(opportunity):
                joint_surplus = self._joint_surplus_if_a_executes(opportunity)
                share = self._executor_surplus_share(opportunity)
                return {
                    "a": status_quo_payoffs["a"] + share * joint_surplus,
                    "b": status_quo_payoffs["b"] + (1.0 - share) * joint_surplus,
                }
            return self._legacy_success_payoffs(outcome, opportunity)

        if outcome == "b_executes_both":
            if self._has_structured_surplus(opportunity):
                joint_surplus = self._joint_surplus_if_b_executes(opportunity)
                share = self._executor_surplus_share(opportunity)
                return {
                    "a": status_quo_payoffs["a"] + (1.0 - share) * joint_surplus,
                    "b": status_quo_payoffs["b"] + share * joint_surplus,
                }
            return self._legacy_success_payoffs(outcome, opportunity)

        return status_quo_payoffs

    @staticmethod
    def _status_quo_payoffs(opportunity: Any) -> Dict[str, float]:
        return {
            "a": float(opportunity.status_quo_a),
            "b": float(opportunity.status_quo_b),
        }

    @staticmethod
    def _has_structured_surplus(opportunity: Any) -> bool:
        required = (
            "surplus_if_a_executes",
            "surplus_if_b_executes",
            "executor_share_of_surplus",
        )
        return all(hasattr(opportunity, field) for field in required)

    @staticmethod
    def _executor_surplus_share(opportunity: Any) -> float:
        raw_share = float(getattr(opportunity, "executor_share_of_surplus", 0.72))
        return max(0.0, min(1.0, raw_share))

    def _joint_surplus_if_a_executes(self, opportunity: Any) -> float:
        if hasattr(opportunity, "surplus_if_a_executes"):
            return max(0.0, float(opportunity.surplus_if_a_executes))

        sq = self._status_quo_payoffs(opportunity)
        a_val = float(opportunity.payoff_if_a_executes_both)
        b_val = float(
            getattr(
                opportunity,
                "payoff_to_b_if_a_executes",
                opportunity.status_quo_b - opportunity.giver_disutility,
            )
        )
        return max(0.0, (a_val + b_val) - (sq["a"] + sq["b"]))

    def _joint_surplus_if_b_executes(self, opportunity: Any) -> float:
        if hasattr(opportunity, "surplus_if_b_executes"):
            return max(0.0, float(opportunity.surplus_if_b_executes))

        sq = self._status_quo_payoffs(opportunity)
        a_val = float(
            getattr(
                opportunity,
                "payoff_to_a_if_b_executes",
                opportunity.status_quo_a - opportunity.giver_disutility,
            )
        )
        b_val = float(opportunity.payoff_if_b_executes_both)
        return max(0.0, (a_val + b_val) - (sq["a"] + sq["b"]))

    @staticmethod
    def _legacy_success_payoffs(outcome: str, opportunity: Any) -> Dict[str, float]:
        if outcome == "a_executes_both":
            a_val = float(opportunity.payoff_if_a_executes_both)
            b_val = float(
                getattr(
                    opportunity,
                    "payoff_to_b_if_a_executes",
                    opportunity.status_quo_b - opportunity.giver_disutility,
                )
            )
            return {"a": a_val, "b": b_val}

        a_val = float(
            getattr(
                opportunity,
                "payoff_to_a_if_b_executes",
                opportunity.status_quo_a - opportunity.giver_disutility,
            )
        )
        b_val = float(opportunity.payoff_if_b_executes_both)
        return {"a": a_val, "b": b_val}

    @staticmethod
    def _status_quo_welfare(opportunity: Any) -> float:
        return float(opportunity.status_quo_a) + float(opportunity.status_quo_b)

    @staticmethod
    def _classify_failure_type(profile: Tuple[str, str], outcome: str) -> str:
        if outcome in SUCCESS_OUTCOMES:
            return "success"

        action_a, action_b = profile
        if action_a == "refuse" and action_b == "refuse":
            return "mutual_refusal"
        if action_a == "refuse" or action_b == "refuse":
            return "one_refusal_failure"
        if outcome == "no_exchange":
            return "mismatch_failure"
        return "other_failure"

    def _failed_coordination_penalty(self, failure_type: str) -> float:
        base_penalty = self.spec.failed_coordination_penalty
        if (
            failure_type == "one_refusal_failure"
            and self.spec.one_refusal_failure_penalty is not None
        ):
            return float(self.spec.one_refusal_failure_penalty)
        if (
            failure_type == "mismatch_failure"
            and self.spec.mismatch_failure_penalty is not None
        ):
            return float(self.spec.mismatch_failure_penalty)
        return float(base_penalty)

    def cooperative_welfare_upper_bound(self, opportunity: Any) -> float:
        """Best feasible welfare if the round ended in successful collaboration."""
        payoffs = self.cooperative_payoffs_upper_bound(opportunity)
        return payoffs["a"] + payoffs["b"]

    def cooperative_payoffs_upper_bound(self, opportunity: Any) -> Dict[str, float]:
        """Per-agent payoffs from the best feasible cooperative benchmark."""
        candidates: List[float] = []
        payoff_candidates: List[Dict[str, float]] = []
        if opportunity.a_can_take:
            payoffs = self._payoffs_for_outcome("a_executes_both", opportunity)
            candidates.append(payoffs["a"] + payoffs["b"])
            payoff_candidates.append(payoffs)
        if opportunity.b_can_take:
            payoffs = self._payoffs_for_outcome("b_executes_both", opportunity)
            candidates.append(payoffs["a"] + payoffs["b"])
            payoff_candidates.append(payoffs)
        if candidates:
            best_index = max(range(len(candidates)), key=lambda i: candidates[i])
            return payoff_candidates[best_index]
        return {
            "a": float(opportunity.status_quo_a),
            "b": float(opportunity.status_quo_b),
        }

    def _resolve_platform_priority(self, opportunity: Any) -> Tuple[str, List[str], str]:
        candidates: List[Tuple[str, float]] = []
        if opportunity.a_can_take:
            a_payoffs = self._payoffs_for_outcome("a_executes_both", opportunity)
            candidates.append(("a_executes_both", a_payoffs["a"] + a_payoffs["b"]))
        if opportunity.b_can_take:
            b_payoffs = self._payoffs_for_outcome("b_executes_both", opportunity)
            candidates.append(("b_executes_both", b_payoffs["a"] + b_payoffs["b"]))

        if not candidates:
            return (
                "no_exchange",
                ["outcome(no_exchange)", "executes(a, ta)", "executes(b, tb)"],
                "platform_conflict_unresolved_infeasible",
            )

        candidates.sort(key=lambda x: x[1], reverse=True)
        winner = candidates[0][0]
        if winner == "a_executes_both":
            return (
                winner,
                ["outcome(a_executes_both)", "executes(a, ta)", "executes(a, tb)"],
                "platform_priority_selected_a",
            )
        return (
            winner,
            ["outcome(b_executes_both)", "executes(b, ta)", "executes(b, tb)"],
            "platform_priority_selected_b",
        )

    def resolve_round(
        self,
        opportunity: Any,
        action_a: str,
        action_b: str,
    ) -> InstitutionalResolution:
        raw_profile = (action_a, action_b)
        applied_profile = self._coerce_for_feasibility(action_a, action_b, opportunity)

        sampled = self._sample_institutional_outcome(applied_profile)
        outcome = str(sampled["outcome"])
        state_facts = list(sampled["state_facts"])
        notes = ""

        if self.spec.platform_priority_enabled and outcome == "platform_priority_conflict":
            outcome, state_facts, notes = self._resolve_platform_priority(opportunity)

        payoffs = self._payoffs_for_outcome(outcome, opportunity)
        if outcome in SUCCESS_OUTCOMES and self.spec.compensation > 0:
            comp = self.spec.compensation
            if outcome == "a_executes_both":
                payoffs["a"] -= comp
                payoffs["b"] += comp
            else:
                payoffs["b"] -= comp
                payoffs["a"] += comp

        failure_type = self._classify_failure_type(applied_profile, outcome)
        attempted_coordination = (
            applied_profile[0] != "refuse" or applied_profile[1] != "refuse"
        )
        if outcome == "no_exchange" and attempted_coordination:
            penalty = self._failed_coordination_penalty(failure_type)
            payoffs["a"] -= penalty
            payoffs["b"] -= penalty

        status_quo_welfare = self._status_quo_welfare(opportunity)
        realized_welfare = payoffs["a"] + payoffs["b"]
        net_gain_over_status_quo = realized_welfare - status_quo_welfare
        welfare = realized_welfare
        collaboration = outcome in SUCCESS_OUTCOMES
        realized_collaboration_surplus = net_gain_over_status_quo if collaboration else 0.0

        return InstitutionalResolution(
            raw_profile=raw_profile,
            applied_profile=applied_profile,
            outcome=outcome,
            state_facts=state_facts,
            payoffs=payoffs,
            welfare=welfare,
            collaboration=collaboration,
            probability=float(sampled["probability"]),
            notes=notes,
            status_quo_welfare=status_quo_welfare,
            realized_welfare=realized_welfare,
            net_gain_over_status_quo=net_gain_over_status_quo,
            realized_collaboration_surplus=realized_collaboration_surplus,
            failure_type=failure_type,
        )
